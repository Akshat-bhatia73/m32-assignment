"""Chat + session schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    title: str | None = None


class SessionUpdate(BaseModel):
    title: str


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime


class Artifact(BaseModel):
    """An attachment sent with a turn — an uploaded file or a long pasted text blob."""

    id: str
    name: str
    kind: str  # "file" | "image" | "paste"
    content: str
    mime: str | None = None


class DataPart(BaseModel):
    """A structured stream part persisted for replay on reload (e.g. an email draft card)."""

    type: str
    data: dict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    artifacts: list[Artifact] | None = None
    data_parts: list[DataPart] | None = None
    created_at: datetime


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    message: str
    artifacts: list[Artifact] = []
    # When true, re-run the last user turn and replace the last assistant reply (retry),
    # rather than recording a new user message.
    regenerate: bool = False
