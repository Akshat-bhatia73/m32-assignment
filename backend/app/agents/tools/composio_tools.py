"""Composio integration — Gmail send + Google Calendar create.

The app user's email is used as the Composio external ``user_id``; their Gmail/Calendar must be
connected under that id (see ``app/scripts/composio_connect.py``). When ``COMPOSIO_API_KEY`` is
unset we *simulate* the call so the confirmation flow still demos without OAuth.

Tool schemas (verified against SDK 0.13.x):
  GMAIL_SEND_EMAIL            -> recipient_email, subject, body, extra_recipients
  GOOGLECALENDAR_CREATE_EVENT -> summary, start_datetime (ISO 8601), event_duration_minutes,
                                 calendar_id, description, timezone
"""

import logging
import uuid
from functools import lru_cache
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

GMAIL_SEND = "GMAIL_SEND_EMAIL"
CALENDAR_CREATE = "GOOGLECALENDAR_CREATE_EVENT"

# Map our toolkit param to the Composio toolkit slug used for connected-account lookup.
_TOOLKIT_FOR_SLUG = {
    GMAIL_SEND: "gmail",
    CALENDAR_CREATE: "googlecalendar",
}


def composio_enabled() -> bool:
    return bool(settings.composio_api_key)


@lru_cache
def _client():
    from composio import Composio

    return Composio(api_key=settings.composio_api_key)


def _active_connected_account_id(user_id: str, toolkit_slug: str) -> str | None:
    """Return the ACTIVE connected_account_id for (user_id, toolkit), if any.

    A user can accumulate multiple connected accounts for one toolkit (e.g. a stale
    ``INITIALIZING`` row from an abandoned OAuth attempt alongside the real ``ACTIVE`` one).
    Passing the ACTIVE id explicitly to ``tools.execute`` removes that ambiguity.
    """
    try:
        res = _client().connected_accounts.list(
            user_ids=[user_id], toolkit_slugs=[toolkit_slug], statuses=["ACTIVE"]
        )
    except Exception:  # noqa: BLE001 — lookup is best-effort; fall back to user_id routing
        logger.exception("connected_accounts.list failed for %s/%s", user_id, toolkit_slug)
        return None
    items = getattr(res, "items", None) or []
    for acc in items:
        acc_id = getattr(acc, "id", None)
        if acc_id:
            return acc_id
    return None


def _execute(slug: str, arguments: dict[str, Any], *, user_id: str) -> dict[str, Any]:
    """Execute a Composio tool for ``user_id``, resolving the ACTIVE account explicitly.

    Centralizes two things the raw ``tools.execute`` got wrong:
    - manual execution now requires a toolkit version, so we skip the version check (use latest);
    - if multiple connected accounts exist for the toolkit, we target the ACTIVE one by id.
    """
    kwargs: dict[str, Any] = {"user_id": user_id, "dangerously_skip_version_check": True}
    toolkit = _TOOLKIT_FOR_SLUG.get(slug)
    if toolkit:
        acc_id = _active_connected_account_id(user_id, toolkit)
        if acc_id:
            kwargs["connected_account_id"] = acc_id
    res = _client().tools.execute(slug, arguments, **kwargs)
    return _result(dict(res))


def _result(res: dict) -> dict[str, Any]:
    """Normalize a ToolExecutionResponse (dict-like) into our own result shape."""
    successful = bool(res.get("successful"))
    return {
        "status": "ok" if successful else "error",
        "data": res.get("data") or {},
        "error": res.get("error"),
    }


def send_gmail(*, user_id: str, to: list[str], subject: str, body: str) -> dict[str, Any]:
    if not composio_enabled():
        return {
            "status": "simulated",
            "to": to,
            "subject": subject,
            "detail": "No COMPOSIO_API_KEY set — email drafted but not actually sent.",
        }
    arguments: dict[str, Any] = {"recipient_email": to[0], "subject": subject, "body": body}
    if len(to) > 1:
        arguments["extra_recipients"] = to[1:]
    try:
        out = _execute(GMAIL_SEND, arguments, user_id=user_id)
    except Exception as exc:  # e.g. no connected Gmail account for this user_id
        return {"status": "error", "error": str(exc), "to": to}
    out["to"] = to
    return out


def create_calendar_event(
    *, user_id: str, summary: str, event_date: str, description: str | None = None
) -> dict[str, Any]:
    if not composio_enabled():
        return {
            "status": "simulated",
            "event_id": f"sim_{uuid.uuid4().hex[:12]}",
            "summary": summary,
            "date": event_date,
            "detail": "No COMPOSIO_API_KEY set — event drafted but not actually created.",
        }
    arguments: dict[str, Any] = {
        "summary": summary,
        # Default the due date to a 9am, 30-minute block.
        "start_datetime": f"{event_date}T09:00:00",
        "event_duration_minutes": 30,
        "calendar_id": "primary",
        "timezone": settings.composio_timezone,
    }
    if description:
        arguments["description"] = description
    try:
        out = _execute(CALENDAR_CREATE, arguments, user_id=user_id)
    except Exception as exc:  # e.g. no connected Google Calendar account for this user_id
        return {"status": "error", "error": str(exc), "summary": summary}
    data = out.get("data") or {}
    # Event id location varies; dig it out best-effort.
    out["event_id"] = (
        data.get("id")
        or (data.get("response_data") or {}).get("id")
        or f"evt_{uuid.uuid4().hex[:12]}"
    )
    out["summary"] = summary
    return out


# --- connection helpers (used by the connect script / a future settings screen) -------------

def connection_status(user_id: str) -> dict[str, bool]:
    """Whether Gmail and Google Calendar are connected (ACTIVE) for this user_id."""
    if not composio_enabled():
        return {"gmail": False, "googlecalendar": False}
    res = _client().connected_accounts.list(
        user_ids=[user_id], toolkit_slugs=["gmail", "googlecalendar"], statuses=["ACTIVE"]
    )
    items = getattr(res, "items", None) or []
    active = set()
    for acc in items:
        slug = (getattr(getattr(acc, "toolkit", None), "slug", "") or "").lower()
        active.add(slug)
    return {"gmail": "gmail" in active, "googlecalendar": "googlecalendar" in active}


def _auth_config_map() -> dict[str, str]:
    """Map toolkit slug -> auth_config_id from the project's configured auth configs."""
    res = _client().auth_configs.list()
    items = getattr(res, "items", None) or []
    mapping: dict[str, str] = {}
    for a in items:
        slug = (
            getattr(getattr(a, "toolkit", None), "slug", None)
            or getattr(a, "toolkit_slug", "")
            or ""
        ).lower()
        cfg_id = getattr(a, "id", None)
        if slug and cfg_id:
            mapping[slug] = cfg_id
    return mapping


def authorize_url(user_id: str, toolkit: str) -> str:
    """Return the OAuth redirect URL the user must visit to connect a toolkit.

    Uses connected_accounts.link with the toolkit's auth_config_id (the supported flow for
    Composio-managed OAuth).
    """
    cfg_id = _auth_config_map().get(toolkit)
    if not cfg_id:
        raise RuntimeError(
            f"No auth config found for '{toolkit}'. Add one in the Composio dashboard."
        )
    conn = _client().connected_accounts.link(user_id=user_id, auth_config_id=cfg_id)
    return getattr(conn, "redirect_url", "") or ""
