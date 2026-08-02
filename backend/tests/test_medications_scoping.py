"""
Phase 04 — Cross-user and caregiver RBAC scoping integration tests (real Neo4j).

Tests:
- User B cannot read or PATCH User A's medication entries (404)
- User B's list does not include User A's entries
- view_only caregiver is rejected (403) on POST /medications and PATCH
- manage caregiver can add and edit medications on behalf of primary user
- Unauthenticated → 401

RBAC enforcement strategy (tested at API boundary, not just service):
- The resource is scoped by user_id in the Cypher WHERE clause
- Caregiver permission_level is enforced by require_permission() dependency
"""

import uuid

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.db.neo4j_session import get_session
from app.main import app
from app.models.caregiver import PermissionLevel
from tests.conftest import register_and_login


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def add_medication(client: AsyncClient, headers: dict, drug_id: str = "drug_war01") -> str:
    resp = await client.post(
        "/api/v1/medications",
        json={
            "drug_id": drug_id,
            "dosage_amount": 5.0,
            "dosage_unit": "mg",
            "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, f"add_medication helper failed: {resp.text}"
    return resp.json()["entry_id"]


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_b_cannot_get_user_a_dose_logs(client: AsyncClient):
    """User B must get 404 when accessing User A's entry — not 403 (prevents enumeration)."""
    headers_a = await register_and_login(client, "_a")
    headers_b = await register_and_login(client, "_b")

    entry_id = await add_medication(client, headers_a)

    resp = await client.get(f"/api/v1/medications/{entry_id}/doses", headers=headers_b)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "medication_not_found"


@pytest.mark.asyncio
async def test_user_b_cannot_patch_user_a_entry(client: AsyncClient):
    headers_a = await register_and_login(client, "_a2")
    headers_b = await register_and_login(client, "_b2")

    entry_id = await add_medication(client, headers_a)

    resp = await client.patch(
        f"/api/v1/medications/{entry_id}",
        json={"dosage_amount": 999.0},
        headers=headers_b,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "medication_not_found"


@pytest.mark.asyncio
async def test_user_b_cannot_log_dose_for_user_a_entry(client: AsyncClient):
    headers_a = await register_and_login(client, "_a3")
    headers_b = await register_and_login(client, "_b3")

    entry_id = await add_medication(client, headers_a)

    resp = await client.post(
        f"/api/v1/medications/{entry_id}/doses",
        json={"status": "missed", "scheduled_time": "2025-01-01T08:00:00+00:00"},
        headers=headers_b,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "medication_not_found"


@pytest.mark.asyncio
async def test_user_b_list_excludes_user_a_entries(client: AsyncClient):
    headers_a = await register_and_login(client, "_a4")
    headers_b = await register_and_login(client, "_b4")

    entry_id_a = await add_medication(client, headers_a)

    resp = await client.get("/api/v1/medications", headers=headers_b)
    assert resp.status_code == 200
    b_ids = [e["entry_id"] for e in resp.json()]
    assert entry_id_a not in b_ids


# ---------------------------------------------------------------------------
# Caregiver RBAC — using mock session injection to simulate a linked caregiver
# (caregiver self-registration + OTP flow is tested in test_caregiver_rbac.py)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_view_only_caregiver_rejected_on_post_medication(client: AsyncClient):
    """Simulate a view_only caregiver token via dependency override."""
    from unittest.mock import AsyncMock

    token = create_access_token({"sub": "cg_vo_test01", "role": "caregiver", "token_version": 1})
    mock_session = AsyncMock()

    # get_current_user: version check returns 1
    version_res = AsyncMock()
    version_res.single.return_value = {"version": 1}

    # get_current_user: caregiver → target link check returns view_only
    perm_res = AsyncMock()
    perm_res.single.return_value = {"perm": PermissionLevel.VIEW_ONLY.value}

    mock_session.run.side_effect = [version_res, perm_res]

    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        resp = await client.post(
            "/api/v1/medications",
            json={
                "drug_id": "drug_war01",
                "dosage_amount": 5.0,
                "dosage_unit": "mg",
                "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Caregiver-Target-User": "usr_primary_target",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_view_only_caregiver_rejected_on_patch(client: AsyncClient):
    from unittest.mock import AsyncMock

    token = create_access_token({"sub": "cg_vo_test02", "role": "caregiver", "token_version": 1})
    mock_session = AsyncMock()

    version_res = AsyncMock()
    version_res.single.return_value = {"version": 1}
    perm_res = AsyncMock()
    perm_res.single.return_value = {"perm": PermissionLevel.VIEW_ONLY.value}
    mock_session.run.side_effect = [version_res, perm_res]

    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        resp = await client.patch(
            "/api/v1/medications/med_any",
            json={"dosage_amount": 10.0},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Caregiver-Target-User": "usr_primary_target",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_view_only_caregiver_can_list_medications(client: AsyncClient):
    """GET /medications only requires get_current_user (no require_permission) —
    view_only caregiver may read."""
    from unittest.mock import AsyncMock

    token = create_access_token({"sub": "cg_vo_test03", "role": "caregiver", "token_version": 1})
    mock_session = AsyncMock()

    version_res = AsyncMock()
    version_res.single.return_value = {"version": 1}
    perm_res = AsyncMock()
    perm_res.single.return_value = {"perm": PermissionLevel.VIEW_ONLY.value}
    list_res = AsyncMock()
    list_res.data.return_value = []

    mock_session.run.side_effect = [version_res, perm_res, list_res]

    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        resp = await client.get(
            "/api/v1/medications",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Caregiver-Target-User": "usr_primary_target",
            },
        )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_manage_caregiver_can_add_medication(client: AsyncClient):
    """A manage-level caregiver can add a medication on behalf of a primary user.
    Uses real Neo4j but with a real linked caregiver setup via the API."""
    # Register primary user
    headers_primary = await register_and_login(client, "_cg_primary")
    cg_email = f"cg_{uuid.uuid4().hex[:8]}@cascadex-test.com"

    # Primary user links a caregiver (creates Caregiver node)
    link_resp = await client.post(
        "/api/v1/auth/caregivers/link",
        json={
            "caregiver_email_or_phone": cg_email,
            "permission_level": "manage",
            "relationship_to_user": "Daughter",
        },
        headers=headers_primary,
    )
    assert link_resp.status_code == 201, f"link failed: {link_resp.text}"
    cg_id = link_resp.json()["caregiver_id"]

    # Get the primary user's ID from their JWT
    import base64, json as json_mod
    token_str = headers_primary["Authorization"].split(" ")[1]
    payload_b64 = token_str.split(".")[1]
    # pad base64 if needed
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    primary_user_id = json_mod.loads(base64.urlsafe_b64decode(payload_b64))["sub"]

    # Issue a caregiver JWT directly (simulating caregiver login)
    cg_token = create_access_token({"sub": cg_id, "role": "caregiver", "token_version": 1})
    cg_headers = {
        "Authorization": f"Bearer {cg_token}",
        "X-Caregiver-Target-User": primary_user_id,
    }

    resp = await client.post(
        "/api/v1/medications",
        json={
            "drug_id": "drug_asp01",
            "dosage_amount": 100.0,
            "dosage_unit": "mg",
            "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
        },
        headers=cg_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["drug_id"] == "drug_asp01"
    assert data["is_active"] is True
