"""Pytest fixtures for the service.

This test suite uses an in-memory SQLite database and lightweight fakes for Redis
and messaging to keep tests deterministic and fast.

Notes about FastAPI-Limiter:
- The production app uses `fastapi-limiter` on some auth endpoints.
- In unit/integration tests we strip those dependencies from routes to avoid
  requiring a real Redis instance that supports Lua scripts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.db.models import Base
from app.main import app


class FakeRedis:
    """In-memory async Redis substitute with call counters.

    This fake implements a minimal subset used by app cache helpers:
    - get
    - setex
    - delete

    It also tracks call counts so tests can assert cache hits.
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self.get_calls: int = 0
        self.setex_calls: int = 0
        self.delete_calls: int = 0

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self._data.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.setex_calls += 1
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self.delete_calls += 1
        self._data.pop(key, None)

    async def aclose(self) -> None:
        return None


class FakePublisher:
    """Publisher stub for tests collecting published events."""

    def __init__(self) -> None:
        self.published: list[str] = []

    async def publish_new_order(self, order_id) -> None:  # type: ignore
        self.published.append(str(order_id))


@pytest.fixture()
async def session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """SQLite async session factory for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest.fixture()
async def db_session(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Provide a transactional session."""
    async with session_maker() as session:
        yield session


@pytest.fixture()
def fake_redis() -> FakeRedis:
    """Provide fake Redis."""
    return FakeRedis()


@pytest.fixture()
def fake_publisher() -> FakePublisher:
    """Provide fake publisher."""
    return FakePublisher()


def _strip_fastapi_limiter_dependencies() -> None:
    """Remove fastapi-limiter dependencies from all routes (test-only).

    The `RateLimiter` dependency requires FastAPILimiter.init + a real Redis
    supporting Lua scripts. For tests we validate application behavior without
    exercising fastapi-limiter itself.
    """
    for route in getattr(app.router, "routes", []):
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        # Keep non-limiter dependencies intact
        new_deps = []
        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            # fastapi-limiter creates a callable with class name "RateLimiter"
            if call is not None and call.__class__.__name__ == "RateLimiter":
                continue
            new_deps.append(dep)
        dependant.dependencies = new_deps


@pytest.fixture()
async def client(
    db_session: AsyncSession, fake_redis: FakeRedis, fake_publisher: FakePublisher
) -> AsyncIterator[AsyncClient]:
    """HTTP client with dependency overrides."""
    _strip_fastapi_limiter_dependencies()

    async def _get_session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    async def _get_redis_override() -> AsyncIterator[FakeRedis]:
        yield fake_redis

    def _get_publisher_override() -> FakePublisher:
        return fake_publisher

    app.dependency_overrides[deps.get_session] = _get_session_override  # type: ignore
    app.dependency_overrides[deps.get_redis] = _get_redis_override
    # If deps.get_publisher exists, override it (preferred to patching modules).
    if hasattr(deps, "get_publisher"):
        app.dependency_overrides[deps.get_publisher] = _get_publisher_override

    # Ensure app lifespan events run (if any)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
