"""A submitted meeting transcript / notes blob."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Meeting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "meetings"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    raw_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="paste")  # "paste" | "upload"
