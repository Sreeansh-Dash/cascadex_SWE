"""
Tests for backend/app/services/drug_normalizer.py.

These tests require a live Neo4j instance loaded with the fixture dataset.
Run the import job first:

    python -m data.seed_ddinter \\
        --source backend/data/fixtures \\
        --version pytest-normalizer-v1

Then run:
    cd backend
    pytest tests/test_drug_normalizer.py -v

Safety contract tested here:
- A known generic name always returns match_type == "exact_generic".
- A known brand name always returns match_type == "exact_brand" and
  resolves to the correct generic Drug.
- An unrecognised name ALWAYS returns matched=False, match_type="unmatched".
  This is the core safety invariant: the normalizer must never return a
  false positive — an unmatched drug must be surfaced as unmatched, never
  silently treated as "no interactions".
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

pytestmark = pytest.mark.asyncio

FIXTURE_VERSION = "pytest-normalizer-v1"


@pytest_asyncio.fixture(scope="module")
async def seeded_session():
    """Seed the fixture data and provide a session for all tests in this module."""
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
    # Seed the fixture dataset before tests run
    from pathlib import Path

    from data.seed_ddinter import run_import

    fixtures = Path(__file__).parent.parent / "data" / "fixtures"
    await run_import(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
        source_dir=fixtures,
        version=FIXTURE_VERSION,
        dry_run=False,
    )

    try:
        async with driver.session() as session:
            yield session
    finally:
        await driver.close()


# ── Generic name matching ──────────────────────────────────────────────────

async def test_known_generic_name_matches(seeded_session):
    """'warfarin' (generic) resolves to the warfarin Drug with match_type=exact_generic."""
    from app.services.drug_normalizer import normalize

    result = await normalize(seeded_session, "warfarin")

    assert result.matched is True
    assert result.match_type == "exact_generic"
    assert result.drug is not None
    assert result.drug.generic_name == "warfarin"
    assert result.drug.drug_id == "D001"


async def test_generic_name_case_insensitive(seeded_session):
    """Generic name match is case-insensitive: 'WARFARIN' == 'warfarin'."""
    from app.services.drug_normalizer import normalize

    result = await normalize(seeded_session, "WARFARIN")

    assert result.matched is True
    assert result.match_type == "exact_generic"
    assert result.drug.drug_id == "D001"


async def test_generic_name_whitespace_trimmed(seeded_session):
    """Leading/trailing whitespace is stripped before matching."""
    from app.services.drug_normalizer import normalize

    result = await normalize(seeded_session, "  metformin  ")

    assert result.matched is True
    assert result.drug.drug_id == "D003"


# ── Brand name matching ────────────────────────────────────────────────────

async def test_known_brand_name_matches(seeded_session):
    """'Coumadin' (brand) resolves to the warfarin Drug with match_type=exact_brand."""
    from app.services.drug_normalizer import normalize

    result = await normalize(seeded_session, "Coumadin")

    assert result.matched is True
    assert result.match_type == "exact_brand"
    assert result.drug is not None
    assert result.drug.drug_id == "D001"  # warfarin
    assert result.drug.generic_name == "warfarin"


async def test_brand_name_case_insensitive(seeded_session):
    """Brand name match is case-insensitive: 'LIPITOR' == 'Lipitor'."""
    from app.services.drug_normalizer import normalize

    result = await normalize(seeded_session, "LIPITOR")

    assert result.matched is True
    assert result.match_type == "exact_brand"
    assert result.drug.drug_id == "D005"  # atorvastatin


# ── Unmatched — SAFETY INVARIANT ──────────────────────────────────────────

async def test_unknown_name_returns_unmatched(seeded_session):
    """
    SAFETY INVARIANT: an unrecognised drug name MUST return matched=False
    and match_type='unmatched'.

    This must never return a false positive — treating an unknown drug as
    "matched with no interactions" would be a patient-safety error.
    """
    from app.services.drug_normalizer import normalize

    result = await normalize(seeded_session, "xyzdrug_totally_fake_12345")

    assert result.matched is False
    assert result.match_type == "unmatched"
    assert result.drug is None


async def test_empty_string_returns_unmatched(seeded_session):
    """An empty string must return unmatched, not crash."""
    from app.services.drug_normalizer import normalize

    result = await normalize(seeded_session, "")

    assert result.matched is False
    assert result.match_type == "unmatched"


async def test_partial_name_returns_unmatched(seeded_session):
    """A partial name ('warf') must not match — exact match only in Phase 02."""
    from app.services.drug_normalizer import normalize

    result = await normalize(seeded_session, "warf")

    assert result.matched is False
    assert result.match_type == "unmatched"
