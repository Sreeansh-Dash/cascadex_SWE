"""
Phase 06 interaction engine core tests.

Tests the check_pairs() function directly against the real Neo4j database.
Parametrized over known_pairs_fixture.csv — each row asserts exact severity
and that the mechanism text contains the expected keyword.

Coverage:
- All 8 known fixture pairs (exact severity assertion)
- False-positive check: non-interacting pair returns no result
- 3-drug combinatorics: warfarin + aspirin + amiodarone → both INT001 + INT002
- is_clean flag semantics
- Result ordering (major before moderate before minor)
- normalize_severity unit tests (no DB needed)
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

from app.services.interaction_engine import (
    InteractionCheckResult,
    check_pairs,
    normalize_severity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "data" / "fixtures"
KNOWN_PAIRS_CSV = FIXTURES_DIR / "known_pairs_fixture.csv"


def load_known_pairs() -> list[dict]:
    """Load known_pairs_fixture.csv as list of dicts."""
    rows = []
    with open(KNOWN_PAIRS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# normalize_severity unit tests (pure, no DB required)
# ---------------------------------------------------------------------------

class TestNormalizeSeverity:
    """Unit tests for the severity normaliser — no Neo4j required."""

    def test_lowercase_minor(self):
        assert normalize_severity("minor") == "minor"

    def test_lowercase_moderate(self):
        assert normalize_severity("moderate") == "moderate"

    def test_lowercase_major(self):
        assert normalize_severity("major") == "major"

    def test_title_case_minor(self):
        assert normalize_severity("Minor") == "minor"

    def test_title_case_moderate(self):
        assert normalize_severity("Moderate") == "moderate"

    def test_title_case_major(self):
        assert normalize_severity("Major") == "major"

    def test_uppercase(self):
        assert normalize_severity("MAJOR") == "major"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown severity"):
            normalize_severity("severe")


# ---------------------------------------------------------------------------
# Integration fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def neo4j_session(neo4j_driver):
    """Yield a single async session for engine tests."""
    async with neo4j_driver.session() as session:
        yield session


# ---------------------------------------------------------------------------
# Parametrized known-pairs tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("row", load_known_pairs(), ids=[r["drug_a"] + "+" + r["drug_b"] for r in load_known_pairs()])
@pytest.mark.asyncio
async def test_known_pair_exact_severity(neo4j_session, row):
    """Every row in known_pairs_fixture.csv must produce the exact expected severity.

    This test is the canonical correctness gate for the interaction engine.
    A failure here means either the fixture data is wrong or the engine has
    a severity normalisation bug.
    """
    drug_a_id = row["drug_a_id"]
    drug_b_id = row["drug_b_id"]
    expected_severity = row["expected_severity"]
    expected_keyword = row["expected_mechanism_contains"].lower()

    result: InteractionCheckResult = await check_pairs(
        neo4j_session, drug_ids=[drug_a_id, drug_b_id]
    )

    assert len(result.interactions) == 1, (
        f"Expected 1 interaction for ({row['drug_a']}, {row['drug_b']}), "
        f"got {len(result.interactions)}"
    )
    interaction = result.interactions[0]
    assert interaction.severity == expected_severity, (
        f"Expected severity '{expected_severity}' for "
        f"({row['drug_a']}, {row['drug_b']}), got '{interaction.severity}'"
    )
    assert expected_keyword in interaction.mechanism.lower(), (
        f"Expected mechanism to contain '{expected_keyword}' for "
        f"({row['drug_a']}, {row['drug_b']}), got: {interaction.mechanism!r}"
    )
    assert result.unmatched_warnings == []
    assert result.is_clean is False


# ---------------------------------------------------------------------------
# False-positive check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_interacting_pair_returns_empty(neo4j_session):
    """A pair with no INTERACTS_WITH edge must return an empty interactions list.

    Asserts no false positives: the engine only returns real edges.
    D001 (warfarin) and D003 (metformin) have no interaction in the fixture.
    """
    result = await check_pairs(neo4j_session, drug_ids=["D001", "D003"])

    assert result.interactions == [], (
        "warfarin + metformin should produce NO interaction; "
        f"got: {result.interactions}"
    )
    assert result.unmatched_warnings == []
    assert result.is_clean is True


# ---------------------------------------------------------------------------
# 3-drug combinatorics test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_three_drug_combinatorics_warfarin_aspirin_amiodarone(neo4j_session):
    """3-drug list (warfarin + aspirin + amiodarone) must return BOTH interactions.

    warfarin+aspirin  → INT001 (major)
    warfarin+amiodarone → INT002 (major)
    aspirin+amiodarone  → no interaction in fixture

    This guards against the engine returning only the first pair it finds.
    """
    result = await check_pairs(
        neo4j_session, drug_ids=["D001", "D002", "D006"]
    )

    # Must have exactly 2 interactions (the 3rd pair has no edge)
    assert len(result.interactions) == 2, (
        f"Expected 2 interactions for (warfarin, aspirin, amiodarone), "
        f"got {len(result.interactions)}: {result.interactions}"
    )

    severities = {i.severity for i in result.interactions}
    assert severities == {"major"}, (
        f"Expected both interactions to be 'major', got {severities}"
    )

    # Both drug pair orderings must be represented
    pairs_found = {
        (i.drug_a_id, i.drug_b_id) for i in result.interactions
    }
    # At least one pair must involve D001+D002 and one D001+D006 (order may vary)
    drug_ids_in_pairs = {did for pair in pairs_found for did in pair}
    assert "D001" in drug_ids_in_pairs
    assert "D002" in drug_ids_in_pairs
    assert "D006" in drug_ids_in_pairs

    assert result.is_clean is False


# ---------------------------------------------------------------------------
# is_clean semantics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_clean_true_for_no_interactions_no_warnings(neo4j_session):
    """is_clean must be True only when both lists are empty."""
    # D003 (metformin) alone — no pairs to check
    result = await check_pairs(neo4j_session, drug_ids=["D003"])
    assert result.is_clean is True
    assert result.interactions == []
    assert result.unmatched_warnings == []


@pytest.mark.asyncio
async def test_is_clean_false_when_interaction_present(neo4j_session):
    """is_clean must be False whenever at least one interaction is found."""
    result = await check_pairs(neo4j_session, drug_ids=["D001", "D002"])
    assert result.is_clean is False


# ---------------------------------------------------------------------------
# Ordering test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_results_ordered_major_first(neo4j_session):
    """Major interactions must appear before moderate and minor in the result list."""
    # D001 (warfarin), D009 (omeprazole) → minor (INT013)
    # D001 (warfarin), D002 (aspirin)    → major (INT001)
    result = await check_pairs(
        neo4j_session, drug_ids=["D001", "D002", "D009"]
    )

    assert len(result.interactions) >= 2
    # First interaction must be major
    assert result.interactions[0].severity == "major", (
        f"Expected first result to be 'major', got '{result.interactions[0].severity}'"
    )
    # Last should be minor (if only major + minor)
    severities = [i.severity for i in result.interactions]
    assert severities == sorted(severities, key=lambda s: {"major": 0, "moderate": 1, "minor": 2}[s])


# ---------------------------------------------------------------------------
# plain_language stub test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_plain_language_falls_back_to_mechanism_in_stub_mode(neo4j_session):
    """In stub mode (no GEMINI_API_KEY), plain_language must equal mechanism."""
    # GEMINI_API_KEY is empty in test env — stub mode active
    result = await check_pairs(neo4j_session, drug_ids=["D001", "D002"])
    interaction = result.interactions[0]
    # In stub mode: plain_language_rewrite returns mechanism unchanged
    assert interaction.plain_language == interaction.mechanism
