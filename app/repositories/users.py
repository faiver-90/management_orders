from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

"""
Users repository.

A repository encapsulates persistence concerns (SQLAlchemy/DB access).
It provides a small, testable API for common user operations, keeping
database queries out of API handlers and business services.

This repository is intentionally free of HTTP concerns (no FastAPI types)
and free of crypto/auth concerns (password hashing is done elsewhere).
"""


class UsersRepository:
    """
    Data access layer for User entities.

    Args:
        session: SQLAlchemy async session scoped to the current request/unit-of-work.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        """
        Fetch a user by email.

        Args:
            email: User email address.

        Returns:
            User instance or None if not found.
        """
        stmt = select(User).where(User.email == email)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        """
        Fetch a user by database id.

        Args:
            user_id: User primary key.

        Returns:
            User instance or None if not found.
        """
        stmt = select(User).where(User.id == user_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, email: str, password_hash: str) -> User:
        """
        Create a new user.

        Notes:
            - Expects an already-hashed password.
            - Commits within the method (simple unit-of-work model).

        Args:
            email: User email.
            password_hash: Hashed password string.

        Returns:
            The created User model with refreshed fields (e.g., id).
        """
        user = User(email=email, password_hash=password_hash)
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user
