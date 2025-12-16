from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi_limiter.depends import RateLimiter

from app.api.deps import AuthServiceDep
from app.schemas.auth import Token, UserCreate, UserRead

"""
Authentication API routes.

This module defines HTTP endpoints for:
- User registration.
- User login (token issuance).

Responsibilities:
- Validate request/response schemas (Pydantic).
- Enforce rate limits for abuse protection.
- Map domain/service errors to HTTP errors.

Non-responsibilities:
- Database access (handled by repositories).
- Password hashing / token creation (handled by services/security utilities).
"""


router = APIRouter(tags=["auth"])

# Rate limits are applied at the route level to protect the auth endpoints
# from brute-force and credential-stuffing attacks.
_rate_limits = [
    Depends(RateLimiter(times=5, seconds=60)),
    Depends(RateLimiter(times=100, seconds=3600)),
]


@router.post("/register/", response_model=UserRead, dependencies=_rate_limits)
async def register_user(payload: UserCreate, service: AuthServiceDep) -> UserRead:
    """
    Register a new user.

    Args:
        payload: Registration data (email + password).
        service: AuthService dependency.

    Returns:
        UserRead: Public user representation (id, email).

    Raises:
        HTTPException:
            - 400 if the email is already registered.
    """
    try:
        return await service.register(payload)
    except ValueError as err:
        # Service uses a stable error code string to indicate this condition.
        if str(err) == "email_exists":
            raise HTTPException(status_code=400, detail="Email already registered") from err
        raise


@router.post("/token/", response_model=Token, dependencies=_rate_limits)
async def login_for_access_token(payload: UserCreate, service: AuthServiceDep) -> Token:
    """
    Authenticate a user and return an access token.

    Args:
        payload: Login data (email + password).
        service: AuthService dependency.

    Returns:
        Token: JWT access token payload.

    Raises:
        HTTPException:
            - 401 for incorrect credentials.
    """
    try:
        return await service.login(payload)
    except PermissionError as err:
        raise HTTPException(status_code=401, detail="Incorrect email or password") from err
