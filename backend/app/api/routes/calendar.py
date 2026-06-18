"""Calendar — read the current user's upcoming Google Calendar events for the sidebar agenda."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from app.agents.tools import composio_tools
from app.api.deps import CurrentUser

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events")
def list_events(current_user: CurrentUser, days: int = 7) -> dict:
    """Normalized upcoming events for the next ``days`` days (scoped to the current user)."""
    days = max(1, min(days, 31))
    now = datetime.now(UTC)
    result = composio_tools.list_calendar_events(
        user_id=current_user.email,
        time_min=now.isoformat(),
        time_max=(now + timedelta(days=days)).isoformat(),
    )
    connected = result.get("status") == "ok"
    return {"connected": connected, "events": result.get("events", [])}
