"""
Messaging abstractions and implementations for order-related events.

This module defines:
- Event payload structures.
- Publisher protocol (interface).
- RabbitMQ-based publisher implementation.

Responsibilities:
- Define stable event contracts.
- Provide a concrete publisher for RabbitMQ.
- Decouple business logic from transport details.

Non-responsibilities:
- Business decisions (when to publish).
- Retry policies / dead-letter handling (can be added later).
- Message consumption (handled by consumers).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Protocol

import aio_pika


@dataclass(frozen=True)
class NewOrderEvent:
    """
    Event payload for a newly created order.

    Attributes:
        order_id: UUID of the created order.
    """

    order_id: uuid.UUID

    def to_bytes(self) -> bytes:
        """
        Serialize the event to bytes for message transport.

        Returns:
            UTF-8 encoded JSON bytes.

        Example payload:
            {"order_id": "<uuid>"}
        """
        return json.dumps({"order_id": str(self.order_id)}).encode("utf-8")


class Publisher(Protocol):
    """
    Messaging publisher protocol.

    This protocol allows services to depend on an abstract publisher,
    making them testable and decoupled from the concrete transport
    (RabbitMQ, Kafka, mock publisher, etc.).
    """

    async def publish_new_order(self, order_id: uuid.UUID) -> None:
        """
        Publish a `new_order` event.

        Args:
            order_id: UUID of the newly created order.
        """
        ...


class RabbitPublisher:
    """
    RabbitMQ-based implementation of the Publisher protocol.

    Notes:
        - Establishes a connection per publish call.
        - Suitable for low/medium throughput.
        - For high throughput, consider connection/channel pooling
          managed via application lifespan.
    """

    def __init__(self, dsn: str, queue_name: str) -> None:
        """
        Initialize RabbitMQ publisher.

        Args:
            dsn: RabbitMQ connection DSN.
            queue_name: Target queue for `new_order` events.
        """
        self._dsn = dsn
        self._queue_name = queue_name

    async def publish_new_order(self, order_id: uuid.UUID) -> None:
        """
        Publish a `new_order` event to RabbitMQ.

        Args:
            order_id: UUID of the created order.

        Side effects:
            - Declares the queue if it does not exist.
            - Publishes a persistent message.
        """
        connection = await aio_pika.connect_robust(self._dsn)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(self._queue_name, durable=True)

            message = aio_pika.Message(
                body=NewOrderEvent(order_id).to_bytes(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )

            await channel.default_exchange.publish(
                message,
                routing_key=self._queue_name,
            )
