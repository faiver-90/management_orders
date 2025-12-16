"""Tests for services and repositories to improve coverage."""

from __future__ import annotations

import uuid

import pytest
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OrderStatus
from app.repositories.orders import OrdersRepository
from app.repositories.users import UsersRepository
from app.schemas.auth import UserCreate
from app.schemas.orders import OrderCreate, OrderUpdateStatus
from app.services.auth import AuthService
from app.services.orders import OrdersService
from tests.conftest import FakePublisher, FakeRedis


async def test_users_repo_create_and_lookup(db_session: AsyncSession, faker: Faker) -> None:
    repo = UsersRepository(db_session)

    email = faker.unique.email()
    user = await repo.create(email=email, password_hash="hash")
    assert user.id is not None

    by_email = await repo.get_by_email(email)
    assert by_email is not None and by_email.id == user.id

    by_id = await repo.get_by_id(user.id)
    assert by_id is not None and by_id.email == email


async def test_auth_service_register_and_login(
    db_session: AsyncSession, faker: Faker, password: str
) -> None:
    """Use a minimal payload object to avoid coupling tests to UserCreate schema details."""
    users = UsersRepository(db_session)
    svc = AuthService(users)

    email = faker.unique.email()
    payload_ok: UserCreate = UserCreate(email=email, password=password)
    created = await svc.register(payload_ok)
    assert created.email == email

    token = await svc.login(payload_ok)
    assert token.access_token

    with pytest.raises(ValueError):
        await svc.register(payload_ok)

    payload_bad: UserCreate = UserCreate(email=email, password="wrong12")
    with pytest.raises(PermissionError):
        await svc.login(payload_bad)


async def test_orders_repo_cache_aside(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
    faker: Faker,
    order_items: dict[str, int],
    order_price: float,
) -> None:
    repo = OrdersRepository(session=db_session, redis=fake_redis)  # type: ignore[arg-type]

    created = await repo.create(
        user_id=faker.random_int(min=1, max=10_000),
        data=OrderCreate(items=order_items, total_price=order_price),
    )
    oid = created.id

    fake_redis.get_calls = 0
    o1 = await repo.get(oid)
    assert o1.id == oid
    assert fake_redis.get_calls >= 1

    fake_redis.get_calls = 0
    o2 = await repo.get(oid)
    assert o2 == o1
    assert fake_redis.get_calls >= 1

    upd = await repo.update_status(order_id=oid, data=OrderUpdateStatus(status=OrderStatus.PAID))
    assert upd.status == OrderStatus.PAID


async def test_orders_service_permission_and_publish(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
    fake_publisher: FakePublisher,
    faker: Faker,
    order_items: dict[str, int],
    order_price: float,
) -> None:
    repo = OrdersRepository(session=db_session, redis=fake_redis)  # type: ignore[arg-type]
    svc = OrdersService(repo=repo, publisher=fake_publisher)

    owner_id = faker.random_int(min=1, max=10_000)
    other_id = faker.random_int(min=1, max=10_000)

    created = await svc.create_order(
        owner_id, OrderCreate(items=order_items, total_price=order_price)
    )
    assert fake_publisher.published == [str(created.id)]

    with pytest.raises(PermissionError):
        await svc.get_order_for_user(other_id, created.id)

    with pytest.raises(PermissionError):
        await svc.update_status_for_user(
            other_id, created.id, OrderUpdateStatus(status=OrderStatus.PAID)
        )

    with pytest.raises(ValueError):
        await svc.get_order_for_user(owner_id, uuid.UUID("00000000-0000-0000-0000-000000000000"))
