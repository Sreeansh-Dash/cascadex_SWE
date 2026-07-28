"""
Medications router.

Routes implemented in Phase 04:
- GET  /drugs/search
- POST /medications
- GET  /medications
- PATCH /medications/{entry_id}
- POST /medications/{entry_id}/doses
- GET  /medications/{entry_id}/doses
"""

from fastapi import APIRouter

router = APIRouter(prefix="/medications", tags=["medications"])

# TODO: Phase 04 — implement medication CRUD, catalog search, dose logging
