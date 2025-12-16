"""Tests for rate limiting middleware."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core import config


@pytest.mark.asyncio
async def test_rate_limit_exceeded(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """After N requests per minute, service must return 429."""
    monkeypatch.setattr(config.settings, "rate_limit_per_minute", 2)

    # healthz does not require auth; easiest to test
    r1 = await client.get("/healthz")
    r2 = await client.get("/healthz")
    r3 = await client.get("/healthz")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
