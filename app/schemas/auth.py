"""Schemas for authentication endpoints."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Input schema for user registration."""
    email: EmailStr
    password: str = Field(min_length=6)


class Token(BaseModel):
    """Output schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    """Output schema for user info."""
    id: int
    email: EmailStr
