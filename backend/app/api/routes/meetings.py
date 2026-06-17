"""Submit a meeting transcript (paste). Upload parsing comes later."""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.api.deps import CurrentUser, DbSession
from app.models import ChatSession, Meeting


class MeetingCreate(BaseModel):
    session_id: uuid.UUID
    raw_text: str
    source: str = "paste"


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    source: str


router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
def create_meeting(payload: MeetingCreate, current_user: CurrentUser, db: DbSession) -> Meeting:
    session = db.get(ChatSession, payload.session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    meeting = Meeting(
        session_id=payload.session_id,
        user_id=current_user.id,
        raw_text=payload.raw_text,
        source=payload.source,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting
