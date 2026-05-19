"""Stripe SDK wrapper — Authentication & Payment Phase 1, Slice 3.

The Stripe Python SDK is synchronous. We wrap every Stripe call in
``anyio.to_thread.run_sync`` so the FastAPI event loop isn't blocked while
Stripe is on the wire.

All public functions raise ``HTTPException`` with stable, machine-readable
``detail`` strings — they're written to be safe to surface to the frontend.
Stripe exception internals (URLs, request IDs, account IDs, etc.) are logged
server-side at WARNING level but never returned to the caller.
"""
from __future__ import annotations

import logging
from typing import Any

import anyio
import stripe
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.subscriber_profile import SubscriberProfile

log = logging.getLogger(__name__)

PLAN_MONTHLY = "monthly"
PLAN_ANNUAL = "annual"


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------


def _require_stripe_api_key() -> None:
    """Set ``stripe.api_key`` from settings or raise 500 ``stripe_not_configured``."""
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_not_configured",
        )
    stripe.api_key = settings.stripe_secret_key


def _price_id_for_plan(plan: str) -> str:
    """Map a plan literal to a configured Stripe price id, or raise."""
    if plan == PLAN_MONTHLY:
        price_id = settings.stripe_monthly_price_id
    elif plan == PLAN_ANNUAL:
        price_id = settings.stripe_annual_price_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_plan",
        )
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_price_not_configured",
        )
    return price_id


def _strip_trailing_slash(url: str) -> str:
    return url.rstrip("/") if url else url


def resolve_checkout_urls() -> tuple[str, str]:
    """Return (success_url, cancel_url), falling back to derived paths under
    ``FRONTEND_BASE_URL`` when explicit values are unset. Raise 500 if neither
    source supplies a usable URL — surfaces as
    ``stripe_checkout_urls_not_configured``.
    """
    base = _strip_trailing_slash(settings.frontend_base_url)
    success = settings.stripe_checkout_success_url or (
        f"{base}/billing/success" if base else ""
    )
    cancel = settings.stripe_checkout_cancel_url or (
        f"{base}/pricing" if base else ""
    )
    if not success or not cancel:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_checkout_urls_not_configured",
        )
    return success, cancel


def resolve_portal_return_url() -> str:
    base = _strip_trailing_slash(settings.frontend_base_url)
    return_url = settings.stripe_portal_return_url or (
        f"{base}/account/billing" if base else ""
    )
    if not return_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_portal_return_url_not_configured",
        )
    return return_url


# ---------------------------------------------------------------------------
# Stripe calls (sync, run in a worker thread)
# ---------------------------------------------------------------------------


def _sync_create_customer(*, email: str, metadata: dict[str, str]) -> Any:
    return stripe.Customer.create(email=email or None, metadata=metadata)


def _sync_create_checkout_session(
    *,
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    client_reference_id: str,
    metadata: dict[str, str],
    subscription_metadata: dict[str, str],
) -> Any:
    return stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=client_reference_id,
        metadata=metadata,
        subscription_data={"metadata": subscription_metadata},
    )


def _sync_create_portal_session(*, customer_id: str, return_url: str) -> Any:
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )


# ---------------------------------------------------------------------------
# Async wrappers + business logic
# ---------------------------------------------------------------------------


def _log_stripe_error(op: str, exc: Exception) -> None:
    """Log a Stripe error without exposing tokens or response bodies in detail."""
    log.warning("stripe %s failed: %s", op, type(exc).__name__)


async def create_or_get_customer(
    db: AsyncSession, profile: SubscriberProfile
) -> str:
    """Return the Stripe customer id for ``profile``, creating one on first use.

    Persists ``stripe_customer_id`` back onto the profile so subsequent calls
    reuse the same Stripe customer.
    """
    _require_stripe_api_key()
    if profile.stripe_customer_id:
        return profile.stripe_customer_id

    metadata = {
        "subscriber_profile_id": str(profile.id),
        "supabase_user_id": profile.supabase_user_id,
    }
    try:
        customer = await anyio.to_thread.run_sync(
            lambda: _sync_create_customer(email=profile.email, metadata=metadata)
        )
    except stripe.StripeError as exc:
        _log_stripe_error("Customer.create", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="stripe_customer_create_failed",
        ) from exc

    customer_id = getattr(customer, "id", None) or customer["id"]
    profile.stripe_customer_id = customer_id
    await db.commit()
    await db.refresh(profile)
    return customer_id


async def create_checkout_session(
    db: AsyncSession,
    profile: SubscriberProfile,
    plan: str,
) -> str:
    """Create a Stripe Checkout Session in subscription mode and return its URL."""
    _require_stripe_api_key()
    price_id = _price_id_for_plan(plan)
    success_url, cancel_url = resolve_checkout_urls()

    customer_id = await create_or_get_customer(db, profile)

    metadata = {
        "subscriber_profile_id": str(profile.id),
        "supabase_user_id": profile.supabase_user_id,
        "plan": plan,
    }
    try:
        session_obj = await anyio.to_thread.run_sync(
            lambda: _sync_create_checkout_session(
                customer_id=customer_id,
                price_id=price_id,
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=str(profile.id),
                metadata=metadata,
                subscription_metadata=metadata,
            )
        )
    except stripe.StripeError as exc:
        _log_stripe_error("checkout.Session.create", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="stripe_checkout_failed",
        ) from exc

    url = getattr(session_obj, "url", None) or session_obj.get("url")
    if not url:
        # Defensive: Stripe should always return a url, but if for some reason
        # it doesn't, fail loud rather than returning an empty response.
        log.warning("stripe Checkout Session returned no url")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="stripe_checkout_failed",
        )
    return url


async def create_customer_portal_session(
    profile: SubscriberProfile,
) -> str:
    """Create a Stripe Customer Portal session for an existing customer."""
    _require_stripe_api_key()
    if not profile.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stripe_customer_missing",
        )
    return_url = resolve_portal_return_url()

    try:
        session_obj = await anyio.to_thread.run_sync(
            lambda: _sync_create_portal_session(
                customer_id=profile.stripe_customer_id,
                return_url=return_url,
            )
        )
    except stripe.StripeError as exc:
        _log_stripe_error("billing_portal.Session.create", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="stripe_customer_portal_failed",
        ) from exc

    url = getattr(session_obj, "url", None) or session_obj.get("url")
    if not url:
        log.warning("stripe Customer Portal Session returned no url")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="stripe_customer_portal_failed",
        )
    return url
