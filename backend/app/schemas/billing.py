from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    plan: Literal["monthly", "annual"]


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class BillingStatusResponse(BaseModel):
    """Local view of a subscriber's billing state — never touches Stripe.

    Source of truth: the ``subscriptions`` table, which the webhook keeps in
    sync with Stripe in Slice 4. ``has_active_access`` is derived on read by
    :func:`app.services.subscription_service.has_active_subscription_access`.
    """

    has_active_access: bool
    subscription_status: str | None
    plan_type: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
