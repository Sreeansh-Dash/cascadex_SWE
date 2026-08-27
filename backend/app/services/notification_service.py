"""
CascadeX Notification Service — Phase 07.

Provides a pluggable channel abstraction for sending notifications to users.

Design:
- NotificationChannel is a Protocol — any object with send() qualifies.
- InAppChannel writes a Notification node to Neo4j so the client can poll
  GET /notifications for in-app badges.
- Future channels (FCM/APNs) can be drop-in replacements or additions
  without touching call-sites.

Call site usage::

    from app.services import notification_service
    await notification_service.send(
        session=session,
        user_id=user_id,
        type_="interaction_alert",
        message="Warfarin + Aspirin: major interaction detected.",
        related_alert_id=alert_id,
    )

FCM / APNs extension slot:
    To add push notifications, implement a class that satisfies the
    NotificationChannel Protocol and pass it as `channel=` in the call.
    Example::

        class FCMChannel:
            async def send(self, session, user_id, type_, message, related_alert_id):
                await fcm_client.send_push(user_id, message)

        await notification_service.send(..., channel=FCMChannel())
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal, Protocol

from neo4j import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel abstraction
# ---------------------------------------------------------------------------

class NotificationChannel(Protocol):
    """Protocol that any notification channel must satisfy.

    Implementing classes must define an async ``send`` method with the
    same signature as InAppChannel.send.
    """

    async def send(
        self,
        session: AsyncSession,
        user_id: str,
        type_: Literal["interaction_alert", "dose_reminder"],
        message: str,
        related_alert_id: str | None,
    ) -> str:
        """Deliver a notification; return the notification_id."""
        ...


class InAppChannel:
    """Writes a Notification node to Neo4j for in-app display.

    Node label: ``Notification``
    Properties: notification_id, user_id, type, message, related_alert_id,
                created_at, read (bool, default False)

    The node is linked to the owning User via HAS_NOTIFICATION so it can
    be fetched with a simple MATCH pattern.
    """

    async def send(
        self,
        session: AsyncSession,
        user_id: str,
        type_: Literal["interaction_alert", "dose_reminder"],
        message: str,
        related_alert_id: str | None = None,
    ) -> str:
        """Persist a Notification node and return notification_id."""
        notification_id = f"notif_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(UTC).isoformat()

        await session.run(
            """
            MATCH (u:User {user_id: $user_id})
            CREATE (n:Notification {
                notification_id: $notification_id,
                user_id:         $user_id,
                type:            $type,
                message:         $message,
                related_alert_id: $related_alert_id,
                created_at:      $created_at,
                read:            false
            })
            CREATE (u)-[:HAS_NOTIFICATION]->(n)
            """,
            {
                "user_id": user_id,
                "notification_id": notification_id,
                "type": type_,
                "message": message,
                "related_alert_id": related_alert_id,
                "created_at": now_iso,
            },
        )
        logger.info(
            "Notification created notification_id=%s user_id=%s type=%s",
            notification_id,
            user_id,
            type_,
        )
        return notification_id


# ---------------------------------------------------------------------------
# Default entry point
# ---------------------------------------------------------------------------

_default_channel = InAppChannel()


async def send(
    session: AsyncSession,
    user_id: str,
    type_: Literal["interaction_alert", "dose_reminder"],
    message: str,
    related_alert_id: str | None = None,
    channel: NotificationChannel = _default_channel,  # type: ignore[assignment]
) -> str:
    """Send a notification via the given channel (default: InAppChannel).

    Args:
        session: Open Neo4j async session.
        user_id: Recipient user's ID.
        type_: ``"interaction_alert"`` or ``"dose_reminder"``.
        message: Notification body text.
        related_alert_id: Optional alert_id for cross-referencing.
        channel: Notification delivery channel (default: InAppChannel).

    Returns:
        The notification_id of the created/delivered notification.
    """
    return await channel.send(
        session=session,
        user_id=user_id,
        type_=type_,
        message=message,
        related_alert_id=related_alert_id,
    )
