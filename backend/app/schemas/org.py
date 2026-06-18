"""Organization / team request + response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrgMemberOut(BaseModel):
    id: str
    name: str | None = None
    email: EmailStr
    role: str


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str | None = None
    role: str
    status: str
    created_at: datetime


class OrgOut(BaseModel):
    id: uuid.UUID
    name: str
    role: str  # the current user's role in this org
    member_cap: int
    members: list[OrgMemberOut]
    invites: list[InvitationOut]


class OrgUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class InviteCreate(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=200)
