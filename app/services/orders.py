"""Order business logic and repository-like operations."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Order, OrderStatus
from app.schemas.orders import OrderCreate, OrderRead, OrderUpdateStatus
from app.services.messaging import Publisher


async def create_order(
    session: AsyncSession, user_id: int, data: OrderCreate, publisher: Publisher
) -> OrderRead:
    """Create an order, persist it, and publish `new_order` event."""
    order = Order(
        user_id=user_id, items=data.items, total_price=data.total_price, status=OrderStatus.PENDING
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    await publisher.publish_new_order(order.id)
    return OrderRead.model_validate(order, from_attributes=True)


async def get_order(session: AsyncSession, order_id: uuid.UUID) -> OrderRead:
    """Get order from DB; raise ValueError if not found."""
    stmt = select(Order).where(Order.id == order_id)
    res = await session.execute(stmt)
    order = res.scalar_one_or_none()
    if order is None:
        raise ValueError("Order not found")
    return OrderRead.model_validate(order, from_attributes=True)


async def update_order_status(
    session: AsyncSession, order_id: uuid.UUID, data: OrderUpdateStatus
) -> OrderRead:
    """Update order status; raise ValueError if order does not exist."""
    stmt = select(Order).where(Order.id == order_id)
    res = await session.execute(stmt)
    order = res.scalar_one_or_none()
    if order is None:
        raise ValueError("Order not found")
    order.status = data.status
    await session.commit()
    await session.refresh(order)
    return OrderRead.model_validate(order, from_attributes=True)


async def list_orders_for_user(session: AsyncSession, user_id: int) -> list[OrderRead]:
    """Return all orders for a user."""
    stmt = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    res = await session.execute(stmt)
    orders = res.scalars().all()
    return [OrderRead.model_validate(o, from_attributes=True) for o in orders]
