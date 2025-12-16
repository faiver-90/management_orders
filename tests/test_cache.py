"""Tests for Redis caching helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from redis.asyncio import Redis

from app.db.models import OrderStatus
from app.schemas.orders import OrderRead
from app.services.cache import cache_key, get_cached_order, invalidate_order, set_cached_order


@pytest.fixture()
def sample_order() -> OrderRead:
    """Create a sample order for caching tests."""
    return OrderRead(
        id=uuid.uuid4(),
        user_id=1,
        items={"a": 1},
        total_price=10.0,
        status=OrderStatus.PENDING,
        created_at=datetime.now(tz=UTC),
    )


async def test_cache_roundtrip(fake_redis: Redis[Any], sample_order: OrderRead) -> None:
    """Cached order should be retrievable and invalidatable."""
    assert cache_key(sample_order.id).startswith("order:")
    assert await get_cached_order(fake_redis, sample_order.id) is None

    await set_cached_order(fake_redis, sample_order)
    cached = await get_cached_order(fake_redis, sample_order.id)
    assert cached == sample_order

    await invalidate_order(fake_redis, sample_order.id)
    assert await get_cached_order(fake_redis, sample_order.id) is None
