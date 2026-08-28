"""
Unit tests for ocr_match_service — Phase 05.

These are *unit* tests: Neo4j is replaced by an AsyncMock so the match
pipeline logic can be verified without a live database.  The LLM client
is always mocked — no Gemini API calls ever leave this test suite.

Test cases:
  1. Exact generic name match  → no LLM call, method="exact_generic"
  2. Brand name match          → no LLM call, method="exact_brand"
  3. Misspelled name           → LLM fuzzy stage triggered (Stage 2)
  4. Garbage text              → OcrMatchResult(matched_drug=None)
  5. LLM invents drug_id       → rejected (not in candidate list)
  6. Empty candidates          → OcrMatchResult(matched_drug=None)
  7. OCR noise stripping       → dosage tokens removed before matching
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.models.drug import DrugRead
from app.services.ocr_match_service import _clean_ocr_text, run_ocr_match

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WARFARIN = DrugRead(
    drug_id="D001",
    generic_name="warfarin",
    drug_class="anticoagulant",
    atc_code="B01AA03",
    default_form="tablet",
    external_source_id="DDI_001",
)

ASPIRIN = DrugRead(
    drug_id="D002",
    generic_name="aspirin",
    drug_class="nsaid",
    atc_code="B01AC06",
    default_form="tablet",
    external_source_id="DDI_002",
)


def _mock_norm_hit(drug: DrugRead, match_type: str = "exact_generic"):
    """Return a NormalizeResult-like mock that signals a match."""
    from app.services.drug_normalizer import NormalizeResult
    return NormalizeResult(matched=True, drug=drug, match_type=match_type)  # type: ignore[arg-type]


def _mock_norm_miss():
    """Return a NormalizeResult-like mock that signals no match."""
    from app.services.drug_normalizer import NormalizeResult
    return NormalizeResult(matched=False, drug=None, match_type="unmatched")


# ---------------------------------------------------------------------------
# 1. Exact generic name hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exact_generic_name_match():
    """Known generic name → Stage 1 hit, no LLM call."""
    mock_session = AsyncMock()

    with (
        patch("app.services.ocr_match_service.normalize", return_value=_mock_norm_hit(WARFARIN)) as mock_norm,
        patch("app.services.ocr_match_service.match_drug_name") as mock_llm,
    ):
        result = await run_ocr_match("warfarin", mock_session)

    mock_norm.assert_awaited_once()
    mock_llm.assert_not_called()  # LLM never reached

    assert result.matched_drug is not None
    assert result.matched_drug.drug_id == "D001"
    assert result.method == "exact_generic"
    assert result.confidence == 1.0


# ---------------------------------------------------------------------------
# 2. Brand name hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brand_name_match():
    """Brand name 'Coumadin' → Stage 1 brand hit, method='exact_brand'."""
    mock_session = AsyncMock()

    with (
        patch(
            "app.services.ocr_match_service.normalize",
            return_value=_mock_norm_hit(WARFARIN, match_type="exact_brand"),
        ),
        patch("app.services.ocr_match_service.match_drug_name") as mock_llm,
    ):
        result = await run_ocr_match("Coumadin", mock_session)

    mock_llm.assert_not_called()
    assert result.matched_drug is not None
    assert result.matched_drug.drug_id == "D001"
    assert result.method == "exact_brand"
    assert result.confidence == 0.90


# ---------------------------------------------------------------------------
# 3. Fuzzy match via LLM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fuzzy_match_via_llm():
    """Misspelling 'warfarinn' → Stage 1 miss → Stage 2 LLM match."""
    mock_session = AsyncMock()

    # Mock _fetch_candidates to return warfarin as a candidate
    warfarin_with_name = WARFARIN.model_copy(update={"matched_name": "warfarin"})

    with (
        patch("app.services.ocr_match_service.normalize", return_value=_mock_norm_miss()),
        patch(
            "app.services.ocr_match_service._fetch_candidates",
            return_value=[warfarin_with_name],
        ),
        patch(
            "app.services.ocr_match_service.match_drug_name",
            return_value="warfarin",
        ) as mock_llm,
    ):
        result = await run_ocr_match("warfarinn", mock_session)

    mock_llm.assert_called_once()
    assert result.matched_drug is not None
    assert result.matched_drug.drug_id == "D001"
    assert result.method == "fuzzy_llm"
    assert result.confidence == 0.75


# ---------------------------------------------------------------------------
# 4. No match — garbage text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_garbage_text_returns_no_match():
    """Garbage OCR text → no Stage 1 hit, LLM returns None → unmatched."""
    mock_session = AsyncMock()

    with (
        patch("app.services.ocr_match_service.normalize", return_value=_mock_norm_miss()),
        patch("app.services.ocr_match_service._fetch_candidates", return_value=[ASPIRIN]),
        patch("app.services.ocr_match_service.match_drug_name", return_value=None),
    ):
        result = await run_ocr_match("xqz123!!!", mock_session)

    assert result.matched_drug is None
    assert result.method == "fuzzy_llm"


# ---------------------------------------------------------------------------
# 5. LLM invents a drug_id not in the candidate list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_invented_name_is_rejected():
    """LLM returns a name not in the candidate list → rejected, no match."""
    mock_session = AsyncMock()

    warfarin_with_name = WARFARIN.model_copy(update={"matched_name": "warfarin"})

    with (
        patch("app.services.ocr_match_service.normalize", return_value=_mock_norm_miss()),
        patch(
            "app.services.ocr_match_service._fetch_candidates",
            return_value=[warfarin_with_name],
        ),
        # LLM returns a name that is NOT in the candidate list
        patch(
            "app.services.ocr_match_service.match_drug_name",
            return_value="invented_drug_xyz",
        ),
    ):
        result = await run_ocr_match("something", mock_session)

    # The service must reject the invented name
    assert result.matched_drug is None
    assert result.method == "none"


# ---------------------------------------------------------------------------
# 6. Empty candidate list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_candidates_returns_no_match():
    """When pre-filter returns no candidates, LLM is never called."""
    mock_session = AsyncMock()

    with (
        patch("app.services.ocr_match_service.normalize", return_value=_mock_norm_miss()),
        patch("app.services.ocr_match_service._fetch_candidates", return_value=[]),
        patch("app.services.ocr_match_service.match_drug_name") as mock_llm,
    ):
        result = await run_ocr_match("aspirine", mock_session)

    mock_llm.assert_not_called()
    assert result.matched_drug is None
    assert result.method == "none"


# ---------------------------------------------------------------------------
# 7. OCR noise stripping
# ---------------------------------------------------------------------------


def test_clean_ocr_text_strips_dosage():
    """Dosage tokens, numbers, and dates should be stripped."""
    raw = "Warfarin 5mg Tablet 01/12/2024 Lot 4831"
    cleaned = _clean_ocr_text(raw)
    assert "5mg" not in cleaned
    assert "01/12/2024" not in cleaned
    assert "4831" not in cleaned
    assert "Warfarin" in cleaned or "warfarin" in cleaned.lower()


def test_clean_ocr_text_truncates_to_60():
    """Output should be at most 60 characters."""
    raw = "A" * 200
    cleaned = _clean_ocr_text(raw)
    assert len(cleaned) <= 60
