"""
Phase 01 — Health endpoint tests.

Tests:
- GET /health returns HTTP 200.
- Response JSON contains status: "ok".
- Response JSON contains a "neo4j" field (connected or unreachable).

The Neo4j driver is mocked so this test runs offline in CI without
a real Neo4j instance.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_200():
    """GET /health must always return HTTP 200."""
    with patch("app.main.ping_neo4j", new=AsyncMock(return_value=True)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_returns_ok_status():
    """GET /health must return {"status": "ok"} in the JSON body."""
    with patch("app.main.ping_neo4j", new=AsyncMock(return_value=True)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_neo4j_connected():
    """When Neo4j is reachable, the 'neo4j' field should be 'connected'."""
    with patch("app.main.ping_neo4j", new=AsyncMock(return_value=True)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
    data = response.json()
    assert data["neo4j"] == "connected"


@pytest.mark.asyncio
async def test_health_neo4j_unreachable():
    """When Neo4j is unreachable, the response is still HTTP 200 with 'unreachable'."""
    with patch("app.main.ping_neo4j", new=AsyncMock(return_value=False)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["neo4j"] == "unreachable"
