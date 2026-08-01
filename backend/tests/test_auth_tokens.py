"""
Unit tests for JWT access and refresh token lifecycle, expiration, and token rotation.
"""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.services.auth_service import refresh_tokens


@pytest.mark.asyncio
async def test_access_token_creation_and_decoding():
    """Access token decodes to expected subject and role."""
    payload = {"sub": "usr_123", "role": "user"}
    token = create_access_token(payload)

    decoded = decode_token(token)
    assert decoded["sub"] == "usr_123"
    assert decoded["role"] == "user"
    assert decoded["type"] == "access"
    assert "exp" in decoded


@pytest.mark.asyncio
async def test_expired_token_rejected():
    """Expired token raises 401 HTTPException."""
    payload = {"sub": "usr_123", "role": "user"}
    token = create_access_token(payload, expires_delta=timedelta(seconds=-10))

    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "invalid_token"


@pytest.mark.asyncio
async def test_refresh_token_rotation():
    """Refreshing tokens increments token_version and returns a new token pair."""
    refresh_tok = create_refresh_token({"sub": "usr_123", "role": "user", "token_version": 1})

    mock_session = AsyncMock()
    # 1. Fetch current version = 1
    mock_res_get = AsyncMock()
    mock_res_get.single.return_value = {"current_version": 1}

    # 2. Update version to 2
    mock_res_update = AsyncMock()

    mock_session.run.side_effect = [mock_res_get, mock_res_update]

    new_pair = await refresh_tokens(refresh_tok, mock_session)

    assert new_pair.access_token is not None
    assert new_pair.refresh_token is not None

    new_decoded = decode_token(new_pair.refresh_token)
    assert new_decoded["token_version"] == 2


@pytest.mark.asyncio
async def test_revoked_refresh_token_rejected():
    """If stored token_version in database has incremented, old refresh token is rejected."""
    refresh_tok = create_refresh_token({"sub": "usr_123", "role": "user", "token_version": 1})

    mock_session = AsyncMock()
    # Current DB version is 2 (already rotated)
    mock_res_get = AsyncMock()
    mock_res_get.single.return_value = {"current_version": 2}
    mock_session.run.return_value = mock_res_get

    with pytest.raises(HTTPException) as exc_info:
        await refresh_tokens(refresh_tok, mock_session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "token_revoked"
