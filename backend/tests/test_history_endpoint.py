"""
Phase 08 — test_history_endpoint.py

Tests for `GET /api/v1/history` endpoint:
- Auth required (401 if missing token)
- Chronological ordering: mix of doses and alerts returned in correct merged order (newest-first)
- Pagination cursor (`before`) works as expected
- Empty history returns empty list with has_more=False
"""

import asyncio
from datetime import UTC, datetime, timedelta
import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_get_history_requires_auth(client: AsyncClient):
    """GET /api/v1/history without token returns 401."""
    res = await client.get("/api/v1/history")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_history_empty_initially(client: AsyncClient):
    """Newly registered user has empty history feed."""
    headers = await register_and_login(client)
    res = await client.get("/api/v1/history", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["events"] == []
    assert data["has_more"] is False
    assert data["next_cursor"] is None


@pytest.mark.asyncio
async def test_get_history_chronological_ordering(client: AsyncClient):
    """Feed merges dose logs and alerts in descending chronological order."""
    headers = await register_and_login(client)

    # 1. Add Warfarin
    add_w = await client.post(
        "/api/v1/medications",
        headers=headers,
        json={
            "drug_id": "D001",
            "dosage_amount": 5.0,
            "dosage_unit": "mg",
            "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
        },
    )
    assert add_w.status_code == 201
    entry_w_id = add_w.json()["entry_id"]

    # 2. Log a dose 2 hours ago
    t_dose = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    log_res = await client.post(
        f"/api/v1/medications/{entry_w_id}/doses",
        headers=headers,
        json={
            "status": "taken",
            "scheduled_time": t_dose,
            "taken_at": t_dose,
            "notes": "Morning dose",
        },
    )
    assert log_res.status_code == 201

    # 3. Add Aspirin (triggers a major interaction alert with Warfarin)
    add_a = await client.post(
        "/api/v1/medications",
        headers=headers,
        json={
            "drug_id": "D002",
            "dosage_amount": 81.0,
            "dosage_unit": "mg",
            "schedules": [{"time_of_day": "12:00", "days_of_week": []}],
        },
    )
    assert add_a.status_code == 201

    # 4. Fetch history feed
    res = await client.get("/api/v1/history", headers=headers)
    assert res.status_code == 200
    data = res.json()
    events = data["events"]
    assert len(events) >= 2

    # Verify both dose and alert are present
    event_types = [e["event_type"] for e in events]
    assert "dose" in event_types
    assert "alert" in event_types

    # Verify sorted strictly newest-first (descending timestamp)
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps, reverse=True)


@pytest.mark.asyncio
async def test_get_history_pagination_cursor(client: AsyncClient):
    """Pagination via `before` cursor correctly slices events."""
    headers = await register_and_login(client)

    # Add a medication
    add_res = await client.post(
        "/api/v1/medications",
        headers=headers,
        json={
            "drug_id": "D001",
            "dosage_amount": 5.0,
            "dosage_unit": "mg",
            "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
        },
    )
    entry_id = add_res.json()["entry_id"]

    # Log 3 doses at spaced times
    for i in range(3):
        t = (datetime.now(UTC) - timedelta(hours=i + 1)).isoformat()
        await client.post(
            f"/api/v1/medications/{entry_id}/doses",
            headers=headers,
            json={
                "status": "taken",
                "scheduled_time": t,
                "taken_at": t,
            },
        )

    # Page 1 (limit=2)
    p1 = await client.get("/api/v1/history?limit=2", headers=headers)
    assert p1.status_code == 200
    d1 = p1.json()
    assert len(d1["events"]) == 2
    assert d1["has_more"] is True
    assert d1["next_cursor"] is not None

    # Page 2 (with cursor)
    p2 = await client.get(f"/api/v1/history?limit=2&before={d1['next_cursor']}", headers=headers)
    assert p2.status_code == 200
    d2 = p2.json()
    assert len(d2["events"]) >= 1
    # Check no overlap
    p1_ids = {e["event_id"] for e in d1["events"]}
    p2_ids = {e["event_id"] for e in d2["events"]}
    assert p1_ids.isdisjoint(p2_ids)
