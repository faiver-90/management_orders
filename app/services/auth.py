from __future__ import annotations

from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.users import UsersRepository
from app.schemas.auth import Token, UserCreate, UserRead

"""
Authentication service.

Contains the application/business logic for:
- user registration
- user login and JWT issuance

This layer must NOT:
- talk HTTP (status codes, FastAPI exceptions)
- execute SQL queries directly (use repositories)
"""


class AuthService:
    """
    Authentication use-cases.

    Args:
        users_repo: Repository used for user persistence and lookups.
    """

    def __init__(self, users_repo: UsersRepository) -> None:
        self._users_repo = users_repo

    async def register(self, payload: UserCreate) -> UserRead:
        """
        Register a new user.

        Args:
            payload: UserCreate payload (email + password).

        Returns:
            UserRead DTO of the created user.

        Raises:
            ValueError: "email_exists" when email is already registered.
        """
        existing = await self._users_repo.get_by_email(payload.email)
        if existing is not None:
            raise ValueError("email_exists")

        user = await self._users_repo.create(
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        return UserRead(id=user.id, email=user.email)

    async def login(self, payload: UserCreate) -> Token:
        """
        Authenticate a user and issue a JWT access token.

        Args:
            payload: UserCreate payload (email + password).

        Returns:
            Token DTO (access_token).

        Raises:
            PermissionError: "bad_credentials" if email/password is invalid.
        """
        user = await self._users_repo.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise PermissionError("bad_credentials")

        token = create_access_token(subject=str(user.id))
        return Token(access_token=token)
