"""Background tasks executed by Celery workers."""
from __future__ import annotations

import time
import uuid

from app.tasks.celery_app import celery_app


@celery_app.task(name="process_order") # type: ignore
def process_order(order_id: str) -> str:
    """Fake processing task required by the specification."""
    parsed = uuid.UUID(order_id)
    time.sleep(2)
    message = f"Order {parsed} processed"
    print(message)
    return message
