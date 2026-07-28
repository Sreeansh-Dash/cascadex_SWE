"""
OCR scan router.

Routes implemented in Phase 05:
- POST /scans  (submit OCR text, returns drug candidates — does NOT add medication)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/scans", tags=["scans"])

# TODO: Phase 05 — implement OCR text intake, fuzzy match, ScanRecord creation
