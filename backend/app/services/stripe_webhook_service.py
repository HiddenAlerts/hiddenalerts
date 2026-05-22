"""Stripe webhook event processing — Authentication & Payment Phase 1, Slice 4.

This module is the trusted writer for subscription state. The route layer
(``app.api.stripe_webhooks``) verifies the Stripe signature, then hands the
parsed event here. We never trust frontend state for access — the local
``subscriptions`` table is kept in sync only from verified Stripe events.

Idempotency: every event is recorded in ``stripe_webhook_events`` keyed on the
unique ``stripe_event_id``. Duplicates (Stripe retries) are detected by a fast
pre-SELECT and, under a concurrent race, by catching the unique-constraint
``IntegrityError`` on flush. In both cases we return ``duplicate`` without
re-running any handler.

Never logs raw payloads or secrets.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.stripe_webhook_event import StripeWebhookEvent
from app.models.subscriber_profile import SubscriberProfile
from app.models.subscription import Subscription

log = logging.getLogger(__name__)

# Event types we actively handle. Anything else is stored and ignored.
_SUBSCRIPTION_UPSERT_EVENTS = frozenset(
    {"customer.subscription.created", "customer.subscription.updated"}
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def stripe_timestamp_to_utc(value: Any) -> datetime | None:
    """Convert a Stripe Unix-seconds timestamp to a timezone-aware UTC datetime.

    Returns ``None`` only when ``value`` is ``None`` or cannot be coerced to an
    int. ``0`` is a valid epoch and converts to 1970-01-01T00:00:00+00:00 — we
    deliberately do NOT use a truthy check here.
    """
    if value is None:
        return None
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def _plan_type_for_price(price_id: str | None) -> str | None:
    if price_id and price_id == settings.stripe_monthly_price_id:
        return "monthly"
    if price_id and price_id == settings.stripe_annual_price_id:
        return "annual"
    return None


def _extract_price_id(subscription: Mapping[str, Any]) -> str | None:
    """Pull the first subscription item's price id, defensive against gaps."""
    try:
        items = subscription.get("items") or {}
        data = items.get("data") or []
        if not data:
            return None
        price = data[0].get("price") or {}
        return price.get("id")
    except (AttributeError, IndexError, TypeError):
        return None


