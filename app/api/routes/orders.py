"""Order endpoints with auth, Redis caching, and messaging."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import RedisDep, SessionDep, UserIdDep, get_publisher
from app.schemas.orders import OrderCreate, OrderRead, OrdersList, OrderUpdateStatus
from app.services.cache import get_cached_order, invalidate_order, set_cached_order
from app.services.orders import create_order, get_order, list_orders_for_user, update_order_status

router = APIRouter(tags=["orders"])


@router.post("/orders/", response_model=OrderRead)
async def create_order_endpoint(
    payload: OrderCreate,
    session: SessionDep,
    user_id: UserIdDep,
) -> OrderRead:
    """Create an order for the current user and publish `new_order` event."""
    publisher = get_publisher()
    order = await create_order(session, user_id, payload, publisher)
    return order


@router.get("/orders/{order_id}/", response_model=OrderRead)
async def get_order_endpoint(
    order_id: uuid.UUID, session: SessionDep, redis: RedisDep, user_id: UserIdDep
) -> OrderRead:  # type: ignore[type-arg]
    """Get order by id; first try Redis cache."""
    cached = await get_cached_order(redis, order_id)
    if cached is not None:
        return cached
    try:
        order = await get_order(session, order_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail="Order not found") from err
    if order.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await set_cached_order(redis, order)
    return order


@router.patch("/orders/{order_id}/", response_model=OrderRead)
async def update_order_endpoint(
    order_id: uuid.UUID,
    payload: OrderUpdateStatus,
    session: SessionDep,
    redis: RedisDep,
    user_id: UserIdDep,  # type: ignore[type-arg]
) -> OrderRead:
    """Update order status and refresh cache."""
    try:
        order = await get_order(session, order_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail="Order not found") from err
    if order.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    updated = await update_order_status(session, order_id, payload)
    await invalidate_order(redis, order_id)
    await set_cached_order(redis, updated)
    return updated


@router.get("/orders/user/{user_id}/", response_model=OrdersList)
async def list_user_orders_endpoint(
    user_id: int, session: SessionDep, current_user_id: UserIdDep
) -> OrdersList:
    """List orders for a user; only the user themselves may view the list."""
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    orders = await list_orders_for_user(session, user_id)
    return OrdersList(orders=orders)
