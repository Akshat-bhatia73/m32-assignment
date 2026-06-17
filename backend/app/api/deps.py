"""Shared FastAPI dependencies."""

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.jwt import COOKIE_NAME, decode_access_token
from app.database import get_db
from app.models import User

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    creds_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )
    if not token:
        raise creds_error
    subject = decode_access_token(token)
    if not subject:
        raise creds_error
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise creds_error from None
    user = db.get(User, user_id)
    if user is None:
        raise creds_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
