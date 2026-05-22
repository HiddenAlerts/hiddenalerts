"""Endpoint tests for /api/v1/billing/* — Auth/Payment Phase 1 Slice 3.

We mock both Supabase validation (so tests don't need real tokens) and the
Stripe SDK seams (so no network is touched). The billing router code and the
``stripe_service`` business logic run for real against the in-memory DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import supabase as supabase_auth
from app.config import settings
from app.models.subscriber_profile import SubscriberProfile
from app.models.subscription import Subscription
from app.services import stripe_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claims(*, sub: str, email: str = "billing@example.com") -> dict:
    return {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "iss": "https://test.supabase.co/auth/v1",
    }


def _patch_validator(claims):
    async def _fake_validate(token):
        return claims

    return patch.object(
        supabase_auth, "validate_supabase_token", side_effect=_fake_validate
    )


@pytest.fixture(autouse=True)
def configure_stripe_settings():
    originals = {
        "stripe_secret_key": settings.stripe_secret_key,
        "stripe_monthly_price_id": settings.stripe_monthly_price_id,
        "stripe_annual_price_id": settings.stripe_annual_price_id,
        "stripe_checkout_success_url": settings.stripe_checkout_success_url,
        "stripe_checkout_cancel_url": settings.stripe_checkout_cancel_url,
        "stripe_portal_return_url": settings.stripe_portal_return_url,
        "frontend_base_url": settings.frontend_base_url,
    }
    settings.stripe_secret_key = "sk_test_dummy"
    settings.stripe_monthly_price_id = "price_monthly_test"
    settings.stripe_annual_price_id = "price_annual_test"
    settings.stripe_checkout_success_url = "https://app.example/billing/success"
    settings.stripe_checkout_cancel_url = "https://app.example/pricing"
    settings.stripe_portal_return_url = "https://app.example/account/billing"
    settings.frontend_base_url = ""
    yield
    for k, v in originals.items():
        setattr(settings, k, v)


# ---------------------------------------------------------------------------
# POST /billing/checkout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckoutEndpoint:
    async def test_missing_auth_returns_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/billing/checkout", json={"plan": "monthly"}
        )
        assert resp.status_code == 401

    async def test_invalid_plan_returns_422(self, client: AsyncClient):
        sub = f"billing-invalid-plan-{uuid.uuid4()}"
        with _patch_validator(_claims(sub=sub)):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "lifetime"},
                headers={"Authorization": "Bearer ignored"},
            )
        # Pydantic Literal validation -> FastAPI 422
        assert resp.status_code == 422

    async def test_monthly_plan_creates_checkout_url(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"billing-monthly-{uuid.uuid4()}"
        fake_customer = SimpleNamespace(id="cus_for_monthly")
        fake_session = SimpleNamespace(
            url="https://checkout.stripe.com/c/sess_monthly"
        )
        with _patch_validator(_claims(sub=sub)), patch.object(
            stripe_service, "_sync_create_customer", return_value=fake_customer
        ), patch.object(
            stripe_service,
            "_sync_create_checkout_session",
            return_value=fake_session,
        ) as session_mock:
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        assert resp.json() == {
            "checkout_url": "https://checkout.stripe.com/c/sess_monthly"
        }
        kwargs = session_mock.call_args.kwargs
        assert kwargs["price_id"] == "price_monthly_test"
        assert kwargs["metadata"]["plan"] == "monthly"

    async def test_annual_plan_creates_checkout_url(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"billing-annual-{uuid.uuid4()}"
        fake_customer = SimpleNamespace(id="cus_for_annual")
        fake_session = SimpleNamespace(url="https://checkout.stripe.com/c/y")
        with _patch_validator(_claims(sub=sub)), patch.object(
            stripe_service, "_sync_create_customer", return_value=fake_customer
        ), patch.object(
            stripe_service,
            "_sync_create_checkout_session",
            return_value=fake_session,
        ) as session_mock:
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "annual"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        assert session_mock.call_args.kwargs["price_id"] == "price_annual_test"

    async def test_existing_stripe_customer_id_is_reused(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"billing-reuse-{uuid.uuid4()}"
        # Pre-create profile with stripe_customer_id already set
        profile = SubscriberProfile(
            supabase_user_id=sub,
            email="reuse@example.com",
            role="subscriber",
            stripe_customer_id="cus_already_set",
        )
        db_session.add(profile)
        await db_session.commit()

        fake_session = SimpleNamespace(url="https://checkout.stripe.com/c/z")
        with _patch_validator(_claims(sub=sub, email="reuse@example.com")), patch.object(
            stripe_service, "_sync_create_customer"
        ) as customer_mock, patch.object(
            stripe_service,
            "_sync_create_checkout_session",
            return_value=fake_session,
        ) as session_mock:
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        customer_mock.assert_not_called()
        assert session_mock.call_args.kwargs["customer_id"] == "cus_already_set"

    async def test_new_customer_id_is_persisted(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"billing-persist-{uuid.uuid4()}"
        fake_customer = SimpleNamespace(id="cus_persisted_999")
        fake_session = SimpleNamespace(url="https://checkout.stripe.com/c/p")
        with _patch_validator(_claims(sub=sub)), patch.object(
            stripe_service, "_sync_create_customer", return_value=fake_customer
        ), patch.object(
            stripe_service,
            "_sync_create_checkout_session",
            return_value=fake_session,
        ):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200

        result = await db_session.execute(
            select(SubscriberProfile).where(
                SubscriberProfile.supabase_user_id == sub
            )
        )
        profile = result.scalar_one()
        assert profile.stripe_customer_id == "cus_persisted_999"

    async def test_missing_stripe_secret_returns_500(
        self, client: AsyncClient
    ):
        settings.stripe_secret_key = ""
        sub = f"billing-no-secret-{uuid.uuid4()}"
        with _patch_validator(_claims(sub=sub)):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "stripe_not_configured"

    async def test_missing_monthly_price_returns_500(
        self, client: AsyncClient
    ):
        settings.stripe_monthly_price_id = ""
        sub = f"billing-no-monthly-{uuid.uuid4()}"
        with _patch_validator(_claims(sub=sub)):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "stripe_price_not_configured"

    async def test_missing_annual_price_returns_500(
        self, client: AsyncClient
    ):
        settings.stripe_annual_price_id = ""
        sub = f"billing-no-annual-{uuid.uuid4()}"
        with _patch_validator(_claims(sub=sub)):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "annual"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "stripe_price_not_configured"

    async def test_stripe_failure_returns_safe_502(
        self, client: AsyncClient
    ):
        sub = f"billing-stripe-fail-{uuid.uuid4()}"
        fake_customer = SimpleNamespace(id="cus_will_fail")

        def _raise(**_):
            raise stripe.StripeError("internal stripe diagnostic — must not leak")

        with _patch_validator(_claims(sub=sub)), patch.object(
            stripe_service, "_sync_create_customer", return_value=fake_customer
        ), patch.object(
            stripe_service,
            "_sync_create_checkout_session",
            side_effect=_raise,
        ):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 502
        body = resp.json()
        assert body["detail"] == "stripe_checkout_failed"
        # Sanity: the original Stripe diagnostic must not surface to the client.
        assert "internal stripe diagnostic" not in resp.text


# ---------------------------------------------------------------------------
# POST /billing/portal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPortalEndpoint:
    async def test_missing_auth_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/billing/portal")
        assert resp.status_code == 401

    async def test_no_stripe_customer_returns_400(
        self, client: AsyncClient
    ):
        sub = f"portal-nocust-{uuid.uuid4()}"
        with _patch_validator(_claims(sub=sub)):
            resp = await client.post(
                "/api/v1/billing/portal",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "stripe_customer_missing"

    async def test_existing_customer_returns_portal_url(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"portal-ok-{uuid.uuid4()}"
        profile = SubscriberProfile(
            supabase_user_id=sub,
            email="portal@example.com",
            role="subscriber",
            stripe_customer_id="cus_portal_ready",
        )
        db_session.add(profile)
        await db_session.commit()

        fake_session = SimpleNamespace(
            url="https://billing.stripe.com/p/sess_portal"
        )
        with _patch_validator(_claims(sub=sub, email="portal@example.com")), patch.object(
            stripe_service, "_sync_create_portal_session", return_value=fake_session
        ) as mock:
            resp = await client.post(
                "/api/v1/billing/portal",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        assert resp.json() == {
            "portal_url": "https://billing.stripe.com/p/sess_portal"
        }
        assert mock.call_args.kwargs["customer_id"] == "cus_portal_ready"

    async def test_stripe_failure_returns_safe_502(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"portal-fail-{uuid.uuid4()}"
        profile = SubscriberProfile(
            supabase_user_id=sub,
            email="pf@example.com",
            role="subscriber",
            stripe_customer_id="cus_portal_will_fail",
        )
        db_session.add(profile)
        await db_session.commit()

        def _raise(**_):
            raise stripe.StripeError("portal diagnostic — must not leak")

        with _patch_validator(_claims(sub=sub, email="pf@example.com")), patch.object(
            stripe_service, "_sync_create_portal_session", side_effect=_raise
        ):
            resp = await client.post(
                "/api/v1/billing/portal",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 502
        assert resp.json()["detail"] == "stripe_customer_portal_failed"
        assert "portal diagnostic" not in resp.text


# ---------------------------------------------------------------------------
# GET /billing/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBillingStatusEndpoint:
    async def test_no_subscription_returns_false(self, client: AsyncClient):
        sub = f"status-none-{uuid.uuid4()}"
        with _patch_validator(_claims(sub=sub)):
            resp = await client.get(
                "/api/v1/billing/status",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active_access"] is False
        assert body["subscription_status"] is None
        assert body["plan_type"] is None
        assert body["current_period_end"] is None
        assert body["cancel_at_period_end"] is False

    async def test_active_subscription_returns_true(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"status-active-{uuid.uuid4()}"
        profile = SubscriberProfile(
            supabase_user_id=sub,
            email="active@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.flush()
        subscription = Subscription(
            subscriber_profile_id=profile.id,
            stripe_customer_id="cus_active",
            stripe_subscription_id=f"sub_active_{uuid.uuid4()}",
            plan_type="monthly",
            status="active",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=15),
            cancel_at_period_end=False,
        )
        db_session.add(subscription)
        await db_session.commit()

        with _patch_validator(_claims(sub=sub, email="active@example.com")):
            resp = await client.get(
                "/api/v1/billing/status",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active_access"] is True
        assert body["subscription_status"] == "active"
        assert body["plan_type"] == "monthly"
        assert body["cancel_at_period_end"] is False

    async def test_canceled_with_future_period_end_returns_true(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"status-cancel-future-{uuid.uuid4()}"
        profile = SubscriberProfile(
            supabase_user_id=sub,
            email="cf@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.flush()
        subscription = Subscription(
            subscriber_profile_id=profile.id,
            stripe_customer_id="cus_cf",
            stripe_subscription_id=f"sub_cf_{uuid.uuid4()}",
            plan_type="annual",
            status="canceled",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=10),
            cancel_at_period_end=True,
        )
        db_session.add(subscription)
        await db_session.commit()

        with _patch_validator(_claims(sub=sub, email="cf@example.com")):
            resp = await client.get(
                "/api/v1/billing/status",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active_access"] is True
        assert body["subscription_status"] == "canceled"
        assert body["cancel_at_period_end"] is True

    async def test_canceled_with_past_period_end_returns_false(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"status-cancel-past-{uuid.uuid4()}"
        profile = SubscriberProfile(
            supabase_user_id=sub,
            email="cp@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.flush()
        subscription = Subscription(
            subscriber_profile_id=profile.id,
            stripe_customer_id="cus_cp",
            stripe_subscription_id=f"sub_cp_{uuid.uuid4()}",
            plan_type="monthly",
            status="canceled",
            current_period_end=datetime.now(timezone.utc) - timedelta(days=1),
            cancel_at_period_end=True,
        )
        db_session.add(subscription)
        await db_session.commit()

        with _patch_validator(_claims(sub=sub, email="cp@example.com")):
            resp = await client.get(
                "/api/v1/billing/status",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        assert resp.json()["has_active_access"] is False

    async def test_past_due_returns_false(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"status-pastdue-{uuid.uuid4()}"
        profile = SubscriberProfile(
            supabase_user_id=sub,
            email="pd@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.flush()
        subscription = Subscription(
            subscriber_profile_id=profile.id,
            stripe_customer_id="cus_pd",
            stripe_subscription_id=f"sub_pd_{uuid.uuid4()}",
            plan_type="monthly",
            status="past_due",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=10),
            cancel_at_period_end=False,
        )
        db_session.add(subscription)
        await db_session.commit()

        with _patch_validator(_claims(sub=sub, email="pd@example.com")):
            resp = await client.get(
                "/api/v1/billing/status",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active_access"] is False
        assert body["subscription_status"] == "past_due"


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


class TestCorsAllowsPost:
    def test_cors_middleware_allows_post(self):
        # Env-independent: assert the configured CORS middleware permits POST,
        # regardless of whether FRONTEND_BASE_URL locks allow_origins to a
        # specific domain or leaves it as "*". (A live preflight would depend on
        # the request Origin matching the configured origin, which varies by env.)
        from starlette.middleware.cors import CORSMiddleware

        from app.main import app

        cors = [mw for mw in app.user_middleware if mw.cls is CORSMiddleware]
        assert cors, "CORSMiddleware is not configured"
        allow_methods = cors[0].kwargs.get("allow_methods", [])
        assert "POST" in allow_methods
        assert "GET" in allow_methods
        assert "OPTIONS" in allow_methods
