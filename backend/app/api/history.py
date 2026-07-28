"""
History router.

Routes implemented in Phase 08:
- GET /history  (dose timeline, alert history)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/history", tags=["history"])

# TODO: Phase 08 — implement history timeline, PDF export
