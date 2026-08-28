"""
CascadeX History Service — Phase 08.

Provides:
- `get_history_feed()` — unified, paginated, chronological timeline of dose intake logs and interaction alerts.
- `export_history_pdf()` — generates a downloadable clinical summary PDF with reportlab.
"""

from __future__ import annotations

import io
import logging
from datetime import UTC, datetime
from typing import Any

from neo4j import AsyncSession
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.history import (
    AlertHistoryEvent,
    DoseHistoryEvent,
    HistoryEvent,
    HistoryFeedResponse,
)

logger = logging.getLogger(__name__)

_DISCLAIMER = "This document is an automated medication summary and does not constitute medical advice. Consult a licensed pharmacist or doctor before altering any regimen."


# ---------------------------------------------------------------------------
# History feed (merged timeline)
# ---------------------------------------------------------------------------

async def get_history_feed(
    session: AsyncSession,
    user_id: str,
    before: str | None = None,
    limit: int = 20,
) -> HistoryFeedResponse:
    """Fetch a unified chronological history feed of dose intake logs and interaction alerts.

    Args:
        session: Open Neo4j async session.
        user_id: The authenticated user's ID.
        before: Optional ISO-8601 cursor to fetch items before this timestamp.
        limit: Maximum number of events to return per page.

    Returns:
        HistoryFeedResponse with unified events, next_cursor, and has_more flag.
    """
    # 1. Fetch dose logs
    dose_filter = "WHERE l.scheduled_time < $before" if before else ""
    dose_query = f"""
    MATCH (u:User {{user_id: $user_id}})-[:HAS_MEDICATION]->(me:MedicationEntry)-[:HAS_DOSE_LOG]->(l:DoseIntakeLog)
    {dose_filter}
    RETURN l.log_id AS log_id,
           l.scheduled_time AS scheduled_time,
           l.taken_at AS taken_at,
           l.status AS status,
           l.notes AS notes,
           me.entry_id AS entry_id,
           me.generic_name AS generic_name,
           me.dosage_amount AS dosage_amount,
           me.dosage_unit AS dosage_unit
    ORDER BY l.scheduled_time DESC
    LIMIT $fetch_limit
    """
    dose_res = await session.run(
        dose_query,
        {"user_id": user_id, "before": before, "fetch_limit": limit + 5},
    )
    dose_records = await dose_res.data()

    dose_events: list[HistoryEvent] = []
    for r in dose_records:
        ts = r["scheduled_time"] or r.get("taken_at") or datetime.now(UTC).isoformat()
        dose_events.append(
            DoseHistoryEvent(
                event_id=r["log_id"],
                timestamp=ts,
                entry_id=r["entry_id"],
                generic_name=r["generic_name"],
                dosage_amount=float(r["dosage_amount"]),
                dosage_unit=r["dosage_unit"],
                status=r["status"],
                taken_at=r.get("taken_at"),
                notes=r.get("notes"),
            )
        )

    # 2. Fetch interaction alerts
    alert_filter = "AND a.triggered_at < $before" if before else ""
    alert_query = f"""
    MATCH (u:User {{user_id: $user_id}})-[:HAS_ALERT]->(a:InteractionAlert)
    WHERE true {alert_filter}
    RETURN a.alert_id AS alert_id,
           a.triggered_at AS triggered_at,
           a.drug_a_name AS drug_a_name,
           a.drug_b_name AS drug_b_name,
           a.severity_at_trigger AS severity,
           a.requires_acknowledgment AS requires_acknowledgment,
           a.acknowledged AS acknowledged,
           a.acknowledged_at AS acknowledged_at,
           a.plain_language AS plain_language,
           a.disclaimer AS disclaimer
    ORDER BY a.triggered_at DESC
    LIMIT $fetch_limit
    """
    alert_res = await session.run(
        alert_query,
        {"user_id": user_id, "before": before, "fetch_limit": limit + 5},
    )
    alert_records = await alert_res.data()

    alert_events: list[HistoryEvent] = []
    for r in alert_records:
        alert_events.append(
            AlertHistoryEvent(
                event_id=r["alert_id"],
                timestamp=r["triggered_at"],
                drug_a_name=r["drug_a_name"],
                drug_b_name=r["drug_b_name"],
                severity=r["severity"],
                requires_acknowledgment=bool(r.get("requires_acknowledgment", False)),
                acknowledged=bool(r.get("acknowledged", False)),
                acknowledged_at=r.get("acknowledged_at"),
                plain_language=r.get("plain_language") or "",
                disclaimer=r.get("disclaimer") or _DISCLAIMER,
            )
        )

    # 3. Merge and sort descending
    all_events = dose_events + alert_events
    all_events.sort(key=lambda x: x.timestamp, reverse=True)

    has_more = len(all_events) > limit
    page_events = all_events[:limit]
    next_cursor = page_events[-1].timestamp if has_more and page_events else None

    return HistoryFeedResponse(
        events=page_events,
        next_cursor=next_cursor,
        has_more=has_more,
    )


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------

