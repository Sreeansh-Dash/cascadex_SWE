"""
CascadeX structured request logging middleware — Phase 09.

Logs every HTTP request/response with:
  - method, path, status_code, latency_ms
  - user_id extracted from JWT (if present and valid) — NEVER username/email

Explicitly excluded from logs:
  - Request/response body (may contain drug names, health data, PII)
  - Authorization header value (token payload)
  - User names, emails, or any personally identifiable strings
  - Medication or drug names

Design rationale:
  Logging bodies on a medication-safety API risks PHI/PII leakage.
  We log only the structural metadata needed for latency monitoring and
  audit (method, path, status, latency, opaque user_id).
"""

from __future__ import annotations

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Paths to skip (health + docs — high-frequency, no auth)
_SKIP_PATHS = frozenset({"/health", "/docs", "/redoc", "/openapi.json"})


def _extract_user_id(request: Request) -> str | None:
    """Extract user_id from the JWT payload — returns None on any failure.

    We intentionally catch ALL exceptions so logging never disrupts a request.
    We never log the token string itself, only the opaque user_id claim.
    """
    try:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None
        token = auth_header[7:]
        from app.core.security import decode_token  # local import avoids circular

        payload = decode_token(token)
        uid = payload.get("sub") or payload.get("user_id")
        return str(uid) if uid else None
    except Exception:  # noqa: BLE001
        return None


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured PII-free request logging middleware.

    Logs one JSON-formatted line per request containing:
      method, path, status_code, latency_ms, user_id (opaque, never name/email).

    Never logs: request body, response body, Authorization header value,
    query parameters (may contain drug names), or any user-readable name.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """Process the request and log structured metadata."""
        path = request.url.path
        if path in _SKIP_PATHS:
            return await call_next(request)

        method = request.method
        user_id = _extract_user_id(request)
        start = time.perf_counter()

        response: Response = await call_next(request)

        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        status = response.status_code

        # Structured log — fields are opaque identifiers, never human names
        logger.info(
            "request method=%s path=%s status=%d latency_ms=%.1f user_id=%s",
            method,
            path,
            status,
            latency_ms,
            user_id or "anonymous",
        )

        return response
