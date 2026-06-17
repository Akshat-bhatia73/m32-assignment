"""User account model. Supports email/password and Google OAuth (nullable fields)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Nullable for OAuth-only accounts.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Google "sub" claim, set when the account is linked via OAuth.
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
