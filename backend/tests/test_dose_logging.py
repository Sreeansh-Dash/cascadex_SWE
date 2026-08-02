"""
Phase 04 — Dose logging integration tests (real Neo4j).

Tests:
- Log taken / missed / skipped — all persist correctly
- taken_at required when status=taken, else 400
- Invalid status → 422
- Chronological ordering (scheduled_time ASC)
- Dose history preserved after medication deactivation
- Pagination (limit + offset)
- Dose log for nonexistent entry → 404
"""

import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def create_medication(client: AsyncClient, headers: dict, drug_id: str = "drug_war01") -> str:
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
    assert resp.status_code == 201, f"create_medication helper failed: {resp.text}"
    return resp.json()["entry_id"]


async def log_dose(
    client: AsyncClient,
    headers: dict,
    entry_id: str,
    status: str,
    scheduled_time: str,
    taken_at: str | None = None,
    notes: str | None = None,
) -> dict:
    payload: dict = {"status": status, "scheduled_time": scheduled_time}
    if taken_at:
        payload["taken_at"] = taken_at
    if notes:
        payload["notes"] = notes
    resp = await client.post(f"/api/v1/medications/{entry_id}/doses", json=payload, headers=headers)
    return resp


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_dose_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/medications/med_any/doses",
        json={"status": "missed", "scheduled_time": "2025-01-01T08:00:00+00:00"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_doses_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/medications/med_any/doses")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Status variants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_taken_persists(client: AsyncClient):
    headers = await register_and_login(client)
    entry_id = await create_medication(client, headers)

    resp = await log_dose(
        client, headers, entry_id,
        status="taken",
        scheduled_time="2025-01-01T08:00:00+00:00",
        taken_at="2025-01-01T08:05:00+00:00",
    )
    assert resp.status_code == 201, resp.text
    log = resp.json()
    assert log["status"] == "taken"
    assert log["taken_at"] is not None
    assert log["entry_id"] == entry_id
    assert "log_id" in log
    assert "logged_at" in log


@pytest.mark.asyncio
async def test_log_missed_persists(client: AsyncClient):
    headers = await register_and_login(client)
    entry_id = await create_medication(client, headers)

    resp = await log_dose(
        client, headers, entry_id,
        status="missed",
        scheduled_time="2025-01-01T20:00:00+00:00",
    )
    assert resp.status_code == 201, resp.text
    log = resp.json()
    assert log["status"] == "missed"
    assert log["taken_at"] is None


@pytest.mark.asyncio
async def test_log_skipped_with_notes(client: AsyncClient):
    headers = await register_and_login(client)
    entry_id = await create_medication(client, headers)

    resp = await log_dose(
        client, headers, entry_id,
        status="skipped",
        scheduled_time="2025-01-02T08:00:00+00:00",
        notes="Felt nauseous",
    )
    assert resp.status_code == 201, resp.text
    log = resp.json()
    assert log["status"] == "skipped"
    assert log["notes"] == "Felt nauseous"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_taken_without_taken_at_returns_400(client: AsyncClient):
    headers = await register_and_login(client)
    entry_id = await create_medication(client, headers)

    resp = await log_dose(
        client, headers, entry_id,
        status="taken",
        scheduled_time="2025-01-01T08:00:00+00:00",
        # taken_at intentionally omitted
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["code"] == "missing_taken_at"


@pytest.mark.asyncio
async def test_invalid_status_returns_422(client: AsyncClient):
    headers = await register_and_login(client)
    entry_id = await create_medication(client, headers)

    resp = await client.post(
        f"/api/v1/medications/{entry_id}/doses",
        json={"status": "INVALID_STATUS", "scheduled_time": "2025-01-01T08:00:00+00:00"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_log_dose_for_nonexistent_entry_returns_404(client: AsyncClient):
    headers = await register_and_login(client)

    resp = await log_dose(
        client, headers, "med_DOES_NOT_EXIST",
        status="missed",
        scheduled_time="2025-01-01T08:00:00+00:00",
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "medication_not_found"


# ---------------------------------------------------------------------------
# List + chronological ordering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_doses_empty_initially(client: AsyncClient):
    headers = await register_and_login(client)
    entry_id = await create_medication(client, headers)

    resp = await client.get(f"/api/v1/medications/{entry_id}/doses", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_dose_logs_returned_chronologically(client: AsyncClient):
    """Doses inserted out-of-order must be returned in scheduled_time ASC order."""
    headers = await register_and_login(client)
    entry_id = await create_medication(client, headers)

    # Log three doses with non-sequential insert order
    times_to_insert = [
        "2025-01-03T08:00:00+00:00",
        "2025-01-01T08:00:00+00:00",
        "2025-01-02T08:00:00+00:00",
    ]
    for t in times_to_insert:
        r = await log_dose(client, headers, entry_id, status="missed", scheduled_time=t)
        assert r.status_code == 201

    resp = await client.get(f"/api/v1/medications/{entry_id}/doses", headers=headers)
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) == 3
    returned_times = [l["scheduled_time"] for l in logs]
    assert returned_times == sorted(returned_times), \
        f"Expected chronological ASC order, got: {returned_times}"


@pytest.mark.asyncio
async def test_all_three_statuses_in_one_entry(client: AsyncClient):
    """Mixed status logs for one entry all retrieved and accurate."""
    headers = await register_and_login(client)
    entry_id = await create_medication(client, headers)

    await log_dose(client, headers, entry_id, "taken", "2025-01-01T08:00:00+00:00", taken_at="2025-01-01T08:02:00+00:00")
    await log_dose(client, headers, entry_id, "missed", "2025-01-02T08:00:00+00:00")
    await log_dose(client, headers, entry_id, "skipped", "2025-01-03T08:00:00+00:00", notes="Travel day")

    resp = await client.get(f"/api/v1/medications/{entry_id}/doses", headers=headers)
    logs = resp.json()
    assert len(logs) == 3
    statuses = [l["status"] for l in logs]
    assert set(statuses) == {"taken", "missed", "skipped"}


# ---------------------------------------------------------------------------
# Dose history after deactivation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dose_history_preserved_after_deactivation(client: AsyncClient):
    """Deactivating a medication does not delete its dose logs."""
    headers = await register_and_login(client)
    entry_id = await create_medication(client, headers)

    # Log a dose
    r = await log_dose(
        client, headers, entry_id,
        status="taken",
        scheduled_time="2025-01-01T08:00:00+00:00",
        taken_at="2025-01-01T08:02:00+00:00",
    )
    assert r.status_code == 201

    # Deactivate entry
    deact = await client.patch(f"/api/v1/medications/{entry_id}", json={"deactivate": True}, headers=headers)
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    # Dose history still accessible
    doses_resp = await client.get(f"/api/v1/medications/{entry_id}/doses", headers=headers)
    assert doses_resp.status_code == 200
    logs = doses_resp.json()
    assert len(logs) == 1
    assert logs[0]["status"] == "taken"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dose_list_pagination(client: AsyncClient):
    headers = await register_and_login(client)
    entry_id = await create_medication(client, headers)

    # Insert 6 doses
    for i in range(6):
        r = await log_dose(
            client, headers, entry_id,
            status="missed",
            scheduled_time=f"2025-01-{i+1:02d}T08:00:00+00:00",
        )
        assert r.status_code == 201

    # Page 1: limit=4
    page1 = await client.get(
        f"/api/v1/medications/{entry_id}/doses",
        params={"limit": 4, "offset": 0},
        headers=headers,
    )
    assert page1.status_code == 200
    assert len(page1.json()) == 4

    # Page 2: remaining 2
    page2 = await client.get(
        f"/api/v1/medications/{entry_id}/doses",
        params={"limit": 4, "offset": 4},
        headers=headers,
    )
    assert page2.status_code == 200
    assert len(page2.json()) == 2

    # Page 3: empty
    page3 = await client.get(
        f"/api/v1/medications/{entry_id}/doses",
        params={"limit": 4, "offset": 8},
        headers=headers,
    )
    assert page3.status_code == 200
    assert page3.json() == []
