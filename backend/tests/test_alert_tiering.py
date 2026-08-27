"""
Phase 07 — test_alert_tiering.py

Tests for the alert tiering invariants:
- major severity → requires_acknowledgment = True
- moderate severity → requires_acknowledgment = False
- minor severity → requires_acknowledgment = False
- disclaimer is always present and non-empty on every alert
"""

from __future__ import annotations

import pytest

from app.models.interaction import InteractionCheckResult, PairwiseInteraction
from app.services import alert_service


def _make_pair(severity: str, mechanism_suffix: str = "") -> PairwiseInteraction:
    return PairwiseInteraction(
        drug_a_id="D001",
        drug_b_id="D009",
        drug_a_name="warfarin",
        drug_b_name="omeprazole",
        severity=severity,
        mechanism=f"Test mechanism {mechanism_suffix or severity}",
        plain_language=f"Plain language for {severity} interaction.",
        management_advice="Consult your doctor.",
        source="DDInter_2.0",
    )


def _make_result(severity: str) -> InteractionCheckResult:
    return InteractionCheckResult(
        checked_drug_ids=["D001", "D009"],
        interactions=[_make_pair(severity, severity)],
        unmatched_warnings=[],
        is_clean=False,
    )


@pytest.mark.asyncio
async def test_major_requires_acknowledgment(neo4j_driver):
    """Major severity alert → requires_acknowledgment=True."""
    async with neo4j_driver.session() as session:
        user_id = "tier_user_major"
        await session.run("MERGE (u:User {user_id: $uid, token_version: 1})", {"uid": user_id})
        result = _make_result("major")
        created = await alert_service.create_alerts_from_check_result(
            session, user_id, result, {"D001": "e1", "D009": "e2"}
        )
        assert len(created) == 1
        alerts = await alert_service.list_alerts(session, user_id)
        assert len(alerts) == 1
        assert alerts[0].requires_acknowledgment is True
        assert alerts[0].severity_at_trigger == "major"


@pytest.mark.asyncio
async def test_moderate_passive(neo4j_driver):
    """Moderate severity alert → requires_acknowledgment=False."""
    async with neo4j_driver.session() as session:
        user_id = "tier_user_moderate"
        await session.run("MERGE (u:User {user_id: $uid, token_version: 1})", {"uid": user_id})
        result = _make_result("moderate")
        await alert_service.create_alerts_from_check_result(
            session, user_id, result, {"D001": "e1", "D009": "e2"}
        )
        alerts = await alert_service.list_alerts(session, user_id)
        assert alerts[0].requires_acknowledgment is False
        assert alerts[0].severity_at_trigger == "moderate"


@pytest.mark.asyncio
async def test_minor_passive(neo4j_driver):
    """Minor severity alert → requires_acknowledgment=False."""
    async with neo4j_driver.session() as session:
        user_id = "tier_user_minor"
        await session.run("MERGE (u:User {user_id: $uid, token_version: 1})", {"uid": user_id})
        result = _make_result("minor")
        await alert_service.create_alerts_from_check_result(
            session, user_id, result, {"D001": "e1", "D009": "e2"}
        )
        alerts = await alert_service.list_alerts(session, user_id)
        assert alerts[0].requires_acknowledgment is False
        assert alerts[0].severity_at_trigger == "minor"


@pytest.mark.asyncio
async def test_disclaimer_always_present(neo4j_driver):
    """disclaimer field is always non-empty on every alert regardless of severity."""
    async with neo4j_driver.session() as session:
        for i, severity in enumerate(["minor", "moderate", "major"]):
            user_id = f"tier_disc_user_{i}"
            await session.run("MERGE (u:User {user_id: $uid, token_version: 1})", {"uid": user_id})
            result = _make_result(severity)
            await alert_service.create_alerts_from_check_result(
                session, user_id, result, {"D001": "e1", "D009": "e2"}
            )
            alerts = await alert_service.list_alerts(session, user_id)
            assert len(alerts) > 0
            for alert in alerts:
                assert alert.disclaimer
                assert len(alert.disclaimer) > 10
                # Must mention consulting professional
                assert "pharmacist" in alert.disclaimer.lower() or "doctor" in alert.disclaimer.lower()
