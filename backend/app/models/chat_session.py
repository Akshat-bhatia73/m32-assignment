"""A chat session groups messages, a meeting, and its action items."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class ChatSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Org that owns this session (the workspace it's shared in). Nullable for legacy rows.
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), default="New session")
    # Latest external action awaiting user confirmation (send email / create events), or null.
    pending_action: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    # The session's creator ("meeting owner"). Eager-loaded so listing sessions can expose who
    # owns each one without an N+1 — drives the read-only-for-non-owners rule in the UI.
    owner: Mapped["User"] = relationship("User", lazy="joined")  # noqa: F821

    @property
    def owner_id(self) -> uuid.UUID:
        return self.user_id

    @property
    def owner_name(self) -> str | None:
        return self.owner.name if self.owner else None
