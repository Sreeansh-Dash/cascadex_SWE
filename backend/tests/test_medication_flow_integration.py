"""
Phase 06 — Medication flow integration tests.

Tests the full HTTP path:  POST /medications → interaction check embedded in response.
These are end-to-end tests against the real FastAPI app with real Neo4j.

Coverage (6 tests):
1. warfarin + aspirin (2nd add) → response contains major interaction
2. Non-interacting pair (metformin + lisinopril = minor) → correct severity
3. Truly non-interacting pair (warfarin + metformin) → empty interactions list
4. PATCH /medications also triggers interaction check
5. First medication (only 1 drug) → interaction_check present but empty
6. Deactivation (PATCH deactivate=true) → no interaction_check (None)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MED_BASE = {
    "dosage_amount": 5.0,
    "dosage_unit": "mg",
    "schedules": [{"time_of_day": "08:00", "days_of_week": []}],
}


async def add_med(client: AsyncClient, headers: dict, drug_id: str) -> dict:
    """POST /medications for a given drug_id and return the JSON response."""
    resp = await client.post(
        "/api/v1/medications",
        json={**MED_BASE, "drug_id": drug_id},
        headers=headers,
    )
    assert resp.status_code == 201, f"add_med failed [{resp.status_code}]: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Test 1: warfarin + aspirin → major interaction in response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_aspirin_after_warfarin_returns_major_interaction(client):
    """Adding aspirin when warfarin is already active must trigger a major interaction.

    This is the canonical end-to-end safety test for Phase 06.
    The POST /medications response must contain interaction_check with severity 'major'.
    """
    headers = await register_and_login(client, suffix="_p06_test1")

    # Add warfarin first (only 1 drug — no pairs yet)
    resp1 = await add_med(client, headers, "D001")
    check1 = resp1.get("interaction_check")
    assert check1 is not None, "interaction_check must be present even for 1st drug"
    assert check1["interactions"] == [], "1st drug alone must have no interactions"
    assert check1["is_clean"] is True, "1 drug → is_clean must be True"

    # Add aspirin (now warfarin + aspirin → major)
    resp2 = await add_med(client, headers, "D002")
    check2 = resp2.get("interaction_check")
    assert check2 is not None, "interaction_check must be present on 2nd add"
    assert len(check2["interactions"]) >= 1, (
        f"Expected ≥1 interaction after adding aspirin to warfarin; "
        f"interaction_check: {check2}"
    )

    # Find the warfarin+aspirin interaction
    interactions = check2["interactions"]
    pair_ids = {frozenset([i["drug_a_id"], i["drug_b_id"]]) for i in interactions}
    assert frozenset(["D001", "D002"]) in pair_ids, (
        f"warfarin+aspirin pair not found in: {interactions}"
    )

    # Verify severity
    war_asp = next(
        i for i in interactions
        if frozenset([i["drug_a_id"], i["drug_b_id"]]) == frozenset(["D001", "D002"])
    )
    assert war_asp["severity"] == "major", (
        f"Expected 'major', got '{war_asp['severity']}'"
    )
    assert check2["is_clean"] is False


# ---------------------------------------------------------------------------
# Test 2: metformin + lisinopril → minor interaction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_lisinopril_after_metformin_returns_minor_interaction(client):
    """metformin + lisinopril must produce a minor interaction (INT014 in fixture)."""
    headers = await register_and_login(client, suffix="_p06_test2")

    await add_med(client, headers, "D003")  # metformin
    resp = await add_med(client, headers, "D004")  # lisinopril

    check = resp.get("interaction_check")
    assert check is not None
    assert len(check["interactions"]) >= 1

    interactions = check["interactions"]
    met_lis = next(
        (i for i in interactions
         if frozenset([i["drug_a_id"], i["drug_b_id"]]) == frozenset(["D003", "D004"])),
        None,
    )
    assert met_lis is not None, (
        f"metformin+lisinopril pair not found; interactions: {interactions}"
    )
    assert met_lis["severity"] == "minor"
    assert "hypoglycemia" in met_lis["mechanism"].lower()


# ---------------------------------------------------------------------------
# Test 3: truly non-interacting pair → empty interactions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_interacting_pair_returns_empty_interactions(client):
    """warfarin + metformin have no interaction in the DDInter fixture.

    The response must have interactions==[] and is_clean=True.
    This guards against false positives.
    """
    headers = await register_and_login(client, suffix="_p06_test3")

    await add_med(client, headers, "D001")   # warfarin
    resp = await add_med(client, headers, "D003")  # metformin (no interaction with warfarin)

    check = resp.get("interaction_check")
    assert check is not None
    # warfarin + metformin: no DDInter edge
    assert check["interactions"] == [], (
        f"Expected no interaction for warfarin+metformin; got: {check['interactions']}"
    )
    assert check["unmatched_warnings"] == []
    assert check["is_clean"] is True


# ---------------------------------------------------------------------------
# Test 4: PATCH also triggers interaction check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_medication_triggers_interaction_check(client):
    """PATCH /medications/{id} (notes update) must also return interaction_check."""
    headers = await register_and_login(client, suffix="_p06_test4")

    r1 = await add_med(client, headers, "D001")  # warfarin
    await add_med(client, headers, "D002")        # aspirin (triggers major in add response)

    entry_id = r1["entry_id"]

    # Patch warfarin's notes (non-deactivation edit)
    patch_resp = await client.patch(
        f"/api/v1/medications/{entry_id}",
        json={"notes": "Updated note"},
        headers=headers,
    )
    assert patch_resp.status_code == 200, (
        f"PATCH failed [{patch_resp.status_code}]: {patch_resp.text}"
    )

    check = patch_resp.json().get("interaction_check")
    assert check is not None, "PATCH response must include interaction_check"
    # warfarin + aspirin still active → major interaction
    assert any(i["severity"] == "major" for i in check["interactions"]), (
        f"Expected major interaction in PATCH response; got: {check}"
    )


# ---------------------------------------------------------------------------
# Test 5: Deactivation → interaction_check is None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deactivation_returns_none_interaction_check(client):
    """PATCH with deactivate=True must NOT run a check (interaction_check is None)."""
    headers = await register_and_login(client, suffix="_p06_test5")

    r1 = await add_med(client, headers, "D001")
    entry_id = r1["entry_id"]

    deact_resp = await client.patch(
        f"/api/v1/medications/{entry_id}",
        json={"deactivate": True},
        headers=headers,
    )
    assert deact_resp.status_code == 200, (
        f"Deactivate PATCH failed [{deact_resp.status_code}]: {deact_resp.text}"
    )

    check = deact_resp.json().get("interaction_check")
    assert check is None, (
        "Deactivation response must have interaction_check=None "
        "(no check needed when removing a drug)"
    )


# ---------------------------------------------------------------------------
# Test 6: interaction_check response shape is complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interaction_check_response_shape(client):
    """Verify the exact shape of interaction_check in the POST response.

    Checks that all required fields (checked_drug_ids, interactions,
    unmatched_warnings, is_clean) are present and correctly typed.
    """
    headers = await register_and_login(client, suffix="_p06_test6")

    await add_med(client, headers, "D001")   # warfarin
    resp = await add_med(client, headers, "D002")  # aspirin

    check = resp["interaction_check"]
    assert isinstance(check["checked_drug_ids"], list)
    assert isinstance(check["interactions"], list)
    assert isinstance(check["unmatched_warnings"], list)
    assert isinstance(check["is_clean"], bool)

    # Interaction fields
    if check["interactions"]:
        ix = check["interactions"][0]
        required_fields = [
            "drug_a_id", "drug_b_id", "drug_a_name", "drug_b_name",
            "severity", "mechanism", "plain_language", "management_advice", "source",
        ]
        for field in required_fields:
            assert field in ix, f"Field '{field}' missing from interaction: {ix}"
        assert ix["severity"] in ("minor", "moderate", "major")
