"""
CascadeX Pydantic models for Phase 08 — History & Timeline Feed.

Models:
    DoseHistoryEvent       — dose intake event in the timeline
    AlertHistoryEvent      — interaction alert event in the timeline
    HistoryEvent           — discriminated union of dose and alert events
    HistoryFeedResponse    — paginated response for GET /history
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class DoseHistoryEvent(BaseModel):
    """A dose intake event in the unified timeline feed."""

    event_type: Literal["dose"] = "dose"
    event_id: str = Field(..., description="Dose log_id (log_XXXX)")
    timestamp: str = Field(..., description="ISO-8601 timestamp of dose scheduled_time or taken_at")
    entry_id: str
    generic_name: str
    dosage_amount: float
    dosage_unit: str
    status: Literal["taken", "missed", "skipped"]
    taken_at: str | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AlertHistoryEvent(BaseModel):
    """An interaction alert event in the unified timeline feed."""

    event_type: Literal["alert"] = "alert"
    event_id: str = Field(..., description="Alert alert_id (alert_XXXX)")
    timestamp: str = Field(..., description="ISO-8601 timestamp when alert was triggered (triggered_at)")
    drug_a_name: str
    drug_b_name: str
    severity: Literal["minor", "moderate", "major"]
    requires_acknowledgment: bool
    acknowledged: bool
    acknowledged_at: str | None = None
    plain_language: str
    disclaimer: str

    model_config = ConfigDict(from_attributes=True)


# Discriminated union of timeline events
HistoryEvent = Annotated[DoseHistoryEvent | AlertHistoryEvent, Field(discriminator="event_type")]


class HistoryFeedResponse(BaseModel):
    """Paginated response containing chronological history events."""

    events: list[HistoryEvent]
    next_cursor: str | None = Field(default=None, description="Cursor (ISO-8601 timestamp) for next page")
    has_more: bool

    model_config = ConfigDict(from_attributes=True)
