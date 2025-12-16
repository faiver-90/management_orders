"""
Redis-based cache helpers for order retrieval.

This module contains low-level cache utilities used by repositories.
It implements a simple key-value cache for orders with a fixed TTL.

Responsibilities:
- Build stable Redis keys for orders.
- Serialize / deserialize OrderRead DTOs.
- Provide simple cache-aside primitives (get/set/invalidate).

Non-responsibilities:
- Business rules (ownership, permissions).
- Database access.
- HTTP concerns.

Usage:
    This module MUST be used only from repositories (e.g. OrdersRepository),
    never directly from API routes or services.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from redis.asyncio import Redis

from app.schemas.orders import OrderRead

# Default time-to-live for cached orders (in seconds)
CACHE_TTL_SECONDS = 300


def cache_key(order_id: uuid.UUID) -> str:
    """
    Build a Redis key for storing an order.

    Args:
        order_id: Order UUID.

    Returns:
        Redis key string in the format: "order:{uuid}".
    """
    return f"order:{order_id}"


async def get_cached_order(redis: Redis[Any], order_id: uuid.UUID) -> OrderRead | None:
    """
    Retrieve an order from Redis cache.

    Args:
        redis: Redis client instance.
        order_id: Order UUID.

    Returns:
        OrderRead DTO if present in cache, otherwise None.

    Notes:
        - Cache miss is not an error and must be handled by the caller.
        - Deserialization errors will propagate to the caller.
    """
    raw = await redis.get(cache_key(order_id))
    if raw is None:
        return None

    data = json.loads(raw)
    return OrderRead.model_validate(data)


async def set_cached_order(redis: Redis[Any], order: OrderRead) -> None:
    """
    Store an order in Redis cache with TTL.

    Args:
        redis: Redis client instance.
        order: OrderRead DTO to cache.

    Side effects:
        - Overwrites existing cache entry for the same order id.
    """
    await redis.setex(
        cache_key(order.id),
        CACHE_TTL_SECONDS,
        order.model_dump_json(),
    )


async def invalidate_order(redis: Redis[Any], order_id: uuid.UUID) -> None:
    """
    Remove an order from cache.

    Args:
        redis: Redis client instance.
        order_id: Order UUID.

    Notes:
        - Safe to call even if the key does not exist.
    """
    await redis.delete(cache_key(order_id))
