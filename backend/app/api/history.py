"""
History router — Phase 08.

Endpoints:
- GET /api/v1/history        — paginated unified chronological feed of doses & alerts
- GET /api/v1/history/export — streams clinical summary PDF
"""


from fastapi import APIRouter, Depends, Query, Response
from neo4j import AsyncSession

from app.core.dependencies import get_current_user
from app.db.neo4j_session import get_session
from app.models.history import HistoryFeedResponse
from app.services import history_service

router = APIRouter(prefix="/history", tags=["history"])


@router.get(
    "",
    response_model=HistoryFeedResponse,
    summary="Get unified history timeline",
    description=(
        "Returns a unified chronological feed of dose intake logs and interaction alerts, "
        "sorted newest-first. Supports cursor-based pagination via the `before` parameter."
    ),
)
async def get_history(
    before: str | None = Query(default=None, description="Cursor timestamp (ISO-8601) to fetch events before"),
    limit: int = Query(default=20, ge=1, le=100, description="Max events per page"),
    auth_context: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> HistoryFeedResponse:
    """Fetch unified history feed for authenticated user."""
    user_id: str = auth_context["user_id"]
    return await history_service.get_history_feed(
        session=session,
        user_id=user_id,
        before=before,
        limit=limit,
    )


@router.get(
    "/export",
    summary="Export clinical history as PDF",
    description=(
        "Generates and streams a downloadable PDF medical summary containing the user's "
        "active medications, recent dose intake logs, interaction alert history, and data source attributions."
    ),
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Rendered PDF document stream",
        }
    },
)
async def export_history_pdf(
    auth_context: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Generate and return PDF report."""
    user_id: str = auth_context["user_id"]
    pdf_bytes = await history_service.export_history_pdf(session=session, user_id=user_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="cascadex_medication_history.pdf"',
            "Content-Type": "application/pdf",
        },
    )
