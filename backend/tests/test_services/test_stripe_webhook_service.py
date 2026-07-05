"""Unit tests for app/services/stripe_webhook_service.py.

Service-layer tests call the functions directly with plain dict events + a real
in-memory db_session. No Stripe SDK mock is needed — handlers access fields via
dict subscript/.get, which dict fixtures support.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import settings
from app.models.stripe_webhook_event import StripeWebhookEvent
from app.models.subscriber_profile import SubscriberProfile
from app.models.subscription import Subscription
from app.services import stripe_webhook_service as svc


@pytest.fixture(autouse=True)
def configure_price_settings():
    originals = {
        "stripe_monthly_price_id": settings.stripe_monthly_price_id,
        "stripe_annual_price_id": settings.stripe_annual_price_id,
    }
    settings.stripe_monthly_price_id = "price_monthly_test"
    settings.stripe_annual_price_id = "price_annual_test"
    yield
    for k, v in originals.items():
        setattr(settings, k, v)


@pytest_asyncio.fixture
async def profile(db_session):
    p = SubscriberProfile(
        supabase_user_id=f"wh-user-{uuid.uuid4()}",
        email="wh@example.com",
        role="subscriber",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


def _evt(event_type: str, obj: dict, event_id: str | None = None) -> dict:
    return {
        "id": event_id or f"evt_{uuid.uuid4()}",
        "type": event_type,
        "data": {"object": obj},
    }


def _subscription_obj(
    *,
    sub_id: str,
    customer: str,
    price_id: str = "price_monthly_test",
    status: str = "active",
    metadata: dict | None = None,
    cancel_at_period_end: bool = False,
    current_period_end: int | None = None,
    canceled_at: int | None = None,
) -> dict:
    return {
        "id": sub_id,
        "customer": customer,
        "status": status,
        "metadata": metadata or {},
        "cancel_at_period_end": cancel_at_period_end,
        "current_period_start": 1_700_000_000,
        "current_period_end": current_period_end or 1_710_000_000,
        "canceled_at": canceled_at,
        "items": {"data": [{"price": {"id": price_id}}]},
    }


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------


class TestStripeTimestampToUtc:
    def test_none_returns_none(self):
        assert svc.stripe_timestamp_to_utc(None) is None

    def test_zero_is_valid_epoch(self):
        result = svc.stripe_timestamp_to_utc(0)
        assert result == datetime(1970, 1, 1, tzinfo=timezone.utc)

    def test_valid_epoch_is_tz_aware_utc(self):
        result = svc.stripe_timestamp_to_utc(1_700_000_000)
        assert result.tzinfo is timezone.utc
        assert result == datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)

    def test_non_int_returns_none(self):
        assert svc.stripe_timestamp_to_utc("not-a-number") is None


# ---------------------------------------------------------------------------
# Plan-type mapping
# ---------------------------------------------------------------------------


class TestPlanTypeForPrice:
    def test_monthly(self):
        assert svc._plan_type_for_price("price_monthly_test") == "monthly"

    def test_annual(self):
        assert svc._plan_type_for_price("price_annual_test") == "annual"

    def test_unknown_returns_none(self):
        assert svc._plan_type_for_price("price_unknown") is None

    def test_none_returns_none(self):
        assert svc._plan_type_for_price(None) is None


class TestExtractPriceId:
    def test_extracts_first_item_price(self):
        sub = {"items": {"data": [{"price": {"id": "price_x"}}]}}
        assert svc._extract_price_id(sub) == "price_x"

    def test_missing_items_returns_none(self):
        assert svc._extract_price_id({}) is None

    def test_empty_data_returns_none(self):
        assert svc._extract_price_id({"items": {"data": []}}) is None


# ---------------------------------------------------------------------------
# Profile mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestProfileMapping:
    async def test_maps_by_metadata_subscriber_profile_id(
        self, db_session, profile
    ):
        sub = _subscription_obj(
            sub_id=f"sub_{uuid.uuid4()}",
            customer="cus_no_match",
            metadata={"subscriber_profile_id": str(profile.id)},
        )
        event = _evt("customer.subscription.created", sub)
        result = await svc.process_stripe_event(db_session, event)
        assert result["status"] == "processed"
        row = await svc._subscription_by_stripe_id(db_session, sub["id"])
        assert row is not None
        assert row.subscriber_profile_id == profile.id

    async def test_maps_by_stripe_customer_id_fallback(
        self, db_session, profile
    ):
        profile.stripe_customer_id = f"cus_{uuid.uuid4()}"
        await db_session.commit()
        sub = _subscription_obj(
            sub_id=f"sub_{uuid.uuid4()}",
            customer=profile.stripe_customer_id,
            metadata={},  # no metadata → must fall back to customer id
        )
        event = _evt("customer.subscription.updated", sub)
        result = await svc.process_stripe_event(db_session, event)
        assert result["status"] == "processed"
        row = await svc._subscription_by_stripe_id(db_session, sub["id"])
        assert row.subscriber_profile_id == profile.id

    async def test_no_mapping_logs_warning_and_returns_processed(
        self, db_session, caplog
    ):
        sub = _subscription_obj(
            sub_id=f"sub_{uuid.uuid4()}",
            customer="cus_orphan",
            metadata={},
        )
        event = _evt("customer.subscription.created", sub)
        with caplog.at_level("WARNING"):
            result = await svc.process_stripe_event(db_session, event)
        assert result["status"] == "processed"
        # No subscription row should have been created.
        row = await svc._subscription_by_stripe_id(db_session, sub["id"])
        assert row is None
        assert any("no matching subscriber profile" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Plan-type stored on upsert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUpsertPlanType:
    async def test_monthly_price_maps_plan_type(self, db_session, profile):
        sub = _subscription_obj(
            sub_id=f"sub_{uuid.uuid4()}",
            customer="cus_m",
            price_id="price_monthly_test",
            metadata={"subscriber_profile_id": str(profile.id)},
        )
        await svc.process_stripe_event(db_session, _evt("customer.subscription.created", sub))
        row = await svc._subscription_by_stripe_id(db_session, sub["id"])
        assert row.plan_type == "monthly"

    async def test_annual_price_maps_plan_type(self, db_session, profile):
        sub = _subscription_obj(
            sub_id=f"sub_{uuid.uuid4()}",
            customer="cus_a",
            price_id="price_annual_test",
            metadata={"subscriber_profile_id": str(profile.id)},
        )
        await svc.process_stripe_event(db_session, _evt("customer.subscription.created", sub))
        row = await svc._subscription_by_stripe_id(db_session, sub["id"])
        assert row.plan_type == "annual"

    async def test_unknown_price_stores_null_plan_type(self, db_session, profile):
        sub = _subscription_obj(
            sub_id=f"sub_{uuid.uuid4()}",
            customer="cus_u",
            price_id="price_nonexistent",
            metadata={"subscriber_profile_id": str(profile.id)},
        )
        await svc.process_stripe_event(db_session, _evt("customer.subscription.created", sub))
        row = await svc._subscription_by_stripe_id(db_session, sub["id"])
        assert row.plan_type is None

    async def test_upsert_updates_existing_row_in_place(self, db_session, profile):
        sub_id = f"sub_{uuid.uuid4()}"
        meta = {"subscriber_profile_id": str(profile.id)}
        first = _subscription_obj(
            sub_id=sub_id, customer="cus_up", status="active", metadata=meta
        )
        await svc.process_stripe_event(
            db_session, _evt("customer.subscription.created", first)
        )
        second = _subscription_obj(
            sub_id=sub_id,
            customer="cus_up",
            status="past_due",
            metadata=meta,
            cancel_at_period_end=True,
        )
        await svc.process_stripe_event(
            db_session, _evt("customer.subscription.updated", second)
        )
        # Exactly one row, updated in place.
        result = await db_session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "past_due"
        assert rows[0].cancel_at_period_end is True


# ---------------------------------------------------------------------------
# Event recording / idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEventRecording:
    async def test_payload_json_and_processed_at_stored(self, db_session, profile):
        sub = _subscription_obj(
            sub_id=f"sub_{uuid.uuid4()}",
            customer="cus_rec",
            metadata={"subscriber_profile_id": str(profile.id)},
        )
        event = _evt("customer.subscription.created", sub)
        await svc.process_stripe_event(db_session, event)

        result = await db_session.execute(
            select(StripeWebhookEvent).where(
                StripeWebhookEvent.stripe_event_id == event["id"]
            )
        )
        record = result.scalar_one()
        assert record.payload_json is not None
        assert record.payload_json["id"] == event["id"]
        assert record.processed_at is not None

    async def test_ignored_event_stored_with_processed_at(self, db_session):
        event = _evt("customer.updated", {"id": "cus_x"})
        result = await svc.process_stripe_event(db_session, event)
        assert result["status"] == "ignored"
        row = await db_session.execute(
            select(StripeWebhookEvent).where(
                StripeWebhookEvent.stripe_event_id == event["id"]
            )
        )
        record = row.scalar_one()
        assert record.processed_at is not None

    async def test_preexisting_duplicate_returns_duplicate(self, db_session, profile):
        event_id = f"evt_dup_{uuid.uuid4()}"
        sub = _subscription_obj(
            sub_id=f"sub_{uuid.uuid4()}",
            customer="cus_dup",
            metadata={"subscriber_profile_id": str(profile.id)},
        )
        first = _evt("customer.subscription.created", sub, event_id=event_id)
        r1 = await svc.process_stripe_event(db_session, first)
        assert r1["status"] == "processed"

        # Same event id again → duplicate, no second row.
        second = _evt("customer.subscription.updated", sub, event_id=event_id)
        r2 = await svc.process_stripe_event(db_session, second)
        assert r2["status"] == "duplicate"

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(
                StripeWebhookEvent.stripe_event_id == event_id
            )
        )
        assert len(rows.scalars().all()) == 1


# ---------------------------------------------------------------------------
# Subscription deleted / invoice events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubscriptionDeleted:
    async def test_marks_existing_subscription_canceled(self, db_session, profile):
        sub_id = f"sub_{uuid.uuid4()}"
        meta = {"subscriber_profile_id": str(profile.id)}
        await svc.process_stripe_event(
            db_session,
            _evt(
                "customer.subscription.created",
                _subscription_obj(sub_id=sub_id, customer="cus_del", metadata=meta),
            ),
        )
        await svc.process_stripe_event(
            db_session,
            _evt(
                "customer.subscription.deleted",
                _subscription_obj(
                    sub_id=sub_id,
                    customer="cus_del",
                    status="canceled",
                    metadata=meta,
                    canceled_at=1_710_500_000,
                ),
            ),
        )
        row = await svc._subscription_by_stripe_id(db_session, sub_id)
        assert row.status == "canceled"
        assert row.canceled_at is not None


@pytest.mark.asyncio
class TestInvoiceEvents:
    async def test_payment_failed_sets_past_due(self, db_session, profile):
        sub_id = f"sub_{uuid.uuid4()}"
        meta = {"subscriber_profile_id": str(profile.id)}
        await svc.process_stripe_event(
            db_session,
            _evt(
                "customer.subscription.created",
                _subscription_obj(sub_id=sub_id, customer="cus_inv", metadata=meta),
            ),
        )
        await svc.process_stripe_event(
            db_session,
            _evt("invoice.payment_failed", {"id": "in_1", "subscription": sub_id}),
        )
        row = await svc._subscription_by_stripe_id(db_session, sub_id)
        assert row.status == "past_due"

    async def test_payment_failed_does_not_override_canceled(self, db_session, profile):
        sub_id = f"sub_{uuid.uuid4()}"
        meta = {"subscriber_profile_id": str(profile.id)}
        await svc.process_stripe_event(
            db_session,
            _evt(
                "customer.subscription.deleted",
                _subscription_obj(
                    sub_id=sub_id, customer="cus_c", status="canceled", metadata=meta
                ),
            ),
        )
        await svc.process_stripe_event(
            db_session,
            _evt("invoice.payment_failed", {"id": "in_2", "subscription": sub_id}),
        )
        row = await svc._subscription_by_stripe_id(db_session, sub_id)
        assert row.status == "canceled"  # unchanged

    async def test_payment_succeeded_minimal_payload_does_not_fail(self, db_session):
        # No 'subscription' key at all → no-op, returns processed.
        result = await svc.process_stripe_event(
            db_session, _evt("invoice.payment_succeeded", {"id": "in_3"})
        )
        assert result["status"] == "processed"

    async def test_payment_succeeded_reactivates_past_due(self, db_session, profile):
        sub_id = f"sub_{uuid.uuid4()}"
        meta = {"subscriber_profile_id": str(profile.id)}
        await svc.process_stripe_event(
            db_session,
            _evt(
                "customer.subscription.created",
                _subscription_obj(
                    sub_id=sub_id, customer="cus_react", status="past_due", metadata=meta
                ),
            ),
        )
        await svc.process_stripe_event(
            db_session,
            _evt("invoice.payment_succeeded", {"id": "in_4", "subscription": sub_id}),
        )
        row = await svc._subscription_by_stripe_id(db_session, sub_id)
        assert row.status == "active"


# ---------------------------------------------------------------------------
# checkout.session.completed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckoutSessionCompleted:
    async def test_updates_profile_customer_id_subscription_string(
        self, db_session, profile
    ):
        session = {
            "id": "cs_1",
            "client_reference_id": str(profile.id),
            "customer": "cus_checkout_str",
            "metadata": {"subscriber_profile_id": str(profile.id), "plan": "monthly"},
            "subscription": "sub_string_only",  # bare string → must not fail
        }
        result = await svc.process_stripe_event(
            db_session, _evt("checkout.session.completed", session)
        )
        assert result["status"] == "processed"
        await db_session.refresh(profile)
        assert profile.stripe_customer_id == "cus_checkout_str"
        # No subscription row from a string-only subscription.
        row = await svc._subscription_by_stripe_id(db_session, "sub_string_only")
        assert row is None

    async def test_expanded_subscription_upserts_row(self, db_session, profile):
        sub_id = f"sub_{uuid.uuid4()}"
        session = {
            "id": "cs_2",
            "client_reference_id": str(profile.id),
            "customer": "cus_checkout_exp",
            "metadata": {"subscriber_profile_id": str(profile.id), "plan": "monthly"},
            "subscription": _subscription_obj(
                sub_id=sub_id, customer="cus_checkout_exp"
            ),
        }
        result = await svc.process_stripe_event(
            db_session, _evt("checkout.session.completed", session)
        )
        assert result["status"] == "processed"
        row = await svc._subscription_by_stripe_id(db_session, sub_id)
        assert row is not None
        assert row.subscriber_profile_id == profile.id
        assert row.status == "active"
