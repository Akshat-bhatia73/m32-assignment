"""Action Board mutations.

These are the agent's "tools" for the live board. Each function owns a short-lived DB session
and returns a JSON-serializable board event (dict) that the streamer forwards to the client as a
`data-action-item` part. Extraction is deterministic-after-LLM (the extractor node calls these
directly), which is far more reliable than a free-form tool-calling loop.
"""

import uuid
from datetime import date

from app.database import SessionLocal
from app.models import ActionItem, Meeting


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _event(item: ActionItem, op: str) -> dict:
    """Serialize an action item into a board event for the data-action-item stream part."""
    return {
        "op": op,  # "created" | "updated" | "deleted"
        "id": str(item.id),
        "session_id": str(item.session_id),
        "task": item.task,
        "owner": item.owner,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def create_meeting(
    *, session_id: uuid.UUID, user_id: uuid.UUID, raw_text: str, source: str = "paste"
) -> uuid.UUID:
    with SessionLocal() as db:
        meeting = Meeting(
            session_id=session_id, user_id=user_id, raw_text=raw_text, source=source
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        return meeting.id


def add_action_item(
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    meeting_id: uuid.UUID | None,
    task: str,
    owner: str | None = None,
    due_date: str | None = None,
) -> dict:
    with SessionLocal() as db:
        item = ActionItem(
            session_id=session_id,
            user_id=user_id,
            meeting_id=meeting_id,
            task=task,
            owner=owner,
            due_date=_parse_date(due_date),
            status="open",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return _event(item, "created")
