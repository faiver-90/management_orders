"""RabbitMQ consumer that forwards `new_order` events to Celery."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.core.config import settings
from app.tasks.worker_tasks import process_order


async def handle_message(message: AbstractIncomingMessage) -> None:
    """Handle a single `new_order` event and enqueue Celery task."""
    async with message.process():
        payload: Any = json.loads(message.body.decode("utf-8"))
        order_id = uuid.UUID(str(payload["order_id"]))
        process_order.delay(str(order_id))


async def main() -> None:
    """Consume from RabbitMQ indefinitely."""
    connection = await aio_pika.connect_robust(settings.rabbitmq_dsn)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(settings.rabbitmq_queue, durable=True)
        await queue.consume(handle_message)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
