"""Chat session create/list + message history (in-session memory)."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import ChatSession, Message
from app.schemas.chat import MessageOut, SessionCreate, SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _owned_session(db: DbSession, session_id: uuid.UUID, user_id: uuid.UUID) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, current_user: CurrentUser, db: DbSession) -> ChatSession:
    session = ChatSession(user_id=current_user.id, title=payload.title or "New session")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("", response_model=list[SessionOut])
def list_sessions(current_user: CurrentUser, db: DbSession) -> list[ChatSession]:
    rows = db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
    ).all()
    return list(rows)


@router.get("/{session_id}/messages", response_model=list[MessageOut])
def list_messages(
    session_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> list[Message]:
    _owned_session(db, session_id, current_user.id)
    rows = db.scalars(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    ).all()
    return list(rows)
