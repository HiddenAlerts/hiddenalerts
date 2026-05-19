"""Unit tests for app/auth/supabase.py — Supabase JWT validator.

Mints an in-process RSA keypair, builds a JWK, mocks the JWKS fetch to return it,
and exercises validate_supabase_token through every failure branch listed in
CLAUDE.md's access rules.
"""
from __future__ import annotations

import base64
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jose import jwt

from app.auth import supabase as supabase_auth
from app.config import settings


# ---------------------------------------------------------------------------
# RSA keypair + JWK helpers (session-scoped — RSA gen is slow)
# ---------------------------------------------------------------------------


def _int_to_b64url(value: int) -> str:
    byte_length = (value.bit_length() + 7) // 8
    raw = value.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


@pytest.fixture(scope="session")
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    from cryptography.hazmat.primitives import serialization

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": "test-kid-1",
        "use": "sig",
        "alg": "RS256",
        "n": _int_to_b64url(public_numbers.n),
        "e": _int_to_b64url(public_numbers.e),
    }
    return {"private_pem": pem, "jwk": jwk}


@pytest.fixture(autouse=True)
def configure_supabase_settings():
    """Pin Supabase settings to deterministic test values, restoring after each test."""
    originals = {
        "supabase_project_url": settings.supabase_project_url,
        "supabase_jwks_url": settings.supabase_jwks_url,
        "supabase_jwt_audience": settings.supabase_jwt_audience,
        "supabase_issuer": settings.supabase_issuer,
    }
    settings.supabase_project_url = "https://test.supabase.co"
    settings.supabase_jwks_url = "https://test.supabase.co/auth/v1/.well-known/jwks.json"
    settings.supabase_jwt_audience = "authenticated"
    settings.supabase_issuer = "https://test.supabase.co/auth/v1"
    supabase_auth._reset_jwks_cache()
    yield
    for k, v in originals.items():
        setattr(settings, k, v)
    supabase_auth._reset_jwks_cache()


