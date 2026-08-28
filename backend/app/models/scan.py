"""
CascadeX Scan Pydantic models — Phase 05.

ScanRecord lifecycle:
  1. Frontend ML Kit extracts text from camera frame.
  2. Frontend POST /scans → backend runs OCR match pipeline → ScanRecord created.
  3. Backend returns ``ScanCandidateList`` to the frontend.
  4. User reviews candidates, taps "Confirm & Add".
  5. Frontend POST /medications (input_method="scan") — a SEPARATE call.

Critical invariant: POST /scans NEVER creates a MedicationEntry.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.drug import DrugRead

# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------

ScanStatus = Literal["pending", "matched", "unmatched"]
MatchMethod = Literal["exact_generic", "exact_brand", "fuzzy_llm", "none"]


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class ScanCreate(BaseModel):
    """Body for POST /scans."""

    ocr_text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description=(
            "Raw text extracted from a prescription label by the on-device "
            "ML Kit OCR engine. May contain dosage, dates, and other noise."
        ),
    )


# ---------------------------------------------------------------------------
# Internal pipeline result (service layer only — not returned by API)
# ---------------------------------------------------------------------------


class OcrMatchResult(BaseModel):
    """Internal result of the two-stage OCR match pipeline.

    Not serialised directly into the API response; used between
    ``ocr_match_service`` and the ``scans`` router.
    """

    matched_drug: DrugRead | None = None
    matched_name: str | None = None  # the specific name (brand/generic) that matched
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    method: MatchMethod = "none"


# ---------------------------------------------------------------------------
# API response schemas
# ---------------------------------------------------------------------------


class ScanRecord(BaseModel):
    """A ScanRecord node stored in Neo4j and returned by the API.

    Returned by both ``POST /scans`` (inside ``ScanCandidateList``) and
    ``GET /scans/{scan_id}``.
    """

    scan_id: str
    user_id: str
    ocr_text: str
    status: ScanStatus
    matched_drug_id: str | None = None
    matched_drug_name: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    match_method: MatchMethod = "none"
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanCandidateList(BaseModel):
    """Response body for ``POST /scans``.

    The frontend must show this list and require the user to tap
    "Confirm & Add" before calling ``POST /medications``.
    No auto-add: this response never triggers a MedicationEntry directly.
    """

    scan_id: str
    ocr_text: str
    status: ScanStatus
    # Best single match (shown prominently in the confirmation UI).
    primary_match: DrugRead | None = None
    # Full candidate list for manual fallback selection.
    candidates: list[DrugRead] = Field(default_factory=list)
    # UI hint (e.g. "No confident match — please select manually").
    message: str = ""
