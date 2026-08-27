"""
CascadeX Alert Service — Phase 07.

Persists InteractionAlert nodes from check_pairs() results, enforces
acknowledgment RBAC, and drives notification delivery.

=============================================================================
Design invariants
=============================================================================

Idempotency invariant:
    create_alerts_from_check_result() uses MERGE on
    (user_id, interaction_id, entry_a_id, entry_b_id).
    Re-running the same check after an unrelated field edit does NOT create
    a second unacknowledged alert.  Notification is sent ONLY when the MERGE
    actually creates a new node (ON CREATE SET path).

Tiering invariant:
    severity == "major"  → requires_acknowledgment = True
    severity != "major"  → requires_acknowledgment = False

RBAC invariant:
    acknowledge_alert() rejects view_only caregivers with 403.
    Primary users always pass.

Disclaimer invariant:
    InteractionAlertRead always carries the fixed disclaimer string
    (enforced by the Pydantic model default).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from neo4j import AsyncSession

from app.models.alert import InteractionAlertRead
from app.models.caregiver import PermissionLevel
from app.models.interaction import InteractionCheckResult
from app.services import notification_service

logger = logging.getLogger(__name__)

_DISCLAIMER = "This is not medical advice — consult your pharmacist or doctor."


# ---------------------------------------------------------------------------
# Create alerts (idempotent)
# ---------------------------------------------------------------------------

async def create_alerts_from_check_result(
    session: AsyncSession,
    user_id: str,
    check_result: InteractionCheckResult,
    entry_ids_by_drug_id: dict[str, str],
) -> list[str]:
    """Persist InteractionAlert nodes from a check_pairs() result.

    Uses MERGE so re-running the same check never creates duplicate
    unacknowledged alerts.  Notification is fired ONLY for newly-created
    alerts (ON CREATE path in Cypher).

    Args:
        session: Open Neo4j async session.
        user_id: Owner of the medication list.
        check_result: Result from interaction_engine.check_pairs().
        entry_ids_by_drug_id: Mapping of {drug_id: entry_id} for active
            medication entries, so alert nodes can reference entry_a_id /
            entry_b_id.

    Returns:
        List of alert_ids that were created (not re-merged).
    """
    created_alert_ids: list[str] = []

    for pair in check_result.interactions:
        entry_a_id = entry_ids_by_drug_id.get(pair.drug_a_id, "")
        entry_b_id = entry_ids_by_drug_id.get(pair.drug_b_id, "")
        requires_ack = pair.severity == "major"
        alert_id = f"alert_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(UTC).isoformat()

        # MERGE on the natural key; ON CREATE sets all fields.
        # ON MATCH is intentionally empty — we never overwrite an existing alert.
        result = await session.run(
            """
            MATCH (u:User {user_id: $user_id})
            MERGE (a:InteractionAlert {
                user_id:        $user_id,
                interaction_id: $interaction_id,
                entry_a_id:     $entry_a_id,
                entry_b_id:     $entry_b_id
            })
            ON CREATE SET
                a.alert_id               = $alert_id,
                a.drug_a_name            = $drug_a_name,
                a.drug_b_name            = $drug_b_name,
                a.severity_at_trigger    = $severity,
                a.requires_acknowledgment = $requires_ack,
                a.acknowledged           = false,
                a.acknowledged_at        = null,
                a.triggered_at           = $triggered_at,
                a.mechanism              = $mechanism,
                a.plain_language         = $plain_language,
                a.management_advice      = $management_advice,
                a.disclaimer             = $disclaimer
            MERGE (u)-[:HAS_ALERT]->(a)
            RETURN a.alert_id AS alert_id,
                   (a.triggered_at = $triggered_at) AS is_new
            """,
            {
                "user_id": user_id,
                "interaction_id": pair.drug_a_id + "_" + pair.drug_b_id + "_" + pair.mechanism[:20],
                "entry_a_id": entry_a_id,
                "entry_b_id": entry_b_id,
                "alert_id": alert_id,
                "drug_a_name": pair.drug_a_name,
                "drug_b_name": pair.drug_b_name,
                "severity": pair.severity,
                "requires_ack": requires_ack,
                "triggered_at": now_iso,
                "mechanism": pair.mechanism,
                "plain_language": pair.plain_language,
                "management_advice": pair.management_advice,
                "disclaimer": _DISCLAIMER,
            },
        )
        record = await result.single()
        if record is None:
            continue

        actual_alert_id = record["alert_id"]
        is_new = record["is_new"]

        if is_new:
            created_alert_ids.append(actual_alert_id)
            message = (
                f"Interaction detected: {pair.drug_a_name} + {pair.drug_b_name} "
                f"({pair.severity}). {_DISCLAIMER}"
            )
            await notification_service.send(
                session=session,
                user_id=user_id,
                type_="interaction_alert",
                message=message,
                related_alert_id=actual_alert_id,
            )
            logger.info(
                "InteractionAlert created alert_id=%s user_id=%s severity=%s",
                actual_alert_id,
                user_id,
                pair.severity,
            )
        else:
            logger.debug(
                "InteractionAlert already exists for interaction_id — skipping notification user_id=%s",
                user_id,
            )

    return created_alert_ids


# ---------------------------------------------------------------------------
# Acknowledge
# ---------------------------------------------------------------------------

async def acknowledge_alert(
    session: AsyncSession,
    user_id: str,
    alert_id: str,
    caregiver_role: str | None = None,
    permission_level: PermissionLevel | None = None,
) -> InteractionAlertRead:
    """Acknowledge an InteractionAlert.

    Args:
        session: Open Neo4j async session.
        user_id: The target user who owns the alert.
        alert_id: The alert to acknowledge.
        caregiver_role: ``"caregiver"`` if acting as a caregiver, else None.
        permission_level: The caregiver's permission level.

    Returns:
        Updated InteractionAlertRead.

    Raises:
        HTTPException(403): If a view_only caregiver tries to acknowledge.
        HTTPException(404): If alert not found or not owned by user.
    """
    # RBAC: view_only caregivers cannot acknowledge
    if caregiver_role == "caregiver" and permission_level == PermissionLevel.VIEW_ONLY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "permission_denied",
                "message": "View-only caregivers cannot acknowledge alerts.",
            },
        )

    now_iso = datetime.now(UTC).isoformat()
    result = await session.run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_ALERT]->(a:InteractionAlert {alert_id: $alert_id})
        SET a.acknowledged    = true,
            a.acknowledged_at = $acknowledged_at
        RETURN a
        """,
        {"user_id": user_id, "alert_id": alert_id, "acknowledged_at": now_iso},
    )
    record = await result.single()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "alert_not_found",
                "message": f"Alert '{alert_id}' not found or not owned by user.",
            },
        )
    return _record_to_alert_read(dict(record["a"]))


