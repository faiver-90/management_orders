"""Security helpers: password hashing and JWT token creation/verification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

security = HTTPBearer(auto_error=True)

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """Hash a plain password."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain password against a hash."""
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(tz=UTC) + timedelta(
        minutes=expires_minutes or settings.jwt_access_token_expire_minutes
    )
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str:
    """Decode JWT token and return its subject (user id as string)."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise ValueError("Invalid token payload")
        return subject
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid token") from exc
