"""Celery application instance."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "order_service",
    broker=str(settings.celery_broker_url),
    backend=settings.celery_result_backend,
)
celery_app.conf.task_always_eager = False
celery_app.autodiscover_tasks(["app.tasks"])
import app.tasks.worker_tasks  # noqa
