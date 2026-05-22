"""Endpoint tests for POST /api/v1/stripe/webhook.

We patch ``stripe.Webhook.construct_event`` (on the route module) so no real
signature verification or network happens; the idempotency + dispatch service
runs for real against the in-memory DB. The endpoint requires NO Supabase auth.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import stripe_webhooks as webhook_route
from app.config import settings
from app.models.subscriber_profile import SubscriberProfile
from app.models.subscription import Subscription


@pytest.fixture(autouse=True)
def configure_webhook_settings():
    originals = {
        "stripe_webhook_secret": settings.stripe_webhook_secret,
        "stripe_monthly_price_id": settings.stripe_monthly_price_id,
        "stripe_annual_price_id": settings.stripe_annual_price_id,
    }
    settings.stripe_webhook_secret = "whsec_test_dummy"
    settings.stripe_monthly_price_id = "price_monthly_test"
    settings.stripe_annual_price_id = "price_annual_test"
    yield
    for k, v in originals.items():
        setattr(settings, k, v)


def _patch_construct_event(event):
    def _fake(payload, sig_header, secret):
        return event

    return patch.object(
        webhook_route.stripe.Webhook, "construct_event", side_effect=_fake
    )


def _evt(event_type: str, obj: dict, event_id: str | None = None) -> dict:
    return {
        "id": event_id or f"evt_{uuid.uuid4()}",
        "type": event_type,
        "data": {"object": obj},
    }


def _subscription_obj(*, sub_id, customer, price_id="price_monthly_test",
                      status="active", metadata=None, cancel_at_period_end=False):
    return {
        "id": sub_id,
        "customer": customer,
        "status": status,
        "metadata": metadata or {},
        "cancel_at_period_end": cancel_at_period_end,
        "current_period_start": 1_700_000_000,
        "current_period_end": 1_710_000_000,
        "canceled_at": None,
        "items": {"data": [{"price": {"id": price_id}}]},
    }


_HDR = {"Stripe-Signature": "t=1,v1=deadbeef", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Config / signature failure paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWebhookGuards:
    async def test_missing_secret_returns_500(self, client: AsyncClient):
        settings.stripe_webhook_secret = ""
        resp = await client.post(
            "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
        )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "stripe_webhook_not_configured"

    async def test_missing_signature_returns_400(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/stripe/webhook",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "missing_stripe_signature"

    async def test_invalid_signature_returns_400(self, client: AsyncClient):
        def _raise(payload, sig_header, secret):
            raise stripe.SignatureVerificationError(
                "internal stripe diagnostic — must not leak", "sig_header"
            )

        with patch.object(
            webhook_route.stripe.Webhook, "construct_event", side_effect=_raise
        ):
            resp = await client.post(
                "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
            )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid_stripe_signature"
        assert "internal stripe diagnostic" not in resp.text

    async def test_malformed_payload_value_error_returns_400(self, client: AsyncClient):
        def _raise(payload, sig_header, secret):
            raise ValueError("bad payload")

        with patch.object(
            webhook_route.stripe.Webhook, "construct_event", side_effect=_raise
        ):
            resp = await client.post(
                "/api/v1/stripe/webhook", content=b"not-json", headers=_HDR
            )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid_stripe_signature"


# ---------------------------------------------------------------------------
# Dispatch outcomes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWebhookDispatch:
    async def test_unknown_event_type_ignored(self, client: AsyncClient):
        event = _evt("customer.created", {"id": "cus_unknown"})
        with _patch_construct_event(event):
            resp = await client.post(
                "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ignored"
        assert body["event_type"] == "customer.created"

    async def test_duplicate_event_not_reprocessed(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        profile = SubscriberProfile(
            supabase_user_id=f"wh-dup-{uuid.uuid4()}",
            email="dup@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.commit()

        sub_id = f"sub_{uuid.uuid4()}"
        event_id = f"evt_dup_{uuid.uuid4()}"
        event1 = _evt(
            "customer.subscription.created",
            _subscription_obj(
                sub_id=sub_id,
                customer="cus_dup",
                status="active",
                metadata={"subscriber_profile_id": str(profile.id)},
            ),
            event_id=event_id,
        )
        with _patch_construct_event(event1):
            r1 = await client.post(
                "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
            )
        assert r1.json()["status"] == "processed"

        # Same event id, but a "canceled" body — must NOT be reprocessed.
        event2 = _evt(
            "customer.subscription.updated",
            _subscription_obj(
                sub_id=sub_id,
                customer="cus_dup",
                status="canceled",
                metadata={"subscriber_profile_id": str(profile.id)},
            ),
            event_id=event_id,
        )
        with _patch_construct_event(event2):
            r2 = await client.post(
                "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
            )
        assert r2.json()["status"] == "duplicate"

        # Status stayed "active" because the duplicate was not processed.
        result = await db_session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        row = result.scalar_one()
        assert row.status == "active"

    async def test_checkout_completed_updates_profile_customer(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        profile = SubscriberProfile(
            supabase_user_id=f"wh-co-{uuid.uuid4()}",
            email="co@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.commit()

        session = {
            "id": "cs_api",
            "client_reference_id": str(profile.id),
            "customer": "cus_api_checkout",
            "metadata": {"subscriber_profile_id": str(profile.id), "plan": "monthly"},
            "subscription": "sub_str",
        }
        with _patch_construct_event(_evt("checkout.session.completed", session)):
            resp = await client.post(
                "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"
        await db_session.refresh(profile)
        assert profile.stripe_customer_id == "cus_api_checkout"

    async def test_checkout_completed_expanded_subscription_creates_row(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        profile = SubscriberProfile(
            supabase_user_id=f"wh-coe-{uuid.uuid4()}",
            email="coe@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.commit()

        sub_id = f"sub_{uuid.uuid4()}"
        session = {
            "id": "cs_exp",
            "client_reference_id": str(profile.id),
            "customer": "cus_exp",
            "metadata": {"subscriber_profile_id": str(profile.id)},
            "subscription": _subscription_obj(sub_id=sub_id, customer="cus_exp"),
        }
        with _patch_construct_event(_evt("checkout.session.completed", session)):
            resp = await client.post(
                "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
            )
        assert resp.status_code == 200
        result = await db_session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        assert result.scalar_one().subscriber_profile_id == profile.id

    async def test_subscription_created_creates_row(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        profile = SubscriberProfile(
            supabase_user_id=f"wh-cr-{uuid.uuid4()}",
            email="cr@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.commit()

        sub_id = f"sub_{uuid.uuid4()}"
        event = _evt(
            "customer.subscription.created",
            _subscription_obj(
                sub_id=sub_id,
                customer="cus_cr",
                metadata={"subscriber_profile_id": str(profile.id)},
            ),
        )
        with _patch_construct_event(event):
            resp = await client.post(
                "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
            )
        assert resp.json()["status"] == "processed"
        result = await db_session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        row = result.scalar_one()
        assert row.status == "active"
        assert row.plan_type == "monthly"

    async def test_subscription_deleted_marks_canceled(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        profile = SubscriberProfile(
            supabase_user_id=f"wh-del-{uuid.uuid4()}",
            email="del@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.commit()
        sub_id = f"sub_{uuid.uuid4()}"
        meta = {"subscriber_profile_id": str(profile.id)}

        with _patch_construct_event(
            _evt(
                "customer.subscription.created",
                _subscription_obj(sub_id=sub_id, customer="cus_del", metadata=meta),
            )
        ):
            await client.post("/api/v1/stripe/webhook", content=b"{}", headers=_HDR)

        with _patch_construct_event(
            _evt(
                "customer.subscription.deleted",
                _subscription_obj(
                    sub_id=sub_id, customer="cus_del", status="canceled", metadata=meta
                ),
            )
        ):
            resp = await client.post(
                "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
            )
        assert resp.json()["status"] == "processed"
        result = await db_session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        assert result.scalar_one().status == "canceled"

    async def test_invoice_payment_failed_sets_past_due(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        profile = SubscriberProfile(
            supabase_user_id=f"wh-pf-{uuid.uuid4()}",
            email="pf@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.commit()
        sub_id = f"sub_{uuid.uuid4()}"
        meta = {"subscriber_profile_id": str(profile.id)}

        with _patch_construct_event(
            _evt(
                "customer.subscription.created",
                _subscription_obj(sub_id=sub_id, customer="cus_pf", metadata=meta),
            )
        ):
            await client.post("/api/v1/stripe/webhook", content=b"{}", headers=_HDR)

        with _patch_construct_event(
            _evt("invoice.payment_failed", {"id": "in_api", "subscription": sub_id})
        ):
            resp = await client.post(
                "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
            )
        assert resp.json()["status"] == "processed"
        result = await db_session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        assert result.scalar_one().status == "past_due"

    async def test_invoice_payment_succeeded_minimal_payload(self, client: AsyncClient):
        with _patch_construct_event(
            _evt("invoice.payment_succeeded", {"id": "in_min"})
        ):
            resp = await client.post(
                "/api/v1/stripe/webhook", content=b"{}", headers=_HDR
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"
