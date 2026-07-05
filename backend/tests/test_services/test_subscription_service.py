"""Tests for app/services/subscription_service.py — pure access-matrix decisions.

Mirrors the access rules in CLAUDE.md:
  - active / trialing grant access regardless of period_end
  - canceled grants access only while current_period_end is in the future
  - past_due, unpaid, incomplete, incomplete_expired, None, unknown deny access
"""
from datetime import datetime, timedelta, timezone

from app.services.subscription_service import has_active_subscription_access


FIXED_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


class TestStatusGrantsAccess:
    def test_active_grants_access(self):
        assert (
            has_active_subscription_access("active", None, now=FIXED_NOW) is True
        )

    def test_trialing_grants_access(self):
        assert (
            has_active_subscription_access("trialing", None, now=FIXED_NOW) is True
        )

    def test_active_grants_access_even_without_period_end(self):
        # period_end is irrelevant for active subscriptions
        assert (
            has_active_subscription_access("active", None, now=FIXED_NOW) is True
        )


class TestCanceledStatus:
    def test_canceled_with_future_period_end_grants_access(self):
        future = FIXED_NOW + timedelta(hours=1)
        assert (
            has_active_subscription_access("canceled", future, now=FIXED_NOW) is True
        )

    def test_canceled_with_past_period_end_denies_access(self):
        past = FIXED_NOW - timedelta(hours=1)
        assert (
            has_active_subscription_access("canceled", past, now=FIXED_NOW) is False
        )

    def test_canceled_with_no_period_end_denies_access(self):
        assert (
            has_active_subscription_access("canceled", None, now=FIXED_NOW) is False
        )

    def test_canceled_with_naive_future_datetime_is_treated_as_utc(self):
        # Naive datetimes must be interpreted as UTC to avoid accidentally
        # granting (or denying) access based on a missing tzinfo.
        naive_future = (FIXED_NOW + timedelta(hours=1)).replace(tzinfo=None)
        assert (
            has_active_subscription_access(
                "canceled", naive_future, now=FIXED_NOW
            )
            is True
        )


class TestInactiveStatuses:
    def test_past_due_denies_access(self):
        assert (
            has_active_subscription_access(
                "past_due",
                FIXED_NOW + timedelta(days=30),
                now=FIXED_NOW,
            )
            is False
        )

    def test_unpaid_denies_access(self):
        assert (
            has_active_subscription_access(
                "unpaid",
                FIXED_NOW + timedelta(days=30),
                now=FIXED_NOW,
            )
            is False
        )

    def test_incomplete_denies_access(self):
        assert (
            has_active_subscription_access(
                "incomplete",
                FIXED_NOW + timedelta(days=30),
                now=FIXED_NOW,
            )
            is False
        )

    def test_incomplete_expired_denies_access(self):
        assert (
            has_active_subscription_access(
                "incomplete_expired",
                FIXED_NOW + timedelta(days=30),
                now=FIXED_NOW,
            )
            is False
        )

    def test_unknown_status_denies_access(self):
        assert (
            has_active_subscription_access(
                "something_else",
                FIXED_NOW + timedelta(days=30),
                now=FIXED_NOW,
            )
            is False
        )


class TestMissingValues:
    def test_none_status_denies_access(self):
        assert has_active_subscription_access(None, None, now=FIXED_NOW) is False

    def test_none_status_denies_access_even_with_future_period_end(self):
        assert (
            has_active_subscription_access(
                None,
                FIXED_NOW + timedelta(days=30),
                now=FIXED_NOW,
            )
            is False
        )


class TestNowParameter:
    def test_injected_now_is_honored(self):
        # Period ends at 13:00 UTC; injected now=12:00 UTC → access granted.
        period_end = datetime(2026, 5, 19, 13, 0, 0, tzinfo=timezone.utc)
        injected_now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
        assert (
            has_active_subscription_access(
                "canceled", period_end, now=injected_now
            )
            is True
        )

    def test_injected_now_after_period_end_denies(self):
        # Period ends at 12:00 UTC; injected now=13:00 UTC → access denied.
        period_end = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
        injected_now = datetime(2026, 5, 19, 13, 0, 0, tzinfo=timezone.utc)
        assert (
            has_active_subscription_access(
                "canceled", period_end, now=injected_now
            )
            is False
        )

    def test_default_now_uses_current_utc_time(self):
        # Without injecting now, an obviously-future period end still grants access
        # for a canceled subscription.
        far_future = datetime.now(timezone.utc) + timedelta(days=365)
        assert has_active_subscription_access("canceled", far_future) is True
