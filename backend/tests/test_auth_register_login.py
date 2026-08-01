"""
Unit and API integration tests for User Registration, Password Login, and OTP authentication.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_otp, hash_password, verify_password
from app.db.neo4j_session import get_session
from app.main import app


@pytest.mark.asyncio
async def test_password_hashing_and_verification():
    """Argon2 password hashing and verification test."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


@pytest.mark.asyncio
async def test_register_user_success():
    """Registering a new user returns UserRead without exposing password_hash."""
    mock_session = AsyncMock()

    mock_res_check = AsyncMock()
    mock_res_check.single.return_value = None

    mock_res_create = AsyncMock()
    mock_node = {
        "user_id": "usr_1234567890ab",
        "full_name": "Jane Doe",
        "date_of_birth": "1960-05-15",
        "email": "jane@example.com",
        "phone_number": "+15551234567",
        "preferred_language": "en",
        "large_text_mode": True,
        "created_at": "2026-08-01T12:00:00Z",
    }
    mock_res_create.single.return_value = {"u": mock_node}

    mock_session.run.side_effect = [mock_res_check, mock_res_create]

    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {
                "full_name": "Jane Doe",
                "date_of_birth": "1960-05-15",
                "email": "jane@example.com",
                "phone_number": "+15551234567",
                "password": "SecretPassword123!",
                "large_text_mode": True,
            }
            response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == "usr_1234567890ab"
        assert data["email"] == "jane@example.com"
        assert "password_hash" not in data
        assert "password" not in data
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected():
    """Duplicate email registration is rejected with 400 and error code."""
    mock_session = AsyncMock()
    mock_res = AsyncMock()
    mock_res.single.return_value = {"email": "jane@example.com", "phone_number": None}
    mock_session.run.return_value = mock_res

    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {
                "full_name": "Jane Copy",
                "date_of_birth": "1960-05-15",
                "email": "jane@example.com",
                "password": "SecretPassword123!",
            }
            response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["code"] == "email_already_registered"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_success():
    """Login with correct credentials returns a TokenPair."""
    mock_session = AsyncMock()
    mock_res = AsyncMock()
    pw_hash = hash_password("SecretPassword123!")
    mock_node = {
        "user_id": "usr_1234567890ab",
        "email": "jane@example.com",
        "password_hash": pw_hash,
        "token_version": 1,
    }
    mock_res.single.return_value = {"u": mock_node, "role": "user"}
    mock_session.run.return_value = mock_res

    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {
                "email_or_phone": "jane@example.com",
                "password": "SecretPassword123!",
            }
            response = await client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_wrong_password_rejected():
    """Login with wrong password returns 401 invalid_credentials."""
    mock_session = AsyncMock()
    mock_res = AsyncMock()
    pw_hash = hash_password("SecretPassword123!")
    mock_node = {
        "user_id": "usr_1234567890ab",
        "email": "jane@example.com",
        "password_hash": pw_hash,
        "token_version": 1,
    }
    mock_res.single.return_value = {"u": mock_node, "role": "user"}
    mock_session.run.return_value = mock_res

    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {
                "email_or_phone": "jane@example.com",
                "password": "WrongPassword!",
            }
            response = await client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["code"] == "invalid_credentials"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_otp_request_and_verify_success():
    """Requesting an OTP and verifying it returns a TokenPair."""
    mock_session = AsyncMock()

    # 1. OTP Request query
    mock_res_req = AsyncMock()
    mock_res_req.single.return_value = {"user_id": "usr_1234567890ab"}

    # 2. OTP Request update query
    mock_res_update = AsyncMock()

    # 3. OTP Verify lookup query
    mock_res_ver = AsyncMock()
    otp_code = "654321"
    otp_h = hash_otp(otp_code)
    expires_iso = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    mock_node = {
        "user_id": "usr_1234567890ab",
        "otp_hash": otp_h,
        "otp_expires_at": expires_iso,
        "token_version": 1,
    }
    mock_res_ver.single.return_value = {"u": mock_node}

    # 4. OTP Verify clear query
    mock_res_clear = AsyncMock()

    mock_session.run.side_effect = [
        mock_res_req,
        mock_res_update,
        mock_res_ver,
        mock_res_clear,
    ]

    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Request OTP
            req_resp = await client.post(
                "/api/v1/auth/otp/request",
                json={"email_or_phone": "jane@example.com"},
            )
            assert req_resp.status_code == 200
            req_data = req_resp.json()
            assert req_data["message"] == "OTP sent successfully"
            assert req_data["otp_dev"] is not None  # ENV=dev in test

            # Verify OTP
            ver_resp = await client.post(
                "/api/v1/auth/otp/verify",
                json={"email_or_phone": "jane@example.com", "otp": otp_code},
            )
            assert ver_resp.status_code == 200
            ver_data = ver_resp.json()
            assert "access_token" in ver_data
            assert "refresh_token" in ver_data
    finally:
        app.dependency_overrides.clear()
