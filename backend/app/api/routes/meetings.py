"""Submit a meeting transcript (paste) or extract text from an uploaded file/image."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict

from app.api.deps import CurrentMembership, CurrentUser, DbSession
from app.models import ChatSession, Meeting
from app.services.transcript import TranscriptError, extract_transcript


class MeetingCreate(BaseModel):
    session_id: uuid.UUID
    raw_text: str
    source: str = "paste"


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    source: str


class ExtractedTranscript(BaseModel):
    text: str
    filename: str
    source: str  # "upload" (file) | "image"


router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/extract", response_model=ExtractedTranscript)
async def extract_upload(
    current_user: CurrentUser, file: Annotated[UploadFile, File()]
) -> ExtractedTranscript:
    """Turn an uploaded transcript file or screenshot into plain text for the chat composer."""
    data = await file.read()
    content_type = file.content_type or ""
    try:
        text = await extract_transcript(file.filename or "upload", content_type, data)
    except TranscriptError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    is_image = content_type.startswith("image/") or (file.filename or "").lower().endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".gif")
    )
    return ExtractedTranscript(
        text=text, filename=file.filename or "upload", source="image" if is_image else "upload"
    )


@router.post("", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
def create_meeting(
    payload: MeetingCreate, current_user: CurrentUser, membership: CurrentMembership, db: DbSession
) -> Meeting:
    session = db.get(ChatSession, payload.session_id)
    if session is None or session.org_id != membership.org_id:
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
