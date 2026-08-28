"""
CascadeX Pydantic models for medication management.

Covers Phase 04 CRUD:
- MedicationCreate / MedicationUpdate / MedicationRead  (MedicationEntry Neo4j node)
- DoseScheduleCreate / DoseScheduleRead                 (DoseSchedule Neo4j node)
- DoseLogCreate / DoseLogRead                           (DoseIntakeLog Neo4j node)

Allowed dosage units (document here — enforced via Literal):
    "mg", "ml", "mcg", "tablet", "capsule", "unit", "drop", "patch", "puff", "spray"

input_method is always "manual" in Phase 04; Phase 05 will write "scan" for
OCR-originated entries without needing a migration.

Phase 06 adds:
- MedicationRead.interaction_check (optional) — populated after add/update.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Phase 06: direct import needed (Pydantic resolves annotations at runtime)
from app.models.interaction import InteractionCheckResult  # noqa: F401  (re-exported)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

# Allowed dosage unit values — extend with care; kept narrow for data hygiene
DosageUnit = Literal["mg", "ml", "mcg", "tablet", "capsule", "unit", "drop", "patch", "puff", "spray"]


class DoseStatus(str, Enum):
    """Status of a single dose intake log entry (FR-MED-4)."""

    TAKEN = "taken"
    MISSED = "missed"
    SKIPPED = "skipped"


class InputMethod(str, Enum):
    """How the medication entry was created."""

    MANUAL = "manual"
    SCAN = "scan"  # written by Phase 05; field exists now to avoid a migration


# ---------------------------------------------------------------------------
# DoseSchedule schemas
# ---------------------------------------------------------------------------

class DoseScheduleCreate(BaseModel):
    """One schedule row for a medication (e.g. morning dose).

    A single MedicationEntry may have multiple DoseSchedule rows
    (e.g. twice-daily = two rows).

    Attributes:
        time_of_day: HH:MM in 24-hour format (e.g. "08:00", "20:00").
        days_of_week: List of day names (full English, e.g. ["Monday", "Wednesday"]).
                      Empty list means every day.
    """

    time_of_day: str = Field(
        ...,
        pattern=r"^\d{2}:\d{2}$",
        description="HH:MM in 24-hour format",
        examples=["08:00", "20:30"],
    )
    days_of_week: list[str] = Field(
        default_factory=list,
        description="Days of week (e.g. ['Monday', 'Friday']). Empty = every day.",
    )


class DoseScheduleRead(BaseModel):
    """Response schema for a DoseSchedule node."""

    schedule_id: str
    time_of_day: str
    days_of_week: list[str] = []

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# MedicationEntry schemas
# ---------------------------------------------------------------------------

class MedicationCreate(BaseModel):
    """Request body for adding a new medication.

    Attributes:
        drug_id: Must reference an existing Drug node in Neo4j (validated server-side).
        dosage_amount: Numeric quantity (e.g. 500 for "500 mg").
        dosage_unit: One of the allowed unit strings (see DosageUnit).
        notes: Optional free-text clinical notes.
        schedules: One or more schedule rows; at least one is required.
    """

    drug_id: str = Field(..., description="drug_id of an existing Drug node")
    dosage_amount: float = Field(..., gt=0, description="Numeric dosage amount (e.g. 500)")
    dosage_unit: DosageUnit = Field(..., description="Unit of dosage amount")
    notes: str | None = Field(default=None, max_length=1000)
    schedules: list[DoseScheduleCreate] = Field(
        ..., min_length=1, description="At least one schedule row required"
    )


class MedicationUpdate(BaseModel):
    """Request body for editing or deactivating a medication entry.

    All fields are optional.  To deactivate, set ``deactivate=True``.
    Dosage and schedule edits are ignored when ``deactivate=True``.

    Attributes:
        dosage_amount: Updated dosage amount (optional).
        dosage_unit: Updated dosage unit (optional).
        notes: Updated notes (optional).
        schedules: Replace all schedules for this entry (optional).
        deactivate: If True, sets is_active=False and records end_date.
    """

    dosage_amount: float | None = Field(default=None, gt=0)
    dosage_unit: DosageUnit | None = None
    notes: str | None = Field(default=None, max_length=1000)
    schedules: list[DoseScheduleCreate] | None = None
    deactivate: bool = Field(default=False, description="Set True to end/deactivate this medication")


class MedicationRead(BaseModel):
    """Response schema for a MedicationEntry node.

    Phase 06 note: ``interaction_check`` is populated on POST /medications and
    PATCH /medications/{id} responses.  It is ``None`` on GET list/detail calls
    (no check is triggered for read-only operations).
    """

    entry_id: str
    drug_id: str
    generic_name: str           # denormalised from Drug for display
    drug_class: str = ""
    dosage_amount: float
    dosage_unit: str
    input_method: str           # "manual" | "scan"
    is_active: bool
    notes: str | None = None
    start_date: str
    end_date: str | None = None
    created_at: str
    schedules: list[DoseScheduleRead] = []
    # Phase 06 — populated after add/update; None for read-only responses
    interaction_check: InteractionCheckResult | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# DoseIntakeLog schemas
# ---------------------------------------------------------------------------

class DoseLogCreate(BaseModel):
    """Request body for logging a dose intake event (FR-MED-4).

    Attributes:
        status: Whether the dose was taken, missed, or skipped.
        scheduled_time: ISO-8601 datetime the dose was scheduled.
        taken_at: ISO-8601 datetime when actually taken (required when status=taken).
        notes: Optional free-text note for this dose event.
    """

    status: DoseStatus
    scheduled_time: str = Field(..., description="ISO-8601 scheduled datetime")
    taken_at: str | None = Field(
        default=None,
        description="ISO-8601 actual intake time (required when status=taken)",
    )
    notes: str | None = Field(default=None, max_length=500)


class DoseLogRead(BaseModel):
    """Response schema for a DoseIntakeLog node."""

    log_id: str
    entry_id: str
    status: str                 # "taken" | "missed" | "skipped"
    scheduled_time: str
    taken_at: str | None = None
    notes: str | None = None
    logged_at: str

    model_config = ConfigDict(from_attributes=True)
