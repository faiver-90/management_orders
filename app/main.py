"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aio_pika
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from sqlalchemy import text

from app.api.deps import RedisDep, SessionDep
from app.api.routes.auth import router as auth_router
from app.api.routes.orders import router as orders_router
from app.core.config import get_settings
from app.tasks.celery_app import celery_app

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_client = redis.from_url(
        f"redis://{settings.redis_host}:{settings.redis_port}",
        encoding="utf-8",
        decode_responses=True,
    )
    await FastAPILimiter.init(redis_client)
    yield
    await redis_client.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Security: CORS protection
allowed_origins = [o.strip() for o in settings.api_cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.add_middleware(RateLimitMiddleware) # You can set a rate limit manually for the entire application.

app.include_router(auth_router)
app.include_router(orders_router)


@app.get("/healthz")
async def healthz(session: SessionDep, redis: RedisDep) -> dict[str, Any]:  # type: ignore
    status: dict[str, Any] = {}

    # Postgres
    try:
        await session.execute(text("SELECT 1"))
        status["postgres"] = "ok"
    except Exception as e:
        status["postgres"] = f"fail: {type(e).__name__}"

    # Redis
    try:
        pong = await redis.ping()
        status["redis"] = "ok" if pong else "fail"
    except Exception as e:
        status["redis"] = f"fail: {type(e).__name__}"

    # RabbitMQ
    try:
        conn = await aio_pika.connect_robust(settings.rabbitmq_dsn)
        await conn.close()
        status["rabbitmq"] = "ok"
    except Exception as e:
        status["rabbitmq"] = f"fail: {type(e).__name__}"

    # Celery worker
    try:
        replies = celery_app.control.ping(timeout=1.0)
        status["celery_worker"] = "ok" if replies else "fail"
    except Exception as e:
        status["celery_worker"] = f"fail: {type(e).__name__}"

    # Итог
    if any(v != "ok" for v in status.values()):
        raise HTTPException(status_code=503, detail=status)

    return {"status": "ok", "detail": status}
