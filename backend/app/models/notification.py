"""
CascadeX Pydantic models for Phase 07 — Notifications.

NotificationRead — represents a Notification node persisted to Neo4j
                   by InAppChannel after alert creation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    """A notification persisted to Neo4j by the in-app channel.

    Attributes:
        notification_id: Unique identifier (notif_XXXX).
        user_id: Recipient user_id.
        type: ``"interaction_alert"`` or ``"dose_reminder"``.
        message: Human-readable notification body.
        related_alert_id: alert_id this notification references (None for reminders).
        created_at: ISO-8601 creation timestamp.
        read: Whether the user has read / dismissed this notification.
    """

    notification_id: str
    user_id: str
    type: Literal["interaction_alert", "dose_reminder"]
    message: str
    related_alert_id: str | None = None
    created_at: str
    read: bool = False

    model_config = ConfigDict(from_attributes=True)