# ---------------------------------------------------------------------------
# List alerts
# ---------------------------------------------------------------------------

async def list_alerts(
    session: AsyncSession,
    user_id: str,
    acknowledged: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[InteractionAlertRead]:
    """List interaction alerts for a user, newest-first.

    Args:
        session: Open Neo4j async session.
        user_id: The authenticated user.
        acknowledged: If provided, filter by acknowledged status.
        limit: Max results (default 50).
        offset: Pagination offset.

    Returns:
        List of InteractionAlertRead ordered by triggered_at descending.
    """
    ack_filter = ""
    params: dict = {"user_id": user_id, "limit": limit, "offset": offset}
    if acknowledged is not None:
        ack_filter = "AND a.acknowledged = $acknowledged"
        params["acknowledged"] = acknowledged

    cypher = f"""
    MATCH (u:User {{user_id: $user_id}})-[:HAS_ALERT]->(a:InteractionAlert)
    WHERE true {ack_filter}
    RETURN a
    ORDER BY a.triggered_at DESC
    SKIP $offset
    LIMIT $limit
    """
    result = await session.run(cypher, params)
    records = await result.data()
    return [_record_to_alert_read(dict(row["a"])) for row in records]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _record_to_alert_read(node: dict) -> InteractionAlertRead:
    """Convert a raw Neo4j node dict to InteractionAlertRead."""
    return InteractionAlertRead(
        alert_id=node["alert_id"],
        user_id=node["user_id"],
        interaction_id=node.get("interaction_id", ""),
        entry_a_id=node.get("entry_a_id", ""),
        entry_b_id=node.get("entry_b_id", ""),
        drug_a_name=node.get("drug_a_name", ""),
        drug_b_name=node.get("drug_b_name", ""),
        severity_at_trigger=node["severity_at_trigger"],
        requires_acknowledgment=node.get("requires_acknowledgment", False),
        acknowledged=node.get("acknowledged", False),
        acknowledged_at=node.get("acknowledged_at"),
        triggered_at=node["triggered_at"],
        mechanism=node.get("mechanism", ""),
        plain_language=node.get("plain_language", ""),
        management_advice=node.get("management_advice", ""),
        disclaimer=node.get("disclaimer", _DISCLAIMER),
    )
