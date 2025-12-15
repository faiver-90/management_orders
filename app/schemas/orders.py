"""Schemas for order endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models import OrderStatus


class OrderCreate(BaseModel):
    """Input schema for creating an order."""
    items: dict[str, Any]
    total_price: float = Field(gt=0)


class OrderUpdateStatus(BaseModel):
    """Input schema for updating order status."""
    status: OrderStatus


class OrderRead(BaseModel):
    """Output schema for returning an order."""
    id: uuid.UUID
    user_id: int
    items: dict[str, Any]
    total_price: float
    status: OrderStatus
    created_at: datetime


class OrdersList(BaseModel):
    """Output schema for listing orders."""
    orders: list[OrderRead]
