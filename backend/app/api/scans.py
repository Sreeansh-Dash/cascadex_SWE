"""
CascadeX scans router — Phase 05.

Endpoints:
  POST /scans          Submit OCR text → run match pipeline → return candidates.
  GET  /scans/{id}     Retrieve a past ScanRecord (audit trail).

Critical invariant:
  POST /scans NEVER creates a MedicationEntry.
  The frontend must call POST /medications separately after the user confirms.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from neo4j import AsyncSession

from app.core.dependencies import get_current_user
from app.core.security import decrypt_field, encrypt_field
from app.db.neo4j_session import get_session
from app.models.scan import ScanCandidateList, ScanCreate, ScanRecord
from app.services.ocr_match_service import run_ocr_match

router = APIRouter(prefix="/scans", tags=["scans"])


# ---------------------------------------------------------------------------
# POST /scans
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ScanCandidateList,
    status_code=status.HTTP_201_CREATED,
    summary="Submit OCR text and get drug candidates",
    description=(
        "Accepts raw OCR text extracted by the on-device ML Kit scanner. "
        "Runs a two-stage drug name matching pipeline (exact → LLM fuzzy) "
        "and returns a list of candidate drugs. "
        "**This endpoint NEVER creates a MedicationEntry.** "
        "The user must explicitly confirm via POST /medications."
    ),
)
async def create_scan(
    body: ScanCreate,
    auth_context: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ScanCandidateList:
    """Run OCR match pipeline and persist a ScanRecord audit node."""
    user_id: str = auth_context["user_id"]
    scan_id = f"scan_{uuid.uuid4().hex}"
    now = datetime.now(tz=UTC)

    # Run the two-stage match pipeline
    match_result = await run_ocr_match(body.ocr_text, session)

    # Determine response fields
    if match_result.matched_drug is not None:
        scan_status = "matched"
        primary_match = match_result.matched_drug
        candidates = [match_result.matched_drug]
        message = (
            f"Best match: {match_result.matched_drug.generic_name}. "
            "Please confirm to add."
        )
    else:
        scan_status = "unmatched"
        primary_match = None
        candidates = []
        message = (
            "No confident match found. "
            "Please search for the medication manually or try scanning again."
        )

    # Persist ScanRecord node in Neo4j (audit trail)
    # encrypt_field: Fernet-encrypts the raw OCR text at rest.
    # Passthrough (plaintext) when FIELD_ENCRYPTION_KEY is empty (dev/test).
    encrypted_ocr = encrypt_field(body.ocr_text)
    await session.run(
        """
        MERGE (u:User {user_id: $user_id})
        CREATE (s:ScanRecord {
            scan_id:          $scan_id,
            user_id:          $user_id,
            ocr_text:         $ocr_text,
            status:           $status,
            matched_drug_id:  $matched_drug_id,
            matched_drug_name:$matched_drug_name,
            confidence:       $confidence,
            match_method:     $method,
            created_at:       $created_at
        })
        CREATE (u)-[:HAS_SCAN]->(s)
        """,
        user_id=user_id,
        scan_id=scan_id,
        ocr_text=encrypted_ocr,
        status=scan_status,
        matched_drug_id=(
            match_result.matched_drug.drug_id if match_result.matched_drug else None
        ),
        matched_drug_name=match_result.matched_name,
        confidence=match_result.confidence,
        method=match_result.method,
        created_at=now.isoformat(),
    )

    return ScanCandidateList(
        scan_id=scan_id,
        ocr_text=body.ocr_text,
        status=scan_status,  # type: ignore[arg-type]
        primary_match=primary_match,
        candidates=candidates,
        message=message,
    )


# ---------------------------------------------------------------------------
# GET /scans/{scan_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{scan_id}",
    response_model=ScanRecord,
    status_code=status.HTTP_200_OK,
    summary="Get a scan record by ID",
    description=(
        "Returns the stored ScanRecord for audit / review purposes. "
        "Users can only retrieve their own scans."
    ),
)
async def get_scan(
    scan_id: str,
    auth_context: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ScanRecord:
    """Retrieve a ScanRecord by ID, scoped to the requesting user."""
    user_id: str = auth_context["user_id"]

    result = await session.run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_SCAN]->(s:ScanRecord {scan_id: $scan_id})
        RETURN s.scan_id          AS scan_id,
               s.user_id          AS user_id,
               s.ocr_text         AS ocr_text,
               s.status           AS status,
               s.matched_drug_id  AS matched_drug_id,
               s.matched_drug_name AS matched_drug_name,
               s.confidence       AS confidence,
               s.match_method     AS match_method,
               s.created_at       AS created_at
        """,
        user_id=user_id,
        scan_id=scan_id,
    )
    record = await result.single()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan '{scan_id}' not found.",
        )

    data = dict(record)
    data["created_at"] = datetime.fromisoformat(data["created_at"])
    # decrypt_field: reverses Fernet encryption applied at write time.
    # Passthrough (identity) when FIELD_ENCRYPTION_KEY is empty.
    data["ocr_text"] = decrypt_field(data["ocr_text"])
    return ScanRecord(**data)
