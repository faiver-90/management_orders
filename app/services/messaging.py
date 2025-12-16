"""RabbitMQ messaging helpers for publishing `new_order` events."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Protocol

import aio_pika


@dataclass(frozen=True)
class NewOrderEvent:
    """Message payload for `new_order`."""

    order_id: uuid.UUID

    def to_bytes(self) -> bytes:
        """Serialize event to bytes."""
        return json.dumps({"order_id": str(self.order_id)}).encode("utf-8")


class Publisher(Protocol):
    """Protocol for publishing messages (useful for testing)."""

    async def publish_new_order(self, order_id: uuid.UUID) -> None:
        """Publish new order event."""


class RabbitPublisher:
    """RabbitMQ publisher implementation."""

    def __init__(self, dsn: str, queue_name: str) -> None:
        self._dsn = dsn
        self._queue_name = queue_name

    async def publish_new_order(self, order_id: uuid.UUID) -> None:
        """Publish `new_order` message to the configured queue."""
        connection = await aio_pika.connect_robust(self._dsn)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(self._queue_name, durable=True)
            message = aio_pika.Message(
                body=NewOrderEvent(order_id).to_bytes(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await channel.default_exchange.publish(message, routing_key=self._queue_name)
