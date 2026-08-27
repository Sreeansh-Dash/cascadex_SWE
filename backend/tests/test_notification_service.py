"""
Phase 07 — test_notification_service.py

Integration tests for notification_service.InAppChannel.

Covers:
1. InAppChannel.send() creates a retrievable Notification node in Neo4j
2. Acknowledging an alert does NOT create an additional notification
"""

from __future__ import annotations

import pytest

from app.models.interaction import InteractionCheckResult, PairwiseInteraction
from app.services import alert_service, notification_service
from app.services.notification_service import InAppChannel


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_in_app_channel_persists_notification(neo4j_driver):
    """InAppChannel.send() writes a Notification node retrievable from Neo4j."""
    async with neo4j_driver.session() as session:
        user_id = "notif_user_01"
        await session.run("MERGE (u:User {user_id: $uid, token_version: 1})", {"uid": user_id})

        channel = InAppChannel()
        notification_id = await channel.send(
            session=session,
            user_id=user_id,
            type_="interaction_alert",
            message="warfarin + omeprazole: major interaction detected.",
            related_alert_id="alert_test123",
        )

        assert notification_id.startswith("notif_")

        # Verify node in Neo4j
        res = await session.run(
            """
            MATCH (u:User {user_id: $uid})-[:HAS_NOTIFICATION]->(n:Notification)
            WHERE n.notification_id = $nid
            RETURN n
            """,
            {"uid": user_id, "nid": notification_id},
        )
        record = await res.single()
        assert record is not None
        node = dict(record["n"])
        assert node["type"] == "interaction_alert"
        assert node["related_alert_id"] == "alert_test123"
        assert node["read"] is False


@pytest.mark.asyncio
async def test_notification_via_default_send_function(neo4j_driver):
    """notification_service.send() uses InAppChannel by default."""
    async with neo4j_driver.session() as session:
        user_id = "notif_user_02"
        await session.run("MERGE (u:User {user_id: $uid, token_version: 1})", {"uid": user_id})

        nid = await notification_service.send(
            session=session,
            user_id=user_id,
            type_="dose_reminder",
            message="Time to take your aspirin (08:00).",
        )
        assert nid.startswith("notif_")

        # Verify via query
        res = await session.run(
            "MATCH (u:User {user_id: $uid})-[:HAS_NOTIFICATION]->(n:Notification {notification_id: $nid}) RETURN n",
            {"uid": user_id, "nid": nid},
        )
        record = await res.single()
        assert record is not None


@pytest.mark.asyncio
async def test_acknowledging_does_not_create_notification(neo4j_driver):
    """Acknowledging an alert does NOT create an additional Notification node."""
    async with neo4j_driver.session() as session:
        user_id = "notif_user_03"
        await session.run("MERGE (u:User {user_id: $uid, token_version: 1})", {"uid": user_id})

        # Create an alert (this fires one notification)
        pair = PairwiseInteraction(
            drug_a_id="D001", drug_b_id="D009",
            drug_a_name="warfarin", drug_b_name="omeprazole",
            severity="major", mechanism="CYP2C19",
            plain_language="risk of bleeding", management_advice="Monitor INR",
            source="DDInter_2.0",
        )
        cr = InteractionCheckResult(
            checked_drug_ids=["D001", "D009"],
            interactions=[pair],
            unmatched_warnings=[],
            is_clean=False,
        )
        created = await alert_service.create_alerts_from_check_result(
            session, user_id, cr, {"D001": "e1", "D009": "e2"}
        )
        alert_id = created[0]

        # Count notifications before ack
        res_before = await session.run(
            "MATCH (u:User {user_id: $uid})-[:HAS_NOTIFICATION]->(n) RETURN count(n) AS cnt",
            {"uid": user_id},
        )
        before_count = (await res_before.single())["cnt"]

        # Acknowledge the alert
        await alert_service.acknowledge_alert(session, user_id, alert_id)

        # Count notifications after ack
        res_after = await session.run(
            "MATCH (u:User {user_id: $uid})-[:HAS_NOTIFICATION]->(n) RETURN count(n) AS cnt",
            {"uid": user_id},
        )
        after_count = (await res_after.single())["cnt"]

        # No new notification should have been created
        assert after_count == before_count
