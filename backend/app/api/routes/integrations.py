"""Integrations (Composio) — connection status + OAuth connect, so a non-technical user can
connect Gmail/Calendar from the app instead of the CLI script."""

from fastapi import APIRouter, HTTPException, status

from app.agents.tools import composio_tools
from app.api.deps import CurrentUser

router = APIRouter(prefix="/integrations", tags=["integrations"])

_TOOLKITS = {"gmail", "googlecalendar"}


@router.get("/status")
def integrations_status(current_user: CurrentUser) -> dict[str, bool]:
    """Whether Gmail and Google Calendar are connected (ACTIVE) for the current user."""
    return composio_tools.connection_status(current_user.email)


@router.post("/{toolkit}/connect")
def connect_toolkit(toolkit: str, current_user: CurrentUser) -> dict[str, str]:
    """Return the OAuth URL the user opens in a new tab to connect ``toolkit``."""
    if toolkit not in _TOOLKITS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown toolkit")
    if not composio_tools.composio_enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Integrations are not configured on the server (no Composio API key).",
        )
    try:
        url = composio_tools.authorize_url(current_user.email, toolkit)
    except Exception as exc:  # noqa: BLE001 — surface the real reason to the UI
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Couldn't start connection: {exc}"
        ) from exc
    if not url:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "No authorization URL returned.")
    return {"url": url}
