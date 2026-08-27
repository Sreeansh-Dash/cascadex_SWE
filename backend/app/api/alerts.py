"""
Alerts router — Phase 07.

Endpoints:
- GET  /api/v1/alerts                       — list interaction alerts (filterable by acknowledged)
- POST /api/v1/alerts/{alert_id}/acknowledge — acknowledge an alert (RBAC enforced)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from neo4j import AsyncSession

from app.core.dependencies import get_current_user, require_permission
from app.db.neo4j_session import get_session
from app.models.alert import AcknowledgeRequest, InteractionAlertRead
from app.models.caregiver import PermissionLevel
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get(
    "",
    response_model=list[InteractionAlertRead],
    summary="List interaction alerts",
    description=(
        "Returns interaction alerts for the authenticated user, newest-first. "
        "Use ``?acknowledged=false`` to get only unacknowledged alerts. "
        "Every alert carries a ``disclaimer`` field reminding the user to "
        "consult a pharmacist or doctor."
    ),
)
async def list_alerts(
    acknowledged: bool | None = Query(default=None, description="Filter by acknowledged status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth_context: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[InteractionAlertRead]:
    """List interaction alerts for the authenticated user."""
    user_id: str = auth_context["user_id"]
    return await alert_service.list_alerts(
        session=session,
        user_id=user_id,
        acknowledged=acknowledged,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{alert_id}/acknowledge",
    response_model=InteractionAlertRead,
    summary="Acknowledge an interaction alert",
    description=(
        "Marks an InteractionAlert as acknowledged by the user. "
        "Requires ``manage`` permission — view-only caregivers will receive 403. "
        "Idempotent: re-acknowledging an already-acknowledged alert is a no-op."
    ),
)
async def acknowledge_alert(
    alert_id: str,
    _body: AcknowledgeRequest = AcknowledgeRequest(),
    auth_context: Annotated[dict, Depends(require_permission(PermissionLevel.MANAGE))] = None,
    session: AsyncSession = Depends(get_session),
) -> InteractionAlertRead:
    """Acknowledge an interaction alert. View-only caregivers get 403."""
    user_id: str = auth_context["user_id"]
    return await alert_service.acknowledge_alert(
        session=session,
        user_id=user_id,
        alert_id=alert_id,
        caregiver_role=auth_context.get("role"),
        permission_level=auth_context.get("permission_level"),
    )
