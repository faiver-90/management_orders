"""Tests for security helpers."""
from __future__ import annotations

import pytest

from app.core.security import create_access_token, decode_token, hash_password, verify_password


@pytest.mark.parametrize("password", ["secret12", "another-secret"])
def test_password_hash_and_verify(password: str) -> None:
    """Password hashing must verify correctly and fail for different password."""
    h = hash_password(password)
    assert verify_password(password, h) is True
    assert verify_password(password + "x", h) is False


def test_jwt_roundtrip() -> None:
    """Token must decode to original subject."""
    token = create_access_token("123", expires_minutes=5)
    assert decode_token(token) == "123"


@pytest.mark.parametrize("bad", ["", "not-a-jwt", "a.b.c"])
def test_decode_token_invalid(bad: str) -> None:
    """Invalid tokens must raise ValueError."""
    with pytest.raises(ValueError):
        decode_token(bad)
