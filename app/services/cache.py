"""
Redis-based generic cache helpers.

Low-level cache utilities intended for repositories only.

Responsibilities:
- Build stable Redis keys (via caller-provided key or helper builders).
- Serialize / deserialize Pydantic DTOs to/from JSON.
- Provide minimal cache primitives: get/set/invalidate.

Non-responsibilities:
- Business rules (ownership, permissions).
- Database access.
- HTTP concerns.
- Key naming conventions across domains (caller owns the key design).

Usage:
    This module MUST be used only from repositories (e.g. OrdersRepository),
    never directly from API routes or business services.
"""

from __future__ import annotations

import uuid
from typing import Any, TypeVar

from pydantic import BaseModel
from redis.asyncio import Redis

T = TypeVar("T", bound=BaseModel)


def cache_key(prefix: str, entity_id: uuid.UUID) -> str:
    """
    Build a Redis key for an entity.

    Args:
        prefix: Namespace/prefix (e.g. "order", "user", "invoice").
        entity_id: Entity UUID.

    Returns:
        Redis key string in the format: "{prefix}:{uuid}".
    """
    return f"{prefix}:{entity_id}"


async def get_cached(
    redis: Redis[str],
    key: str,
    model: type[T],
) -> T | None:
    """
    Retrieve a cached model from Redis by key.

    Args:
        redis: Redis client instance (decode_responses=True recommended).
        key: Full Redis key.
        model: Pydantic model class to deserialize into.

    Returns:
        Parsed Pydantic model instance if present in cache, otherwise None.

    Raises:
        pydantic.ValidationError: If cached JSON is invalid for the model.
        ValueError: If JSON parsing fails (rare if producer is consistent).
    """
    raw: str | None = await redis.get(key)
    if raw is None:
        return None
    return model.model_validate_json(raw)


async def set_cached(
    redis: Redis[str],
    key: str,
    value: T,
    ttl_seconds: int,
) -> None:
    """
    Store a Pydantic model in Redis cache with TTL.

    Args:
        redis: Redis client instance (decode_responses=True recommended).
        key: Full Redis key.
        value: Pydantic model instance to cache.
        ttl_seconds: TTL in seconds.

    Side effects:
        - Overwrites existing cache entry for the same key.
    """
    await redis.setex(
        name=key,
        time=ttl_seconds,
        value=value.model_dump_json(),
    )


async def invalidate_key(redis: Redis[Any], key: str) -> None:
    """
    Remove a cache entry by key.

    Args:
        redis: Redis client instance.
        key: Full Redis key.

    Notes:
        - Safe to call even if the key does not exist.
    """
    await redis.delete(key)
