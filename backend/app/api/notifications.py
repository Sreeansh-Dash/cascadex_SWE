"""In-app notification feed."""

from fastapi import APIRouter, Depends, Query
from neo4j import AsyncSession

from app.core.dependencies import get_current_user
from app.db.neo4j_session import get_session
from app.models.notification import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth_context: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[NotificationRead]:
    """Return newest notifications for the resolved user/caregiver target."""
    result = await session.run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_NOTIFICATION]->(n:Notification)
        RETURN n
        ORDER BY n.created_at DESC
        SKIP $offset LIMIT $limit
        """,
        user_id=auth_context["user_id"], offset=offset, limit=limit,
    )
    rows = await result.data()
    return [NotificationRead(**dict(row["n"])) for row in rows]