def _event_to_jsonable(event: Any) -> dict:
    """Best-effort conversion of a Stripe event (or dict) to a JSON-storable dict."""
    to_dict = getattr(event, "to_dict_recursive", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:  # noqa: BLE001 — never let serialization break the webhook
            pass
    try:
        return json.loads(json.dumps(event, default=str))
    except (TypeError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# Profile resolution
# ---------------------------------------------------------------------------


async def _profile_by_id(
    db: AsyncSession, raw_id: Any
) -> SubscriberProfile | None:
    try:
        profile_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    result = await db.execute(
        select(SubscriberProfile).where(SubscriberProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


async def _profile_by_customer(
    db: AsyncSession, customer_id: Any
) -> SubscriberProfile | None:
    if not customer_id:
        return None
    result = await db.execute(
        select(SubscriberProfile).where(
            SubscriberProfile.stripe_customer_id == customer_id
        )
    )
    return result.scalar_one_or_none()


async def _resolve_profile_for_subscription(
    db: AsyncSession, subscription: Mapping[str, Any]
) -> SubscriberProfile | None:
    """Map a subscription object to a local profile: metadata first, then customer."""
    metadata = subscription.get("metadata") or {}
    profile = await _profile_by_id(db, metadata.get("subscriber_profile_id"))
    if profile is not None:
        return profile
    return await _profile_by_customer(db, subscription.get("customer"))


# ---------------------------------------------------------------------------
# Subscription upsert
# ---------------------------------------------------------------------------


async def _subscription_by_stripe_id(
    db: AsyncSession, stripe_subscription_id: str | None
) -> Subscription | None:
    if not stripe_subscription_id:
        return None
    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_subscription_id
        )
    )
    return result.scalar_one_or_none()


async def _upsert_subscription(
    db: AsyncSession,
    profile: SubscriberProfile,
    subscription: Mapping[str, Any],
) -> Subscription:
    """Create or update the local subscription row keyed on stripe_subscription_id."""
    stripe_subscription_id = subscription.get("id")
    price_id = _extract_price_id(subscription)

    row = await _subscription_by_stripe_id(db, stripe_subscription_id)
    if row is None:
        row = Subscription(
            subscriber_profile_id=profile.id,
            stripe_customer_id=subscription.get("customer") or "",
            stripe_subscription_id=stripe_subscription_id,
        )
        db.add(row)

    row.subscriber_profile_id = profile.id
    if subscription.get("customer"):
        row.stripe_customer_id = subscription["customer"]
    row.stripe_subscription_id = stripe_subscription_id
    row.stripe_price_id = price_id
    row.plan_type = _plan_type_for_price(price_id)
    row.status = subscription.get("status")
    row.current_period_start = stripe_timestamp_to_utc(
        subscription.get("current_period_start")
    )
    row.current_period_end = stripe_timestamp_to_utc(
        subscription.get("current_period_end")
    )
    row.cancel_at_period_end = bool(subscription.get("cancel_at_period_end", False))
    row.canceled_at = stripe_timestamp_to_utc(subscription.get("canceled_at"))
    await db.flush()
    return row


# ---------------------------------------------------------------------------
# Event handlers — each returns "processed"
# ---------------------------------------------------------------------------


async def handle_checkout_session_completed(
    db: AsyncSession, session: Mapping[str, Any]
) -> str:
    # Prefer client_reference_id (we set it to the profile id at checkout),
    # then fall back to metadata.
    metadata = session.get("metadata") or {}
    profile = await _profile_by_id(db, session.get("client_reference_id"))
    if profile is None:
        profile = await _profile_by_id(db, metadata.get("subscriber_profile_id"))

    if profile is None:
        log.warning("checkout.session.completed: no matching subscriber profile")
        return "processed"

    if session.get("customer"):
        profile.stripe_customer_id = session["customer"]

    subscription = session.get("subscription")
    # Only upsert when the subscription is expanded into an object. A bare
    # string id is left for customer.subscription.created/updated to fill in.
    if isinstance(subscription, Mapping):
        await _upsert_subscription(db, profile, subscription)

    await db.flush()
    return "processed"


async def handle_subscription_created_or_updated(
    db: AsyncSession, subscription: Mapping[str, Any]
) -> str:
    profile = await _resolve_profile_for_subscription(db, subscription)
    if profile is None:
        log.warning(
            "customer.subscription.* : no matching subscriber profile for "
            "subscription_id=%s",
            subscription.get("id"),
        )
        return "processed"
    await _upsert_subscription(db, profile, subscription)
    return "processed"


async def handle_subscription_deleted(
    db: AsyncSession, subscription: Mapping[str, Any]
) -> str:
    stripe_subscription_id = subscription.get("id")
    canceled_at = stripe_timestamp_to_utc(
        subscription.get("canceled_at")
    ) or datetime.now(timezone.utc)
    cancel_at_period_end = bool(subscription.get("cancel_at_period_end", False))
    period_end = stripe_timestamp_to_utc(subscription.get("current_period_end"))

    row = await _subscription_by_stripe_id(db, stripe_subscription_id)
    if row is not None:
        row.status = "canceled"
        row.cancel_at_period_end = cancel_at_period_end
        row.canceled_at = canceled_at
        if period_end is not None:
            row.current_period_end = period_end
        await db.flush()
        return "processed"

    # No existing row — create a canceled one if we can map a profile.
    profile = await _resolve_profile_for_subscription(db, subscription)
    if profile is None:
        log.warning(
            "customer.subscription.deleted: no row and no profile mapping for "
            "subscription_id=%s",
            stripe_subscription_id,
        )
        return "processed"

    price_id = _extract_price_id(subscription)
    row = Subscription(
        subscriber_profile_id=profile.id,
        stripe_customer_id=subscription.get("customer") or "",
        stripe_subscription_id=stripe_subscription_id,
        stripe_price_id=price_id,
        plan_type=_plan_type_for_price(price_id),
        status="canceled",
        current_period_end=period_end,
        cancel_at_period_end=cancel_at_period_end,
        canceled_at=canceled_at,
    )
    db.add(row)
    await db.flush()
    return "processed"


async def handle_invoice_payment_failed(
    db: AsyncSession, invoice: Mapping[str, Any]
) -> str:
    stripe_subscription_id = invoice.get("subscription")
    if not stripe_subscription_id:
        return "processed"
    row = await _subscription_by_stripe_id(db, stripe_subscription_id)
    if row is not None and row.status != "canceled":
        row.status = "past_due"
        await db.flush()
    return "processed"


async def handle_invoice_payment_succeeded(
    db: AsyncSession, invoice: Mapping[str, Any]
) -> str:
    stripe_subscription_id = invoice.get("subscription")
    if not stripe_subscription_id:
        return "processed"
    row = await _subscription_by_stripe_id(db, stripe_subscription_id)
    if row is not None and row.status not in {"active", "trialing", "canceled"}:
        row.status = "active"
        await db.flush()
    return "processed"


_HANDLERS = {
    "checkout.session.completed": handle_checkout_session_completed,
    "customer.subscription.created": handle_subscription_created_or_updated,
    "customer.subscription.updated": handle_subscription_created_or_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
    "invoice.payment_failed": handle_invoice_payment_failed,
    "invoice.payment_succeeded": handle_invoice_payment_succeeded,
}


# ---------------------------------------------------------------------------
# Entry point — idempotency + dispatch
# ---------------------------------------------------------------------------


async def process_stripe_event(db: AsyncSession, event: Mapping[str, Any]) -> dict:
    """Idempotently record and dispatch a verified Stripe event.

    Returns one of:
      {"status": "processed", "event_type": ...}
      {"status": "ignored",   "event_type": ...}   (unknown event type)
      {"status": "duplicate", "event_type": ...}   (already seen / race)
    """
    event_id = event["id"]
    event_type = event["type"]

    # Fast path: already recorded → duplicate, no reprocessing, no timestamp touch.
    existing = await db.execute(
        select(StripeWebhookEvent).where(
            StripeWebhookEvent.stripe_event_id == event_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        return {"status": "duplicate", "event_type": event_type}

    # Claim the event id by inserting before any business mutation. If a
    # concurrent request already claimed it, the unique constraint fires here.
    record = StripeWebhookEvent(
        stripe_event_id=event_id,
        event_type=event_type,
        payload_json=_event_to_jsonable(event),
        processed_at=None,
    )
    db.add(record)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # The winner of the race owns processing; we return without dispatching.
        return {"status": "duplicate", "event_type": event_type}

    handler = _HANDLERS.get(event_type)
    if handler is None:
        outcome = "ignored"
    else:
        obj = (event.get("data") or {}).get("object") or {}
        await handler(db, obj)
        outcome = "processed"

    record.processed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": outcome, "event_type": event_type}
