"""
CascadeX Pydantic models for drug-related API responses.

These schemas are used by:
- `seed_ddinter.py` for data validation during import
- `drug_normalizer.py` for its return type
- Later phases' endpoints (Phases 04, 05, 06) for catalog search responses

All models are read-only (response schemas).  Write schemas (create/update)
are added in Phase 04 when medication CRUD endpoints are built.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DrugRead(BaseModel):
    """A drug from the catalog (generic drug node).

    Attributes:
        drug_id: Canonical unique identifier (e.g. DDInter drug ID or ATC code).
        generic_name: Lowercase canonical generic name (e.g. ``"warfarin"``).
        drug_class: Pharmacological class (e.g. ``"anticoagulant"``).
        atc_code: WHO ATC code (e.g. ``"B01AA03"``), may be empty string.
        default_form: Typical dosage form (e.g. ``"tablet"``, ``"capsule"``).
        external_source_id: Source-system ID from DDInter or RxNorm, if available.
    """

    drug_id: str
    generic_name: str
    drug_class: str = ""
    atc_code: str = ""
    default_form: str = ""
    external_source_id: str = ""


class DrugInteractionRead(BaseModel):
    """A pairwise drug-drug interaction edge from the DDInter dataset.

    The edge is stored as directed in Neo4j (drug_a → drug_b) but queried
    as undirected in the interaction engine (Phase 06).  See ``seed_ddinter.py``
    for the rationale and Phase 06 for query details.

    Attributes:
        interaction_id: Unique identifier for this interaction pair.
        drug_a_id: First drug in the pair (source of the directed edge).
        drug_b_id: Second drug in the pair (target of the directed edge).
        severity: One of ``"minor"``, ``"moderate"``, or ``"major"``.
        mechanism: Clinical mechanism string from DDInter (may be dense/technical).
        management_advice: Recommended clinical action or monitoring note.
        source: Data source label, e.g. ``"DDInter_2.0"``.
    """

    interaction_id: str
    drug_a_id: str
    drug_b_id: str
    severity: str  # "minor" | "moderate" | "major" — validated in engine
    mechanism: str = ""
    management_advice: str = ""
    source: str = "DDInter_2.0"


class DatasetVersionRead(BaseModel):
    """Metadata about a loaded DDInter/RxNorm dataset version.

    A ``DatasetVersion`` node is written (MERGE) on every successful import
    run, allowing the app to report exactly which dataset is loaded.

    Attributes:
        version: Caller-supplied version label (e.g. ``"ddinter-2.0-2024-01"``).
        source: Human-readable source description.
        imported_at: ISO-8601 timestamp of the import run.
        drug_count: Number of Drug nodes imported in this version.
        interaction_count: Number of INTERACTS_WITH edges imported.
    """

    version: str
    source: str = ""
    imported_at: str = ""
    drug_count: int = Field(default=0, ge=0)
    interaction_count: int = Field(default=0, ge=0)
