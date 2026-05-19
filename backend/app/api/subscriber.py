"""Subscriber-facing API — Authentication & Payment Phase 1, Slice 2.

Mounted at ``/api/v1/subscriber/*`` in ``app.main``. Every route requires a
valid Supabase Bearer token (enforced by :func:`get_current_subscriber`).

This slice intentionally exposes only the two identity / access endpoints —
content endpoints (alerts, search, briefs) ship in later slices once the
access guard, Stripe checkout, and webhook are in place.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase import SubscriberContext, get_current_subscriber
from app.database import get_db
from app.models.subscription import Subscription
from app.schemas.subscriber import (
    SubscriberAccessResponse,
    SubscriberMeResponse,
    SubscriptionMeRead,
)
from app.services.subscription_service import has_active_subscription_access

log = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriber", tags=["subscriber"])


async def _latest_subscription(
    db: AsyncSession, subscriber_profile_id: int
) -> Subscription | None:
    """Return the most recent subscription row for this profile, if any.

    "Most recent" = highest ``id`` — subscriptions are append-only from the
    webhook in later slices, so newest id wins.
    """
    result = await db.execute(
        select(Subscription)
        .where(Subscription.subscriber_profile_id == subscriber_profile_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/me", response_model=SubscriberMeResponse)
async def get_subscriber_me(
    subscriber: SubscriberContext = Depends(get_current_subscriber),
    db: AsyncSession = Depends(get_db),
) -> SubscriberMeResponse:
    """Return the authenticated subscriber's identity + access state.

    For Slice 2 (Stripe not yet wired) most authenticated users will see
    ``has_active_subscription=false`` and ``access_level="locked"``. Once a
    subscription row exists for the profile (created by the webhook in a later
    slice) and ``has_active_subscription_access`` agrees, the response flips to
    ``access_level="subscriber"``.
    """
    subscription = await _latest_subscription(db, subscriber.profile.id)
    has_access = False
    sub_payload: SubscriptionMeRead | None = None
    if subscription is not None:
        has_access = has_active_subscription_access(
            subscription.status, subscription.current_period_end
        )
        sub_payload = SubscriptionMeRead.model_validate(subscription)

    return SubscriberMeResponse(
        authenticated=True,
        has_active_subscription=has_access,
        access_level="subscriber" if has_access else "locked",
        email=subscriber.email,
        subscription=sub_payload,
    )


@router.get("/access", response_model=SubscriberAccessResponse)
async def get_subscriber_access(
    subscriber: SubscriberContext = Depends(get_current_subscriber),
    db: AsyncSession = Depends(get_db),
) -> SubscriberAccessResponse:
    """Lightweight route-guard helper for the frontend.

    Returns ``can_access_full_content`` plus a machine-readable ``reason``
    string so Hasnain can render different paywall messaging
    (``subscription_required`` vs ``active_subscription``).
    """
    subscription = await _latest_subscription(db, subscriber.profile.id)
    if subscription is None:
        return SubscriberAccessResponse(
            can_access_full_content=False,
            reason="subscription_required",
        )
    has_access = has_active_subscription_access(
        subscription.status, subscription.current_period_end
    )
    return SubscriberAccessResponse(
        can_access_full_content=has_access,
        reason="active_subscription" if has_access else "subscription_required",
    )
