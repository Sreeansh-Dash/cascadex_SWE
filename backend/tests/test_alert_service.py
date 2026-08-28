"""
Phase 07 — test_alert_service.py

Integration tests for alert_service using real Neo4j.

Covers:
1. check_result with one PairwiseInteraction → exactly one InteractionAlert created
2. Re-running same check (idempotency) → no duplicate unacknowledged alert
3. acknowledge_alert() → alert.acknowledged becomes True
4. acknowledge_alert() → acknowledged_at is set
5. view_only caregiver cannot acknowledge → 403
"""

from __future__ import annotations

import pytest

from app.models.interaction import InteractionCheckResult, PairwiseInteraction
from app.services import alert_service

# Re-use conftest fixtures: neo4j_driver, client, seed_drug_catalog, register_and_login


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_check_result(
    drug_a_id: str = "D001",
    drug_b_id: str = "D009",
    drug_a_name: str = "warfarin",
    drug_b_name: str = "omeprazole",
    severity: str = "major",
    mechanism: str = "CYP2C19 inhibition raises warfarin levels",
) -> InteractionCheckResult:
    pair = PairwiseInteraction(
        drug_a_id=drug_a_id,
        drug_b_id=drug_b_id,
        drug_a_name=drug_a_name,
        drug_b_name=drug_b_name,
        severity=severity,
        mechanism=mechanism,
        plain_language=f"Taking {drug_a_name} with {drug_b_name} can increase bleeding risk.",
        management_advice="Monitor INR closely.",
        source="DDInter_2.0",
    )
    return InteractionCheckResult(
        checked_drug_ids=[drug_a_id, drug_b_id],
        interactions=[pair],
        unmatched_warnings=[],
        is_clean=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_alert_from_check_result(neo4j_driver):
    """One PairwiseInteraction → exactly one InteractionAlert node created."""
    async with neo4j_driver.session() as session:
        # Create a minimal user node
        user_id = "test_alert_user_01"
        await session.run(
            "MERGE (u:User {user_id: $uid, token_version: 1})",
            {"uid": user_id},
        )
        check_result = _make_check_result()
        entry_ids = {"D001": "med_e001", "D009": "med_e009"}

        created = await alert_service.create_alerts_from_check_result(
            session, user_id, check_result, entry_ids
        )
        assert len(created) == 1

        # Verify Neo4j node exists
        res = await session.run(
            "MATCH (u:User {user_id: $uid})-[:HAS_ALERT]->(a:InteractionAlert) RETURN a",
            {"uid": user_id},
        )
        records = await res.data()
        assert len(records) == 1
        node = records[0]["a"]
        assert node["acknowledged"] is False
        assert "warfarin" in node["drug_a_name"] or "omeprazole" in node["drug_b_name"]


@pytest.mark.asyncio
async def test_create_alert_idempotent(neo4j_driver):
    """Re-running the same check does NOT create a second unacknowledged alert."""
    async with neo4j_driver.session() as session:
        user_id = "test_alert_user_02"
        await session.run(
            "MERGE (u:User {user_id: $uid, token_version: 1})",
            {"uid": user_id},
        )
        check_result = _make_check_result()
        entry_ids = {"D001": "med_e001", "D009": "med_e009"}

        # First call
        await alert_service.create_alerts_from_check_result(
            session, user_id, check_result, entry_ids
        )
        # Second call with same data
        created2 = await alert_service.create_alerts_from_check_result(
            session, user_id, check_result, entry_ids
        )

        # Second call should return empty (merge was a no-op)
        assert created2 == []

        # Only ONE alert node in DB
        res = await session.run(
            "MATCH (u:User {user_id: $uid})-[:HAS_ALERT]->(a:InteractionAlert) RETURN count(a) AS cnt",
            {"uid": user_id},
        )
        record = await res.single()
        assert record["cnt"] == 1


@pytest.mark.asyncio
async def test_acknowledge_alert(neo4j_driver):
    """acknowledge_alert() sets acknowledged=True and acknowledged_at."""
    async with neo4j_driver.session() as session:
        user_id = "test_alert_user_03"
        await session.run(
            "MERGE (u:User {user_id: $uid, token_version: 1})",
            {"uid": user_id},
        )
        check_result = _make_check_result()
        entry_ids = {"D001": "med_e001", "D009": "med_e009"}
        created = await alert_service.create_alerts_from_check_result(
            session, user_id, check_result, entry_ids
        )
        assert len(created) == 1
        alert_id = created[0]

        updated = await alert_service.acknowledge_alert(
            session, user_id, alert_id,
            caregiver_role=None, permission_level=None,
        )
        assert updated.acknowledged is True
        assert updated.acknowledged_at is not None


@pytest.mark.asyncio
async def test_acknowledge_alert_sets_acknowledged_at_timestamp(neo4j_driver):
    """acknowledged_at is a valid ISO-8601 timestamp after acknowledgment."""
    async with neo4j_driver.session() as session:
        user_id = "test_alert_user_04"
        await session.run(
            "MERGE (u:User {user_id: $uid, token_version: 1})",
            {"uid": user_id},
        )
        check_result = _make_check_result()
        entry_ids = {"D001": "med_e001", "D009": "med_e009"}
        created = await alert_service.create_alerts_from_check_result(
            session, user_id, check_result, entry_ids
        )
        alert_id = created[0]
        updated = await alert_service.acknowledge_alert(
            session, user_id, alert_id,
        )
        from datetime import datetime
        # Should parse without exception
        parsed = datetime.fromisoformat(updated.acknowledged_at)
        assert parsed.year >= 2024


@pytest.mark.asyncio
async def test_view_only_caregiver_cannot_acknowledge(neo4j_driver):
    """View-only caregiver → acknowledge_alert raises 403."""
    from fastapi import HTTPException

    from app.models.caregiver import PermissionLevel

    async with neo4j_driver.session() as session:
        user_id = "test_alert_user_05"
        await session.run(
            "MERGE (u:User {user_id: $uid, token_version: 1})",
            {"uid": user_id},
        )
        check_result = _make_check_result()
        entry_ids = {"D001": "med_e001", "D009": "med_e009"}
        created = await alert_service.create_alerts_from_check_result(
            session, user_id, check_result, entry_ids
        )
        alert_id = created[0]

        with pytest.raises(HTTPException) as exc_info:
            await alert_service.acknowledge_alert(
                session, user_id, alert_id,
                caregiver_role="caregiver",
                permission_level=PermissionLevel.VIEW_ONLY,
            )
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_list_alerts_returns_newest_first(neo4j_driver):
    """list_alerts returns alerts ordered newest-first."""
    import asyncio
    async with neo4j_driver.session() as session:
        user_id = "test_alert_user_06"
        await session.run(
            "MERGE (u:User {user_id: $uid, token_version: 1})",
            {"uid": user_id},
        )
        # Create two distinct alerts by using different drug pairs
        cr1 = _make_check_result("D001", "D009", mechanism="CYP2C19 warfarin effect")
        cr2 = _make_check_result("D002", "D003", "aspirin", "lisinopril",
                                 "major", "ACE inhibitor NSAID risk")

        await alert_service.create_alerts_from_check_result(session, user_id, cr1, {"D001": "e1", "D009": "e2"})
        await asyncio.sleep(0.01)  # ensure time ordering
        await alert_service.create_alerts_from_check_result(session, user_id, cr2, {"D002": "e3", "D003": "e4"})

        alerts = await alert_service.list_alerts(session, user_id)
        assert len(alerts) >= 2
        # Newest first: triggered_at of first result ≥ second
        assert alerts[0].triggered_at >= alerts[1].triggered_at


@pytest.mark.asyncio
async def test_list_alerts_acknowledged_filter(neo4j_driver):
    """list_alerts with acknowledged=False excludes acknowledged alerts."""
    async with neo4j_driver.session() as session:
        user_id = "test_alert_user_07"
        await session.run(
            "MERGE (u:User {user_id: $uid, token_version: 1})",
            {"uid": user_id},
        )
        check_result = _make_check_result()
        entry_ids = {"D001": "med_e001", "D009": "med_e009"}
        created = await alert_service.create_alerts_from_check_result(
            session, user_id, check_result, entry_ids
        )
        alert_id = created[0]

        # Acknowledge it
        await alert_service.acknowledge_alert(session, user_id, alert_id)

        # Filter for unacknowledged → should be empty
        unacked = await alert_service.list_alerts(session, user_id, acknowledged=False)
        assert all(not a.acknowledged for a in unacked)
