"""Custom in-memory rate limiting middleware.

This intentionally avoids external state for simplicity. In production, a distributed limiter is recommended.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.config import get_settings

settings = get_settings()


@dataclass(frozen=True)
class Bucket:
    """Token bucket state for one client."""

    reset_at: float
    count: int


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that blocks requests above a per-minute limit."""

    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore
        self._buckets: dict[str, Bucket] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and enforce limit per client IP."""
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = self._buckets.get(client)
        if bucket is None or now >= bucket.reset_at:
            bucket = Bucket(reset_at=now + 60.0, count=0)

        if bucket.count >= settings.rate_limit_per_minute:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        self._buckets[client] = Bucket(reset_at=bucket.reset_at, count=bucket.count + 1)
        response_obj = await call_next(request)
        assert isinstance(response_obj, Response)
        return response_obj
