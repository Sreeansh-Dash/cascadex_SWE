"""
CascadeX medication service — Phase 04.

Implements all business logic for:
- Catalog drug search (prefix/contains, generic + brand)
- MedicationEntry CRUD (add, list, update/deactivate)
- DoseSchedule management
- DoseIntakeLog creation and retrieval

Design rules:
- Every query is scoped to the authenticated user_id — client-supplied user IDs
  in request bodies are NEVER trusted for ownership decisions.
- Deactivation sets is_active=False + end_date; node and history are preserved.
- add_medication validates the referenced drug_id exists before creating nodes
  (raises 404 / "drug_not_found" if the drug does not exist in the catalog).
- input_method is always "manual" in this phase; Phase 05 passes "scan" through
  the same service function without any schema changes.
- No interaction checking is triggered here; Phase 06 wires that in explicitly.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from neo4j import AsyncSession

from app.models.drug import DrugRead
from app.models.medication import (
    DoseLogCreate,
    DoseLogRead,
    DoseScheduleRead,
    InputMethod,
    MedicationCreate,
    MedicationRead,
    MedicationUpdate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Catalog search
# ---------------------------------------------------------------------------

async def search_drugs(
    session: AsyncSession,
    q: str,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """Search the drug catalog by partial generic or brand name.

    Uses indexed CONTAINS on both Drug.generic_name and DrugBrandName.brand_name
    (case-insensitive via toLower).  Each result includes a ``matched_name`` field
    indicating which name triggered the match (for UI display).

    Args:
        session: Open Neo4j async session.
        q: Search query string (trimmed/lowercased internally).
        limit: Maximum results per page (default 20, max enforced by caller).
        offset: Pagination offset.

    Returns:
        List of dicts with DrugRead fields + ``matched_name``.
    """
    cleaned = q.strip().lower()
    if not cleaned:
        return []

    cypher = """
    CALL {
        MATCH (d:Drug)
        WHERE toLower(d.generic_name) CONTAINS $q
        RETURN d.drug_id          AS drug_id,
               d.generic_name     AS generic_name,
               d.drug_class       AS drug_class,
               d.atc_code         AS atc_code,
               d.default_form     AS default_form,
               d.external_source_id AS external_source_id,
               d.generic_name     AS matched_name
        UNION
        MATCH (b:DrugBrandName)-[:BRAND_OF]->(d:Drug)
        WHERE toLower(b.brand_name) CONTAINS $q
        RETURN d.drug_id          AS drug_id,
               d.generic_name     AS generic_name,
               d.drug_class       AS drug_class,
               d.atc_code         AS atc_code,
               d.default_form     AS default_form,
               d.external_source_id AS external_source_id,
               b.brand_name       AS matched_name
    }
    RETURN DISTINCT drug_id, generic_name, drug_class, atc_code,
                    default_form, external_source_id, matched_name
    ORDER BY generic_name
    SKIP $offset
    LIMIT $limit
    """
    res = await session.run(cypher, {"q": cleaned, "offset": offset, "limit": limit})
    records = await res.data()
    return [dict(r) for r in records]


# ---------------------------------------------------------------------------
# Medication CRUD
# ---------------------------------------------------------------------------

async def add_medication(
    session: AsyncSession,
    user_id: str,
    payload: MedicationCreate,
    input_method: str = InputMethod.MANUAL.value,
) -> MedicationRead:
    """Add a new MedicationEntry for the authenticated user.

    Validates that the referenced drug_id exists in the catalog.
    Creates the MedicationEntry node plus one DoseSchedule node per schedule row.

    Args:
        session: Open Neo4j async session.
        user_id: Authenticated user's ID (from token — never from request body).
        payload: Validated MedicationCreate request body.
        input_method: "manual" (default) or "scan" (set by Phase 05).

    Returns:
        MedicationRead for the newly created entry.

    Raises:
        HTTPException(404): If the drug_id does not exist in the catalog.
    """
    # 1. Validate the drug exists — 404 if not
    drug_res = await session.run(
        """
        MATCH (d:Drug {drug_id: $drug_id})
        RETURN d.drug_id AS drug_id, d.generic_name AS generic_name,
               d.drug_class AS drug_class
        """,
        {"drug_id": payload.drug_id},
    )
    drug_record = await drug_res.single()
    if not drug_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "drug_not_found", "message": f"Drug '{payload.drug_id}' not found in catalog"},
        )

    generic_name = drug_record["generic_name"]
    drug_class = drug_record["drug_class"] or ""

    # 2. Create MedicationEntry node
    entry_id = f"med_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(UTC).isoformat()

    create_entry_query = """
    MATCH (u:User {user_id: $user_id})
    CREATE (me:MedicationEntry {
        entry_id:      $entry_id,
        drug_id:       $drug_id,
        generic_name:  $generic_name,
        drug_class:    $drug_class,
        dosage_amount: $dosage_amount,
        dosage_unit:   $dosage_unit,
        input_method:  $input_method,
        is_active:     true,
        notes:         $notes,
        start_date:    $start_date,
        end_date:      null,
        created_at:    $created_at
    })
    CREATE (u)-[:HAS_MEDICATION]->(me)
    RETURN me
    """
    entry_res = await session.run(
        create_entry_query,
        {
            "user_id": user_id,
            "entry_id": entry_id,
            "drug_id": payload.drug_id,
            "generic_name": generic_name,
            "drug_class": drug_class,
            "dosage_amount": payload.dosage_amount,
            "dosage_unit": payload.dosage_unit,
            "input_method": input_method,
            "notes": payload.notes,
            "start_date": now_iso,
            "created_at": now_iso,
        },
    )
    entry_record = await entry_res.single()
    me_node = dict(entry_record["me"])

    # 3. Create DoseSchedule nodes
    schedule_reads: list[DoseScheduleRead] = []
    for sched in payload.schedules:
        sched_id = f"sched_{uuid.uuid4().hex[:10]}"
        sched_query = """
        MATCH (me:MedicationEntry {entry_id: $entry_id})
        CREATE (s:DoseSchedule {
            schedule_id:  $schedule_id,
            time_of_day:  $time_of_day,
            days_of_week: $days_of_week
        })
        CREATE (me)-[:HAS_SCHEDULE]->(s)
        RETURN s
        """
        sched_res = await session.run(
            sched_query,
            {
                "entry_id": entry_id,
                "schedule_id": sched_id,
                "time_of_day": sched.time_of_day,
                "days_of_week": sched.days_of_week,
            },
        )
        sched_record = await sched_res.single()
        s_node = dict(sched_record["s"])
        schedule_reads.append(DoseScheduleRead(
            schedule_id=s_node["schedule_id"],
            time_of_day=s_node["time_of_day"],
            days_of_week=s_node.get("days_of_week") or [],
        ))

    return MedicationRead(
        entry_id=me_node["entry_id"],
        drug_id=me_node["drug_id"],
        generic_name=me_node["generic_name"],
        drug_class=me_node.get("drug_class", ""),
        dosage_amount=me_node["dosage_amount"],
        dosage_unit=me_node["dosage_unit"],
        input_method=me_node["input_method"],
        is_active=me_node["is_active"],
        notes=me_node.get("notes"),
        start_date=me_node["start_date"],
        end_date=me_node.get("end_date"),
        created_at=me_node["created_at"],
        schedules=schedule_reads,
    )


async def list_medications(
    session: AsyncSession,
    user_id: str,
    include_inactive: bool = False,
) -> list[MedicationRead]:
    """List medication entries for a user, with their schedules.

    Args:
        session: Open Neo4j async session.
        user_id: Authenticated user's ID.
        include_inactive: If True, include deactivated entries.

    Returns:
        List of MedicationRead ordered by created_at descending.
    """
    active_filter = "" if include_inactive else "WHERE me.is_active = true"

    cypher = f"""
    MATCH (u:User {{user_id: $user_id}})-[:HAS_MEDICATION]->(me:MedicationEntry)
    {active_filter}
    OPTIONAL MATCH (me)-[:HAS_SCHEDULE]->(s:DoseSchedule)
    RETURN me, collect(s) AS schedules
    ORDER BY me.created_at DESC
    """
    res = await session.run(cypher, {"user_id": user_id})
    records = await res.data()

    results: list[MedicationRead] = []
    for row in records:
        me = dict(row["me"])
        scheds = [
            DoseScheduleRead(
                schedule_id=s["schedule_id"],
                time_of_day=s["time_of_day"],
                days_of_week=s.get("days_of_week") or [],
            )
            for s in row["schedules"]
            if s is not None
        ]
        results.append(MedicationRead(
            entry_id=me["entry_id"],
            drug_id=me["drug_id"],
            generic_name=me.get("generic_name", ""),
            drug_class=me.get("drug_class", ""),
            dosage_amount=me["dosage_amount"],
            dosage_unit=me["dosage_unit"],
            input_method=me.get("input_method", "manual"),
            is_active=me["is_active"],
            notes=me.get("notes"),
            start_date=me["start_date"],
            end_date=me.get("end_date"),
            created_at=me["created_at"],
            schedules=scheds,
        ))
    return results


async def get_medication(
    session: AsyncSession,
    user_id: str,
    entry_id: str,
) -> MedicationRead:
    """Fetch a single MedicationEntry, scoped to the authenticated user.

    Args:
        session: Open Neo4j async session.
        user_id: Authenticated user's ID.
        entry_id: MedicationEntry ID to fetch.

    Returns:
        MedicationRead.

    Raises:
        HTTPException(404): If the entry does not exist or belongs to another user.
    """
    cypher = """
    MATCH (u:User {user_id: $user_id})-[:HAS_MEDICATION]->(me:MedicationEntry {entry_id: $entry_id})
    OPTIONAL MATCH (me)-[:HAS_SCHEDULE]->(s:DoseSchedule)
    RETURN me, collect(s) AS schedules
    """
    res = await session.run(cypher, {"user_id": user_id, "entry_id": entry_id})
    record = await res.single()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "medication_not_found", "message": "Medication entry not found or access denied"},
        )

    me = dict(record["me"])
    scheds = [
        DoseScheduleRead(
            schedule_id=s["schedule_id"],
            time_of_day=s["time_of_day"],
            days_of_week=s.get("days_of_week") or [],
        )
        for s in record["schedules"]
        if s is not None
    ]

    return MedicationRead(
        entry_id=me["entry_id"],
        drug_id=me["drug_id"],
        generic_name=me.get("generic_name", ""),
        drug_class=me.get("drug_class", ""),
        dosage_amount=me["dosage_amount"],
        dosage_unit=me["dosage_unit"],
        input_method=me.get("input_method", "manual"),
        is_active=me["is_active"],
        notes=me.get("notes"),
        start_date=me["start_date"],
        end_date=me.get("end_date"),
        created_at=me["created_at"],
        schedules=scheds,
    )


async def update_medication(
    session: AsyncSession,
    user_id: str,
    entry_id: str,
    payload: MedicationUpdate,
) -> MedicationRead:
    """Edit dosage/schedule or deactivate a MedicationEntry.

    Ownership is enforced — the entry must be linked to user_id via
    HAS_MEDICATION.  A 404 is returned for missing or unowned entries
    (same response as a missing entry to prevent enumeration).

    Deactivation: sets is_active=False and end_date to now; the node and
    its DoseIntakeLog / DoseSchedule history remain intact and queryable.

    Args:
        session: Open Neo4j async session.
        user_id: Authenticated user's ID.
        entry_id: MedicationEntry ID to modify.
        payload: MedicationUpdate body.

    Returns:
        Updated MedicationRead.

    Raises:
        HTTPException(404): If entry not found or not owned by user.
        HTTPException(400): If trying to update an already-deactivated entry.
    """
    # Verify ownership first
    check_res = await session.run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_MEDICATION]->(me:MedicationEntry {entry_id: $entry_id})
        RETURN me.is_active AS is_active
        """,
        {"user_id": user_id, "entry_id": entry_id},
    )
    check_record = await check_res.single()
    if not check_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "medication_not_found", "message": "Medication entry not found or access denied"},
        )

    now_iso = datetime.now(UTC).isoformat()

    if payload.deactivate:
        if not check_record["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "already_inactive", "message": "Medication entry is already deactivated"},
            )
        # Deactivate: set is_active=False, record end_date
        await session.run(
            """
            MATCH (me:MedicationEntry {entry_id: $entry_id})
            SET me.is_active = false, me.end_date = $end_date
            """,
            {"entry_id": entry_id, "end_date": now_iso},
        )
    else:
        # Build dynamic SET clause for any provided fields
        set_parts: list[str] = []
        params: dict = {"entry_id": entry_id}

        if payload.dosage_amount is not None:
            set_parts.append("me.dosage_amount = $dosage_amount")
            params["dosage_amount"] = payload.dosage_amount
        if payload.dosage_unit is not None:
            set_parts.append("me.dosage_unit = $dosage_unit")
            params["dosage_unit"] = payload.dosage_unit
        if payload.notes is not None:
            set_parts.append("me.notes = $notes")
            params["notes"] = payload.notes

        if set_parts:
            set_clause = ", ".join(set_parts)
            await session.run(
                f"MATCH (me:MedicationEntry {{entry_id: $entry_id}}) SET {set_clause}",
                params,
            )

        # If schedules provided, replace all existing DoseSchedule nodes
        if payload.schedules is not None:
            # Delete old schedules
            await session.run(
                """
                MATCH (me:MedicationEntry {entry_id: $entry_id})-[:HAS_SCHEDULE]->(s:DoseSchedule)
                DETACH DELETE s
                """,
                {"entry_id": entry_id},
            )
            # Create new schedules
            for sched in payload.schedules:
                sched_id = f"sched_{uuid.uuid4().hex[:10]}"
                await session.run(
                    """
                    MATCH (me:MedicationEntry {entry_id: $entry_id})
                    CREATE (s:DoseSchedule {
                        schedule_id:  $schedule_id,
                        time_of_day:  $time_of_day,
                        days_of_week: $days_of_week
                    })
                    CREATE (me)-[:HAS_SCHEDULE]->(s)
                    """,
                    {
                        "entry_id": entry_id,
                        "schedule_id": sched_id,
                        "time_of_day": sched.time_of_day,
                        "days_of_week": sched.days_of_week,
                    },
                )

    return await get_medication(session, user_id, entry_id)


