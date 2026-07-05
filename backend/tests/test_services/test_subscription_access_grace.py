"""Grace-seconds tests for has_active_subscription_access (Slice 5 addition).

The new ``grace_seconds`` kwarg extends the canceled access window. Default 0
must preserve all prior behavior (covered by test_subscription_service.py).
"""
from datetime import datetime, timedelta, timezone

from app.services.subscription_service import has_active_subscription_access

NOW = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)


class TestGraceSeconds:
    def test_grace_extends_canceled_past_period_end(self):
        # Period ended 30s ago; 60s grace → still granted.
        period_end = NOW - timedelta(seconds=30)
        assert (
            has_active_subscription_access(
                "canceled", period_end, now=NOW, grace_seconds=60
            )
            is True
        )

    def test_grace_too_small_still_denies(self):
        period_end = NOW - timedelta(seconds=120)
        assert (
            has_active_subscription_access(
                "canceled", period_end, now=NOW, grace_seconds=60
            )
            is False
        )

    def test_default_grace_zero_preserves_behavior(self):
        # Without grace, a just-past period end denies.
        period_end = NOW - timedelta(seconds=1)
        assert (
            has_active_subscription_access("canceled", period_end, now=NOW) is False
        )

    def test_grace_does_not_revive_past_due(self):
        # Grace only applies to the canceled branch — never past_due.
        period_end = NOW + timedelta(days=5)
        assert (
            has_active_subscription_access(
                "past_due", period_end, now=NOW, grace_seconds=100000
            )
            is False
        )

    def test_grace_irrelevant_for_active(self):
        assert (
            has_active_subscription_access(
                "active", None, now=NOW, grace_seconds=999
            )
            is True
        )

    def test_negative_grace_treated_as_zero(self):
        period_end = NOW - timedelta(seconds=5)
        assert (
            has_active_subscription_access(
                "canceled", period_end, now=NOW, grace_seconds=-100
            )
            is False
        )
