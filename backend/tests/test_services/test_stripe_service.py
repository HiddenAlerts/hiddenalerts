"""Unit tests for app/services/stripe_service.py — Stripe SDK is mocked.

We patch the three sync seams (``_sync_create_customer``,
``_sync_create_checkout_session``, ``_sync_create_portal_session``) so no
network call is made and so we can assert exactly what was passed to Stripe.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pytest_asyncio
import stripe

from app.config import settings
from app.models.subscriber_profile import SubscriberProfile
from app.services import stripe_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


@pytest_asyncio.fixture
async def fresh_profile(db_session):
    profile = SubscriberProfile(
        supabase_user_id=f"svc-user-{uuid.uuid4()}",
        email="svc@example.com",
        role="subscriber",
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# URL fallback tests
# ---------------------------------------------------------------------------


class TestCheckoutUrlFallback:
    def test_explicit_urls_win(self):
        settings.stripe_checkout_success_url = "https://explicit/success"
        settings.stripe_checkout_cancel_url = "https://explicit/cancel"
        settings.frontend_base_url = "https://wrong-base"
        assert stripe_service.resolve_checkout_urls() == (
            "https://explicit/success",
            "https://explicit/cancel",
        )

    def test_derives_from_frontend_base_url_when_unset(self):
        settings.stripe_checkout_success_url = ""
        settings.stripe_checkout_cancel_url = ""
        settings.frontend_base_url = "https://app.example/"
        success, cancel = stripe_service.resolve_checkout_urls()
        assert success == "https://app.example/billing/success"
        assert cancel == "https://app.example/pricing"

    def test_raises_500_when_nothing_resolvable(self):
        settings.stripe_checkout_success_url = ""
        settings.stripe_checkout_cancel_url = ""
        settings.frontend_base_url = ""
        with pytest.raises(stripe_service.HTTPException) as exc:
            stripe_service.resolve_checkout_urls()
        assert exc.value.status_code == 500
        assert exc.value.detail == "stripe_checkout_urls_not_configured"


class TestPortalReturnUrlFallback:
    def test_explicit_url_wins(self):
        settings.stripe_portal_return_url = "https://explicit/return"
        settings.frontend_base_url = "https://wrong"
        assert (
            stripe_service.resolve_portal_return_url()
            == "https://explicit/return"
        )

    def test_derives_from_frontend_base_url_when_unset(self):
        settings.stripe_portal_return_url = ""
        settings.frontend_base_url = "https://app.example"
        assert (
            stripe_service.resolve_portal_return_url()
            == "https://app.example/account/billing"
        )

    def test_raises_500_when_nothing_resolvable(self):
        settings.stripe_portal_return_url = ""
        settings.frontend_base_url = ""
        with pytest.raises(stripe_service.HTTPException) as exc:
            stripe_service.resolve_portal_return_url()
        assert exc.value.status_code == 500
        assert exc.value.detail == "stripe_portal_return_url_not_configured"


# ---------------------------------------------------------------------------
# Plan / config validation
# ---------------------------------------------------------------------------


class TestPriceIdResolution:
    def test_monthly_returns_configured_price(self):
        assert stripe_service._price_id_for_plan("monthly") == "price_monthly_test"

    def test_annual_returns_configured_price(self):
        assert stripe_service._price_id_for_plan("annual") == "price_annual_test"

    def test_unknown_plan_raises_400_invalid_plan(self):
        with pytest.raises(stripe_service.HTTPException) as exc:
            stripe_service._price_id_for_plan("lifetime")
        assert exc.value.status_code == 400
        assert exc.value.detail == "invalid_plan"

    def test_missing_monthly_price_raises_500(self):
        settings.stripe_monthly_price_id = ""
        with pytest.raises(stripe_service.HTTPException) as exc:
            stripe_service._price_id_for_plan("monthly")
        assert exc.value.status_code == 500
        assert exc.value.detail == "stripe_price_not_configured"

    def test_missing_annual_price_raises_500(self):
        settings.stripe_annual_price_id = ""
        with pytest.raises(stripe_service.HTTPException) as exc:
            stripe_service._price_id_for_plan("annual")
        assert exc.value.status_code == 500
        assert exc.value.detail == "stripe_price_not_configured"


class TestStripeApiKeyRequired:
    def test_missing_secret_key_raises_500(self):
        settings.stripe_secret_key = ""
        with pytest.raises(stripe_service.HTTPException) as exc:
            stripe_service._require_stripe_api_key()
        assert exc.value.status_code == 500
        assert exc.value.detail == "stripe_not_configured"


# ---------------------------------------------------------------------------
# Customer creation / reuse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateOrGetCustomer:
    async def test_creates_new_customer_and_persists_id(
        self, fresh_profile, db_session
    ):
        fake_customer = SimpleNamespace(id="cus_new_abc")
        with patch.object(
            stripe_service, "_sync_create_customer", return_value=fake_customer
        ) as create_mock:
            customer_id = await stripe_service.create_or_get_customer(
                db_session, fresh_profile
            )
        assert customer_id == "cus_new_abc"
        assert fresh_profile.stripe_customer_id == "cus_new_abc"
        create_mock.assert_called_once()
        kwargs = create_mock.call_args.kwargs
        assert kwargs["email"] == "svc@example.com"
        assert kwargs["metadata"]["subscriber_profile_id"] == str(fresh_profile.id)
        assert kwargs["metadata"]["supabase_user_id"] == fresh_profile.supabase_user_id

    async def test_existing_customer_id_is_reused(
        self, fresh_profile, db_session
    ):
        fresh_profile.stripe_customer_id = "cus_existing_999"
        await db_session.commit()
        with patch.object(
            stripe_service, "_sync_create_customer"
        ) as create_mock:
            customer_id = await stripe_service.create_or_get_customer(
                db_session, fresh_profile
            )
        assert customer_id == "cus_existing_999"
        create_mock.assert_not_called()

    async def test_stripe_failure_returns_502(self, fresh_profile, db_session):
        def _raise(**_):
            raise stripe.StripeError("boom")

        with patch.object(
            stripe_service, "_sync_create_customer", side_effect=_raise
        ):
            with pytest.raises(stripe_service.HTTPException) as exc:
                await stripe_service.create_or_get_customer(
                    db_session, fresh_profile
                )
        assert exc.value.status_code == 502
        assert exc.value.detail == "stripe_customer_create_failed"


# ---------------------------------------------------------------------------
# Checkout session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateCheckoutSession:
    async def test_monthly_creates_url_and_passes_metadata(
        self, fresh_profile, db_session
    ):
        fresh_profile.stripe_customer_id = "cus_already"
        await db_session.commit()
        fake_session = SimpleNamespace(
            url="https://checkout.stripe.com/c/sess_abc",
            id="cs_test_abc",
        )
        with patch.object(
            stripe_service,
            "_sync_create_checkout_session",
            return_value=fake_session,
        ) as mock:
            result = await stripe_service.create_checkout_session(
                db_session, fresh_profile, "monthly"
            )
        assert result == {
            "id": "cs_test_abc",
            "url": "https://checkout.stripe.com/c/sess_abc",
        }
        kwargs = mock.call_args.kwargs
        assert kwargs["customer_id"] == "cus_already"
        assert kwargs["price_id"] == "price_monthly_test"
        assert kwargs["success_url"] == "https://app.example/billing/success"
        assert kwargs["cancel_url"] == "https://app.example/pricing"
        assert kwargs["client_reference_id"] == str(fresh_profile.id)
        assert kwargs["metadata"]["plan"] == "monthly"
        assert (
            kwargs["metadata"]["subscriber_profile_id"] == str(fresh_profile.id)
        )
        assert kwargs["subscription_metadata"]["plan"] == "monthly"

    async def test_annual_uses_annual_price(self, fresh_profile, db_session):
        fresh_profile.stripe_customer_id = "cus_annual"
        await db_session.commit()
        fake_session = SimpleNamespace(url="https://checkout.stripe.com/x")
        with patch.object(
            stripe_service,
            "_sync_create_checkout_session",
            return_value=fake_session,
        ) as mock:
            await stripe_service.create_checkout_session(
                db_session, fresh_profile, "annual"
            )
        assert mock.call_args.kwargs["price_id"] == "price_annual_test"

    async def test_creates_customer_when_missing(self, fresh_profile, db_session):
        assert fresh_profile.stripe_customer_id is None
        fake_customer = SimpleNamespace(id="cus_brand_new")
        fake_session = SimpleNamespace(url="https://checkout.stripe.com/y")
        with patch.object(
            stripe_service, "_sync_create_customer", return_value=fake_customer
        ), patch.object(
            stripe_service,
            "_sync_create_checkout_session",
            return_value=fake_session,
        ):
            await stripe_service.create_checkout_session(
                db_session, fresh_profile, "monthly"
            )
        assert fresh_profile.stripe_customer_id == "cus_brand_new"

    async def test_stripe_checkout_failure_returns_502(
        self, fresh_profile, db_session
    ):
        fresh_profile.stripe_customer_id = "cus_x"
        await db_session.commit()

        def _raise(**_):
            raise stripe.StripeError("checkout failed")

        with patch.object(
            stripe_service,
            "_sync_create_checkout_session",
            side_effect=_raise,
        ):
            with pytest.raises(stripe_service.HTTPException) as exc:
                await stripe_service.create_checkout_session(
                    db_session, fresh_profile, "monthly"
                )
        assert exc.value.status_code == 502
        assert exc.value.detail == "stripe_checkout_failed"


# ---------------------------------------------------------------------------
# Customer Portal session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreatePortalSession:
    async def test_returns_portal_url(self, fresh_profile, db_session):
        fresh_profile.stripe_customer_id = "cus_portal"
        await db_session.commit()
        fake_session = SimpleNamespace(url="https://billing.stripe.com/p/sess_zz")
        with patch.object(
            stripe_service, "_sync_create_portal_session", return_value=fake_session
        ) as mock:
            url = await stripe_service.create_customer_portal_session(
                fresh_profile
            )
        assert url == "https://billing.stripe.com/p/sess_zz"
        kwargs = mock.call_args.kwargs
        assert kwargs["customer_id"] == "cus_portal"
        assert kwargs["return_url"] == "https://app.example/account/billing"

    async def test_no_customer_id_returns_400(self, fresh_profile):
        assert fresh_profile.stripe_customer_id is None
        with pytest.raises(stripe_service.HTTPException) as exc:
            await stripe_service.create_customer_portal_session(fresh_profile)
        assert exc.value.status_code == 400
        assert exc.value.detail == "stripe_customer_missing"

    async def test_stripe_portal_failure_returns_502(
        self, fresh_profile, db_session
    ):
        fresh_profile.stripe_customer_id = "cus_y"
        await db_session.commit()

        def _raise(**_):
            raise stripe.StripeError("portal failed")

        with patch.object(
            stripe_service, "_sync_create_portal_session", side_effect=_raise
        ):
            with pytest.raises(stripe_service.HTTPException) as exc:
                await stripe_service.create_customer_portal_session(fresh_profile)
        assert exc.value.status_code == 502
        assert exc.value.detail == "stripe_customer_portal_failed"
