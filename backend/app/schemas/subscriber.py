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


class SubscriberMeResponse(BaseModel):
    profile: SubscriberProfileRead
    subscription: SubscriptionRead | None
    has_access: bool
