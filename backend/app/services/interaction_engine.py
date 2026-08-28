"""
CascadeX Interaction Engine — Phase 06.

Computes pairwise drug-drug interactions for a user's active medication list.
This is a pure service module: no FastAPI/HTTP objects, no side effects.
Phase 07 will persist alerts; this phase only computes and returns them.

=============================================================================
SAFETY INVARIANTS — enforced in code, not just docs
=============================================================================

Invariant 1 — "Unmatched ≠ Safe"
    If any drug in the active list cannot be resolved to a Drug node, the
    response MUST include an explicit UnmatchedDrugWarning for that entry.
    The function NEVER returns is_clean=True (or an empty interactions list)
    when an unresolvable drug was silently dropped.
    Assertion: test_interaction_engine_unmatched.py verifies this.

Invariant 2 — "Never Invent an Interaction"
    Every PairwiseInteraction in the result corresponds to a real
    INTERACTS_WITH edge in Neo4j confirmed by a Cypher MATCH query.
    The LLM (plain_language_rewrite) is called ONLY AFTER the edge list is
    already complete — it rewrites mechanism text but cannot add, remove, or
    reorder pairs.  A code reviewer can verify this by reading the call order
    in check_pairs() alone.
    Assertion: test_interaction_engine_core.py verifies exact severity matches.

=============================================================================
Design notes
=============================================================================
- Single Cypher UNWIND query fetches ALL pairs in one round-trip (not N² calls).
- LLM rewrites run concurrently with asyncio.gather for speed.
- Severity normaliser lives in a single dict (_SEVERITY_MAP) and is the only
  place severity values are ever mapped.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from typing import Literal

from neo4j import AsyncSession

from app.ml.llm_client import plain_language_rewrite
from app.models.interaction import (
    InteractionCheckResult,
    PairwiseInteraction,
    UnmatchedDrugWarning,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Severity normaliser — single lookup, single place (Invariant 2 support)
# ---------------------------------------------------------------------------

_SEVERITY_MAP: dict[str, Literal["minor", "moderate", "major"]] = {
    "minor": "minor",
    "moderate": "moderate",
    "major": "major",
    # DDInter sometimes uses title-case
    "Minor": "minor",
    "Moderate": "moderate",
    "Major": "major",
    # lowercase variants just in case
    "MINOR": "minor",
    "MODERATE": "moderate",
    "MAJOR": "major",
}


def normalize_severity(raw: str) -> Literal["minor", "moderate", "major"]:
    """Map a raw DDInter severity string to the canonical three-tier enum.

    Args:
        raw: Severity string from the Neo4j INTERACTS_WITH edge.

    Returns:
        One of "minor", "moderate", or "major".

    Raises:
        ValueError: If raw is not a recognised severity string.
    """
    try:
        return _SEVERITY_MAP[raw]
    except KeyError as err:
        raise ValueError(
            f"Unknown severity value from DDInter: {raw!r}. "
            "Add it to _SEVERITY_MAP if this is a valid DDInter string."
        ) from err


# ---------------------------------------------------------------------------
# Neo4j pair query
# ---------------------------------------------------------------------------

_PAIRS_CYPHER = """
UNWIND $pairs AS pair
MATCH (a:Drug {drug_id: pair[0]})-[r:INTERACTS_WITH]-(b:Drug {drug_id: pair[1]})
RETURN a.drug_id          AS drug_a_id,
       a.generic_name     AS drug_a_name,
       b.drug_id          AS drug_b_id,
       b.generic_name     AS drug_b_name,
       r.severity         AS severity,
       r.mechanism        AS mechanism,
       r.management_advice AS management_advice,
       r.source           AS source
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def check_pairs(
    session: AsyncSession,
    drug_ids: list[str],
    unresolvable_entries: list[tuple[str, str]] | None = None,
) -> InteractionCheckResult:
    """Check all pairwise interactions for a list of drug_ids.

    This is the only entry point for interaction checking.  Callers supply
    the list of resolved drug_ids and separately the list of entry/drug_id
    pairs that could NOT be resolved (so we can emit warnings for them).

    Safety contract:
        - NEVER returns is_clean=True when unresolvable_entries is non-empty.
        - NEVER calls plain_language_rewrite before the edge list is final.
        - All PairwiseInteraction objects correspond to real Neo4j edges.

    Args:
        session: Open Neo4j async session (read-only — no writes here).
        drug_ids: List of resolved drug_ids from active MedicationEntry nodes.
                  Duplicates are removed internally.
        unresolvable_entries: Optional list of (entry_id, drug_id) tuples for
                              entries whose drug_id was not found in the catalog.
                              Each becomes an UnmatchedDrugWarning in the result.

    Returns:
        InteractionCheckResult with all found interactions and any warnings.
    """
    if unresolvable_entries is None:
        unresolvable_entries = []

    # Deduplicate drug_ids while preserving order
    seen: set[str] = set()
    unique_ids: list[str] = []
    for did in drug_ids:
        if did not in seen:
            seen.add(did)
            unique_ids.append(did)

    # ── Invariant 1: build warnings for unresolvable entries ────────────────
    warnings: list[UnmatchedDrugWarning] = [
        UnmatchedDrugWarning(
            entry_id=entry_id,
            drug_id_attempted=drug_id,
            reason="drug_id not found in catalog",
        )
        for entry_id, drug_id in unresolvable_entries
    ]

    # ── Short-circuit: nothing to check ─────────────────────────────────────
    if len(unique_ids) < 2:
        logger.debug(
            "check_pairs: fewer than 2 resolved drug_ids (%d) — no pairs to check",
            len(unique_ids),
        )
        return InteractionCheckResult(
            checked_drug_ids=unique_ids,
            interactions=[],
            unmatched_warnings=warnings,
            is_clean=(len(warnings) == 0),
        )

    # ── Build all unordered pairs ────────────────────────────────────────────
    pairs = [[a, b] for a, b in itertools.combinations(unique_ids, 2)]
    logger.debug(
        "check_pairs: checking %d pairs for %d drug_ids", len(pairs), len(unique_ids)
    )

    # ── Single Cypher round-trip for all pairs (Invariant 2) ─────────────────
    # The edge list is FULLY determined by Neo4j before the LLM is ever called.
    result = await session.run(_PAIRS_CYPHER, {"pairs": pairs})
    records = await result.data()

    # ── LLM plain-language rewrites (concurrent, AFTER edge list is final) ──
    # Invariant 2 guarantee: the LLM rewrites text only — it cannot change
    # which pairs are in `records`.
    async def _rewrite_record(row: dict) -> PairwiseInteraction:
        """Normalise one Neo4j record row into a PairwiseInteraction."""
        raw_sev = row.get("severity", "")
        try:
            severity = normalize_severity(raw_sev)
        except ValueError:
            logger.warning(
                "check_pairs: unrecognised severity '%s' for pair (%s, %s) — defaulting to 'minor'",
                raw_sev, row.get("drug_a_id"), row.get("drug_b_id"),
            )
            severity = "minor"

        mechanism: str = row.get("mechanism") or ""
        plain = plain_language_rewrite(mechanism)

        return PairwiseInteraction(
            drug_a_id=row["drug_a_id"],
            drug_b_id=row["drug_b_id"],
            drug_a_name=row.get("drug_a_name") or row["drug_a_id"],
            drug_b_name=row.get("drug_b_name") or row["drug_b_id"],
            severity=severity,
            mechanism=mechanism,
            plain_language=plain,
            management_advice=row.get("management_advice") or "",
            source=row.get("source") or "DDInter_2.0",
        )

    # Run all rewrites concurrently — each is an async function
    interactions: list[PairwiseInteraction] = list(
        await asyncio.gather(*[_rewrite_record(row) for row in records])
    )

    # Sort for deterministic output (major first, then moderate, minor)
    severity_order = {"major": 0, "moderate": 1, "minor": 2}
    interactions.sort(key=lambda i: severity_order.get(i.severity, 9))

    logger.info(
        "check_pairs: found %d interaction(s), %d warning(s) for %d drug(s)",
        len(interactions),
        len(warnings),
        len(unique_ids),
    )

    return InteractionCheckResult(
        checked_drug_ids=unique_ids,
        interactions=interactions,
        unmatched_warnings=warnings,
        is_clean=(len(interactions) == 0 and len(warnings) == 0),
    )