async def export_history_pdf(session: AsyncSession, user_id: str) -> bytes:
    """Generate a formatted medical history PDF report.

    Contains:
    - Patient header information
    - Active medications list & dosage schedules
    - Recent dose intake history
    - Recorded drug-drug interaction alerts & acknowledgment status
    - Medical disclaimer and DDInter 2.0 / RxNorm source attribution

    Args:
        session: Open Neo4j async session.
        user_id: Authenticated user's ID.

    Returns:
        bytes representing the generated PDF file.
    """
    # 1. Fetch user info
    u_res = await session.run(
        "MATCH (u:User {user_id: $user_id}) RETURN u.full_name AS name, u.email AS email, u.date_of_birth AS dob",
        {"user_id": user_id},
    )
    u_rec = await u_res.single()
    user_name = u_rec["name"] if u_rec and u_rec.get("name") else "Patient"
    user_email = u_rec["email"] if u_rec and u_rec.get("email") else "N/A"
    user_dob = u_rec["dob"] if u_rec and u_rec.get("dob") else "N/A"

    # 2. Fetch active medications
    meds_res = await session.run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_MEDICATION]->(me:MedicationEntry)
        OPTIONAL MATCH (me)-[:HAS_SCHEDULE]->(s:DoseSchedule)
        RETURN me.generic_name AS generic_name,
               me.drug_class AS drug_class,
               me.dosage_amount AS dosage_amount,
               me.dosage_unit AS dosage_unit,
               me.is_active AS is_active,
               me.start_date AS start_date,
               collect(s.time_of_day) AS schedules
        ORDER BY me.is_active DESC, me.generic_name ASC
        """,
        {"user_id": user_id},
    )
    meds_records = await meds_res.data()

    # 3. Fetch past doses
    doses_res = await session.run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_MEDICATION]->(me:MedicationEntry)-[:HAS_DOSE_LOG]->(l:DoseIntakeLog)
        RETURN me.generic_name AS generic_name,
               l.scheduled_time AS scheduled_time,
               l.taken_at AS taken_at,
               l.status AS status,
               l.notes AS notes
        ORDER BY l.scheduled_time DESC
        LIMIT 30
        """,
        {"user_id": user_id},
    )
    doses_records = await doses_res.data()

    # 4. Fetch interaction alerts
    alerts_res = await session.run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_ALERT]->(a:InteractionAlert)
        RETURN a.drug_a_name AS drug_a_name,
               a.drug_b_name AS drug_b_name,
               a.severity_at_trigger AS severity,
               a.triggered_at AS triggered_at,
               a.acknowledged AS acknowledged,
               a.plain_language AS plain_language
        ORDER BY a.triggered_at DESC
        LIMIT 20
        """,
        {"user_id": user_id},
    )
    alerts_records = await alerts_res.data()

    # 5. Build PDF with ReportLab
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1565C0"),
        spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "DocH2",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0D47A1"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#212121"),
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Italic"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#C62828"),
    )
    footer_style = ParagraphStyle(
        "FooterNote",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#757575"),
    )

    elements: list[Any] = []

    # Title & Header
    elements.append(Paragraph("CascadeX — Patient Medication Summary", title_style))
    now_str = datetime.now(UTC).strftime("%B %d, %Y at %H:%M UTC")
    elements.append(Paragraph(f"<b>Generated:</b> {now_str}", body_style))
    elements.append(Spacer(1, 4))

    # Patient info box
    patient_info = [
        [
            Paragraph(f"<b>Patient Name:</b> {user_name}", body_style),
            Paragraph(f"<b>Date of Birth:</b> {user_dob}", body_style),
        ],
        [
            Paragraph(f"<b>Email:</b> {user_email}", body_style),
            Paragraph("<b>System:</b> CascadeX Clinical Safety Platform", body_style),
        ],
    ]
    p_table = Table(patient_info, colWidths=[270, 270])
    p_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F5F5")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ]
        )
    )
    elements.append(p_table)
    elements.append(Spacer(1, 8))

    # Disclaimer banner
    disc_box = [[Paragraph(f"<b>⚠️ CLINICAL NOTICE:</b> {_DISCLAIMER}", disclaimer_style)]]
    disc_table = Table(disc_box, colWidths=[540])
    disc_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFEBEE")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#EF5350")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(disc_table)
    elements.append(Spacer(1, 10))

    # SECTION 1: Medications List
    elements.append(Paragraph("1. Current & Historical Medications", h2_style))
    med_rows = [["Medication", "Class", "Dosage", "Schedules", "Status"]]
    for m in meds_records:
        scheds = ", ".join(m.get("schedules") or []) or "As needed"
        status_str = "ACTIVE" if m.get("is_active") else "INACTIVE"
        med_rows.append(
            [
                m["generic_name"].capitalize(),
                m.get("drug_class") or "—",
                f"{m['dosage_amount']} {m['dosage_unit']}",
                scheds,
                status_str,
            ]
        )
    if len(med_rows) == 1:
        med_rows.append(["No medications recorded", "—", "—", "—", "—"])

    med_table = Table(med_rows, colWidths=[130, 110, 80, 140, 80])
    med_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1565C0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
            ]
        )
    )
    elements.append(med_table)
    elements.append(Spacer(1, 10))

    # SECTION 2: Interaction Alerts
    elements.append(Paragraph("2. Drug Interaction Safety History", h2_style))
    alert_rows = [["Drug Pair", "Severity", "Triggered Date", "Acknowledged", "Summary"]]
    for a in alerts_records:
        ack_str = "Yes" if a.get("acknowledged") else "NO (Pending)"
        dt_short = a["triggered_at"][:10] if a.get("triggered_at") else "—"
        sev = str(a.get("severity", "unknown")).upper()
        alert_rows.append(
            [
                f"{a['drug_a_name']} + {a['drug_b_name']}",
                sev,
                dt_short,
                ack_str,
                Paragraph(a.get("plain_language") or "—", body_style),
            ]
        )
    if len(alert_rows) == 1:
        alert_rows.append(["No interaction alerts recorded", "—", "—", "—", "—"])

    alert_table = Table(alert_rows, colWidths=[120, 60, 70, 70, 220])
    alert_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C62828")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FFF8E1")]),
            ]
        )
    )
    elements.append(alert_table)
    elements.append(Spacer(1, 10))

    # SECTION 3: Recent Dose Logs
    elements.append(Paragraph("3. Recent Dose Intake Logs (Last 30 Records)", h2_style))
    dose_rows = [["Medication", "Scheduled Time", "Status", "Taken At", "Notes"]]
    for d in doses_records[:30]:
        dose_rows.append(
            [
                d["generic_name"].capitalize(),
                d["scheduled_time"][:16].replace("T", " "),
                str(d["status"]).upper(),
                d["taken_at"][:16].replace("T", " ") if d.get("taken_at") else "—",
                d.get("notes") or "—",
            ]
        )
    if len(dose_rows) == 1:
        dose_rows.append(["No dose records available", "—", "—", "—", "—"])

    dose_table = Table(dose_rows, colWidths=[130, 100, 70, 100, 140])
    dose_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
            ]
        )
    )
    elements.append(dose_table)
    elements.append(Spacer(1, 12))

    # Source attribution & Footer
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#BDBDBD")))
    elements.append(Spacer(1, 4))
    elements.append(
        Paragraph(
            "<b>Data Sources:</b> DDInter 2.0 Clinical Drug Interaction Knowledgebase & NLM RxNorm Catalog. "
            "CascadeX Software Engineering Academic Demonstration.",
            footer_style,
        )
    )

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
