from __future__ import annotations

import uuid

from app.repositories.orders import OrdersRepository
from app.schemas.orders import OrderCreate, OrderRead, OrderUpdateStatus
from app.services.messaging import Publisher


class OrdersService:
    """
    Orders application service.

    This service contains business logic for working with orders.
    It orchestrates repositories and external side effects (messaging),
    but does NOT perform direct database or cache access.

    Responsibilities:
    - Enforce business rules (ownership, permissions).
    - Coordinate order lifecycle actions.
    - Publish domain events after successful operations.

    Non-responsibilities:
    - SQL queries or cache logic (handled by OrdersRepository).
    - HTTP concerns (status codes, FastAPI exceptions).
    """

    def __init__(self, repo: OrdersRepository, publisher: Publisher) -> None:
        """
        Initialize OrdersService.

        Args:
            repo: OrdersRepository instance.
            publisher: Messaging publisher used to emit domain events.
        """
        self._repo = repo
        self._publisher = publisher

    async def create_order(self, user_id: int, payload: OrderCreate) -> OrderRead:
        """
        Create a new order for a user.

        Business flow:
        1. Persist the order via repository.
        2. Publish "new order created" domain event.

        Args:
            user_id: ID of the user creating the order.
            payload: OrderCreate payload.

        Returns:
            OrderRead DTO representing the created order.
        """
        order = await self._repo.create(user_id=user_id, data=payload)
        await self._publisher.publish_new_order(order.id)
        return order

    async def get_order_for_user(self, user_id: int, order_id: uuid.UUID) -> OrderRead:
        """
        Retrieve an order if it belongs to the given user.

        Args:
            user_id: ID of the requesting user.
            order_id: Order UUID.

        Returns:
            OrderRead DTO.

        Raises:
            PermissionError: If the order belongs to a different user.
            ValueError: If the order does not exist.
        """
        order = await self._repo.get(order_id)
        if order.user_id != user_id:
            raise PermissionError("Forbidden")
        return order

    async def update_status_for_user(
        self,
        user_id: int,
        order_id: uuid.UUID,
        payload: OrderUpdateStatus,
    ) -> OrderRead:
        """
        Update order status if the order belongs to the given user.

        Notes:
            Ownership is checked before performing the update.

        Args:
            user_id: ID of the requesting user.
            order_id: Order UUID.
            payload: New order status payload.

        Returns:
            Updated OrderRead DTO.

        Raises:
            PermissionError: If the order belongs to a different user.
            ValueError: If the order does not exist.
        """
        existing = await self._repo.get(order_id)
        if existing.user_id != user_id:
            raise PermissionError("Forbidden")

        return await self._repo.update_status(order_id=order_id, data=payload)

    async def list_orders_for_user(self, user_id: int) -> list[OrderRead]:
        """
        List all orders for a given user.

        Args:
            user_id: User ID.

        Returns:
            List of OrderRead DTOs.
        """
        return await self._repo.list_for_user(user_id=user_id)
