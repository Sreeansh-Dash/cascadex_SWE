"""
Phase 08 — test_history_export.py

Tests for `GET /api/v1/history/export` endpoint:
- Auth required (401 if missing token)
- Returns 200 with `application/pdf` content-type
- PDF content begins with `%PDF-`
- PDF is parseable with `pypdf`
- PDF contains expected medication names, patient name, and DDInter attribution
"""

import io

import pytest
from httpx import AsyncClient
from pypdf import PdfReader

from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_export_pdf_requires_auth(client: AsyncClient):
    """GET /api/v1/history/export without auth returns 401."""
    res = await client.get("/api/v1/history/export")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_export_pdf_returns_valid_pdf(client: AsyncClient):
    """GET /api/v1/history/export returns valid PDF stream."""
    headers = await register_and_login(client)

    # Add medication
    await client.post(
        "/api/v1/medications",
        headers=headers,
        json={
            "drug_id": "D001",
            "dosage_amount": 5.0,
            "dosage_unit": "mg",
            "schedules": [{"time_of_day": "09:00", "days_of_week": []}],
        },
    )

    res = await client.get("/api/v1/history/export", headers=headers)
    assert res.status_code == 200
    assert "application/pdf" in res.headers["content-type"]
    assert "attachment" in res.headers.get("content-disposition", "")

    # Validate PDF magic bytes
    pdf_bytes = res.content
    assert pdf_bytes.startswith(b"%PDF-")

    # Parse with pypdf
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1

    # Extract text from all pages
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"

    # Check key text elements
    assert "CascadeX" in full_text
    assert "Medication Summary" in full_text
    assert "Warfarin" in full_text or "warfarin" in full_text
    assert "DDInter" in full_text or "RxNorm" in full_text
    assert "pharmacist" in full_text.lower() or "doctor" in full_text.lower()
