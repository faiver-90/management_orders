"""Pytest fixtures for the service."""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.db.models import Base
from app.main import app


class FakeRedis:
    """In-memory async Redis substitute."""
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def aclose(self) -> None:
        return None


class FakePublisher:
    """Publisher stub for tests."""
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
async def db_session(session_maker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
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


@pytest.fixture()
async def client(db_session: AsyncSession, fake_redis: FakeRedis, fake_publisher: FakePublisher) -> AsyncIterator[AsyncClient]:
    """HTTP client with dependency overrides."""
    async def _get_session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    async def _get_redis_override() -> AsyncIterator[FakeRedis]:
        yield fake_redis

    app.dependency_overrides[deps.get_session] = _get_session_override # type: ignore
    app.dependency_overrides[deps.get_redis] = _get_redis_override


    # Patch publisher factory used inside the orders router module.
    from app.api.routes import orders as orders_routes  # local import for test patching
    orders_routes.get_publisher = lambda: fake_publisher  # type: ignore
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
