"""Per-session pending-action store (the confirmation gate's memory)."""

import uuid
from typing import Any

from app.database import SessionLocal
from app.models import ChatSession


def get_pending_action(session_id: uuid.UUID) -> dict[str, Any] | None:
    with SessionLocal() as db:
        session = db.get(ChatSession, session_id)
        return session.pending_action if session else None


def set_pending_action(session_id: uuid.UUID, action: dict[str, Any] | None) -> None:
    with SessionLocal() as db:
        session = db.get(ChatSession, session_id)
        if session is None:
            return
        session.pending_action = action
        db.commit()
