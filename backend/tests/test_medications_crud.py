"""
Phase 04 — Medication CRUD integration tests (real Neo4j).

Tests:
- Drug catalog search (generic + brand name)
- Add medication: valid drug succeeds, bogus drug_id → 404
- List medications: active-only default, include_inactive
- Two-schedule medication persists both schedules
- Deactivate → is_active=False, end_date set, history intact
- Double-deactivate → 400
- PATCH dosage while active
- PATCH schedule replacement
- Auth-gated: unauthenticated requests → 401
"""

# pyrefly: ignore [missing-import]
import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


# ---------------------------------------------------------------------------
# Drug catalog search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_drug_search_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/drugs/search", params={"q": "war"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_drug_search_empty_query_rejected(client: AsyncClient):
    headers = await register_and_login(client)
    resp = await client.get("/api/v1/drugs/search", params={"q": ""}, headers=headers)
    assert resp.status_code == 422  # FastAPI min_length=1 validation


@pytest.mark.asyncio
async def test_drug_search_by_generic_name(client: AsyncClient):
    headers = await register_and_login(client)
    resp = await client.get("/api/v1/drugs/search", params={"q": "war"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    names = [d["generic_name"] for d in data]
    assert "warfarin" in names
    assert all("drug_id" in d and "matched_name" in d for d in data)


@pytest.mark.asyncio
async def test_drug_search_by_brand_name(client: AsyncClient):
    """Searching 'coumadin' (brand of warfarin) should return warfarin."""
    headers = await register_and_login(client)
    resp = await client.get("/api/v1/drugs/search", params={"q": "coumadin"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["generic_name"] == "warfarin"
    assert data[0]["matched_name"] == "coumadin"


@pytest.mark.asyncio
async def test_drug_search_no_match_returns_empty(client: AsyncClient):
    headers = await register_and_login(client)
    resp = await client.get("/api/v1/drugs/search", params={"q": "zzznomatchxxx"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_drug_search_pagination(client: AsyncClient):
    headers = await register_and_login(client)
    # Searching "a" should hit multiple drugs (aspirin, warfarin, simvastatin...)
    resp_all = await client.get("/api/v1/drugs/search", params={"q": "a", "limit": 100}, headers=headers)
    resp_page1 = await client.get("/api/v1/drugs/search", params={"q": "a", "limit": 2, "offset": 0}, headers=headers)
    resp_page2 = await client.get("/api/v1/drugs/search", params={"q": "a", "limit": 2, "offset": 2}, headers=headers)

    total = len(resp_all.json())
    assert len(resp_page1.json()) <= 2
    if total > 2:
        assert len(resp_page2.json()) >= 1


# ---------------------------------------------------------------------------
# Add medication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_medication_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/medications",
        json={
            "drug_id": "drug_war01",
            "dosage_amount": 5.0,
            "dosage_unit": "mg",
            "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_medication_bogus_drug_id(client: AsyncClient):
    headers = await register_and_login(client)
    resp = await client.post(
        "/api/v1/medications",
        json={
            "drug_id": "drug_DOES_NOT_EXIST_999",
            "dosage_amount": 5.0,
            "dosage_unit": "mg",
            "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
        },
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "drug_not_found"


@pytest.mark.asyncio
async def test_add_medication_valid_drug(client: AsyncClient):
    headers = await register_and_login(client)
    resp = await client.post(
        "/api/v1/medications",
        json={
            "drug_id": "drug_war01",
            "dosage_amount": 5.0,
            "dosage_unit": "mg",
            "notes": "Take with food",
            "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["drug_id"] == "drug_war01"
    assert data["generic_name"] == "warfarin"
    assert data["dosage_amount"] == 5.0
    assert data["dosage_unit"] == "mg"
    assert data["input_method"] == "manual"
    assert data["is_active"] is True
    assert data["notes"] == "Take with food"
    assert data["end_date"] is None
    assert "entry_id" in data
    assert len(data["schedules"]) == 1
    assert data["schedules"][0]["time_of_day"] == "08:00"


@pytest.mark.asyncio
async def test_add_medication_two_schedules(client: AsyncClient):
    """Morning + evening schedule both persist (twice-daily)."""
    headers = await register_and_login(client)
    resp = await client.post(
        "/api/v1/medications",
        json={
            "drug_id": "drug_asp01",
            "dosage_amount": 100.0,
            "dosage_unit": "mg",
            "schedules": [
                {"time_of_day": "08:00", "days_of_week": []},
                {"time_of_day": "20:00", "days_of_week": []},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert len(data["schedules"]) == 2
    times = {s["time_of_day"] for s in data["schedules"]}
    assert times == {"08:00", "20:00"}


@pytest.mark.asyncio
async def test_add_medication_invalid_dosage_unit(client: AsyncClient):
    headers = await register_and_login(client)
    resp = await client.post(
        "/api/v1/medications",
        json={
            "drug_id": "drug_war01",
            "dosage_amount": 5.0,
            "dosage_unit": "gallons",  # invalid
            "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_medication_zero_dosage_rejected(client: AsyncClient):
    headers = await register_and_login(client)
    resp = await client.post(
        "/api/v1/medications",
        json={
            "drug_id": "drug_war01",
            "dosage_amount": 0,  # must be > 0
            "dosage_unit": "mg",
            "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
        },
        headers=headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List medications
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_medications_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/medications")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_medications_empty_for_new_user(client: AsyncClient):
    headers = await register_and_login(client)
    resp = await client.get("/api/v1/medications", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_medications_active_only_by_default(client: AsyncClient):
    headers = await register_and_login(client)

    # Add two medications
    for drug_id in ["drug_war01", "drug_asp01"]:
        await client.post(
            "/api/v1/medications",
            json={
                "drug_id": drug_id,
                "dosage_amount": 5.0,
                "dosage_unit": "mg",
                "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
            },
            headers=headers,
        )

    resp = await client.get("/api/v1/medications", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(e["is_active"] for e in data)


@pytest.mark.asyncio
async def test_list_medications_include_inactive_shows_deactivated(client: AsyncClient):
    headers = await register_and_login(client)

    # Add and deactivate one, keep one active
    add1 = await client.post(
        "/api/v1/medications",
        json={"drug_id": "drug_war01", "dosage_amount": 5.0, "dosage_unit": "mg",
              "schedules": [{"time_of_day": "08:00", "days_of_week": []}]},
        headers=headers,
    )
    entry_id_1 = add1.json()["entry_id"]

    await client.post(
        "/api/v1/medications",
        json={"drug_id": "drug_asp01", "dosage_amount": 100.0, "dosage_unit": "mg",
              "schedules": [{"time_of_day": "08:00", "days_of_week": []}]},
        headers=headers,
    )

    # Deactivate first entry
    await client.patch(f"/api/v1/medications/{entry_id_1}", json={"deactivate": True}, headers=headers)

    # Default list: only active
    resp_default = await client.get("/api/v1/medications", headers=headers)
    default_ids = [e["entry_id"] for e in resp_default.json()]
    assert entry_id_1 not in default_ids
    assert len(default_ids) == 1

    # include_inactive: both entries returned
    resp_all = await client.get("/api/v1/medications?include_inactive=true", headers=headers)
    all_entries = resp_all.json()
    assert len(all_entries) == 2
    deactivated = next(e for e in all_entries if e["entry_id"] == entry_id_1)
    assert deactivated["is_active"] is False
    assert deactivated["end_date"] is not None


# ---------------------------------------------------------------------------
# PATCH — deactivate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deactivate_medication_sets_inactive(client: AsyncClient):
    headers = await register_and_login(client)
    add_resp = await client.post(
        "/api/v1/medications",
        json={"drug_id": "drug_war01", "dosage_amount": 5.0, "dosage_unit": "mg",
              "schedules": [{"time_of_day": "08:00", "days_of_week": []}]},
        headers=headers,
    )
    entry_id = add_resp.json()["entry_id"]

    deact = await client.patch(f"/api/v1/medications/{entry_id}", json={"deactivate": True}, headers=headers)
    assert deact.status_code == 200, deact.text
    assert deact.json()["is_active"] is False
    assert deact.json()["end_date"] is not None


@pytest.mark.asyncio
async def test_double_deactivate_returns_400(client: AsyncClient):
    headers = await register_and_login(client)
    add_resp = await client.post(
        "/api/v1/medications",
        json={"drug_id": "drug_war01", "dosage_amount": 5.0, "dosage_unit": "mg",
              "schedules": [{"time_of_day": "08:00", "days_of_week": []}]},
        headers=headers,
    )
    entry_id = add_resp.json()["entry_id"]

    await client.patch(f"/api/v1/medications/{entry_id}", json={"deactivate": True}, headers=headers)
    resp2 = await client.patch(f"/api/v1/medications/{entry_id}", json={"deactivate": True}, headers=headers)
    assert resp2.status_code == 400
    assert resp2.json()["detail"]["code"] == "already_inactive"


# ---------------------------------------------------------------------------
# PATCH — dosage and schedule edits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_dosage_amount(client: AsyncClient):
    headers = await register_and_login(client)
    add_resp = await client.post(
        "/api/v1/medications",
        json={"drug_id": "drug_war01", "dosage_amount": 5.0, "dosage_unit": "mg",
              "schedules": [{"time_of_day": "08:00", "days_of_week": []}]},
        headers=headers,
    )
    entry_id = add_resp.json()["entry_id"]

    patch_resp = await client.patch(
        f"/api/v1/medications/{entry_id}",
        json={"dosage_amount": 7.5, "dosage_unit": "mg"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["dosage_amount"] == 7.5


@pytest.mark.asyncio
async def test_patch_schedules_replaces_all(client: AsyncClient):
    """Replacing schedules via PATCH removes old ones and creates new ones."""
    headers = await register_and_login(client)
    add_resp = await client.post(
        "/api/v1/medications",
        json={"drug_id": "drug_war01", "dosage_amount": 5.0, "dosage_unit": "mg",
              "schedules": [
                  {"time_of_day": "08:00", "days_of_week": []},
                  {"time_of_day": "20:00", "days_of_week": []},
              ]},
        headers=headers,
    )
    entry_id = add_resp.json()["entry_id"]
    assert len(add_resp.json()["schedules"]) == 2

    # Replace with single noon schedule
    patch_resp = await client.patch(
        f"/api/v1/medications/{entry_id}",
        json={"schedules": [{"time_of_day": "12:00", "days_of_week": []}]},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    scheds = patch_resp.json()["schedules"]
    assert len(scheds) == 1
    assert scheds[0]["time_of_day"] == "12:00"


@pytest.mark.asyncio
async def test_patch_nonexistent_entry_returns_404(client: AsyncClient):
    headers = await register_and_login(client)
    resp = await client.patch(
        "/api/v1/medications/med_DOES_NOT_EXIST",
        json={"dosage_amount": 5.0},
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "medication_not_found"
