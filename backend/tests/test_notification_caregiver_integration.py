"""API contract tests for notification visibility and caregiver onboarding."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.neo4j_session import get_session
from app.main import app


@pytest.mark.asyncio
async def test_notification_feed_returns_new_interaction_notification():
    session = AsyncMock()
    result = AsyncMock()
    result.data.return_value = [{
        "n": {
            "notification_id": "notif_1", "user_id": "usr_1",
            "type": "interaction_alert", "message": "Review aspirin and warfarin",
            "related_alert_id": "alert_1", "created_at": "2026-10-13T10:00:00+00:00",
            "read": False,
        }
    }]
    session.run.return_value = result
    app.dependency_overrides[get_session] = lambda: session
    try:
        # The endpoint's auth dependency is intentionally exercised through
        # the application; auth is replaced only with a resolved test context.
        from app.api import notifications
        from app.core.dependencies import get_current_user
        app.dependency_overrides[get_current_user] = lambda: {
            "account_id": "usr_1", "user_id": "usr_1", "role": "user",
            "permission_level": None,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/notifications")
        assert response.status_code == 200
        assert response.json()[0]["related_alert_id"] == "alert_1"
    finally:
        app.dependency_overrides.clear()


def test_caregiver_registration_route_is_exposed():
    paths = {route.path for route in app.routes}
    assert "/api/v1/auth/caregivers/register" in paths
