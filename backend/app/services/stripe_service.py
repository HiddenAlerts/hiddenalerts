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
from collections.abc import Mapping
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


def _idempotency_kwargs(idempotency_key: str | None) -> dict[str, str]:
    """Build the kwarg dict for the Stripe SDK — omit when None to avoid
    sending an empty string."""
    return {"idempotency_key": idempotency_key} if idempotency_key else {}


def _sync_create_customer(
    *,
    email: str,
    metadata: dict[str, str],
    idempotency_key: str | None = None,
) -> Any:
    return stripe.Customer.create(
        email=email or None,
        metadata=metadata,
        **_idempotency_kwargs(idempotency_key),
    )


def _sync_create_checkout_session(
    *,
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    client_reference_id: str,
    metadata: dict[str, str],
    subscription_metadata: dict[str, str],
    idempotency_key: str | None = None,
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
        **_idempotency_kwargs(idempotency_key),
    )


def _sync_create_portal_session(*, customer_id: str, return_url: str) -> Any:
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )


def _sync_list_subscriptions(*, customer_id: str, limit: int = 10) -> Any:
    return stripe.Subscription.list(
        customer=customer_id,
        status="all",
        limit=limit,
        expand=["data.items.data.price"],
    )


# ---------------------------------------------------------------------------
# Async wrappers + business logic
# ---------------------------------------------------------------------------


def _log_stripe_error(op: str, exc: Exception) -> None:
    """Log a Stripe error without exposing tokens or response bodies in detail."""
    log.warning("stripe %s failed: %s", op, type(exc).__name__)


def _get_attr_or_key(obj: Any, name: str) -> Any:
    """Read ``obj.name`` if set; otherwise ``obj[name]`` if obj is mapping-like.

    Stripe SDK returns ``StripeObject`` (dict-subclass) but test fixtures often
    use ``SimpleNamespace`` for terseness. This helper accepts both.
    """
    val = getattr(obj, name, None)
    if val is not None:
        return val
    if isinstance(obj, Mapping):
        return obj.get(name)
    return None


async def create_or_get_customer(
    db: AsyncSession,
    profile: SubscriberProfile,
    *,
    idempotency_key: str | None = None,
) -> str:
    """Return the Stripe customer id for ``profile``, creating one on first use.

    Persists ``stripe_customer_id`` back onto the profile so subsequent calls
    reuse the same Stripe customer. When ``idempotency_key`` is provided, it
    is passed to the Stripe SDK so a retried request returns the same
    customer record rather than creating a duplicate.
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
            lambda: _sync_create_customer(
                email=profile.email,
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
        )
    except stripe.StripeError as exc:
        _log_stripe_error("Customer.create", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="stripe_customer_create_failed",
        ) from exc

    customer_id = _get_attr_or_key(customer, "id")
    profile.stripe_customer_id = customer_id
    await db.commit()
    await db.refresh(profile)
    return customer_id


async def create_checkout_session(
    db: AsyncSession,
    profile: SubscriberProfile,
    plan: str,
    *,
    idempotency_key: str | None = None,
    customer_idempotency_key: str | None = None,
) -> str:
    """Create a Stripe Checkout Session in subscription mode and return its URL.

    ``idempotency_key`` is the per-checkout key sent to Stripe so a retried
    request returns the same Checkout Session URL.
    ``customer_idempotency_key`` is forwarded to ``create_or_get_customer`` so
    the customer-creation step is also retry-safe.
    """
    _require_stripe_api_key()
    price_id = _price_id_for_plan(plan)
    success_url, cancel_url = resolve_checkout_urls()

    customer_id = await create_or_get_customer(
        db, profile, idempotency_key=customer_idempotency_key
    )

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
                idempotency_key=idempotency_key,
            )
        )
    except stripe.StripeError as exc:
        _log_stripe_error("checkout.Session.create", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="stripe_checkout_failed",
        ) from exc

    url = _get_attr_or_key(session_obj, "url")
    session_id = _get_attr_or_key(session_obj, "id")
    if not url:
        # Defensive: Stripe should always return a url, but if for some reason
        # it doesn't, fail loud rather than returning an empty response.
        log.warning("stripe Checkout Session returned no url")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="stripe_checkout_failed",
        )
    return {"id": session_id, "url": url}


async def list_customer_subscriptions(
    customer_id: str, limit: int = 10
) -> list[dict]:
    """List Stripe subscriptions for a customer, normalized to plain dicts.

    Used by ``POST /api/v1/billing/sync`` to reconcile local subscription state
    when the webhook is delayed or has failed. Returns newest-first.
    ``stripe.StripeError`` propagates so callers can map it to a clean 502.
    """
    from app.services.stripe_webhook_service import stripe_object_to_dict

    _require_stripe_api_key()
    raw = await anyio.to_thread.run_sync(
        lambda: _sync_list_subscriptions(customer_id=customer_id, limit=limit)
    )
    # Stripe's list response holds items at .data; tolerate either form.
    data = getattr(raw, "data", None)
    if data is None and isinstance(raw, Mapping):
        data = raw.get("data") or []
    if data is None:
        data = []
    items = [stripe_object_to_dict(item) for item in data]
    # Newest-first by 'created' (Unix seconds). Missing/non-int 'created' sorts
    # to the bottom so it doesn't accidentally win.
    def _created_key(sub: dict) -> int:
        try:
            return int(sub.get("created") or 0)
        except (TypeError, ValueError):
            return 0

    items.sort(key=_created_key, reverse=True)
    return items


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

    url = _get_attr_or_key(session_obj, "url")
    if not url:
        log.warning("stripe Customer Portal Session returned no url")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="stripe_customer_portal_failed",
        )
    return url
