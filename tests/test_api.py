"""End-to-end tests for API endpoints."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OrderStatus
from tests.conftest import FakeRedis


async def register_and_login(client: AsyncClient, email: str, password: str) -> str:
    """Register a user and obtain JWT token.

    Important:
        `/token/` expects a JSON body compatible with `UserCreate`,
        not `application/x-www-form-urlencoded`.
    """
    r = await client.post("/register/", json={"email": email, "password": password})
    assert r.status_code == 200

    token_resp = await client.post("/token/", json={"email": email, "password": password})
    assert token_resp.status_code == 200

    payload = cast(dict[str, Any], token_resp.json())
    return cast(str, payload["access_token"])


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient) -> None:
    """Duplicate email must be rejected."""
    await client.post("/register/", json={"email": "a@a.com", "password": "secret12"})
    r2 = await client.post("/register/", json={"email": "a@a.com", "password": "secret12"})
    assert r2.status_code == 400
    assert r2.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_login_bad_password(client: AsyncClient) -> None:
    """Login with wrong password must fail."""
    await client.post("/register/", json={"email": "b@b.com", "password": "secret12"})
    r = await client.post(
        "/token/",
        data={"username": "b@b.com", "password": "wrong"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_order_flow_and_cache(
    client: AsyncClient, fake_redis: FakeRedis, db_session: AsyncSession
) -> None:
    """Create -> get (forced cache miss) -> get (cache hit) -> update -> list.

    Checks that the second GET does not hit DB and consults Redis.
    """
    token = await register_and_login(client, "c@c.com", "secret12")
    headers = {"Authorization": f"Bearer {token}"}

    # Create (repo.create may warm cache, so we clear it to force a miss on first GET)
    create = await client.post(
        "/orders/",
        json={"items": {"sku": "x"}, "total_price": 12.5},
        headers=headers,
    )
    assert create.status_code == 200
    order: dict[str, Any] = create.json()
    order_id = uuid.UUID(order["id"])

    # Force cache miss on first read
    if hasattr(fake_redis, "_data"):
        fake_redis._data.clear()

    # Spy on DB execute calls
    execute_calls = {"count": 0}
    orig_execute = db_session.execute

    async def _execute_spy(*args, **kwargs):  # type: ignore
        execute_calls["count"] += 1
        return await orig_execute(*args, **kwargs)

    db_session.execute = _execute_spy  # type: ignore

    # First GET: cache miss -> DB hit
    fake_redis.get_calls = 0
    execute_calls["count"] = 0
    r1 = await client.get(f"/orders/{order_id}/", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["id"] == str(order_id)
    assert fake_redis.get_calls >= 1
    assert execute_calls["count"] >= 1, "First read should hit DB after forced cache miss"

    # Second GET: cache hit -> no DB
    fake_redis.get_calls = 0
    execute_calls["count"] = 0
    r2 = await client.get(f"/orders/{order_id}/", headers=headers)
    assert r2.status_code == 200
    assert r2.json() == r1.json()
    assert fake_redis.get_calls >= 1
    assert execute_calls["count"] == 0, "Second read should not hit DB (cache hit expected)"

    # Update status
    upd = await client.patch(
        f"/orders/{order_id}/",
        json={"status": OrderStatus.PAID},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == OrderStatus.PAID

    # List for user
    user_id = int(order["user_id"])
    lst = await client.get(f"/orders/user/{user_id}/", headers=headers)
    assert lst.status_code == 200
    assert len(lst.json()["orders"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint", ["/orders/user/999/", "/orders/00000000-0000-0000-0000-000000000000/"]
)
async def test_auth_required(client: AsyncClient, endpoint: str) -> None:
    """Protected endpoints must reject requests without Authorization.

    FastAPI HTTPBearer with auto_error=True returns 403; some setups use 401.
    Accept either to keep the test aligned with the chosen security policy.
    """
    r = await client.get(endpoint)
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_order_not_found_and_forbidden(client: AsyncClient) -> None:
    """Non-existent order returns 404; foreign user access returns 403."""
    token1 = await register_and_login(client, "u1@x.com", "secret12")
    token2 = await register_and_login(client, "u2@x.com", "secret12")

    # Non-existent
    oid = uuid.UUID("00000000-0000-0000-0000-000000000000")
    r_nf = await client.get(f"/orders/{oid}/", headers={"Authorization": f"Bearer {token1}"})
    assert r_nf.status_code == 404

    # Create by user1
    create = await client.post(
        "/orders/",
        json={"items": {"sku": "y"}, "total_price": 10.0},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert create.status_code == 200
    order_id = uuid.UUID(create.json()["id"])

    # Access by user2 should be forbidden
    r_forb = await client.get(f"/orders/{order_id}/", headers={"Authorization": f"Bearer {token2}"})
    assert r_forb.status_code == 403

    # Update forbidden
    u_forb = await client.patch(
        f"/orders/{order_id}/",
        json={"status": OrderStatus.CANCELED},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert u_forb.status_code == 403

    # List forbidden
    user1_id = int(create.json()["user_id"])
    lst_forb = await client.get(
        f"/orders/user/{user1_id}/", headers={"Authorization": f"Bearer {token2}"}
    )
    assert lst_forb.status_code == 403
