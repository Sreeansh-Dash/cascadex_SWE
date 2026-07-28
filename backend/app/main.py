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

from app.api import alerts, auth, history, medications, scans
from app.core.config import settings
from app.db.neo4j_session import lifespan, ping_neo4j

# ---------------------------------------------------------------------------
# Structured (JSON) logging — log user IDs, never names or drug lists
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
)
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
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    response_description="Service liveness and Neo4j connectivity status",
)
async def health() -> dict:
    """Return service liveness and Neo4j connectivity.

    Returns:
        dict: ``{"status": "ok", "neo4j": "connected" | "unreachable"}``

    This endpoint is intentionally unauthenticated so Docker/K8s healthchecks
    and monitoring systems can call it without a token.
    """
    neo4j_status = "connected" if await ping_neo4j() else "unreachable"
    logger.info("Health check requested — neo4j=%s", neo4j_status)
    return {"status": "ok", "neo4j": neo4j_status}
