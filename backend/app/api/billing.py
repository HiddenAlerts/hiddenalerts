"""Billing API — Stripe checkout, customer portal, local billing status, sync.

Mounted at ``/api/v1/billing/*`` in ``app.main``. Every route requires a valid
Supabase Bearer token (enforced by :func:`get_current_subscriber`).

Slice 6 reliability layer:
- ``POST /checkout`` accepts an optional ``X-Idempotency-Key`` header; backend
  generates a UUID if absent. Same key + same subscriber → same ``checkout_url``
  without a second Stripe call. Recent same-(subscriber, plan) attempts are
  also folded together when no header is sent (double-click protection).
  Already-active subscribers get ``409 already_subscribed`` — no double-charge.
- ``POST /portal`` requires a Stripe customer to already exist —
  400 ``stripe_customer_missing`` otherwise.
- ``GET /status`` is read-only against the local ``subscriptions`` table —
  never calls Stripe. The webhook is the trusted writer.
- ``POST /sync`` is the reconciliation fallback for when the webhook is
  delayed or has failed: it calls Stripe, picks the highest-access
  subscription, upserts the local row, and returns the resulting status.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase import SubscriberContext, get_current_subscriber
from app.config import settings
from app.database import get_db
from app.models.billing_checkout_attempt import BillingCheckoutAttempt
from app.models.subscription import Subscription
from app.schemas.billing import (
    BillingStatusResponse,
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
)
from app.services import stripe_service
from app.services.stripe_webhook_service import (
    stripe_timestamp_to_utc,
    upsert_subscription_from_stripe,
)
from app.services.subscription_service import has_active_subscription_access

log = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

# Window for folding header-less double-clicks into a single attempt.
_RECENT_ATTEMPT_WINDOW = timedelta(minutes=30)
_MAX_IDEMPOTENCY_KEY_LEN = 255


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


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


def _billing_status_from_subscription(
    subscription: Subscription | None,
) -> BillingStatusResponse:
    """Single source of truth for the BillingStatusResponse shape.

    Used by both ``GET /status`` (always) and ``POST /sync`` (after upsert).
    Keeps the response identical so the frontend reads them interchangeably.
    """
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
            subscription.status,
            subscription.current_period_end,
            grace_seconds=settings.subscription_access_grace_seconds,
        ),
        subscription_status=subscription.status,
        plan_type=subscription.plan_type,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
    )


# ---------------------------------------------------------------------------
# Idempotency-key validation + recent-attempt reuse
# ---------------------------------------------------------------------------


def _validate_idempotency_key(raw: str) -> str:
    """Normalize and validate a client-supplied X-Idempotency-Key.

    Rules:
      - Strip whitespace.
      - Reject empty.
      - Reject if longer than ``_MAX_IDEMPOTENCY_KEY_LEN``.
      - Reject if it contains ``@`` (rough email/PII shape — keys are persisted
        in our local table and must stay opaque).
    All failures raise ``HTTPException(422, "invalid_idempotency_key")``.
    Never log the full value (caller truncates for logging).
    """
    key = (raw or "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_idempotency_key",
        )
    if len(key) > _MAX_IDEMPOTENCY_KEY_LEN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_idempotency_key",
        )
    if "@" in key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_idempotency_key",
        )
    return key


async def _recent_reusable_attempt(
    db: AsyncSession,
    *,
    subscriber_profile_id: int,
    plan_type: str,
) -> BillingCheckoutAttempt | None:
    """Find a recent same-(subscriber, plan) attempt whose ``checkout_url`` we
    can hand back without calling Stripe again.

    Only invoked when the frontend did NOT supply an idempotency key — guards
    against double-clicks / no-header retries creating duplicate Stripe
    Checkout Sessions. Window: 30 minutes (well inside Stripe's 24h Checkout
    session validity).
    """
    cutoff = datetime.now(timezone.utc) - _RECENT_ATTEMPT_WINDOW
    result = await db.execute(
        select(BillingCheckoutAttempt)
        .where(
            BillingCheckoutAttempt.subscriber_profile_id == subscriber_profile_id,
            BillingCheckoutAttempt.plan_type == plan_type,
            BillingCheckoutAttempt.status.in_(("pending", "succeeded")),
            BillingCheckoutAttempt.checkout_url.isnot(None),
            BillingCheckoutAttempt.created_at >= cutoff,
        )
        .order_by(BillingCheckoutAttempt.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _attempt_by_key(
    db: AsyncSession, idempotency_key: str
) -> BillingCheckoutAttempt | None:
    result = await db.execute(
        select(BillingCheckoutAttempt).where(
            BillingCheckoutAttempt.idempotency_key == idempotency_key
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Subscription selection for /sync
# ---------------------------------------------------------------------------


_PRIORITY_BUCKETS = ("active", "trialing")


def _pick_subscription_for_sync(subs: Iterable[dict]) -> dict | None:
    """Pick the best-access Stripe subscription for `/sync`.

    Priority: active > trialing > canceled-with-future-period-end > past_due >
    newest fallback > None. Within each bucket, newest by ``created`` wins.
    Never lets a newer ``incomplete`` overwrite an older ``active`` — `/sync`
    must not reduce a healthy user's access.
    """
    subs = list(subs or [])
    if not subs:
        return None

    def _created(s: dict) -> int:
        try:
            return int(s.get("created") or 0)
        except (TypeError, ValueError):
            return 0

    def _newest_with_status(target: str) -> dict | None:
        matches = [s for s in subs if s.get("status") == target]
        return max(matches, key=_created) if matches else None

    for bucket in _PRIORITY_BUCKETS:
        chosen = _newest_with_status(bucket)
        if chosen is not None:
            return chosen

    # Canceled but still within the paid period.
    now = datetime.now(timezone.utc)
    canceled_future = []
    for s in subs:
        if s.get("status") != "canceled":
            continue
        period_end = stripe_timestamp_to_utc(s.get("current_period_end"))
        if period_end is not None and period_end > now:
            canceled_future.append(s)
    if canceled_future:
        return max(canceled_future, key=_created)

    past_due = _newest_with_status("past_due")
    if past_due is not None:
        return past_due

    # Fallback: newest overall (so the local row reflects the latest Stripe
    # state even if denied access).
    return max(subs, key=_created)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
    subscriber: SubscriberContext = Depends(get_current_subscriber),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    """Create (or replay) a Stripe Checkout Session and return its URL.

    Idempotency:
      - If ``X-Idempotency-Key`` is supplied, that key is the retry identity:
        same key from the same subscriber returns the same ``checkout_url``;
        same key from a different subscriber is rejected with 409.
      - If absent, the backend (a) folds recent same-(profile, plan) attempts
        together so a double-click reuses the prior URL, then (b) generates a
        UUID so a unique row is still written.

    Active subscribers get ``409 already_subscribed`` — no double-charge.

    Side effect: persists ``stripe_customer_id`` on the subscriber profile on
    the first successful call.
    """
    profile = subscriber.profile
    header_supplied = x_idempotency_key is not None

    # Step 1 + 2: parse + validate header (or generate one).
    if header_supplied:
        idempotency_key = _validate_idempotency_key(x_idempotency_key)
    else:
        idempotency_key = uuid.uuid4().hex

    # Step 3 (no-header only): fold double-clicks to the same URL.
    if not header_supplied:
        recent = await _recent_reusable_attempt(
            db,
            subscriber_profile_id=profile.id,
            plan_type=body.plan,
        )
        if recent is not None:
            return CheckoutResponse(checkout_url=recent.checkout_url)

    # Step 4: refuse to checkout if the user is already an active subscriber.
    current_sub = await _latest_subscription(db, profile.id)
    if current_sub is not None and has_active_subscription_access(
        current_sub.status,
        current_sub.current_period_end,
        grace_seconds=settings.subscription_access_grace_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="already_subscribed",
        )

    # Step 5: attempt lookup by idempotency_key.
    attempt = await _attempt_by_key(db, idempotency_key)
    if attempt is not None:
        if attempt.subscriber_profile_id != profile.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="idempotency_key_conflict",
            )
        if attempt.status == "succeeded" and attempt.checkout_url:
            return CheckoutResponse(checkout_url=attempt.checkout_url)
        if attempt.status == "pending":
            if attempt.checkout_url:
                # Race winner already populated the URL — hand it back.
                return CheckoutResponse(checkout_url=attempt.checkout_url)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="checkout_in_progress",
            )
        # status == "failed" → fall through and retry with the same row.

    # Step 6: create or reuse the attempt row (status=pending).
    if attempt is None:
        attempt = BillingCheckoutAttempt(
            subscriber_profile_id=profile.id,
            plan_type=body.plan,
            idempotency_key=idempotency_key,
            status="pending",
        )
        db.add(attempt)
    else:
        attempt.status = "pending"
        attempt.plan_type = body.plan
    await db.flush()

    # Step 7: operation-scoped Stripe keys so one user-supplied key can't
    # collide across Stripe's customer/checkout operations.
    customer_key = f"customer:{profile.id}:{idempotency_key}"
    checkout_key = f"checkout:{profile.id}:{body.plan}:{idempotency_key}"

    log.info(
        "billing checkout starting: profile_id=%s plan=%s key_prefix=%s",
        profile.id,
        body.plan,
        idempotency_key[:8],
    )

    # Step 8 + 9 + 10: call Stripe; update the attempt row.
    try:
        result = await stripe_service.create_checkout_session(
            db,
            profile,
            body.plan,
            idempotency_key=checkout_key,
            customer_idempotency_key=customer_key,
        )
    except HTTPException:
        attempt.status = "failed"
        await db.commit()
        raise

    attempt.stripe_checkout_session_id = result.get("id")
    attempt.checkout_url = result["url"]
    attempt.status = "succeeded"
    await db.commit()
    return CheckoutResponse(checkout_url=result["url"])


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

    Never calls Stripe. The webhook is the trusted writer; ``/sync`` is the
    explicit reconciliation fallback when the webhook is delayed/missed.
    """
    subscription = await _latest_subscription(db, subscriber.profile.id)
    return _billing_status_from_subscription(subscription)


