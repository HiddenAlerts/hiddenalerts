from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriberProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supabase_user_id: str
    email: str
    role: str
    stripe_customer_id: str | None
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None


class SubscriptionRead(BaseModel):
    """Full subscription read shape — used by admin/internal callers later."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stripe_subscription_id: str | None
    stripe_price_id: str | None
    plan_type: str | None
    status: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    canceled_at: datetime | None


class SubscriptionMeRead(BaseModel):
    """Subscriber-facing subscription summary returned by GET /subscriber/me.

    Intentionally a narrower shape than ``SubscriptionRead`` — the frontend only
    needs status, plan, period end, and cancel flag to drive the UI.
    """

    model_config = ConfigDict(from_attributes=True)

    status: str | None
    plan_type: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool


class SubscriberMeResponse(BaseModel):
    """Response shape for GET /api/v1/subscriber/me.

    ``access_level`` is ``"subscriber"`` when the linked subscription grants
    access, else ``"locked"``. The frontend uses this string for paywall
    routing without re-running the access-decision logic.
    """

    authenticated: bool
    has_active_subscription: bool
    access_level: str
    email: str
    subscription: SubscriptionMeRead | None


class SubscriberAccessResponse(BaseModel):
    """Response shape for GET /api/v1/subscriber/access — a route-guard helper."""

    can_access_full_content: bool
    reason: str
