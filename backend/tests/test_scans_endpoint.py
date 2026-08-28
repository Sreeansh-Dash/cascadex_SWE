"""
Integration tests for the /scans endpoints — Phase 05.

Uses the real Neo4j database (same conftest.py as Phase 04 tests).
The LLM client is always mocked — no Gemini API calls leave this suite.

Test cases:
  1.  POST /scans requires authentication (401)
  2.  GET  /scans/{id} requires authentication (401)
  3.  POST /scans with empty body returns 422
  4.  POST /scans with a known generic drug name → 201 + primary_match populated
  5.  POST /scans with a brand name → 201 + match resolved to generic
  6.  POST /scans with unknown text → 201 + empty candidates (NOT 404)
  7.  GET  /scans/{id} returns stored ScanRecord with correct fields
  8.  POST /scans does NOT create a MedicationEntry (critical isolation invariant)
  9.  GET  /scans/{id} for another user's scan → 404 (cross-user scoping)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.services.drug_normalizer import NormalizeResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm_hit(drug, match_type="exact_generic"):
    return NormalizeResult(matched=True, drug=drug, match_type=match_type)


def _norm_miss():
    return NormalizeResult(matched=False, drug=None, match_type="unmatched")


# ---------------------------------------------------------------------------
# 1. Auth required — POST /scans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_scan_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/scans", json={"ocr_text": "warfarin"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Auth required — GET /scans/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_scan_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/scans/scan_fake")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. Empty body → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_scan_empty_body_rejected(client: AsyncClient, auth_factory):
    headers = await auth_factory()
    resp = await client.post("/api/v1/scans", json={}, headers=headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 4. Known generic name → 201 + primary_match populated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_scan_known_generic_returns_match(
    client: AsyncClient, auth_factory, seed_drug
):
    headers = await auth_factory()

    with patch(
        "app.services.ocr_match_service.normalize",
        return_value=_norm_hit(seed_drug),
    ):
        resp = await client.post(
            "/api/v1/scans",
            json={"ocr_text": seed_drug.generic_name},
            headers=headers,
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "matched"
    assert body["primary_match"] is not None
    assert body["primary_match"]["drug_id"] == seed_drug.drug_id
    assert len(body["candidates"]) >= 1
    assert body["scan_id"].startswith("scan_")


# ---------------------------------------------------------------------------
# 5. Brand name → resolved to generic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_scan_brand_name_resolves_to_generic(
    client: AsyncClient, auth_factory, seed_drug
):
    headers = await auth_factory()

    with patch(
        "app.services.ocr_match_service.normalize",
        return_value=_norm_hit(seed_drug, match_type="exact_brand"),
    ):
        resp = await client.post(
            "/api/v1/scans",
            json={"ocr_text": "Coumadin"},
            headers=headers,
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "matched"
    assert body["primary_match"]["drug_id"] == seed_drug.drug_id


# ---------------------------------------------------------------------------
# 6. Unknown text → 201 + empty candidates (NOT 404)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_scan_unknown_text_returns_unmatched(
    client: AsyncClient, auth_factory
):
    headers = await auth_factory()

    with (
        patch("app.services.ocr_match_service.normalize", return_value=_norm_miss()),
        patch("app.services.ocr_match_service._fetch_candidates", return_value=[]),
    ):
        resp = await client.post(
            "/api/v1/scans",
            json={"ocr_text": "xqzgarbage!!!"},
            headers=headers,
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "unmatched"
    assert body["primary_match"] is None
    assert body["candidates"] == []
    assert "scan_id" in body


# ---------------------------------------------------------------------------
# 7. GET /scans/{id} returns stored record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_scan_returns_record(client: AsyncClient, auth_factory):
    headers = await auth_factory()

    with (
        patch("app.services.ocr_match_service.normalize", return_value=_norm_miss()),
        patch("app.services.ocr_match_service._fetch_candidates", return_value=[]),
    ):
        post_resp = await client.post(
            "/api/v1/scans",
            json={"ocr_text": "test drug text"},
            headers=headers,
        )

    assert post_resp.status_code == 201
    scan_id = post_resp.json()["scan_id"]

    get_resp = await client.get(f"/api/v1/scans/{scan_id}", headers=headers)
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["scan_id"] == scan_id
    assert body["ocr_text"] == "test drug text"
    assert "created_at" in body


# ---------------------------------------------------------------------------
# 8. POST /scans does NOT create a MedicationEntry (isolation invariant)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_scan_does_not_create_medication_entry(
    client: AsyncClient, auth_factory, seed_drug
):
    """Critical: scanning alone must never auto-add a medication."""
    headers = await auth_factory()

    with patch(
        "app.services.ocr_match_service.normalize",
        return_value=_norm_hit(seed_drug),
    ):
        await client.post(
            "/api/v1/scans",
            json={"ocr_text": seed_drug.generic_name},
            headers=headers,
        )

    meds_resp = await client.get("/api/v1/medications", headers=headers)
    assert meds_resp.status_code == 200
    # GET /medications returns a JSON array directly, not a dict with a "medications" key.
    assert isinstance(meds_resp.json(), list)
    assert meds_resp.json() == []


# ---------------------------------------------------------------------------
# 9. Cannot access another user's scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cannot_access_other_users_scan(client: AsyncClient, auth_factory):
    headers_a = await auth_factory(suffix="_scan_a")
    headers_b = await auth_factory(suffix="_scan_b")

    with (
        patch("app.services.ocr_match_service.normalize", return_value=_norm_miss()),
        patch("app.services.ocr_match_service._fetch_candidates", return_value=[]),
    ):
        post_resp = await client.post(
            "/api/v1/scans",
            json={"ocr_text": "some text"},
            headers=headers_a,
        )

    scan_id = post_resp.json()["scan_id"]

    # User B tries to fetch user A's scan → 404
    get_resp = await client.get(f"/api/v1/scans/{scan_id}", headers=headers_b)
    assert get_resp.status_code == 404