@router.post("/sync", response_model=BillingStatusResponse)
async def sync_billing_from_stripe(
    subscriber: SubscriberContext = Depends(get_current_subscriber),
    db: AsyncSession = Depends(get_db),
) -> BillingStatusResponse:
    """Reconcile local subscription state from Stripe and return billing status.

    Intended use: the frontend's post-checkout success page calls this before
    deciding access, in case the Stripe webhook is delayed or has failed. It
    cannot grant access on its own — it writes the row through the same mapper
    the webhook uses, and ``has_active_subscription_access`` decides.

    Selects the best-access subscription on the Stripe side so a newer
    ``incomplete`` never overwrites an older ``active`` row.
    """
    profile = subscriber.profile
    if not profile.stripe_customer_id:
        # No Stripe customer yet → can't sync; return the local view.
        return _billing_status_from_subscription(None)

    try:
        subs = await stripe_service.list_customer_subscriptions(
            profile.stripe_customer_id
        )
    except stripe.StripeError:
        log.warning(
            "stripe billing sync failed: profile_id=%s", profile.id
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="stripe_billing_sync_failed",
        )

    chosen = _pick_subscription_for_sync(subs)
    if chosen is not None:
        await upsert_subscription_from_stripe(db, profile, chosen)
        await db.commit()

    subscription = await _latest_subscription(db, profile.id)
    return _billing_status_from_subscription(subscription)
