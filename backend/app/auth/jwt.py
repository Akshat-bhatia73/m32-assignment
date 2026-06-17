"""JWT encode/decode for session tokens."""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.config import settings

COOKIE_NAME = "m32_session"


def create_access_token(subject: str) -> str:
    """Create a signed JWT whose `sub` is the user id."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(UTC)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the subject (user id) if the token is valid, else None."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None
