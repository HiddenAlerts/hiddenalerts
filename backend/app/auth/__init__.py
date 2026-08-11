"""Authentication utilities — JWT tokens + bcrypt password hashing.

Supports HTTP-only cookie auth (primary) and Authorization: Bearer token (fallback).
JWT stored in HTTP-only cookie ('access_token') for browser sessions.
Bearer token accepted for API integrations and cross-domain frontend use.

This module is the admin/subscriber-user auth path. The Supabase auth path
(used by paid subscribers in Authentication & Payment Phase 1) lives in
``app.auth.supabase`` and is intentionally separate so admin auth can keep
its current behavior unchanged.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

log = logging.getLogger(__name__)

# bcrypt password hashing context
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

COOKIE_NAME = "access_token"

#: Documentation-only security scheme for the internal HiddenAlerts JWT.
#:
#: This exists so OpenAPI advertises ``AdminBearer`` (and Swagger UI renders an
#: Authorize box) on every operation that already depends on
#: :func:`get_current_user`. It is **not** a second authorization implementation:
#: ``auto_error=False`` means a missing or malformed header returns ``None``
#: instead of raising, so the token is still read, decoded and checked by the
#: existing body below and the existing 401 semantics are preserved exactly.
#: Cookie-based sessions keep working for the same reason — the scheme never
#: rejects a request on its own.
admin_bearer_scheme = HTTPBearer(
    scheme_name="AdminBearer",
    bearerFormat="JWT",
    auto_error=False,
    description=(
        "Internal HiddenAlerts JWT from `POST /api/v1/auth/login`. Used by the "
        "Admin frontend for Admin Alerts, Admin Intelligence Briefs, Admin "
        "Monitoring and the `/api/v1/auth` profile routes."
    ),
)


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------


def create_access_token(data: dict) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload dict — must include 'sub' (user id as string).

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT token.

    Returns:
        Decoded payload dict, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _scheme: HTTPAuthorizationCredentials | None = Security(admin_bearer_scheme),
) -> User:
    """FastAPI dependency: resolve JWT from cookie (primary) or Bearer header (fallback).

    Cookie takes priority. If no cookie, checks Authorization: Bearer <token>.
    Used by both API routes and dashboard routes. Dashboard routes catch the
    HTTPException and redirect to /login.

    ``_scheme`` is declared purely so FastAPI emits ``AdminBearer`` security
    metadata for every operation reached through this dependency — the OpenAPI
    document then follows exactly the same boundary as runtime auth, with no
    second hand-maintained route list. Its value is intentionally unused:
    ``auto_error=False`` makes it ``None`` for cookie sessions and for missing
    headers, and the resolution below is unchanged.

    Raises:
        HTTPException 401 if token is missing, invalid, or user not found/inactive.
    """
    # Cookie first, Bearer header fallback
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Dependency: require an authenticated, active user (any role)."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive account",
        )
    return user


async def require_admin(
    user: User = Depends(get_current_active_user),
) -> User:
    """Dependency: require an authenticated admin user. Raises 403 for other roles."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_subscriber_or_admin(
    user: User = Depends(get_current_active_user),
) -> User:
    """Dependency: require an authenticated admin or subscriber user."""
    if user.role not in ("admin", "subscriber"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    return user


async def authenticate_user(email: str, password: str, db: AsyncSession) -> User | None:
    """Verify email + password against the users table.

    Returns:
        User if credentials are valid and account is active, None otherwise.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None

    return user
