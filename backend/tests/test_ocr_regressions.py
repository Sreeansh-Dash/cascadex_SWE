"""Regression coverage for noisy labels and multi-medicine scans."""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.drug import DrugRead
from app.services.drug_normalizer import NormalizeResult
from app.services.ocr_match_service import run_ocr_match


def _drug(drug_id: str, name: str) -> DrugRead:
    return DrugRead(
        drug_id=drug_id, generic_name=name, drug_class="",
        atc_code="", default_form="tablet", external_source_id="",
        matched_name=name,
    )


@pytest.mark.asyncio
async def test_noisy_label_resolves_the_medicine_name():
    aspirin = _drug("D002", "aspirin")
    with (
        patch(
            "app.services.ocr_match_service.normalize",
            return_value=NormalizeResult(False, None, "unmatched"),
        ),
        patch("app.services.ocr_match_service._fetch_candidates", return_value=[aspirin]),
    ):
        result = await run_ocr_match(
            "sreeansh dash 2026/10/10 aspirin dolo 500mg", AsyncMock()
        )
    assert result.matched_drug == aspirin
    assert result.matched_name == "aspirin"


@pytest.mark.asyncio
async def test_multiple_medicines_require_a_single_medicine_photo():
    aspirin = _drug("D002", "aspirin")
    warfarin = _drug("D001", "warfarin")
    with (
        patch(
            "app.services.ocr_match_service.normalize",
            return_value=NormalizeResult(False, None, "unmatched"),
        ),
        patch(
            "app.services.ocr_match_service._fetch_candidates",
            return_value=[aspirin, warfarin],
        ),
    ):
        result = await run_ocr_match("aspirin and warfarin", AsyncMock())
    assert result.method == "ambiguous"
    assert result.matched_drug is None
    assert {drug.generic_name for drug in result.candidates} == {"aspirin", "warfarin"}
