"""
Unit and integration tests for Caregiver linking and server-side RBAC enforcement.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import require_permission
from app.core.security import create_access_token
from app.db.neo4j_session import get_session
from app.main import app
from app.models.caregiver import PermissionLevel


# Temporary test router to test RBAC dependency enforcement
@app.get("/api/v1/test/manage-action")
async def manage_action_endpoint(
    auth_context: dict = Depends(require_permission(PermissionLevel.MANAGE)),
):
    """Test endpoint gated behind MANAGE permission."""
    return {"status": "success", "account_id": auth_context["account_id"]}


@pytest.mark.asyncio
async def test_primary_user_allowed_on_manage_action():
    """Primary user automatically passes MANAGE permission check."""
    token = create_access_token({"sub": "usr_primary123", "role": "user", "token_version": 1})

    mock_session = AsyncMock()
    mock_res = AsyncMock()
    mock_res.single.return_value = {"version": 1}
    mock_session.run.return_value = mock_res

    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/manage-action", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_caregiver_manage_permission_allowed():
    """Caregiver with MANAGE permission passes MANAGE permission check."""
    token = create_access_token({"sub": "cg_caregiver123", "role": "caregiver", "token_version": 1})

    mock_session = AsyncMock()
    # 1. Fetch caregiver version
    mock_res_cg = AsyncMock()
    mock_res_cg.single.return_value = {"version": 1}

    # 2. Fetch caregiver relationship permission level = "manage"
    mock_res_perm = AsyncMock()
    mock_res_perm.single.return_value = {"perm": "manage"}

    mock_session.run.side_effect = [mock_res_cg, mock_res_perm]

    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Caregiver-Target-User": "usr_primary123",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/manage-action", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_caregiver_view_only_permission_rejected():
    """Caregiver with VIEW_ONLY permission is rejected with HTTP 403 on MANAGE action."""
    token = create_access_token({"sub": "cg_caregiver123", "role": "caregiver", "token_version": 1})

    mock_session = AsyncMock()
    # 1. Fetch caregiver version
    mock_res_cg = AsyncMock()
    mock_res_cg.single.return_value = {"version": 1}

    # 2. Fetch caregiver relationship permission level = "view_only"
    mock_res_perm = AsyncMock()
    mock_res_perm.single.return_value = {"perm": "view_only"}

    mock_session.run.side_effect = [mock_res_cg, mock_res_perm]

    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Caregiver-Target-User": "usr_primary123",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/manage-action", headers=headers)

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["code"] == "permission_denied"
        assert "view_only" in data["detail"]["message"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_link_caregiver_endpoint():
    """POST /auth/caregivers/link links caregiver to primary user."""
    token = create_access_token({"sub": "usr_primary123", "role": "user", "token_version": 1})

    mock_session = AsyncMock()

    # 1. get_current_user token check
    mock_res_ver = AsyncMock()
    mock_res_ver.single.return_value = {"version": 1}

    # 2. check user exists
    mock_res_u = AsyncMock()
    mock_res_u.single.return_value = {"u": {"user_id": "usr_primary123"}}

    # 3. check caregiver exists
    mock_res_cg = AsyncMock()
    mock_res_cg.single.return_value = {"c": {"caregiver_id": "cg_456", "email": "nurse@example.com"}}

    # 4. link query
    mock_res_link = AsyncMock()
    mock_res_link.single.return_value = {
        "c": {"caregiver_id": "cg_456", "email": "nurse@example.com", "full_name": "Nurse Joy"},
        "r": {"permission_level": "view_only", "relationship_to_user": "Nurse", "linked_at": "2026-08-01T12:00:00Z"},
    }

    mock_session.run.side_effect = [mock_res_ver, mock_res_u, mock_res_cg, mock_res_link]

    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "caregiver_email_or_phone": "nurse@example.com",
            "permission_level": "view_only",
            "relationship_to_user": "Nurse",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/caregivers/link", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["caregiver_id"] == "cg_456"
        assert data["permission_level"] == "view_only"
        assert data["relationship_to_user"] == "Nurse"
    finally:
        app.dependency_overrides.clear()
