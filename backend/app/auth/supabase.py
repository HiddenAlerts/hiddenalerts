"""Supabase JWT validation and the subscriber FastAPI dependency.

Authentication & Payment Phase 1 — Slice 2.

Flow:
  1. Frontend (Hasnain) calls Supabase Auth and gets an access token.
  2. Frontend sends the token to this backend as ``Authorization: Bearer <token>``.
  3. ``validate_supabase_token`` verifies the signature against the JWKS published
     by the Supabase project, checks issuer / audience / expiration / sub.
  4. ``get_current_subscriber`` looks up or creates the matching ``SubscriberProfile``
     row, refreshes ``last_seen_at`` and ``email``, and returns a context object.

Intentionally kept independent of ``app.auth.__init__`` (admin auth), so admin
behavior is not changed in this phase.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.subscriber_profile import SubscriberProfile

log = logging.getLogger(__name__)

# JWKS cache TTL — Supabase rotates keys infrequently; 10 minutes balances
# freshness against per-request latency cost.
JWKS_CACHE_TTL_SECONDS = 600
JWKS_FETCH_TIMEOUT_SECONDS = 5.0

_jwks_cache: dict | None = None
_jwks_cache_expires_at: float = 0.0
_jwks_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Config derivation
# ---------------------------------------------------------------------------


def _strip_trailing_slash(url: str) -> str:
    return url.rstrip("/") if url else url


def get_jwks_url() -> str:
    """Resolve the JWKS URL.

    Priority:
      1. settings.supabase_jwks_url if non-empty.
      2. ``{supabase_project_url}/auth/v1/.well-known/jwks.json`` if project URL is set.
    Raises HTTPException 401 with detail ``"supabase_not_configured"`` if neither is set —
    surfaces as a clean 401 instead of a 500 when the env is missing.
    """
    if settings.supabase_jwks_url:
        return settings.supabase_jwks_url
    if settings.supabase_project_url:
        return f"{_strip_trailing_slash(settings.supabase_project_url)}/auth/v1/.well-known/jwks.json"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="supabase_not_configured",
    )


def get_expected_issuer() -> str | None:
    """Resolve the expected ``iss`` claim.

    Priority:
      1. settings.supabase_issuer if non-empty.
      2. ``{supabase_project_url}/auth/v1`` if project URL is set.
      3. None (caller will skip issuer validation).
    """
    if settings.supabase_issuer:
        return settings.supabase_issuer
    if settings.supabase_project_url:
        return f"{_strip_trailing_slash(settings.supabase_project_url)}/auth/v1"
    return None


# ---------------------------------------------------------------------------
# JWKS fetch + cache
# ---------------------------------------------------------------------------


def _reset_jwks_cache() -> None:
    """Clear the JWKS cache. Test-only helper."""
    global _jwks_cache, _jwks_cache_expires_at
    _jwks_cache = None
    _jwks_cache_expires_at = 0.0


async def _fetch_jwks(url: str) -> dict:
    """Fetch JWKS over HTTP. Raises HTTPException 401 on any network/decode error."""
    try:
        async with httpx.AsyncClient(timeout=JWKS_FETCH_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Supabase JWKS fetch failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="jwks_fetch_failed",
        ) from exc
    if not isinstance(data, dict) or "keys" not in data:
        log.warning("Supabase JWKS response missing 'keys' field")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="jwks_invalid",
        )
    return data


async def get_jwks(force_refresh: bool = False) -> dict:
    """Return the cached JWKS, refreshing if expired or ``force_refresh`` is True."""
    global _jwks_cache, _jwks_cache_expires_at
    now = time.monotonic()
    if (
        not force_refresh
        and _jwks_cache is not None
        and now < _jwks_cache_expires_at
    ):
        return _jwks_cache

    async with _jwks_lock:
        # Double-checked: another waiter may have refreshed while we waited.
        now = time.monotonic()
        if (
            not force_refresh
            and _jwks_cache is not None
            and now < _jwks_cache_expires_at
        ):
            return _jwks_cache
        url = get_jwks_url()
        data = await _fetch_jwks(url)
        _jwks_cache = data
        _jwks_cache_expires_at = time.monotonic() + JWKS_CACHE_TTL_SECONDS
        return data


def _find_key_by_kid(jwks: dict, kid: str | None) -> dict | None:
    keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
    if kid is None:
        # If only one key is published, fall back to it.
        if len(keys) == 1:
            return keys[0]
        return None
    for key in keys:
        if key.get("kid") == kid:
            return key
    return None


# ---------------------------------------------------------------------------
# JWT validation
# ---------------------------------------------------------------------------


async def validate_supabase_token(token: str) -> dict:
    """Validate a Supabase access token and return its claims.

    Raises HTTPException 401 on any failure (missing config, network failure,
    invalid signature, expired token, missing ``sub``, wrong issuer/audience).
    Never logs the token value.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_token",
        )

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
        )

    kid = unverified_header.get("kid")
    algorithm = unverified_header.get("alg")
    if not algorithm:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
        )

    jwks = await get_jwks()
    key = _find_key_by_kid(jwks, kid)
    if key is None:
        # Possible key rotation — refresh once and retry.
        jwks = await get_jwks(force_refresh=True)
        key = _find_key_by_kid(jwks, kid)
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="unknown_signing_key",
            )

    audience = settings.supabase_jwt_audience or None
    issuer = get_expected_issuer()
    options = {
        "verify_aud": bool(audience),
        "verify_iss": bool(issuer),
    }

    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=[algorithm],
            audience=audience,
            issuer=issuer,
            options=options,
        )
    except JWTError as exc:
        # ExpiredSignatureError is a subclass of JWTError; surface 401 uniformly.
        log.debug("Supabase token rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_or_expired_token",
        )

    if not claims.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_sub",
        )

    return claims


