"""
Orders repository (ORM + cache).

This repository is the single place that knows about:
- SQLAlchemy persistence (PostgreSQL).
- Redis cache.

It implements cache-aside:
- Read: try Redis first; on miss load from DB; then populate Redis.
- Write: write to DB; then invalidate/update Redis.

Keeping this logic here means:
- API handlers do not know about Redis or SQLAlchemy.
- Business services work with repository methods and domain-level errors only.
"""

from __future__ import annotations

import uuid

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Order
from app.schemas.orders import OrderCreate, OrderRead, OrderUpdateStatus
from app.services.cache import cache_key, get_cached, invalidate_key, set_cached

settings = get_settings()


class OrdersRepository:
    """
    Data access layer for Order entities, with optional Redis caching.

    Args:
        session: SQLAlchemy async session.
        redis: Redis client. If None, repository works without caching.
    """

    def __init__(self, session: AsyncSession, redis: Redis[str] | None = None) -> None:
        self._session = session
        self._redis = redis

    @staticmethod
    def _order_cache_key(order_id: uuid.UUID) -> str:
        return cache_key("order", order_id)

    async def create(self, user_id: int, data: OrderCreate) -> OrderRead:
        """
        Create a new order for a user.

        Args:
            user_id: Owner of the order.
            data: OrderCreate payload.

        Returns:
            OrderRead DTO of the created order.
        """
        order = Order(
            user_id=user_id,
            items=data.items,
            total_price=data.total_price,
            status="PENDING",
        )
        self._session.add(order)
        await self._session.commit()
        await self._session.refresh(order)

        read = OrderRead.model_validate(order, from_attributes=True)

        # Optional: warm the cache for subsequent reads.
        if self._redis is not None:
            await set_cached(
                redis=self._redis,
                key=self._order_cache_key(read.id),
                value=read,
                ttl_seconds=settings.cache_ttl_seconds,
            )

        return read

    async def get(self, order_id: uuid.UUID) -> OrderRead:
        """
        Get an order by id (cache-aside).

        Args:
            order_id: Order UUID.

        Returns:
            OrderRead DTO.

        Raises:
            ValueError: If order not found in DB.
        """
        key = self._order_cache_key(order_id)

        # 1) Cache
        if self._redis is not None:
            cached = await get_cached(self._redis, key, OrderRead)
            if cached is not None:
                return cached

        # 2) DB
        stmt = select(Order).where(Order.id == order_id)
        res = await self._session.execute(stmt)
        order = res.scalar_one_or_none()
        if order is None:
            raise ValueError("Order not found")

        read = OrderRead.model_validate(order, from_attributes=True)

        # 3) Populate cache
        if self._redis is not None:
            await set_cached(
                redis=self._redis,
                key=key,
                value=read,
                ttl_seconds=settings.cache_ttl_seconds,
            )

        return read

    async def update_status(self, order_id: uuid.UUID, data: OrderUpdateStatus) -> OrderRead:
        """
        Update order status and keep cache consistent.

        Args:
            order_id: Order UUID.
            data: New status payload.

        Returns:
            Updated OrderRead DTO.

        Raises:
            ValueError: If order does not exist.
        """
        stmt = select(Order).where(Order.id == order_id)
        res = await self._session.execute(stmt)
        order = res.scalar_one_or_none()
        if order is None:
            raise ValueError("Order not found")

        order.status = data.status
        await self._session.commit()
        await self._session.refresh(order)

        read = OrderRead.model_validate(order, from_attributes=True)

        if self._redis is not None:
            key = self._order_cache_key(order_id)
            # Either invalidate and repopulate, or simply overwrite.
            await invalidate_key(self._redis, key)
            await set_cached(
                redis=self._redis,
                key=key,
                value=read,
                ttl_seconds=settings.cache_ttl_seconds,
            )

        return read

    async def list_for_user(self, user_id: int) -> list[OrderRead]:
        """
        List orders for a user.

        Notes:
            This method intentionally does not use cache by default.
            Caching lists requires careful invalidation strategy and key design.

        Args:
            user_id: User id.

        Returns:
            List of OrderRead DTOs (newest first).
        """
        stmt = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        res = await self._session.execute(stmt)
        orders = res.scalars().all()
        return [OrderRead.model_validate(o, from_attributes=True) for o in orders]
