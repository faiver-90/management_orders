"""Authentication endpoints: /register/ and /token/."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi_limiter.depends import RateLimiter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.schemas.auth import Token, UserCreate, UserRead

router = APIRouter(tags=["auth"])


@router.post(
    "/register/",
    response_model=UserRead,
    dependencies=[
        Depends(RateLimiter(times=5, seconds=60)),  # 5 в минуту
        Depends(RateLimiter(times=100, seconds=3600)),  # 100 в час
    ],
)
async def register_user(session: SessionDep, payload: UserCreate) -> UserRead:
    """Register a user by email/password."""
    stmt = select(User).where(User.email == payload.email)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserRead(id=user.id, email=user.email)


@router.post(
    "/token/",
    response_model=Token,
    dependencies=[
        Depends(RateLimiter(times=5, seconds=60)),  # 5 в минуту
        Depends(RateLimiter(times=100, seconds=3600)),  # 100 в час
    ],
)
async def login_for_access_token(
    session: SessionDep,
    payload: UserCreate,
) -> Token:
    """Login endpoint that returns a JWT token."""
    stmt = select(User).where(User.email == payload.email)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)
