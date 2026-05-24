"""Regression for the Slice 6 hotfix: Stripe id columns must hold real Stripe ids.

A production Stripe checkout session id of 66 chars
(``cs_test_a1ttDjod7dZOSJEyTz5eO8VNVAvoYOGsL5mdfYTGPXTMY48I1mGE07wafL``)
overflowed the original ``VARCHAR(64)`` definition on
``billing_checkout_attempts.stripe_checkout_session_id`` and crashed
``POST /api/v1/billing/checkout`` at commit time. Migration 0009 widened
every Stripe-id column across the four billing tables to ``VARCHAR(255)`` to
match Stripe's documented id ceiling.

These assertions hard-fail if anyone narrows the columns back. SQLite tests
don't enforce varchar length, so this is the layer that catches a regression.
"""
from app.models import (
    BillingCheckoutAttempt,
    StripeWebhookEvent,
    SubscriberProfile,
    Subscription,
)

# Minimum width that safely fits any Stripe id (docs say up to 255).
_MIN_STRIPE_ID_WIDTH = 255


def _column_length(model, column_name: str) -> int:
    col = model.__table__.c[column_name]
    return col.type.length


def test_subscriber_profile_stripe_customer_id_wide_enough():
    assert (
        _column_length(SubscriberProfile, "stripe_customer_id")
        >= _MIN_STRIPE_ID_WIDTH
    )


def test_subscription_stripe_id_columns_wide_enough():
    assert (
        _column_length(Subscription, "stripe_customer_id")
        >= _MIN_STRIPE_ID_WIDTH
    )
    assert (
        _column_length(Subscription, "stripe_subscription_id")
        >= _MIN_STRIPE_ID_WIDTH
    )
    assert (
        _column_length(Subscription, "stripe_price_id")
        >= _MIN_STRIPE_ID_WIDTH
    )


def test_stripe_webhook_event_id_wide_enough():
    assert (
        _column_length(StripeWebhookEvent, "stripe_event_id")
        >= _MIN_STRIPE_ID_WIDTH
    )


def test_billing_checkout_attempt_session_id_wide_enough():
    assert (
        _column_length(BillingCheckoutAttempt, "stripe_checkout_session_id")
        >= _MIN_STRIPE_ID_WIDTH
    )
