"""
CascadeX Neo4j session management.

Provides:
- A Neo4j driver created once at application startup (FastAPI lifespan event).
- `get_session()` — a FastAPI dependency that yields a Neo4j session
  and closes it after each request.

Usage:
    from app.db.neo4j_session import get_session
    # In a route or service:
    session: AsyncSession = Depends(get_session)
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level driver — initialised during startup, closed on shutdown.
_driver: AsyncDriver | None = None


async def init_driver() -> None:
    """Create the Neo4j async driver.

    Called once during FastAPI application startup (lifespan).
    Reads connection details from `settings` (environment variables).
    """
    global _driver
    _driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    logger.info("Neo4j driver initialised (URI=%s)", settings.neo4j_uri)


async def close_driver() -> None:
    """Close the Neo4j async driver.

    Called once during FastAPI application shutdown (lifespan).
    """
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("Neo4j driver closed.")


async def ping_neo4j() -> bool:
    """Return True if Neo4j is reachable, False otherwise.

    Used by the /health endpoint to report connectivity status.
    Does NOT raise — health checks must never crash the server.
    """
    if _driver is None:
        return False
    try:
        await _driver.verify_connectivity()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Neo4j connectivity check failed: %s", exc)
        return False


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a Neo4j async session.

    Automatically closes the session after each request, even on error.
    The driver must already be initialised (i.e., `init_driver` must have
    run during startup) before any request can reach this dependency.

    Yields:
        AsyncSession: a ready-to-use Neo4j session for Cypher queries.
    """
    if _driver is None:
        raise RuntimeError(
            "Neo4j driver is not initialised. "
            "Ensure init_driver() ran during application startup."
        )
    session: AsyncSession = _driver.session()
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """FastAPI lifespan context manager.

    Initialises the Neo4j driver on startup and closes it on shutdown.
    Import this and pass it to `FastAPI(lifespan=lifespan)`.
    """
    await init_driver()
    yield
    await close_driver()
