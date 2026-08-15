"""
CascadeX Pydantic models for Phase 06 — Interaction Engine.

Three models cover the full output of check_pairs():

    PairwiseInteraction    — a confirmed INTERACTS_WITH edge from Neo4j
    UnmatchedDrugWarning   — a drug_id that could not be resolved to a Drug node
    InteractionCheckResult — the top-level result returned by the engine

Safety invariants (mirrored in interaction_engine.py):
    Invariant 1: unresolvable drug  → UnmatchedDrugWarning (never silent drop)
    Invariant 2: PairwiseInteraction only exists for real Neo4j edges
                 (LLM cannot add or remove entries from this list)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class PairwiseInteraction(BaseModel):
    """A confirmed drug-drug interaction backed by a real INTERACTS_WITH edge.

    Every instance of this model corresponds to exactly one Neo4j
    INTERACTS_WITH edge that was found during the check_pairs query.
    The LLM may have rewritten ``mechanism`` into ``plain_language`` but
    it cannot change which pairs appear here.

    Attributes:
        drug_a_id: drug_id of the first drug in the pair.
        drug_b_id: drug_id of the second drug in the pair.
        drug_a_name: Generic name of drug_a (denormalised for display).
        drug_b_name: Generic name of drug_b (denormalised for display).
        severity: Normalised severity level — always one of minor/moderate/major.
        mechanism: Raw DDInter mechanism string.
        plain_language: LLM plain-English rewrite, or ``mechanism`` if LLM skipped.
        management_advice: Clinical management guidance from DDInter.
        source: Dataset identifier (e.g. "DDInter_2.0").
    """

    drug_a_id: str
    drug_b_id: str
    drug_a_name: str
    drug_b_name: str
    severity: Literal["minor", "moderate", "major"]
    mechanism: str
    plain_language: str      # LLM rewrite — or mechanism if LLM unavailable
    management_advice: str
    source: str              # e.g. "DDInter_2.0"

    model_config = ConfigDict(from_attributes=True)


class UnmatchedDrugWarning(BaseModel):
    """Warning emitted when a MedicationEntry's drug_id cannot be resolved.

    Safety Invariant 1 enforcement: this model exists so callers can never
    silently ignore an unresolvable drug. A response with unmatched_warnings
    must NEVER be treated as "all clear".

    Attributes:
        entry_id: The MedicationEntry.entry_id whose drug_id is broken.
        drug_id_attempted: The drug_id value that was not found in the catalog.
        reason: Human-readable explanation (e.g. "drug_id not found in catalog").
    """

    entry_id: str
    drug_id_attempted: str
    reason: str

    model_config = ConfigDict(from_attributes=True)


class InteractionCheckResult(BaseModel):
    """Top-level result from interaction_engine.check_pairs().

    Returned embedded in MedicationRead after add/update operations.
    Phase 07 will persist InteractionAlert nodes from this data.

    Attributes:
        checked_drug_ids: The de-duplicated drug_ids that were evaluated.
        interactions: All confirmed pairwise interactions found.
        unmatched_warnings: Warnings for drug_ids that could not be resolved.
        is_clean: True ONLY when both interactions and unmatched_warnings are
                  empty — i.e. no interactions found AND all drugs resolved.
    """

    checked_drug_ids: list[str]
    interactions: list[PairwiseInteraction]
    unmatched_warnings: list[UnmatchedDrugWarning]
    is_clean: bool          # shorthand: interactions==[] AND unmatched_warnings==[]

    model_config = ConfigDict(from_attributes=True)