# ---------------------------------------------------------------------------
# Dose logging
# ---------------------------------------------------------------------------

async def log_dose(
    session: AsyncSession,
    user_id: str,
    entry_id: str,
    payload: DoseLogCreate,
) -> DoseLogRead:
    """Log a dose intake event for a MedicationEntry (FR-MED-4).

    Validates ownership of the MedicationEntry before creating the log.
    Dose logs are created even for deactivated entries (past events).

    Args:
        session: Open Neo4j async session.
        user_id: Authenticated user's ID.
        entry_id: MedicationEntry the dose belongs to.
        payload: DoseLogCreate body.

    Returns:
        DoseLogRead for the new log.

    Raises:
        HTTPException(404): If entry not found or not owned by user.
        HTTPException(400): If status=taken but taken_at is not provided.
    """
    if payload.status.value == "taken" and not payload.taken_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "missing_taken_at", "message": "'taken_at' is required when status is 'taken'"},
        )

    # Verify ownership (returns 404 for missing OR unowned)
    check_res = await session.run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_MEDICATION]->(me:MedicationEntry {entry_id: $entry_id})
        RETURN me.entry_id AS eid
        """,
        {"user_id": user_id, "entry_id": entry_id},
    )
    if not await check_res.single():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "medication_not_found", "message": "Medication entry not found or access denied"},
        )

    log_id = f"log_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(UTC).isoformat()

    create_log_query = """
    MATCH (me:MedicationEntry {entry_id: $entry_id})
    CREATE (l:DoseIntakeLog {
        log_id:         $log_id,
        entry_id:       $entry_id,
        status:         $status,
        scheduled_time: $scheduled_time,
        taken_at:       $taken_at,
        notes:          $notes,
        logged_at:      $logged_at
    })
    CREATE (me)-[:HAS_DOSE_LOG]->(l)
    RETURN l
    """
    log_res = await session.run(
        create_log_query,
        {
            "entry_id": entry_id,
            "log_id": log_id,
            "status": payload.status.value,
            "scheduled_time": payload.scheduled_time,
            "taken_at": payload.taken_at,
            "notes": payload.notes,
            "logged_at": now_iso,
        },
    )
    log_record = await log_res.single()
    l_node = dict(log_record["l"])

    return DoseLogRead(
        log_id=l_node["log_id"],
        entry_id=l_node["entry_id"],
        status=l_node["status"],
        scheduled_time=l_node["scheduled_time"],
        taken_at=l_node.get("taken_at"),
        notes=l_node.get("notes"),
        logged_at=l_node["logged_at"],
    )


async def list_doses(
    session: AsyncSession,
    user_id: str,
    entry_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[DoseLogRead]:
    """List dose intake logs for a MedicationEntry in chronological order.

    Args:
        session: Open Neo4j async session.
        user_id: Authenticated user's ID.
        entry_id: MedicationEntry to fetch logs for.
        limit: Max results per page.
        offset: Pagination offset.

    Returns:
        List of DoseLogRead ordered by scheduled_time ascending.

    Raises:
        HTTPException(404): If entry not found or not owned by user.
    """
    # Verify ownership
    check_res = await session.run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_MEDICATION]->(me:MedicationEntry {entry_id: $entry_id})
        RETURN me.entry_id AS eid
        """,
        {"user_id": user_id, "entry_id": entry_id},
    )
    if not await check_res.single():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "medication_not_found", "message": "Medication entry not found or access denied"},
        )

    cypher = """
    MATCH (me:MedicationEntry {entry_id: $entry_id})-[:HAS_DOSE_LOG]->(l:DoseIntakeLog)
    RETURN l
    ORDER BY l.scheduled_time ASC
    SKIP $offset
    LIMIT $limit
    """
    res = await session.run(cypher, {"entry_id": entry_id, "offset": offset, "limit": limit})
    records = await res.data()

    return [
        DoseLogRead(
            log_id=row["l"]["log_id"],
            entry_id=row["l"]["entry_id"],
            status=row["l"]["status"],
            scheduled_time=row["l"]["scheduled_time"],
            taken_at=row["l"].get("taken_at"),
            notes=row["l"].get("notes"),
            logged_at=row["l"]["logged_at"],
        )
        for row in records
    ]
