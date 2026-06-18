"""Action items — this table *is* the Action Board."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UpdatedAtMixin, UUIDMixin

# status lifecycle: open -> scheduled / sent -> done
ACTION_STATUSES = ("open", "scheduled", "sent", "done")


class ActionItem(UUIDMixin, TimestampMixin, UpdatedAtMixin, Base):
    __tablename__ = "action_items"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Org that owns this item (so the board is shared across the workspace). Nullable for legacy.
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True,
        index=True,
    )

    task: Mapped[str] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    # External reference (e.g. Google Calendar event id) once scheduled.
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
