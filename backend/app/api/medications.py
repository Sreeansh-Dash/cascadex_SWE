"""
Medications router — Phase 04.

Endpoints:
    GET  /drugs/search                       — Catalog search (generic + brand)
    POST /medications                        — Add medication for authenticated user
    GET  /medications                        — List active (+ optionally inactive) medications
    PATCH /medications/{entry_id}            — Edit or deactivate a medication
    POST /medications/{entry_id}/doses       — Log a dose intake event
    GET  /medications/{entry_id}/doses       — List dose logs for an entry

Auth:
    All endpoints require a valid Bearer JWT (get_current_user).
    Write endpoints (POST, PATCH) require manage-level RBAC via require_permission.
    Read endpoints (GET) are accessible to view_only caregivers.

Ownership:
    All service calls receive the resolved user_id — never a client-supplied body field.
    Caregivers acting on behalf of a user pass X-Caregiver-Target-User header;
    get_current_user resolves auth_context["user_id"] accordingly.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from neo4j import AsyncSession

from app.core.dependencies import get_current_user, require_permission
from app.db.neo4j_session import get_session
from app.models.caregiver import PermissionLevel
from app.models.medication import (
    DoseLogCreate,
    DoseLogRead,
    MedicationCreate,
    MedicationRead,
    MedicationUpdate,
)
from app.services import medication_service

router = APIRouter(tags=["medications"])


# ---------------------------------------------------------------------------
# Drug catalog search
# ---------------------------------------------------------------------------

@router.get(
    "/drugs/search",
    summary="Search the drug catalog",
    description=(
        "Case-insensitive prefix/contains search over Drug.generic_name and "
        "DrugBrandName.brand_name.  Returns matching Drug nodes with an extra "
        "`matched_name` field showing which name triggered the match."
    ),
)
async def search_drugs(
    q: str = Query(..., min_length=1, description="Search query (partial name)"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth_context: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await medication_service.search_drugs(session, q=q, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Medication CRUD
# ---------------------------------------------------------------------------

@router.post(
    "/medications",
    status_code=201,
    summary="Add a medication",
    description="Create a new MedicationEntry for the authenticated user (or manage-caregiver target).",
)
async def add_medication(
    payload: MedicationCreate,
    auth_context: Annotated[dict, Depends(require_permission(PermissionLevel.MANAGE))],
    session: AsyncSession = Depends(get_session),
) -> MedicationRead:
    user_id: str = auth_context["user_id"]
    return await medication_service.add_medication(session, user_id=user_id, payload=payload)


@router.get(
    "/medications",
    summary="List medications",
    description="List active medications (default) or all including inactive with ?include_inactive=true.",
)
async def list_medications(
    include_inactive: bool = Query(default=False, description="Include deactivated entries"),
    auth_context: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MedicationRead]:
    user_id: str = auth_context["user_id"]
    return await medication_service.list_medications(session, user_id=user_id, include_inactive=include_inactive)


@router.patch(
    "/medications/{entry_id}",
    summary="Edit or deactivate a medication",
    description=(
        "Update dosage/schedule/notes or deactivate (set deactivate=true in body). "
        "Requires manage-level permission. Deactivated entries keep their history."
    ),
)
async def update_medication(
    entry_id: str,
    payload: MedicationUpdate,
    auth_context: Annotated[dict, Depends(require_permission(PermissionLevel.MANAGE))],
    session: AsyncSession = Depends(get_session),
) -> MedicationRead:
    user_id: str = auth_context["user_id"]
    return await medication_service.update_medication(session, user_id=user_id, entry_id=entry_id, payload=payload)


# ---------------------------------------------------------------------------
# Dose logging
# ---------------------------------------------------------------------------

@router.post(
    "/medications/{entry_id}/doses",
    status_code=201,
    summary="Log a dose intake",
    description="Record a taken/missed/skipped dose event for a medication entry (FR-MED-4).",
)
async def log_dose(
    entry_id: str,
    payload: DoseLogCreate,
    auth_context: Annotated[dict, Depends(require_permission(PermissionLevel.MANAGE))],
    session: AsyncSession = Depends(get_session),
) -> DoseLogRead:
    user_id: str = auth_context["user_id"]
    return await medication_service.log_dose(session, user_id=user_id, entry_id=entry_id, payload=payload)


@router.get(
    "/medications/{entry_id}/doses",
    summary="List dose logs",
    description="Fetch chronological dose intake history for a medication entry.",
)
async def list_doses(
    entry_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth_context: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DoseLogRead]:
    user_id: str = auth_context["user_id"]
    return await medication_service.list_doses(session, user_id=user_id, entry_id=entry_id, limit=limit, offset=offset)
