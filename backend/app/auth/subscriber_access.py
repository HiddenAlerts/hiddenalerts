"""Active-subscription access guard — Authentication & Payment Phase 1, Slice 5.

``require_active_subscription`` is the single dependency that gates paid
subscriber content. It builds on ``get_current_subscriber`` (Supabase token →
local profile) and then checks the profile's latest subscription against
``has_active_subscription_access``. Access logic lives here once — content
routes just depend on this guard.

Layered failures:
  - missing / invalid Supabase token → 401 (raised by ``get_current_subscriber``)
  - valid token, no active subscription → 403 ``active_subscription_required``
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase import SubscriberContext, get_current_subscriber
from app.config import settings
from app.database import get_db
from app.models.subscriber_profile import SubscriberProfile
from app.models.subscription import Subscription
from app.services.subscription_service import has_active_subscription_access


@dataclass
class ActiveSubscriberContext:
    """Returned by ``require_active_subscription`` — profile + the active subscription."""

    profile: SubscriberProfile
    subscription: Subscription
    claims: dict
    supabase_user_id: str
    email: str


async def _latest_subscription(
    db: AsyncSession, subscriber_profile_id: int
) -> Subscription | None:
    """Most recent subscription row for the profile (highest id wins)."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.subscriber_profile_id == subscriber_profile_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def require_active_subscription(
    subscriber: SubscriberContext = Depends(get_current_subscriber),
    db: AsyncSession = Depends(get_db),
) -> ActiveSubscriberContext:
    """FastAPI dependency: require a valid Supabase token AND an active subscription.

    Raises 403 ``active_subscription_required`` when the token is valid but the
    subscriber has no subscription that currently grants access. (401 for a
    missing/invalid token is raised earlier by ``get_current_subscriber``.)
    """
    subscription = await _latest_subscription(db, subscriber.profile.id)
    if subscription is None or not has_active_subscription_access(
        subscription.status,
        subscription.current_period_end,
        grace_seconds=settings.subscription_access_grace_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="active_subscription_required",
        )
    return ActiveSubscriberContext(
        profile=subscriber.profile,
        subscription=subscription,
        claims=subscriber.claims,
        supabase_user_id=subscriber.supabase_user_id,
        email=subscriber.email,
    )
