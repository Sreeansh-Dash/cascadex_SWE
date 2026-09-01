"""
CascadeX FastAPI application entry point.

Responsibilities:
- Create the FastAPI app instance with lifespan (Neo4j driver init/close).
- Configure CORS middleware.
- Mount all API routers under /api/v1/.
- Expose GET /health for liveness/readiness checks.

All configuration is loaded from environment variables via app.core.config.
"""

import logging
import logging.config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import alerts, auth, history, medications, scans
from app.core.config import settings
from app.db.neo4j_session import get_driver, lifespan, ping_neo4j
from app.middleware.logging_middleware import LoggingMiddleware

# ---------------------------------------------------------------------------
# Structured (JSON) logging — log user IDs, never names or drug lists
# ---------------------------------------------------------------------------
_LOG_FMT = (
    '{"time": "%(asctime)s", "level": "%(levelname)s",'
    ' "logger": "%(name)s", "message": "%(message)s"}'
)
logging.basicConfig(level=logging.INFO, format=_LOG_FMT)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CascadeX API",
    description=(
        "Drug-to-drug interaction warning system. "
        "See /docs for the full OpenAPI specification. "
        "⚠️ This is a course demonstration project — not a certified medical device. "
        "Always consult a pharmacist or doctor for medical advice."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Rate Limiting (slowapi)
# ---------------------------------------------------------------------------
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# LoggingMiddleware: structured PII-free request/response logging
app.add_middleware(LoggingMiddleware)
# SlowAPIMiddleware MUST come after CORSMiddleware so the rate-limit state
# (request.state.view_rate_limit) is set before route handlers run.
app.add_middleware(SlowAPIMiddleware)

# ---------------------------------------------------------------------------
# API routers — all versioned under /api/v1/
# ---------------------------------------------------------------------------
API_V1_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_V1_PREFIX)
app.include_router(medications.router, prefix=API_V1_PREFIX)
app.include_router(scans.router, prefix=API_V1_PREFIX)
app.include_router(alerts.router, prefix=API_V1_PREFIX)
app.include_router(history.router, prefix=API_V1_PREFIX)

# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    summary="Health check",
    tags=["health"],
    response_description="Service liveness, Neo4j connectivity, and runtime status",
)
async def health() -> dict:
    """Return service liveness, Neo4j connectivity, and runtime metadata.

    Returns:
        dict with keys:
          - ``status``: "ok" always (if the server is alive).
          - ``neo4j``: "connected" | "unreachable".
          - ``app_version``: semantic version from FastAPI metadata.
          - ``drug_count``: number of Drug nodes in the graph (0 if unreachable).
          - ``llm_mode``: "active" when GEMINI_API_KEY is set, else "stub".
          - ``dataset_version``: version label of the most recently loaded
            DDInter dataset, or null if not yet seeded.

    This endpoint is intentionally unauthenticated so Docker/K8s healthchecks
    and monitoring systems can call it without a token.
    """
    neo4j_ok = await ping_neo4j()
    neo4j_status = "connected" if neo4j_ok else "unreachable"

    drug_count: int = 0
    dataset_version: str | None = None

    if neo4j_ok:
        try:
            driver = get_driver()
            async with driver.session() as session:
                # Drug count
                count_result = await session.run("MATCH (d:Drug) RETURN count(d) AS n")
                count_record = await count_result.single()
                if count_record:
                    drug_count = count_record["n"]

                # Most recent DatasetVersion label
                ver_result = await session.run(
                    """
                    MATCH (v:DatasetVersion)
                    RETURN v.version AS version
                    ORDER BY v.imported_at DESC
                    LIMIT 1
                    """
                )
                ver_record = await ver_result.single()
                if ver_record:
                    dataset_version = ver_record["version"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("health: failed to query Neo4j details: %s", exc)

    llm_mode = "active" if settings.gemini_api_key else "stub"

    logger.info(
        "Health check — neo4j=%s drug_count=%d llm_mode=%s",
        neo4j_status, drug_count, llm_mode,
    )
    return {
        "status": "ok",
        "neo4j": neo4j_status,
        "app_version": app.version,
        "drug_count": drug_count,
        "llm_mode": llm_mode,
        "dataset_version": dataset_version,
    }
