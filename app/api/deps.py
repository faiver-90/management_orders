"""
FastAPI dependency providers.

This module wires together infrastructure and application layers via FastAPI `Depends`.
It contains factories/providers for:
- Database session (SQLAlchemy AsyncSession)
- Redis client
- JWT-based current user extraction
- Messaging publisher
- Repositories and services

Guidelines:
- Dependency functions should be lightweight and composable.
- Avoid doing heavy work at import time.
- Keep HTTP concerns (status codes/messages) in routers, not here.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated, Any, TypeAlias

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token, security
from app.db.session import get_session
from app.repositories.orders import OrdersRepository
from app.repositories.users import UsersRepository
from app.services.auth import AuthService
from app.services.messaging import Publisher, RabbitPublisher
from app.services.orders import OrdersService


async def get_redis() -> AsyncGenerator[Redis[Any], None]:
    """
    Provide a Redis client scoped to the request lifetime.

    Yields:
        Redis client configured from settings.

    Notes:
        - Uses `decode_responses=True`, so Redis returns strings.
        - Closes the client after request completion.
    """
    redis: Redis[Any] = Redis.from_url(
        settings.redis_dsn,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        yield redis
    finally:
        # redis.close() can be sync/async depending on the library version.
        close = redis.close
        res = close()
        if hasattr(res, "__await__"):
            await res


def get_publisher() -> Publisher:
    """
    Provide a messaging publisher.

    Returns:
        Publisher instance used to emit domain events.

    Notes:
        Publisher is created as a lightweight, stateless factory here.
        If you need connection pooling/lifecycle management, switch to lifespan-managed singleton.
    """
    return RabbitPublisher(settings.rabbitmq_dsn, settings.rabbitmq_queue)


async def get_current_user_id(
    token: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> int:
    """
    Extract current user id from the Authorization header (JWT bearer token).

    Args:
        token: Parsed auth credentials from FastAPI security dependency.

    Returns:
        User id as int.

    Raises:
        HTTPException: 401 if token is invalid or subject is not an int.
    """
    try:
        if token is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        jwt_token = token.credentials
        subject = decode_token(jwt_token)
        return int(subject)
    except (ValueError, TypeError) as err:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials") from err


def get_orders_repo(session: SessionDep, redis: RedisDep) -> OrdersRepository:  # type: ignore
    """
    Build OrdersRepository.

    Args:
        session: Database session dependency.
        redis: Redis client dependency.

    Returns:
        OrdersRepository instance.
    """
    return OrdersRepository(session=session, redis=redis)


def get_users_repo(session: SessionDep) -> UsersRepository:
    """
    Build UsersRepository.

    Args:
        session: Database session dependency.

    Returns:
        UsersRepository instance.
    """
    return UsersRepository(session=session)


def get_auth_service(
    users_repo: Annotated[UsersRepository, Depends(get_users_repo)],
) -> AuthService:
    """
    Build AuthService.

    Args:
        users_repo: UsersRepository dependency.

    Returns:
        AuthService instance.
    """
    return AuthService(users_repo=users_repo)


def get_orders_service(
    repo: Annotated[OrdersRepository, Depends(get_orders_repo)],
    publisher: Annotated[Publisher, Depends(get_publisher)],
) -> OrdersService:
    """
    Build OrdersService.

    Args:
        repo: OrdersRepository dependency.
        publisher: Publisher dependency.

    Returns:
        OrdersService instance.
    """
    return OrdersService(repo=repo, publisher=publisher)


# ---- Public dependency aliases (use these in routers) ----

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep: TypeAlias = Annotated[Redis, Depends(get_redis)]
UserIdDep = Annotated[int, Depends(get_current_user_id)]
OrdersServiceDep = Annotated[OrdersService, Depends(get_orders_service)]
