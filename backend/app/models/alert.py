"""
CascadeX Pydantic models for Phase 07 — Alerts & Acknowledgment.

InteractionAlertRead  — full alert payload returned by GET /alerts and POST acknowledge
AcknowledgeRequest    — empty body for POST /alerts/{id}/acknowledge
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_DISCLAIMER = (
    "This is not medical advice — consult your pharmacist or doctor."
)


class InteractionAlertRead(BaseModel):
    """Full representation of a persisted InteractionAlert node.

    Attributes:
        alert_id: Unique identifier (alert_XXXX).
        user_id: Owner of this alert.
        interaction_id: DDInter interaction_id that triggered this alert.
        entry_a_id: MedicationEntry.entry_id for drug A.
        entry_b_id: MedicationEntry.entry_id for drug B.
        drug_a_name: Generic name of drug A (denormalised).
        drug_b_name: Generic name of drug B (denormalised).
        severity_at_trigger: Severity recorded when alert was created
            (minor | moderate | major).
        requires_acknowledgment: True only when severity_at_trigger == "major".
        acknowledged: Whether the alert has been acknowledged.
        acknowledged_at: ISO-8601 timestamp of acknowledgment (None if not yet).
        triggered_at: ISO-8601 timestamp when alert was first created.
        mechanism: Raw DDInter mechanism string.
        plain_language: LLM plain-English rewrite (or mechanism if LLM skipped).
        management_advice: Clinical management guidance from DDInter.
        disclaimer: Always populated — fixed safety string.
    """

    alert_id: str
    user_id: str
    interaction_id: str
    entry_a_id: str
    entry_b_id: str
    drug_a_name: str
    drug_b_name: str
    severity_at_trigger: Literal["minor", "moderate", "major"]
    requires_acknowledgment: bool
    acknowledged: bool
    acknowledged_at: str | None = None
    triggered_at: str
    mechanism: str
    plain_language: str
    management_advice: str
    disclaimer: str = Field(default=_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)


class AcknowledgeRequest(BaseModel):
    """Empty request body for POST /alerts/{alert_id}/acknowledge.

    No fields are required — the acknowledgement is implicit in the action.
    Kept as a named model so OpenAPI schema is self-documenting.
    """

    model_config = ConfigDict(from_attributes=True)
