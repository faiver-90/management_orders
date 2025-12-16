from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import OrdersServiceDep, UserIdDep
from app.schemas.orders import OrderCreate, OrderRead, OrdersList, OrderUpdateStatus

"""
Orders API routes.

This module exposes CRUD-like endpoints for orders and delegates all application
logic to OrdersService.

Responsibilities:
- HTTP concerns (status codes, request/response models, access checks at HTTP boundary).
- Mapping service-layer errors to HTTP exceptions.

Non-responsibilities:
- SQL queries, caching, or other persistence details (handled by repositories).
"""


router = APIRouter(tags=["orders"])


@router.post("/orders/", response_model=OrderRead)
async def create_order_endpoint(
    payload: OrderCreate,
    user_id: UserIdDep,
    service: OrdersServiceDep,
) -> OrderRead:
    """
    Create a new order for the current user.

    Args:
        payload: OrderCreate payload.
        user_id: Current authenticated user id.
        service: OrdersService dependency.

    Returns:
        Created order representation.
    """
    return await service.create_order(user_id=user_id, payload=payload)


@router.get("/orders/{order_id}/", response_model=OrderRead)
async def get_order_endpoint(
    order_id: uuid.UUID,
    user_id: UserIdDep,
    service: OrdersServiceDep,
) -> OrderRead:
    """
    Get an order by id if it belongs to the current user.

    Args:
        order_id: Order UUID.
        user_id: Current authenticated user id.
        service: OrdersService dependency.

    Returns:
        OrderRead DTO.

    Raises:
        HTTPException:
            - 404 if order not found.
            - 403 if order belongs to another user.
    """
    try:
        return await service.get_order_for_user(user_id=user_id, order_id=order_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail="Order not found") from err
    except PermissionError as err:
        raise HTTPException(status_code=403, detail="Forbidden") from err


@router.patch("/orders/{order_id}/", response_model=OrderRead)
async def update_order_endpoint(
    order_id: uuid.UUID,
    payload: OrderUpdateStatus,
    user_id: UserIdDep,
    service: OrdersServiceDep,
) -> OrderRead:
    """
    Update order status for the current user.

    Args:
        order_id: Order UUID.
        payload: New status payload.
        user_id: Current authenticated user id.
        service: OrdersService dependency.

    Returns:
        Updated order representation.

    Raises:
        HTTPException:
            - 404 if order not found.
            - 403 if user does not own the order.
    """
    try:
        return await service.update_status_for_user(
            user_id=user_id, order_id=order_id, payload=payload
        )
    except ValueError as err:
        raise HTTPException(status_code=404, detail="Order not found") from err
    except PermissionError as err:
        raise HTTPException(status_code=403, detail="Forbidden") from err


@router.get("/orders/user/{user_id}/", response_model=OrdersList)
async def list_user_orders_endpoint(
    user_id: int,
    current_user_id: UserIdDep,
    service: OrdersServiceDep,
) -> OrdersList:
    """
    List orders for a given user id.

    Access control:
        Only allows listing orders for the authenticated user (user_id == current_user_id).

    Args:
        user_id: Path user id whose orders are requested.
        current_user_id: Current authenticated user id.
        service: OrdersService dependency.

    Returns:
        OrdersList wrapper with items.

    Raises:
        HTTPException: 403 if user tries to access another user's orders.
    """
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    orders = await service.list_orders_for_user(user_id=user_id)
    return OrdersList(orders=orders)
