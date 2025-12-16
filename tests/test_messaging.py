"""Tests for messaging serialization and publisher protocol usage."""

from __future__ import annotations

import uuid

from app.services.messaging import NewOrderEvent
from tests.conftest import FakePublisher


def test_new_order_event_bytes() -> None:
    """Event should serialize to JSON bytes with order_id string."""
    oid = uuid.uuid4()
    body = NewOrderEvent(oid).to_bytes().decode("utf-8")
    assert str(oid) in body
    assert body.startswith("{") and body.endswith("}")


async def test_fake_publisher_collects(fake_publisher: FakePublisher) -> None:
    """FakePublisher should collect published order ids."""
    oid = uuid.uuid4()
    await fake_publisher.publish_new_order(oid)
    assert fake_publisher.published == [str(oid)]
