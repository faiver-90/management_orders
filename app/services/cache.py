"""Redis-based cache for order retrieval."""
from __future__ import annotations

import json
import uuid
from typing import Any

from redis.asyncio import Redis

from app.schemas.orders import OrderRead

CACHE_TTL_SECONDS = 300


def cache_key(order_id: uuid.UUID) -> str:
    """Build Redis key for an order."""
    return f"order:{order_id}"


async def get_cached_order(redis: Redis[Any], order_id: uuid.UUID) -> OrderRead | None:
    """Get order from cache; return None on cache miss."""
    raw = await redis.get(cache_key(order_id))
    if raw is None:
        return None
    data = json.loads(raw)
    return OrderRead.model_validate(data)


async def set_cached_order(redis: Redis[Any], order: OrderRead) -> None:
    """Set order in cache with TTL."""
    await redis.setex(cache_key(order.id), CACHE_TTL_SECONDS, order.model_dump_json())


async def invalidate_order(redis: Redis[Any], order_id: uuid.UUID) -> None:
    """Delete cached order."""
    await redis.delete(cache_key(order_id))