def _mint_token(rsa_keypair, *, claims_overrides=None, kid="test-kid-1"):
    claims = {
        "sub": "supabase-user-123",
        "email": "user@example.com",
        "aud": "authenticated",
        "iss": "https://test.supabase.co/auth/v1",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    if claims_overrides:
        claims.update(claims_overrides)
    return jwt.encode(
        claims,
        rsa_keypair["private_pem"],
        algorithm="RS256",
        headers={"kid": kid},
    )


def _patch_jwks(rsa_keypair):
    """Patch the JWKS fetch to return the test JWK without touching the network."""
    async def _fake_fetch(url):
        return {"keys": [rsa_keypair["jwk"]]}

    return patch.object(supabase_auth, "_fetch_jwks", side_effect=_fake_fetch)


# ---------------------------------------------------------------------------
# Config-derivation tests
# ---------------------------------------------------------------------------


class TestJwksUrlDerivation:
    def test_uses_explicit_jwks_url_when_set(self):
        settings.supabase_jwks_url = "https://explicit.example.com/jwks.json"
        assert (
            supabase_auth.get_jwks_url()
            == "https://explicit.example.com/jwks.json"
        )

    def test_derives_from_project_url_when_jwks_url_empty(self):
        settings.supabase_jwks_url = ""
        settings.supabase_project_url = "https://abc123.supabase.co"
        assert (
            supabase_auth.get_jwks_url()
            == "https://abc123.supabase.co/auth/v1/.well-known/jwks.json"
        )

    def test_derives_correctly_when_project_url_has_trailing_slash(self):
        settings.supabase_jwks_url = ""
        settings.supabase_project_url = "https://abc123.supabase.co/"
        assert (
            supabase_auth.get_jwks_url()
            == "https://abc123.supabase.co/auth/v1/.well-known/jwks.json"
        )

    def test_raises_401_when_supabase_unconfigured(self):
        settings.supabase_jwks_url = ""
        settings.supabase_project_url = ""
        with pytest.raises(HTTPException) as exc:
            supabase_auth.get_jwks_url()
        assert exc.value.status_code == 401
        assert exc.value.detail == "supabase_not_configured"


class TestIssuerDerivation:
    def test_uses_explicit_issuer_when_set(self):
        settings.supabase_issuer = "https://custom-issuer.example.com/auth/v1"
        assert (
            supabase_auth.get_expected_issuer()
            == "https://custom-issuer.example.com/auth/v1"
        )

    def test_derives_from_project_url_when_issuer_empty(self):
        settings.supabase_issuer = ""
        settings.supabase_project_url = "https://abc123.supabase.co"
        assert (
            supabase_auth.get_expected_issuer()
            == "https://abc123.supabase.co/auth/v1"
        )

    def test_returns_none_when_unconfigured(self):
        settings.supabase_issuer = ""
        settings.supabase_project_url = ""
        assert supabase_auth.get_expected_issuer() is None


# ---------------------------------------------------------------------------
# Token validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestValidateSupabaseToken:
    async def test_valid_token_returns_claims(self, rsa_keypair):
        token = _mint_token(rsa_keypair)
        with _patch_jwks(rsa_keypair):
            claims = await supabase_auth.validate_supabase_token(token)
        assert claims["sub"] == "supabase-user-123"
        assert claims["email"] == "user@example.com"

    async def test_expired_token_returns_401(self, rsa_keypair):
        token = _mint_token(
            rsa_keypair,
            claims_overrides={
                "exp": int(
                    (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
                )
            },
        )
        with _patch_jwks(rsa_keypair):
            with pytest.raises(HTTPException) as exc:
                await supabase_auth.validate_supabase_token(token)
        assert exc.value.status_code == 401

    async def test_missing_sub_returns_401(self, rsa_keypair):
        token = _mint_token(rsa_keypair, claims_overrides={"sub": ""})
        with _patch_jwks(rsa_keypair):
            with pytest.raises(HTTPException) as exc:
                await supabase_auth.validate_supabase_token(token)
        assert exc.value.status_code == 401
        assert exc.value.detail == "missing_sub"

    async def test_wrong_issuer_returns_401(self, rsa_keypair):
        token = _mint_token(
            rsa_keypair, claims_overrides={"iss": "https://attacker.example.com"}
        )
        with _patch_jwks(rsa_keypair):
            with pytest.raises(HTTPException) as exc:
                await supabase_auth.validate_supabase_token(token)
        assert exc.value.status_code == 401

    async def test_wrong_audience_returns_401(self, rsa_keypair):
        token = _mint_token(rsa_keypair, claims_overrides={"aud": "wrong-aud"})
        with _patch_jwks(rsa_keypair):
            with pytest.raises(HTTPException) as exc:
                await supabase_auth.validate_supabase_token(token)
        assert exc.value.status_code == 401

    async def test_unknown_kid_returns_401(self, rsa_keypair):
        token = _mint_token(rsa_keypair, kid="unknown-kid")
        with _patch_jwks(rsa_keypair):
            with pytest.raises(HTTPException) as exc:
                await supabase_auth.validate_supabase_token(token)
        assert exc.value.status_code == 401
        assert exc.value.detail == "unknown_signing_key"

    async def test_garbage_token_returns_401(self, rsa_keypair):
        with _patch_jwks(rsa_keypair):
            with pytest.raises(HTTPException) as exc:
                await supabase_auth.validate_supabase_token("not.a.jwt")
        assert exc.value.status_code == 401

    async def test_empty_token_returns_401(self):
        with pytest.raises(HTTPException) as exc:
            await supabase_auth.validate_supabase_token("")
        assert exc.value.status_code == 401
        assert exc.value.detail == "missing_token"

    async def test_hs256_algorithm_rejected(self, rsa_keypair):
        # A token signed with HS256 (or claiming HS256 in its header) must be
        # rejected before signature verification — we only allow asymmetric
        # algorithms via the JWKS flow.
        hs256_token = jwt.encode(
            {
                "sub": "supabase-user-123",
                "aud": "authenticated",
                "iss": "https://test.supabase.co/auth/v1",
                "exp": int(
                    (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
                ),
            },
            "shared-secret",
            algorithm="HS256",
        )
        with _patch_jwks(rsa_keypair):
            with pytest.raises(HTTPException) as exc:
                await supabase_auth.validate_supabase_token(hs256_token)
        assert exc.value.status_code == 401
        assert exc.value.detail == "unsupported_token_algorithm"

    async def test_none_algorithm_rejected(self, rsa_keypair):
        # ``alg: "none"`` is the canonical JWT downgrade attack — must be rejected.
        import json

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(
            json.dumps(
                {
                    "sub": "x",
                    "aud": "authenticated",
                    "iss": "https://test.supabase.co/auth/v1",
                    "exp": int(
                        (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
                    ),
                }
            ).encode()
        ).decode().rstrip("=")
        none_token = f"{header}.{payload}."
        with _patch_jwks(rsa_keypair):
            with pytest.raises(HTTPException) as exc:
                await supabase_auth.validate_supabase_token(none_token)
        assert exc.value.status_code == 401
        assert exc.value.detail == "unsupported_token_algorithm"

    async def test_jwks_fetch_failure_returns_401(self, rsa_keypair):
        """Real httpx error must be translated to a 401 inside _fetch_jwks."""
        import httpx

        token = _mint_token(rsa_keypair)

        class _ExplodingClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url):
                raise httpx.ConnectError("simulated network failure")

        with patch.object(supabase_auth.httpx, "AsyncClient", _ExplodingClient):
            with pytest.raises(HTTPException) as exc:
                await supabase_auth.validate_supabase_token(token)
        assert exc.value.status_code == 401
        assert exc.value.detail == "jwks_fetch_failed"


# ---------------------------------------------------------------------------
# JWKS caching tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestJwksCaching:
    async def test_cache_serves_repeat_calls_without_refetch(self, rsa_keypair):
        token = _mint_token(rsa_keypair)
        calls = {"n": 0}

        async def _counting_fetch(url):
            calls["n"] += 1
            return {"keys": [rsa_keypair["jwk"]]}

        with patch.object(supabase_auth, "_fetch_jwks", side_effect=_counting_fetch):
            await supabase_auth.validate_supabase_token(token)
            await supabase_auth.validate_supabase_token(token)
            await supabase_auth.validate_supabase_token(token)

        assert calls["n"] == 1

    async def test_expired_cache_triggers_refetch(self, rsa_keypair):
        token = _mint_token(rsa_keypair)
        calls = {"n": 0}

        async def _counting_fetch(url):
            calls["n"] += 1
            return {"keys": [rsa_keypair["jwk"]]}

        with patch.object(supabase_auth, "_fetch_jwks", side_effect=_counting_fetch):
            await supabase_auth.validate_supabase_token(token)
            # Force the cache to look expired
            supabase_auth._jwks_cache_expires_at = time.monotonic() - 1.0
            await supabase_auth.validate_supabase_token(token)

        assert calls["n"] == 2
