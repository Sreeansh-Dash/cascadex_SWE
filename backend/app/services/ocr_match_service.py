"""
CascadeX OCR Match Service — Phase 05.

Two-stage drug name resolution pipeline:

  Stage 1 — Exact / brand match (``drug_normalizer.normalize``):
    Case-insensitive exact match on generic names and brand names.
    Zero LLM cost.  Returns immediately on hit.

  Stage 2 — LLM fuzzy match (``llm_client.match_drug_name``):
    Only reached when Stage 1 misses.
    Fetches the top-K candidates from Neo4j using a substring pre-filter,
    then passes the *name strings only* to the LLM.
    The LLM receives no drug_id and cannot invent one.

Safety invariants:
- LLM is given a candidate list that is a strict subset of the Neo4j catalog.
- Any LLM response that is not in that list is silently rejected.
- Unmatched → OcrMatchResult(matched_drug=None, method="none").  Never silent.
"""

from __future__ import annotations

import logging
import re

from neo4j import AsyncSession

from app.core.config import settings
from app.ml.llm_client import match_drug_name
from app.models.drug import DrugRead
from app.models.scan import MatchMethod, OcrMatchResult
from app.services.drug_normalizer import normalize

logger = logging.getLogger(__name__)


async def run_ocr_match(ocr_text: str, session: AsyncSession) -> OcrMatchResult:
    """Run the two-stage OCR match pipeline.

    Args:
        ocr_text: Raw OCR output from ML Kit (may be noisy / multi-line).
        session:  Open Neo4j async session.

    Returns:
        ``OcrMatchResult`` with ``matched_drug`` populated on success,
        or ``matched_drug=None`` when no confident match is found.
    """
    clean = _clean_ocr_text(ocr_text)
    logger.info("ocr_match: cleaned='%s' (raw_len=%d)", clean, len(ocr_text))

    # ── Stage 1: exact / brand match ────────────────────────────────────────
    norm = await normalize(session, clean)
    if norm.matched and norm.drug is not None:
        method: MatchMethod = (
            "exact_brand" if norm.match_type == "exact_brand" else "exact_generic"
        )
        confidence = 1.0 if norm.match_type == "exact_generic" else 0.90
        drug = norm.drug.model_copy(update={"matched_name": clean})
        logger.info("ocr_match: Stage 1 hit — drug_id='%s' method='%s'", drug.drug_id, method)
        return OcrMatchResult(
            matched_drug=drug,
            matched_name=clean,
            confidence=confidence,
            method=method,
        )

    # ── Stage 2: LLM fuzzy match ────────────────────────────────────────────
    candidates = await _fetch_candidates(clean, session)
    if not candidates:
        logger.info("ocr_match: no candidates found for '%s'", clean)
        return OcrMatchResult(method="none")

    # Build name list and reverse lookup dict for the LLM
    name_list: list[str] = []
    name_to_drug: dict[str, DrugRead] = {}
    for drug in candidates:
        # Include both generic name and matched_name (brand) if different
        for name in {drug.generic_name, drug.matched_name} - {None}:
            name_list.append(name)  # type: ignore[arg-type]
            name_to_drug[name.lower()] = drug  # type: ignore[union-attr]

    best_name = match_drug_name(clean, name_list)
    if best_name is None:
        logger.info("ocr_match: Stage 2 — no match for '%s'", clean)
        return OcrMatchResult(method="fuzzy_llm")

    matched_drug = name_to_drug.get(best_name.lower())
    if matched_drug is None:
        # Defensive: shouldn't happen, but log and return unmatched
        logger.warning("ocr_match: LLM name '%s' not in name_to_drug — rejected", best_name)
        return OcrMatchResult(method="none")

    matched_drug = matched_drug.model_copy(update={"matched_name": best_name})
    logger.info(
        "ocr_match: Stage 2 hit — '%s' → drug_id='%s'", best_name, matched_drug.drug_id
    )
    return OcrMatchResult(
        matched_drug=matched_drug,
        matched_name=best_name,
        confidence=0.75,
        method="fuzzy_llm",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean_ocr_text(raw: str) -> str:
    """Strip noise from OCR output to extract the most likely drug name token.

    OCR from pill bottles often contains dosage, dates, patient names, and
    lot numbers mixed with the drug name.  We strip common patterns and take
    the first meaningful token sequence (≤ 60 chars).
    """
    text = " ".join(raw.split())
    # Remove dosage patterns: "5mg", "100 mg", "2.5 mL", "500mcg"
    text = re.sub(r"\b\d+(\.\d+)?\s*(mg|mcg|ml|g|iu|units?)\b", "", text, flags=re.IGNORECASE)
    # Remove dates: "01/12/2024", "12-Jan-2024"
    text = re.sub(
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}[/-][A-Za-z]{3}[/-]\d{2,4}\b",
        "",
        text,
    )
    # Remove lone numbers
    text = re.sub(r"\b\d+\b", "", text)
    return text.strip()[:60].strip()


async def _fetch_candidates(query: str, session: AsyncSession) -> list[DrugRead]:
    """Fetch top-K candidate drugs from Neo4j using a substring pre-filter.

    Searches both generic names and brand names.  Returns at most
    ``settings.ocr_match_top_k`` results, each with ``matched_name`` set
    to the name that triggered the match.
    """
    tokens = query.split()
    if not tokens or len(tokens[0]) < 3:
        return []
    search_term = tokens[0]  # use first meaningful token as search key

    result = await session.run(
        """
        // Generic name search
        MATCH (d:Drug)
        WHERE toLower(d.generic_name) CONTAINS toLower($q)
        RETURN d.drug_id            AS drug_id,
               d.generic_name       AS generic_name,
               d.drug_class         AS drug_class,
               d.atc_code           AS atc_code,
               d.default_form       AS default_form,
               d.external_source_id AS external_source_id,
               d.generic_name       AS matched_name
        UNION
        // Brand name search
        MATCH (bn:DrugBrandName)-[:BRAND_OF]->(d:Drug)
        WHERE toLower(bn.brand_name) CONTAINS toLower($q)
        RETURN d.drug_id            AS drug_id,
               d.generic_name       AS generic_name,
               d.drug_class         AS drug_class,
               d.atc_code           AS atc_code,
               d.default_form       AS default_form,
               d.external_source_id AS external_source_id,
               bn.brand_name        AS matched_name
        LIMIT $limit
        """,
        q=search_term,
        limit=settings.ocr_match_top_k,
    )
    rows = await result.data()
    return [
        DrugRead(
            drug_id=row["drug_id"],
            generic_name=row["generic_name"],
            drug_class=row.get("drug_class") or "",
            atc_code=row.get("atc_code") or "",
            default_form=row.get("default_form") or "",
            external_source_id=row.get("external_source_id") or "",
            matched_name=row.get("matched_name"),
        )
        for row in rows
    ]
