"""Action Board mutations.

These are the agent's "tools" for the live board. Each function owns a short-lived DB session
and returns a JSON-serializable board event (dict) that the streamer forwards to the client as a
`data-action-item` part. Extraction is deterministic-after-LLM (the extractor node calls these
directly), which is far more reliable than a free-form tool-calling loop.
"""

import uuid
from datetime import date

from sqlalchemy import select

from app.database import SessionLocal
from app.models import ActionItem, Meeting
from app.models.action_item import ACTION_STATUSES


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


def list_items(session_id: uuid.UUID, *, open_only: bool = False) -> list[dict]:
    """Lightweight board snapshot for grounding the agent's edits (id + fields)."""
    with SessionLocal() as db:
        stmt = select(ActionItem).where(ActionItem.session_id == session_id)
        if open_only:
            stmt = stmt.where(ActionItem.status == "open")
        rows = db.scalars(stmt.order_by(ActionItem.created_at)).all()
        return [
            {
                "id": str(r.id),
                "task": r.task,
                "owner": r.owner,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "status": r.status,
                "external_ref": r.external_ref,
            }
            for r in rows
        ]


_CLEAR = "__clear__"  # sentinel: explicitly null out a field


def update_action_item(
    action_id: str,
    *,
    task: str | None = None,
    owner: str | None = None,
    due_date: str | None = None,
    status: str | None = None,
) -> dict | None:
    """Update fields on an item. Pass the _CLEAR sentinel to null owner/due_date."""
    with SessionLocal() as db:
        item = db.get(ActionItem, uuid.UUID(action_id))
        if item is None:
            return None
        if task is not None:
            item.task = task
        if owner is not None:
            item.owner = None if owner == _CLEAR else owner
        if due_date is not None:
            item.due_date = None if due_date == _CLEAR else _parse_date(due_date)
        if status is not None and status in ACTION_STATUSES:
            item.status = status
        db.commit()
        db.refresh(item)
        return _event(item, "updated")


def set_status(action_id: str, status: str, *, external_ref: str | None = None) -> dict | None:
    with SessionLocal() as db:
        item = db.get(ActionItem, uuid.UUID(action_id))
        if item is None or status not in ACTION_STATUSES:
            return None
        item.status = status
        if external_ref is not None:
            item.external_ref = external_ref
        db.commit()
        db.refresh(item)
        return _event(item, "updated")


def delete_action_item(action_id: str) -> dict | None:
    with SessionLocal() as db:
        item = db.get(ActionItem, uuid.UUID(action_id))
        if item is None:
            return None
        event = _event(item, "deleted")
        db.delete(item)
        db.commit()
        return event
