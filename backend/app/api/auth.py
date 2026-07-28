"""
Authentication & user management router.

Routes implemented in Phase 03:
- POST /auth/register
- POST /auth/login
- POST /auth/refresh
- POST /auth/otp/request
- POST /auth/otp/verify
- POST /auth/caregivers/link
- GET  /auth/caregivers
"""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])

# TODO: Phase 03 — implement registration, login, OTP, refresh, caregiver linking