# ---------------------------------------------------------------------------
# Subscriber FastAPI dependency
# ---------------------------------------------------------------------------


@dataclass
class SubscriberContext:
    profile: SubscriberProfile
    claims: dict
    supabase_user_id: str
    email: str


def _extract_bearer_token(authorization: str | None) -> str:
    """Extract the bearer token from an Authorization header. 401 on any deviation."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_authorization_header",
        )
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_authorization_scheme",
        )
    return parts[1].strip()


async def _upsert_subscriber_profile(
    db: AsyncSession,
    *,
    supabase_user_id: str,
    email: str,
) -> SubscriberProfile:
    """Find the subscriber profile by ``supabase_user_id``, creating it if absent.

    Always refreshes ``last_seen_at``. Updates ``email`` if the token-provided
    email differs from the stored value and is non-empty.
    """
    result = await db.execute(
        select(SubscriberProfile).where(
            SubscriberProfile.supabase_user_id == supabase_user_id
        )
    )
    profile = result.scalar_one_or_none()
    now_utc = datetime.now(timezone.utc)

    if profile is None:
        profile = SubscriberProfile(
            supabase_user_id=supabase_user_id,
            email=email,
            role="subscriber",
            last_seen_at=now_utc,
        )
        db.add(profile)
        await db.flush()
    else:
        if email and email != profile.email:
            profile.email = email
        profile.last_seen_at = now_utc

    await db.commit()
    await db.refresh(profile)
    return profile


async def get_current_subscriber(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SubscriberContext:
    """FastAPI dependency: validate the Supabase Bearer token and load the subscriber.

    Side effects:
      - Creates a ``SubscriberProfile`` on first sight of a new ``supabase_user_id``.
      - Updates ``email`` if the token claims a different (non-empty) email.
      - Refreshes ``last_seen_at`` on every request.

    Raises HTTPException 401 on any auth failure.
    """
    token = _extract_bearer_token(request.headers.get("Authorization"))
    claims = await validate_supabase_token(token)

    supabase_user_id = claims["sub"]
    email = claims.get("email") or ""

    profile = await _upsert_subscriber_profile(
        db, supabase_user_id=supabase_user_id, email=email
    )
    return SubscriberContext(
        profile=profile,
        claims=claims,
        supabase_user_id=supabase_user_id,
        email=profile.email,
    )
