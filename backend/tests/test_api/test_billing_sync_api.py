"""Slice 6 — POST /api/v1/billing/sync (recovery fallback) + priority selection.

Webhook stays the trusted writer; /sync is the explicit reconciliation path
the frontend hits on the post-checkout success page when the webhook is
delayed/missed. Critical guarantee: /sync can NEVER reduce access from a
healthy state to a worse one — that's what _pick_subscription_for_sync
enforces with its priority order.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import billing as billing_api
from app.auth import supabase as supabase_auth
from app.config import settings
from app.models.subscriber_profile import SubscriberProfile
from app.services import stripe_service


@pytest.fixture(autouse=True)
def configure_settings():
    originals = {
        "stripe_secret_key": settings.stripe_secret_key,
        "stripe_monthly_price_id": settings.stripe_monthly_price_id,
        "stripe_annual_price_id": settings.stripe_annual_price_id,
    }
    settings.stripe_secret_key = "sk_test_dummy"
    settings.stripe_monthly_price_id = "price_monthly_test"
    settings.stripe_annual_price_id = "price_annual_test"
    yield
    for k, v in originals.items():
        setattr(settings, k, v)


def _claims(sub: str) -> dict:
    return {
        "sub": sub,
        "email": f"{sub}@example.com",
        "aud": "authenticated",
        "iss": "https://test.supabase.co/auth/v1",
    }


def _patch_validator(claims):
    async def _fake(token):
        return claims

    return patch.object(
        supabase_auth, "validate_supabase_token", side_effect=_fake
    )


def _ts(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc if dt.tzinfo is None else dt.tzinfo).timestamp())


def _sub_dict(
    *,
    sub_id: str,
    customer: str,
    status: str,
    price_id: str = "price_monthly_test",
    created: datetime | None = None,
    period_end: datetime | None = None,
    cancel_at_period_end: bool = False,
):
    base_created = created or datetime.now(timezone.utc)
    base_end = period_end or (datetime.now(timezone.utc) + timedelta(days=15))
    return {
        "id": sub_id,
        "customer": customer,
        "status": status,
        "metadata": {},
        "cancel_at_period_end": cancel_at_period_end,
        "current_period_start": _ts(base_created),
        "current_period_end": _ts(base_end),
        "canceled_at": None,
        "created": _ts(base_created),
        "items": {"data": [{"price": {"id": price_id}}]},
    }


async def _seed_profile(db_session, sub: str, **extra) -> SubscriberProfile:
    profile = SubscriberProfile(
        supabase_user_id=sub,
        email=f"{sub}@example.com",
        role="subscriber",
        **extra,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# _pick_subscription_for_sync — pure unit tests
# ---------------------------------------------------------------------------


def _mk(status: str, created: int, period_end_offset_s: int = 86400) -> dict:
    now = int(datetime.now(timezone.utc).timestamp())
    return {
        "id": f"sub_{uuid.uuid4()}",
        "status": status,
        "created": created,
        "current_period_end": now + period_end_offset_s,
        "items": {"data": [{"price": {"id": "price_monthly_test"}}]},
        "customer": "cus_x",
    }


class TestPickSubscriptionForSync:
    def test_active_beats_newer_incomplete(self):
        # Older active, newer incomplete → active wins (the critical case).
        active = _mk("active", created=1000)
        incomplete = _mk("incomplete", created=2000)
        assert billing_api._pick_subscription_for_sync([incomplete, active]) is active

    def test_trialing_beats_canceled_future(self):
        trial = _mk("trialing", created=1000)
        canceled = _mk("canceled", created=2000)
        assert billing_api._pick_subscription_for_sync([canceled, trial]) is trial

    def test_canceled_with_future_period_end_beats_past_due(self):
        canceled = _mk("canceled", created=1000, period_end_offset_s=3600)
        past_due = _mk("past_due", created=2000)
        assert (
            billing_api._pick_subscription_for_sync([past_due, canceled])
            is canceled
        )

    def test_canceled_with_past_period_end_does_not_qualify(self):
        canceled_past = _mk("canceled", created=1000, period_end_offset_s=-3600)
        past_due = _mk("past_due", created=500)
        assert (
            billing_api._pick_subscription_for_sync([canceled_past, past_due])
            is past_due
        )

    def test_falls_back_to_newest(self):
        a = _mk("incomplete", created=1000)
        b = _mk("incomplete_expired", created=2000)
        assert billing_api._pick_subscription_for_sync([a, b]) is b

    def test_empty_returns_none(self):
        assert billing_api._pick_subscription_for_sync([]) is None
        assert billing_api._pick_subscription_for_sync(None) is None


# ---------------------------------------------------------------------------
# POST /api/v1/billing/sync — endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSyncEndpoint:
    async def test_no_auth_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/billing/sync")
        assert resp.status_code == 401

    async def test_no_stripe_customer_returns_inactive_without_calling_stripe(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"syncnc-{uuid.uuid4()}"
        await _seed_profile(db_session, sub)
        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_list_subscriptions"
        ) as list_mock:
            resp = await client.post(
                "/api/v1/billing/sync",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active_access"] is False
        assert body["subscription_status"] is None
        list_mock.assert_not_called()

    async def test_active_stripe_subscription_grants_access(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"syncact-{uuid.uuid4()}"
        await _seed_profile(db_session, sub, stripe_customer_id="cus_sync_act")
        active = _sub_dict(
            sub_id=f"sub_{uuid.uuid4()}",
            customer="cus_sync_act",
            status="active",
        )
        fake_list = type("L", (), {"data": [active]})()
        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_list_subscriptions", return_value=fake_list
        ):
            resp = await client.post(
                "/api/v1/billing/sync",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active_access"] is True
        assert body["subscription_status"] == "active"
        assert body["plan_type"] == "monthly"

    async def test_incomplete_subscription_does_not_grant_access(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"syncinc-{uuid.uuid4()}"
        await _seed_profile(db_session, sub, stripe_customer_id="cus_sync_inc")
        incomplete = _sub_dict(
            sub_id=f"sub_{uuid.uuid4()}",
            customer="cus_sync_inc",
            status="incomplete",
        )
        fake_list = type("L", (), {"data": [incomplete]})()
        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_list_subscriptions", return_value=fake_list
        ):
            resp = await client.post(
                "/api/v1/billing/sync",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active_access"] is False
        assert body["subscription_status"] == "incomplete"

    async def test_older_active_wins_over_newer_incomplete(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """The headline guarantee: /sync must never overwrite active access."""
        sub = f"syncpick-{uuid.uuid4()}"
        await _seed_profile(db_session, sub, stripe_customer_id="cus_sync_pick")
        old_active = _sub_dict(
            sub_id="sub_old_active",
            customer="cus_sync_pick",
            status="active",
            created=datetime.now(timezone.utc) - timedelta(days=30),
        )
        new_incomplete = _sub_dict(
            sub_id="sub_new_incomplete",
            customer="cus_sync_pick",
            status="incomplete",
            created=datetime.now(timezone.utc),
        )
        fake_list = type("L", (), {"data": [new_incomplete, old_active]})()
        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_list_subscriptions", return_value=fake_list
        ):
            resp = await client.post(
                "/api/v1/billing/sync",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active_access"] is True
        assert body["subscription_status"] == "active"

    async def test_real_stripe_subscription_objects_normalize(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Regression for the production 'AttributeError: get' inside
        /billing/sync: stripe-python returns ``stripe.Subscription`` (a
        StripeObject) for each item, and our list helper must normalize them
        to plain dicts BEFORE the sort key calls ``.get('created')``.
        """
        import stripe

        sub = f"real-sync-{uuid.uuid4()}"
        await _seed_profile(db_session, sub, stripe_customer_id="cus_real_sync")

        real_sub = stripe.Subscription.construct_from(
            {
                "id": f"sub_real_{uuid.uuid4()}",
                "customer": "cus_real_sync",
                "status": "active",
                "created": 1_700_000_500,
                "current_period_start": 1_700_000_500,
                "current_period_end": int(
                    (datetime.now(timezone.utc) + timedelta(days=20)).timestamp()
                ),
                "cancel_at_period_end": False,
                "canceled_at": None,
                "items": {"data": [{"price": {"id": "price_monthly_test"}}]},
            },
            "sk_test_dummy",
        )
        # Mimic stripe.ListObject by holding the Subscription on .data.
        fake_list = type("L", (), {"data": [real_sub]})()

        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_list_subscriptions", return_value=fake_list
        ):
            resp = await client.post(
                "/api/v1/billing/sync",
                headers={"Authorization": "Bearer ignored"},
            )
        # The previous bug surfaced as 500 + AttributeError: get; must now be 200.
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active_access"] is True
        assert body["subscription_status"] == "active"
        assert body["plan_type"] == "monthly"

    async def test_stripe_error_returns_502(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"syncerr-{uuid.uuid4()}"
        await _seed_profile(db_session, sub, stripe_customer_id="cus_sync_err")

        def _raise(**_):
            raise stripe.StripeError("internal — must not leak")

        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_list_subscriptions", side_effect=_raise
        ):
            resp = await client.post(
                "/api/v1/billing/sync",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 502
        assert resp.json()["detail"] == "stripe_billing_sync_failed"
        assert "internal — must not leak" not in resp.text
