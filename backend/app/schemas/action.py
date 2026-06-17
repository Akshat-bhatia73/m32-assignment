"""Action item schemas (Action Board)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ActionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    task: str
    owner: str | None = None
    due_date: date | None = None
    status: str
    external_ref: str | None = None
    created_at: datetime
    updated_at: datetime


class ActionItemCreate(BaseModel):
    task: str
    owner: str | None = None
    due_date: date | None = None


class ActionItemUpdate(BaseModel):
    task: str | None = None
    owner: str | None = None
    due_date: date | None = None
    status: str | None = None
