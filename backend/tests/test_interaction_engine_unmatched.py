"""
Phase 06 — Interaction Engine: Invariant 1 ("Unmatched ≠ Safe") tests.

These tests assert that an unresolvable drug_id ALWAYS produces an explicit
UnmatchedDrugWarning and NEVER causes a silent is_clean=True response.

Coverage (5 tests):
1. Single bogus drug_id → exactly one warning present
2. Warning carries correct entry_id and drug_id_attempted values
3. is_clean is always False when any warning exists (even with no interactions)
4. Multiple unresolvable entries → one warning per entry
5. Valid drug + unresolvable entry → interactions still found AND warning present
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.services.interaction_engine import InteractionCheckResult, check_pairs


@pytest_asyncio.fixture
async def neo4j_session(neo4j_driver):
    """Yield a single async session for engine tests."""
    async with neo4j_driver.session() as session:
        yield session


# ---------------------------------------------------------------------------
# Test 1: Single bogus drug_id → exactly one warning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_unresolvable_entry_produces_one_warning(neo4j_session):
    """Invariant 1: a single bogus drug_id entry must produce exactly one warning.

    The engine receives the already-resolved drug_ids (valid) separately from
    unresolvable_entries.  The caller (medication_service) is responsible for
    detecting that a drug_id didn't exist and passing it as unresolvable.
    This test calls check_pairs directly in the same way the service will.
    """
    result: InteractionCheckResult = await check_pairs(
        neo4j_session,
        drug_ids=["D001"],  # only one valid drug: no pairs, no interactions
        unresolvable_entries=[("entry_xyz", "BOGUS_ID")],
    )

    assert len(result.unmatched_warnings) == 1, (
        f"Expected 1 warning, got {len(result.unmatched_warnings)}"
    )
    warning = result.unmatched_warnings[0]
    assert warning.drug_id_attempted == "BOGUS_ID"


# ---------------------------------------------------------------------------
# Test 2: Warning carries the correct identifiers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_warning_carries_correct_entry_id_and_drug_id(neo4j_session):
    """UnmatchedDrugWarning.entry_id and .drug_id_attempted must match inputs."""
    result = await check_pairs(
        neo4j_session,
        drug_ids=[],
        unresolvable_entries=[("entry_abc123", "NONEXISTENT_DRUG_999")],
    )

    assert len(result.unmatched_warnings) == 1
    w = result.unmatched_warnings[0]
    assert w.entry_id == "entry_abc123", (
        f"entry_id mismatch: expected 'entry_abc123', got '{w.entry_id}'"
    )
    assert w.drug_id_attempted == "NONEXISTENT_DRUG_999", (
        f"drug_id_attempted mismatch: got '{w.drug_id_attempted}'"
    )
    assert w.reason  # reason must be a non-empty string


# ---------------------------------------------------------------------------
# Test 3: is_clean is False when any warning exists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_clean_false_when_warning_exists_even_no_interactions(neo4j_session):
    """Invariant 1: is_clean must NEVER be True when warnings are present.

    Even if interactions=[] (only one valid drug, no pairs), an unresolvable
    entry must keep is_clean=False.  This is the core safety invariant.
    """
    result = await check_pairs(
        neo4j_session,
        drug_ids=["D003"],  # metformin alone: no interactions possible
        unresolvable_entries=[("entry_zzz", "GHOST_DRUG")],
    )

    assert result.interactions == [], "Expected no interactions for single drug"
    assert result.is_clean is False, (
        "is_clean must be False when unmatched_warnings is non-empty — "
        "even when interactions list is empty"
    )
    assert len(result.unmatched_warnings) == 1


# ---------------------------------------------------------------------------
# Test 4: Multiple unresolvable entries → one warning each
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_unresolvable_entries_produce_multiple_warnings(neo4j_session):
    """Each unresolvable entry must produce its own distinct warning."""
    unresolvable = [
        ("entry_111", "FAKE_DRUG_A"),
        ("entry_222", "FAKE_DRUG_B"),
        ("entry_333", "FAKE_DRUG_C"),
    ]
    result = await check_pairs(
        neo4j_session,
        drug_ids=[],
        unresolvable_entries=unresolvable,
    )

    assert len(result.unmatched_warnings) == 3, (
        f"Expected 3 warnings, got {len(result.unmatched_warnings)}"
    )
    warned_ids = {w.drug_id_attempted for w in result.unmatched_warnings}
    assert warned_ids == {"FAKE_DRUG_A", "FAKE_DRUG_B", "FAKE_DRUG_C"}
    assert result.is_clean is False


# ---------------------------------------------------------------------------
# Test 5: Mixed — valid interactions still returned alongside warnings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_interactions_returned_alongside_unmatched_warning(neo4j_session):
    """Warnings must not suppress real interactions.

    D001 (warfarin) + D002 (aspirin) → major interaction.
    An additional bogus entry must produce a warning without hiding the real pair.
    This guards against any short-circuit logic that drops results when warnings exist.
    """
    result = await check_pairs(
        neo4j_session,
        drug_ids=["D001", "D002"],   # known major interaction
        unresolvable_entries=[("entry_bad", "NOT_A_DRUG")],
    )

    # Interaction must still be found
    assert len(result.interactions) >= 1, (
        "Real interaction (warfarin+aspirin) must be returned even when "
        "an unmatched warning is also present"
    )
    assert result.interactions[0].severity == "major"

    # Warning must also be present
    assert len(result.unmatched_warnings) == 1
    assert result.unmatched_warnings[0].drug_id_attempted == "NOT_A_DRUG"

    # is_clean must be False (both conditions fail it)
    assert result.is_clean is False
