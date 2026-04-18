"""Tests for app/auth.py — JWT utilities and login endpoint."""
from __future__ import annotations

import pytest

from app.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self):
        plain = "mysecretpassword123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False


class TestJWT:
    def test_create_and_decode_token(self):
        # Uses TEST_JWT_SECRET patched by conftest session fixture
        token = create_access_token({"sub": "42"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"

    def test_expired_token_returns_none(self):
        from datetime import datetime, timedelta, timezone
        from jose import jwt
        from app.config import settings

        # Manually create an already-expired token
        expired_payload = {
            "sub": "99",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        }
        token = jwt.encode(
            expired_payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        result = decode_access_token(token)
        assert result is None

    def test_invalid_token_returns_none(self):
        result = decode_access_token("not.a.valid.jwt.token")
        assert result is None

    def test_tampered_token_returns_none(self):
        token = create_access_token({"sub": "1"})
        tampered = token[:-5] + "XXXXX"
        result = decode_access_token(tampered)
        assert result is None


@pytest.mark.asyncio
async def test_login_endpoint_success(client, db_session):
    """POST /login with valid credentials sets access_token cookie."""
    from app.models.user import User

    user = User(
        email="logintest@test.com",
        password_hash=hash_password("testpass"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/login",
        data={"username": "logintest@test.com", "password": "testpass"},
        follow_redirects=False,
    )

    # Should redirect to /dashboard on success
    assert response.status_code in (302, 303)
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_endpoint_wrong_password(client, db_session):
    """POST /login with wrong password returns 401."""
    from app.models.user import User

    user = User(
        email="wrongpass@test.com",
        password_hash=hash_password("correct"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/login",
        data={"username": "wrongpass@test.com", "password": "wrong"},
        follow_redirects=False,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_alert_endpoint_requires_auth(client):
    """GET /api/v1/alerts without auth cookie returns 401."""
    response = await client.get("/api/v1/alerts")
    assert response.status_code == 401
