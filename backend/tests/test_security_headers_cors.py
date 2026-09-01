"""
tests/test_security_headers_cors.py — Phase 09

Verifies:
1. CORS rejects a request from a disallowed origin.
2. CORS accepts a request from an allowed origin.
3. No response ever carries Access-Control-Allow-Origin: * (wildcard).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cors_rejects_disallowed_origin(client: AsyncClient) -> None:
    """A preflight from an evil/unknown origin must not be reflected."""
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Either no ACAO header at all, or it must not be the evil origin
    acao = response.headers.get("access-control-allow-origin", "")
    assert acao != "http://evil.com", (
        "CORS must not reflect disallowed origin 'http://evil.com'"
    )


@pytest.mark.asyncio
async def test_cors_accepts_allowed_origin(client: AsyncClient) -> None:
    """A preflight from an explicitly allowed origin must be reflected."""
    # The default allowed_origins in test config includes http://localhost:3000
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    acao = response.headers.get("access-control-allow-origin", "")
    assert acao == "http://localhost:3000", (
        f"Expected ACAO='http://localhost:3000', got '{acao}'"
    )


@pytest.mark.asyncio
async def test_cors_no_wildcard_in_any_response(client: AsyncClient) -> None:
    """No route should ever return Access-Control-Allow-Origin: * (wildcard)."""
    response = await client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    acao = response.headers.get("access-control-allow-origin", "")
    assert acao != "*", (
        "Production CORS must not use wildcard '*'. Use an explicit allow-list."
    )
