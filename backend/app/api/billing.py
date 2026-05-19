"""Billing API — Stripe checkout, customer portal, local billing status.

Mounted at ``/api/v1/billing/*`` in ``app.main``. Every route requires a valid
Supabase Bearer token (enforced by :func:`get_current_subscriber`).

Notes for callers:
- ``POST /billing/checkout`` creates the Stripe customer on first call and
  persists ``stripe_customer_id`` on the local ``SubscriberProfile`` row.
- ``POST /billing/portal`` requires a Stripe customer to already exist —
  i.e. the user must have hit ``checkout`` (or had a webhook backfill it)
  at least once. 400 ``stripe_customer_missing`` otherwise.
- ``GET /billing/status`` is read-only against the local ``subscriptions``
  table — it never calls Stripe. Slice 4's webhook keeps the table in sync.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase import SubscriberContext, get_current_subscriber
from app.database import get_db
from app.models.subscription import Subscription
from app.schemas.billing import (
    BillingStatusResponse,
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
)
from app.services import stripe_service
from app.services.subscription_service import has_active_subscription_access

log = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


async def _latest_subscription(
    db: AsyncSession, subscriber_profile_id: int
) -> Subscription | None:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.subscriber_profile_id == subscriber_profile_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    subscriber: SubscriberContext = Depends(get_current_subscriber),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    """Create a Stripe Checkout Session for ``body.plan`` and return its URL.

    Side effect: persists ``stripe_customer_id`` on the subscriber profile if
    this is the user's first checkout.
    """
    checkout_url = await stripe_service.create_checkout_session(
        db, subscriber.profile, body.plan
    )
    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    subscriber: SubscriberContext = Depends(get_current_subscriber),
) -> PortalResponse:
    """Create a Stripe Customer Portal session for an existing Stripe customer."""
    portal_url = await stripe_service.create_customer_portal_session(
        subscriber.profile
    )
    return PortalResponse(portal_url=portal_url)


@router.get("/status", response_model=BillingStatusResponse)
async def get_billing_status(
    subscriber: SubscriberContext = Depends(get_current_subscriber),
    db: AsyncSession = Depends(get_db),
) -> BillingStatusResponse:
    """Return billing state derived from the local ``subscriptions`` table.

    Never calls Stripe. The webhook in Slice 4 is the trusted writer for
    subscription state — until then, fresh users see ``has_active_access=false``.
    """
    subscription = await _latest_subscription(db, subscriber.profile.id)
    if subscription is None:
        return BillingStatusResponse(
            has_active_access=False,
            subscription_status=None,
            plan_type=None,
            current_period_end=None,
            cancel_at_period_end=False,
        )
    return BillingStatusResponse(
        has_active_access=has_active_subscription_access(
            subscription.status, subscription.current_period_end
        ),
        subscription_status=subscription.status,
        plan_type=subscription.plan_type,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
    )
