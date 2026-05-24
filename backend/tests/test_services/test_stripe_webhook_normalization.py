"""Slice 6 — webhook normalization, malformed-event guard, retryable rows, dispatch rollback.

These are the failure-mode tests that protect against the production P0 bug
where a real ``stripe.Event`` object crashed ``process_stripe_event`` with
``AttributeError: get`` and left users paid-but-locked.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.models.stripe_webhook_event import StripeWebhookEvent
from app.models.subscriber_profile import SubscriberProfile
from app.models.subscription import Subscription
from app.services import stripe_webhook_service as svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def _evt(event_type: str, obj: dict, event_id: str | None = None) -> dict:
    return {
        "id": event_id or f"evt_{uuid.uuid4()}",
        "type": event_type,
        "data": {"object": obj},
    }


def _subscription_obj(*, sub_id, customer, profile_id):
    return {
        "id": sub_id,
        "customer": customer,
        "status": "active",
        "metadata": {"subscriber_profile_id": str(profile_id)},
        "cancel_at_period_end": False,
        "current_period_start": 1_700_000_000,
        "current_period_end": 1_710_000_000,
        "canceled_at": None,
        "items": {"data": [{"price": {"id": "price_monthly_test"}}]},
    }


# ---------------------------------------------------------------------------
# stripe_object_to_dict unit tests
# ---------------------------------------------------------------------------


class TestStripeObjectToDict:
    def test_plain_dict_passes_through_deep_equal(self):
        src = {"a": 1, "b": {"c": [1, 2, {"d": "x"}]}}
        assert svc.stripe_object_to_dict(src) == src

    def test_object_with_to_dict_recursive_is_normalized(self):
        class FakeStripeObj:
            def to_dict_recursive(self):
                return {"id": "evt_1", "type": "x"}

        assert svc.stripe_object_to_dict(FakeStripeObj()) == {
            "id": "evt_1",
            "type": "x",
        }

    def test_recursion_handles_nested_object_inside_list(self):
        class Inner:
            def to_dict_recursive(self):
                return {"k": "v"}

        src = {"list": [Inner(), Inner()], "scalar": 42}
        assert svc.stripe_object_to_dict(src) == {
            "list": [{"k": "v"}, {"k": "v"}],
            "scalar": 42,
        }

    def test_broken_to_dict_recursive_falls_through(self):
        class BrokenButDictLike(dict):
            def to_dict_recursive(self):
                raise RuntimeError("kaboom")

        src = BrokenButDictLike({"a": 1})
        # Falls through to the Mapping branch since BrokenButDictLike IS a dict.
        assert svc.stripe_object_to_dict(src) == {"a": 1}

    def test_scalars_pass_through(self):
        for v in (None, 0, 1.5, "", "hello", True, False):
            assert svc.stripe_object_to_dict(v) == v


# ---------------------------------------------------------------------------
# Malformed event guard (Part A.2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMalformedEventGuard:
    async def test_non_mapping_event_returns_400(self, db_session):
        with pytest.raises(HTTPException) as exc:
            await svc.process_stripe_event(db_session, [1, 2, 3])
        assert exc.value.status_code == 400
        assert exc.value.detail == "invalid_stripe_event"

    async def test_none_event_returns_400(self, db_session):
        with pytest.raises(HTTPException) as exc:
            await svc.process_stripe_event(db_session, None)
        assert exc.value.status_code == 400
        assert exc.value.detail == "invalid_stripe_event"

    async def test_missing_id_returns_400(self, db_session):
        with pytest.raises(HTTPException) as exc:
            await svc.process_stripe_event(
                db_session, {"type": "customer.subscription.updated"}
            )
        assert exc.value.status_code == 400
        assert exc.value.detail == "invalid_stripe_event"

    async def test_missing_type_returns_400(self, db_session):
        with pytest.raises(HTTPException) as exc:
            await svc.process_stripe_event(db_session, {"id": "evt_x"})
        assert exc.value.status_code == 400
        assert exc.value.detail == "invalid_stripe_event"

    async def test_malformed_event_does_not_persist_row(self, db_session):
        event_id = f"evt_malformed_{uuid.uuid4()}"
        with pytest.raises(HTTPException):
            await svc.process_stripe_event(db_session, {"id": event_id})
        row = (
            await db_session.execute(
                select(StripeWebhookEvent).where(
                    StripeWebhookEvent.stripe_event_id == event_id
                )
            )
        ).scalar_one_or_none()
        assert row is None


# ---------------------------------------------------------------------------
# End-to-end: Stripe-like object dispatches without crashing (the P0 bug)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStripeObjectEndToEnd:
    async def test_stripe_event_like_object_dispatches(self, db_session):
        profile = SubscriberProfile(
            supabase_user_id=f"wh-norm-{uuid.uuid4()}",
            email="norm@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.commit()

        sub_id = f"sub_{uuid.uuid4()}"
        raw_dict = _evt(
            "customer.subscription.created",
            _subscription_obj(sub_id=sub_id, customer="cus_norm", profile_id=profile.id),
        )

        class FakeStripeEvent:
            """Simulates stripe.Event: has to_dict_recursive, NOT dict-subscriptable."""

            def __init__(self, payload):
                self._payload = payload

            def to_dict_recursive(self):
                return self._payload

        result = await svc.process_stripe_event(
            db_session, FakeStripeEvent(raw_dict)
        )
        assert result["status"] == "processed"
        row = await svc._subscription_by_stripe_id(db_session, sub_id)
        assert row is not None and row.status == "active"


# ---------------------------------------------------------------------------
# Retryable crashed row (Part B.1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRetryableCrashedRow:
    async def test_row_with_null_processed_at_is_reprocessed(self, db_session):
        profile = SubscriberProfile(
            supabase_user_id=f"wh-retry-{uuid.uuid4()}",
            email="retry@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.flush()

        sub_id = f"sub_{uuid.uuid4()}"
        event_id = f"evt_retry_{uuid.uuid4()}"

        # Simulate a prior crashed run: row exists with processed_at=None,
        # but the subscription row was never written.
        crashed = StripeWebhookEvent(
            stripe_event_id=event_id,
            event_type="customer.subscription.created",
            payload_json={"id": event_id, "type": "customer.subscription.created"},
            processed_at=None,
        )
        db_session.add(crashed)
        await db_session.commit()

        # Retry: must reprocess (not return duplicate).
        event = _evt(
            "customer.subscription.created",
            _subscription_obj(
                sub_id=sub_id, customer="cus_retry", profile_id=profile.id
            ),
            event_id=event_id,
        )
        result = await svc.process_stripe_event(db_session, event)
        assert result["status"] == "processed"

        # The same row was reused (no duplicate insert), processed_at now set.
        rows = (
            await db_session.execute(
                select(StripeWebhookEvent).where(
                    StripeWebhookEvent.stripe_event_id == event_id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].processed_at is not None

        # Subscription was actually written this time.
        sub = await svc._subscription_by_stripe_id(db_session, sub_id)
        assert sub is not None

        # A third call with the same id → duplicate (now processed_at is set).
        third = await svc.process_stripe_event(db_session, event)
        assert third["status"] == "duplicate"


# ---------------------------------------------------------------------------
# Dispatch failure rolls back, allows retry (Part B.2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDispatchFailureRollback:
    async def test_handler_raise_does_not_mark_event_processed(
        self, db_session, monkeypatch
    ):
        event_id = f"evt_fail_{uuid.uuid4()}"
        event = _evt(
            "customer.subscription.created",
            _subscription_obj(sub_id="sub_x", customer="cus_x", profile_id=1),
            event_id=event_id,
        )

        async def _exploding_handler(db, obj):
            raise RuntimeError("handler crashed mid-flight")

        monkeypatch.setitem(
            svc._HANDLERS,
            "customer.subscription.created",
            _exploding_handler,
        )

        with pytest.raises(RuntimeError):
            await svc.process_stripe_event(db_session, event)

        # Row must NOT exist (rollback discarded the claim insert).
        row = (
            await db_session.execute(
                select(StripeWebhookEvent).where(
                    StripeWebhookEvent.stripe_event_id == event_id
                )
            )
        ).scalar_one_or_none()
        assert row is None

    async def test_failed_event_is_processable_on_retry(
        self, db_session, monkeypatch
    ):
        profile = SubscriberProfile(
            supabase_user_id=f"wh-rt2-{uuid.uuid4()}",
            email="rt@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.commit()

        sub_id = f"sub_{uuid.uuid4()}"
        event_id = f"evt_retry2_{uuid.uuid4()}"
        event = _evt(
            "customer.subscription.created",
            _subscription_obj(
                sub_id=sub_id, customer="cus_rt", profile_id=profile.id
            ),
            event_id=event_id,
        )

        # 1st call: handler raises.
        async def _explode(db, obj):
            raise RuntimeError("first try blew up")

        original = svc._HANDLERS["customer.subscription.created"]
        monkeypatch.setitem(
            svc._HANDLERS, "customer.subscription.created", _explode
        )
        with pytest.raises(RuntimeError):
            await svc.process_stripe_event(db_session, event)

        # 2nd call: real handler — must succeed (rollback freed up the claim).
        monkeypatch.setitem(
            svc._HANDLERS, "customer.subscription.created", original
        )
        result = await svc.process_stripe_event(db_session, event)
        assert result["status"] == "processed"
        sub = await svc._subscription_by_stripe_id(db_session, sub_id)
        assert sub is not None and sub.status == "active"


# ---------------------------------------------------------------------------
# Public alias for /sync reuse
# ---------------------------------------------------------------------------


def test_upsert_alias_points_at_internal_upsert():
    assert svc.upsert_subscription_from_stripe is svc._upsert_subscription
