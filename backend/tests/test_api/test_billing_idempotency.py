"""Slice 6 — checkout idempotency, active-subscriber check, X-Idempotency-Key
validation, and recent-attempt reuse for header-less retries.
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
from app.models.billing_checkout_attempt import BillingCheckoutAttempt
from app.models.subscriber_profile import SubscriberProfile
from app.models.subscription import Subscription
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
        "frontend_base_url": settings.frontend_base_url,
    }
    settings.stripe_secret_key = "sk_test_dummy"
    settings.stripe_monthly_price_id = "price_monthly_test"
    settings.stripe_annual_price_id = "price_annual_test"
    settings.stripe_checkout_success_url = "https://app.example/billing/success"
    settings.stripe_checkout_cancel_url = "https://app.example/pricing"
    settings.frontend_base_url = ""
    yield
    for k, v in originals.items():
        setattr(settings, k, v)


def _claims(sub: str, email: str = "user@example.com") -> dict:
    return {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "iss": "https://test.supabase.co/auth/v1",
    }


def _patch_validator(claims):
    async def _fake(token):
        return claims

    return patch.object(
        supabase_auth, "validate_supabase_token", side_effect=_fake
    )


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
# X-Idempotency-Key validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestIdempotencyKeyValidation:
    async def test_email_shaped_key_rejected(self, client: AsyncClient):
        sub = f"keyval-email-{uuid.uuid4()}"
        with _patch_validator(_claims(sub)):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={
                    "Authorization": "Bearer ignored",
                    "X-Idempotency-Key": "user@example.com",
                },
            )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "invalid_idempotency_key"

    async def test_empty_key_rejected(self, client: AsyncClient):
        sub = f"keyval-empty-{uuid.uuid4()}"
        with _patch_validator(_claims(sub)):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={
                    "Authorization": "Bearer ignored",
                    "X-Idempotency-Key": "   ",
                },
            )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "invalid_idempotency_key"

    async def test_too_long_key_rejected(self, client: AsyncClient):
        sub = f"keyval-long-{uuid.uuid4()}"
        with _patch_validator(_claims(sub)):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={
                    "Authorization": "Bearer ignored",
                    "X-Idempotency-Key": "a" * 256,
                },
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Already-active subscriber blocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAlreadySubscribed:
    async def test_active_subscriber_gets_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"already-{uuid.uuid4()}"
        profile = await _seed_profile(db_session, sub)
        db_session.add(
            Subscription(
                subscriber_profile_id=profile.id,
                stripe_customer_id="cus_active",
                stripe_subscription_id=f"sub_act_{uuid.uuid4()}",
                status="active",
                current_period_end=datetime.now(timezone.utc) + timedelta(days=20),
                plan_type="monthly",
            )
        )
        await db_session.commit()

        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_create_customer"
        ) as cust_mock, patch.object(
            stripe_service, "_sync_create_checkout_session"
        ) as sess_mock:
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "already_subscribed"
        # Stripe must not have been called.
        cust_mock.assert_not_called()
        sess_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Idempotency-key reuse (explicit header)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExplicitIdempotencyKey:
    async def test_same_key_returns_same_url_one_stripe_call(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"reuse-{uuid.uuid4()}"
        await _seed_profile(db_session, sub)
        key = f"frontend-key-{uuid.uuid4()}"
        fake_customer = SimpleNamespace(id="cus_reuse")
        fake_session = SimpleNamespace(
            id="cs_reuse_abc", url="https://checkout.stripe.com/c/reuse"
        )
        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_create_customer", return_value=fake_customer
        ), patch.object(
            stripe_service,
            "_sync_create_checkout_session",
            return_value=fake_session,
        ) as sess_mock:
            r1 = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored", "X-Idempotency-Key": key},
            )
            r2 = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored", "X-Idempotency-Key": key},
            )
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() == r2.json()
        sess_mock.assert_called_once()

    async def test_same_key_different_subscriber_conflict(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_a = f"keyA-{uuid.uuid4()}"
        sub_b = f"keyB-{uuid.uuid4()}"
        await _seed_profile(db_session, sub_a)
        await _seed_profile(db_session, sub_b)
        key = f"shared-key-{uuid.uuid4()}"

        # A takes the key first.
        with _patch_validator(_claims(sub_a)), patch.object(
            stripe_service, "_sync_create_customer",
            return_value=SimpleNamespace(id="cus_a"),
        ), patch.object(
            stripe_service, "_sync_create_checkout_session",
            return_value=SimpleNamespace(id="cs_a", url="https://x/a"),
        ):
            r_a = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored", "X-Idempotency-Key": key},
            )
        assert r_a.status_code == 200

        # B tries the same key.
        with _patch_validator(_claims(sub_b)), patch.object(
            stripe_service, "_sync_create_customer"
        ) as cust_mock, patch.object(
            stripe_service, "_sync_create_checkout_session"
        ) as sess_mock:
            r_b = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored", "X-Idempotency-Key": key},
            )
        assert r_b.status_code == 409
        assert r_b.json()["detail"] == "idempotency_key_conflict"
        cust_mock.assert_not_called()
        sess_mock.assert_not_called()

    async def test_pending_attempt_without_url_returns_409_in_progress(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"pending-{uuid.uuid4()}"
        profile = await _seed_profile(db_session, sub)
        key = f"pending-key-{uuid.uuid4()}"
        db_session.add(
            BillingCheckoutAttempt(
                subscriber_profile_id=profile.id,
                plan_type="monthly",
                idempotency_key=key,
                status="pending",
                checkout_url=None,
            )
        )
        await db_session.commit()

        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_create_checkout_session"
        ) as sess_mock:
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored", "X-Idempotency-Key": key},
            )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "checkout_in_progress"
        sess_mock.assert_not_called()

    async def test_failed_attempt_retries_creates_new_stripe_session(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"failed-{uuid.uuid4()}"
        profile = await _seed_profile(db_session, sub)
        key = f"failed-key-{uuid.uuid4()}"
        db_session.add(
            BillingCheckoutAttempt(
                subscriber_profile_id=profile.id,
                plan_type="monthly",
                idempotency_key=key,
                status="failed",
            )
        )
        await db_session.commit()

        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_create_customer",
            return_value=SimpleNamespace(id="cus_retry"),
        ), patch.object(
            stripe_service, "_sync_create_checkout_session",
            return_value=SimpleNamespace(id="cs_retry", url="https://x/retry"),
        ) as sess_mock:
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored", "X-Idempotency-Key": key},
            )
        assert resp.status_code == 200
        sess_mock.assert_called_once()


# ---------------------------------------------------------------------------
# No-header path: generated UUID + recent-attempt reuse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNoHeaderPath:
    async def test_no_header_succeeds_with_generated_key(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"nohdr-{uuid.uuid4()}"
        profile = await _seed_profile(db_session, sub)
        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_create_customer",
            return_value=SimpleNamespace(id="cus_nh"),
        ), patch.object(
            stripe_service, "_sync_create_checkout_session",
            return_value=SimpleNamespace(id="cs_nh", url="https://x/nh"),
        ):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        row = (
            await db_session.execute(
                select(BillingCheckoutAttempt).where(
                    BillingCheckoutAttempt.subscriber_profile_id == profile.id
                )
            )
        ).scalar_one()
        assert row.idempotency_key  # generated UUID
        assert row.status == "succeeded"

    async def test_double_click_no_header_reuses_recent_attempt(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"dbl-{uuid.uuid4()}"
        await _seed_profile(db_session, sub)
        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_create_customer",
            return_value=SimpleNamespace(id="cus_dbl"),
        ), patch.object(
            stripe_service, "_sync_create_checkout_session",
            return_value=SimpleNamespace(id="cs_dbl", url="https://x/dbl"),
        ) as sess_mock:
            r1 = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
            r2 = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() == r2.json()
        # Only the first call hit Stripe; the second reused the recent attempt.
        sess_mock.assert_called_once()

    async def test_no_header_does_not_reuse_across_plans(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"crossplan-{uuid.uuid4()}"
        await _seed_profile(db_session, sub)
        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_create_customer",
            return_value=SimpleNamespace(id="cus_cp"),
        ), patch.object(
            stripe_service, "_sync_create_checkout_session",
            side_effect=[
                SimpleNamespace(id="cs_m", url="https://x/m"),
                SimpleNamespace(id="cs_a", url="https://x/a"),
            ],
        ) as sess_mock:
            r1 = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored"},
            )
            r2 = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "annual"},
                headers={"Authorization": "Bearer ignored"},
            )
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() != r2.json()
        assert sess_mock.call_count == 2


# ---------------------------------------------------------------------------
# Operation-scoped Stripe keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOperationScopedKeys:
    async def test_stripe_seams_receive_operation_scoped_keys(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"scoped-{uuid.uuid4()}"
        profile = await _seed_profile(db_session, sub)
        key = f"clientkey-{uuid.uuid4()}"
        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_create_customer",
            return_value=SimpleNamespace(id="cus_sc"),
        ) as cust_mock, patch.object(
            stripe_service, "_sync_create_checkout_session",
            return_value=SimpleNamespace(id="cs_sc", url="https://x/sc"),
        ) as sess_mock:
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored", "X-Idempotency-Key": key},
            )
        assert resp.status_code == 200
        cust_kwargs = cust_mock.call_args.kwargs
        sess_kwargs = sess_mock.call_args.kwargs
        assert cust_kwargs["idempotency_key"] == f"customer:{profile.id}:{key}"
        assert (
            sess_kwargs["idempotency_key"]
            == f"checkout:{profile.id}:monthly:{key}"
        )


# ---------------------------------------------------------------------------
# Stripe failure → attempt marked 'failed'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStripeFailure:
    async def test_stripe_failure_marks_attempt_failed_and_502(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub = f"sfail-{uuid.uuid4()}"
        profile = await _seed_profile(db_session, sub)
        key = f"fail-key-{uuid.uuid4()}"

        def _raise(**_):
            raise stripe.StripeError("internal — must not leak")

        with _patch_validator(_claims(sub)), patch.object(
            stripe_service, "_sync_create_customer",
            return_value=SimpleNamespace(id="cus_f"),
        ), patch.object(
            stripe_service, "_sync_create_checkout_session", side_effect=_raise
        ):
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "monthly"},
                headers={"Authorization": "Bearer ignored", "X-Idempotency-Key": key},
            )
        assert resp.status_code == 502
        assert resp.json()["detail"] == "stripe_checkout_failed"
        assert "internal — must not leak" not in resp.text

        row = (
            await db_session.execute(
                select(BillingCheckoutAttempt).where(
                    BillingCheckoutAttempt.idempotency_key == key
                )
            )
        ).scalar_one()
        assert row.status == "failed"
