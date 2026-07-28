"""
CascadeX drug name normalizer.

Resolves a raw drug name (brand or generic, any case) to a canonical
``Drug`` node in the Neo4j graph.

Matching strategy (Phase 02 — exact match only)
------------------------------------------------
1. Case-insensitive exact match on ``Drug.generic_name``.
2. If no generic match, case-insensitive exact match on
   ``DrugBrandName.brand_name``, returning the linked generic ``Drug``.
3. If neither matches → ``NormalizeResult(matched=False, ...)``.

Extension point for Phase 05 / Phase 06
----------------------------------------
A clearly-marked stub ``_fuzzy_match`` function is provided below.
Phase 05 will inject an ``llm_client.fuzzy_match_drug`` implementation
here so callers do not change.

Safety note
-----------
This function NEVER returns a false positive.  If the input cannot be
matched with confidence it returns ``match_type="unmatched"`` — the
caller (Phase 06 interaction engine) must treat that as an explicit warning,
not as "no interactions found".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from neo4j import AsyncSession

from app.models.drug import DrugRead


@dataclass
class NormalizeResult:
    """Result of a drug name normalization attempt.

    Attributes:
        matched: True if the raw name was resolved to a Drug node.
        drug: The matched Drug, or None if unmatched.
        match_type: One of ``"exact_generic"``, ``"exact_brand"``,
            or ``"unmatched"``.
    """

    matched: bool
    drug: DrugRead | None
    match_type: Literal["exact_generic", "exact_brand", "unmatched"]


async def normalize(session: AsyncSession, raw_name: str) -> NormalizeResult:
    """Resolve a raw drug name to a canonical Drug node.

    The name is trimmed and lowercased before comparison.  The Neo4j
    data is stored lowercase (applied in ``seed_ddinter.py``), so this
    comparison is always case-insensitive.

    Args:
        session: An open Neo4j async session.
        raw_name: The drug name as entered by the user or extracted by OCR.

    Returns:
        NormalizeResult with ``matched=True`` and the Drug if found,
        or ``matched=False`` and ``match_type="unmatched"`` if not found.

    Note:
        Never returns a false positive.  An unmatched result is an explicit
        ``match_type="unmatched"`` — never a silent empty-interactions result.
    """
    cleaned = raw_name.strip().lower()

    # ── Stage 1: exact generic name match ────────────────────────────────────
    result = await session.run(
        """
        MATCH (d:Drug)
        WHERE d.generic_name = $name
        RETURN d.drug_id          AS drug_id,
               d.generic_name     AS generic_name,
               d.drug_class       AS drug_class,
               d.atc_code         AS atc_code,
               d.default_form     AS default_form,
               d.external_source_id AS external_source_id
        LIMIT 1
        """,
        name=cleaned,
    )
    record = await result.single()
    if record:
        return NormalizeResult(
            matched=True,
            drug=DrugRead(**dict(record)),
            match_type="exact_generic",
        )

    # ── Stage 2: exact brand name match ─────────────────────────────────────
    result = await session.run(
        """
        MATCH (b:DrugBrandName)-[:BRAND_OF]->(d:Drug)
        WHERE b.brand_name = $name
        RETURN d.drug_id          AS drug_id,
               d.generic_name     AS generic_name,
               d.drug_class       AS drug_class,
               d.atc_code         AS atc_code,
               d.default_form     AS default_form,
               d.external_source_id AS external_source_id
        LIMIT 1
        """,
        name=cleaned,
    )
    record = await result.single()
    if record:
        return NormalizeResult(
            matched=True,
            drug=DrugRead(**dict(record)),
            match_type="exact_brand",
        )

    # ── Stage 3: unmatched ───────────────────────────────────────────────────
    # Extension point: Phase 05 will call llm_client.fuzzy_match_drug here
    # after pre-filtering candidates from Neo4j.  For now, return unmatched.
    return NormalizeResult(matched=False, drug=None, match_type="unmatched")


# ---------------------------------------------------------------------------
# Phase 05 extension point — do not implement here
# ---------------------------------------------------------------------------

async def _fuzzy_match(
    session: AsyncSession,
    raw_name: str,
) -> NormalizeResult:
    """Stub: fuzzy/LLM-assisted match (implemented in Phase 05).

    Phase 05 will:
    1. Run a substring/trigram pre-filter on Neo4j to retrieve a short
       candidate list (never send the full catalog to the LLM).
    2. Call ``llm_client.fuzzy_match_drug(raw_name, candidates)`` to rank
       candidates.
    3. Return the top candidate if confidence is sufficient, else unmatched.

    The LLM is never allowed to invent a drug name not in the catalog.
    """
    raise NotImplementedError("Fuzzy match is implemented in Phase 05")
