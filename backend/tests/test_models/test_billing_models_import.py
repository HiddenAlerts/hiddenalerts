"""Smoke tests for Auth/Payment Phase 1 models.

Verifies the three new models are importable, exported from app.models, and
registered on Base.metadata so Alembic + the test engine pick them up.
"""
from app.models import (
    Base,
    StripeWebhookEvent,
    SubscriberProfile,
    Subscription,
)


def test_subscriber_profile_table_registered():
    assert SubscriberProfile.__tablename__ == "subscriber_profiles"
    assert "subscriber_profiles" in Base.metadata.tables


def test_subscription_table_registered():
    assert Subscription.__tablename__ == "subscriptions"
    assert "subscriptions" in Base.metadata.tables


def test_stripe_webhook_event_table_registered():
    assert StripeWebhookEvent.__tablename__ == "stripe_webhook_events"
    assert "stripe_webhook_events" in Base.metadata.tables


def test_subscription_has_subscriber_profile_fk():
    table = Base.metadata.tables["subscriptions"]
    fkeys = list(table.c["subscriber_profile_id"].foreign_keys)
    assert len(fkeys) == 1
    assert fkeys[0].column.table.name == "subscriber_profiles"
