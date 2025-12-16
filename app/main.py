"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter

from app.api.routes.auth import router as auth_router
from app.api.routes.orders import router as orders_router
from app.core.config import get_settings

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


@app.get("/healthz", tags=["meta"])
async def healthcheck() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
