"""Tests for custom in-memory rate limiting middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core import config
from app.middleware.rate_limit import RateLimitMiddleware


async def test_rate_limit_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    """After N requests per minute, service must return 429."""
    monkeypatch.setattr(config.settings, "rate_limit_per_minute", 2)

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/healthz")
        r2 = await client.get("/healthz")
        r3 = await client.get("/healthz")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
