"""
tests/test_logging_no_pii.py — Phase 09

Verifies that structured request logging does NOT leak PII or PHI:
- No drug/medication names appear in log output.
- No user email or full name appears in log output.
- Only opaque identifiers (user_id UUIDs) and structural metadata are logged.

Strategy:
  - Capture log output via pytest's caplog fixture during a real API request
    that touches medication data (adding a drug, fetching interaction results).
  - Assert that sensitive strings are absent from the captured log text.

Note: The logging middleware logs path + user_id (opaque) — not query params
or bodies — so drug names submitted in request bodies must never appear in logs.
"""

from __future__ import annotations

import logging

import pytest
from httpx import AsyncClient

# Drug and user strings that must NEVER appear in logs
_FORBIDDEN_LOG_STRINGS = [
    "warfarin",
    "aspirin",
    "metformin",
    # Email patterns
    "@cascadex-test.com",
    # Generic PII markers
    "full_name",
    "date_of_birth",
]


@pytest.mark.asyncio
async def test_medication_request_logs_no_drug_names(
    client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Submitting a medication name in a request body must not appear in logs."""
    from tests.conftest import register_and_login

    headers = await register_and_login(client, suffix="_piitest")

    with caplog.at_level(logging.INFO, logger="app"):
        # POST a medication with a known drug name in the body
        response = await client.post(
            "/api/v1/medications/",
            json={
                "drug_id": "D001",
                "drug_name": "warfarin",
                "start_date": "2024-01-01",
                "indication": "atrial fibrillation",
                "input_method": "manual",
            },
            headers=headers,
        )
        # We don't assert the response code here — just log capture
        _ = response.status_code

    log_text = caplog.text.lower()
    for forbidden in _FORBIDDEN_LOG_STRINGS:
        assert forbidden.lower() not in log_text, (
            f"PII/PHI leak: '{forbidden}' found in log output. "
            "Logs must never contain drug names or user personal data."
        )


@pytest.mark.asyncio
async def test_health_endpoint_logs_no_pii(
    client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The /health endpoint must not log any user-related PII."""
    with caplog.at_level(logging.INFO, logger="app"):
        response = await client.get("/health")
    assert response.status_code == 200

    log_text = caplog.text.lower()
    # Health endpoint should log neo4j status, drug_count, llm_mode — not emails
    for forbidden in ["@", "password", "secret"]:
        assert forbidden not in log_text, (
            f"Sensitive token '{forbidden}' found in health log output."
        )


@pytest.mark.asyncio
async def test_auth_login_logs_no_credentials(
    client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Login endpoint must not log the user's password or full email."""
    import uuid

    uid = uuid.uuid4().hex[:10]
    email = f"piitest_{uid}@cascadex-test.com"

    with caplog.at_level(logging.INFO, logger="app"):
        # Register
        await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": f"PII Test {uid}",
                "date_of_birth": "1980-01-01",
                "email": email,
                "password": "Secure_Pass_123!",
            },
        )
        # Login
        await client.post(
            "/api/v1/auth/login",
            json={"email_or_phone": email, "password": "Secure_Pass_123!"},
        )

    log_text = caplog.text
    assert "Secure_Pass_123!" not in log_text, "Password must never appear in logs"
    # Email should not appear in structured log output (only user_id should)
    # Note: we check for the unique uid portion to avoid false positives
    assert email not in log_text, (
        f"User email '{email}' found in log output — emails must not be logged."
    )
