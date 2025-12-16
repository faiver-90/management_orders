"""Tests for Redis caching helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from faker import Faker

from app.core.config import get_settings
from app.db.models import OrderStatus
from app.schemas.orders import OrderRead
from app.services.cache import cache_key, get_cached, invalidate_key, set_cached
from tests.conftest import FakeRedis

settings = get_settings()


@pytest.fixture()
def sample_order(faker: Faker, order_items: dict[str, int], order_price: float) -> OrderRead:
    """Create a sample order for caching tests."""
    return OrderRead(
        id=uuid.uuid4(),
        user_id=faker.random_int(min=1, max=10_000),
        items=order_items,
        total_price=order_price,
        status=OrderStatus.PENDING,
        created_at=datetime.now(tz=UTC),
    )


async def test_cache_roundtrip(fake_redis: FakeRedis, sample_order: OrderRead) -> None:
    key = cache_key("order", sample_order.id)

    assert key.startswith("order:")
    assert await get_cached(fake_redis, key, OrderRead) is None  # type: ignore

    await set_cached(
        redis=fake_redis,  # type: ignore
        key=key,
        value=sample_order,
        ttl_seconds=settings.cache_ttl_seconds,
    )

    cached = await get_cached(fake_redis, key, OrderRead)  # type: ignore
    assert cached == sample_order

    await invalidate_key(fake_redis, key)  # type: ignore
    assert await get_cached(fake_redis, key, OrderRead) is None  # type: ignore
