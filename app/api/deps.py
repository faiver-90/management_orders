"""FastAPI dependencies: DB session, Redis client, auth user extraction, publisher."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token, security
from app.db.session import get_session
from app.services.messaging import Publisher, RabbitPublisher


async def get_redis() -> AsyncGenerator[Redis[Any], None]:
    """Create Redis client for request lifetime."""
    redis: Redis[Any] = Redis.from_url(
        settings.redis_dsn,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        yield redis
    finally:
        close = redis.close
        res = close()
        if hasattr(res, "__await__"):
            await res



def get_publisher() -> Publisher:
    """Return RabbitMQ publisher (stateless factory)."""
    return RabbitPublisher(settings.rabbitmq_dsn, settings.rabbitmq_queue)


async def get_current_user_id(token: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> int:
    """Extract current user id from JWT token."""
    try:
        jwt_token = token.credentials
        subject = decode_token(jwt_token)
        return int(subject)
    except (ValueError, TypeError) as err:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials") from err


SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
UserIdDep = Annotated[int, Depends(get_current_user_id)]
