"""Endpoint tests for paid subscriber content — Auth/Payment Phase 1 Slice 5.

Covers the active-subscription guard and the five content endpoints under
/api/v1/subscriber/*. Supabase validation is mocked; the guard, the shared
public impls, and the DB all run for real.

Defensive against the session-scoped engine (committed rows persist across
tests): assertions check presence/absence of specifically-seeded alert ids and
compare the subscriber response to the public response on the *same* DB state,
rather than asserting absolute counts.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import supabase as supabase_auth
from app.config import settings
from app.models.subscriber_profile import SubscriberProfile
from app.models.subscription import Subscription

# Reuse the published-alert seed helpers and the Supabase mock helpers.
from tests.test_api.test_public_alerts import (
    _seed_alert,
    _seed_raw_item,
    _seed_source,
)
from tests.test_api.test_subscriber_api import _claims, _patch_validator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_profile_with_subscription(
    db_session: AsyncSession,
    *,
    sub_id: str,
    status: str | None,
    current_period_end: datetime | None = None,
    cancel_at_period_end: bool = False,
) -> SubscriberProfile:
    """Create a SubscriberProfile (keyed on Supabase sub) + one Subscription row."""
    profile = SubscriberProfile(
        supabase_user_id=sub_id,
        email=f"{sub_id}@example.com",
        role="subscriber",
    )
    db_session.add(profile)
    await db_session.flush()
    subscription = Subscription(
        subscriber_profile_id=profile.id,
        stripe_customer_id=f"cus_{sub_id}",
        stripe_subscription_id=f"sub_{sub_id}",
        plan_type="monthly",
        status=status,
        current_period_end=current_period_end,
        cancel_at_period_end=cancel_at_period_end,
    )
    db_session.add(subscription)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


async def _seed_published_alert(db_session, **alert_kwargs):
    source = await _seed_source(db_session, name=f"Src {uuid.uuid4()}")
    raw = await _seed_raw_item(db_session, source, url=f"https://x/{uuid.uuid4()}")
    return await _seed_alert(db_session, raw, is_published=True, **alert_kwargs)


async def _seed_unpublished_alert(db_session, **alert_kwargs):
    source = await _seed_source(db_session, name=f"Src {uuid.uuid4()}")
    raw = await _seed_raw_item(db_session, source, url=f"https://x/{uuid.uuid4()}")
    return await _seed_alert(db_session, raw, is_published=False, **alert_kwargs)


_AUTH = {"Authorization": "Bearer ignored"}


def _active_claims():
    return _claims(sub=f"sub-{uuid.uuid4()}")


# ---------------------------------------------------------------------------
# Access guard (exercised through GET /alerts)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestActiveSubscriptionGuard:
    async def test_missing_auth_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/subscriber/alerts")
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        from fastapi import HTTPException

        async def _reject(token):
            raise HTTPException(status_code=401, detail="invalid_token")

        with patch.object(
            supabase_auth, "validate_supabase_token", side_effect=_reject
        ):
            resp = await client.get("/api/v1/subscriber/alerts", headers=_AUTH)
        assert resp.status_code == 401

    async def test_valid_token_no_subscription_returns_403(
        self, client: AsyncClient
    ):
        # No subscription row → get_current_subscriber creates the profile,
        # guard finds no subscription → 403.
        with _patch_validator(_claims(sub=f"nosub-{uuid.uuid4()}")):
            resp = await client.get("/api/v1/subscriber/alerts", headers=_AUTH)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "active_subscription_required"

    async def test_active_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = f"active-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get("/api/v1/subscriber/alerts", headers=_AUTH)
        assert resp.status_code == 200

    async def test_trialing_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = f"trial-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="trialing"
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get("/api/v1/subscriber/alerts", headers=_AUTH)
        assert resp.status_code == 200

    async def test_canceled_future_period_end_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = f"cancel-fut-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session,
            sub_id=sub_id,
            status="canceled",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=5),
            cancel_at_period_end=True,
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get("/api/v1/subscriber/alerts", headers=_AUTH)
        assert resp.status_code == 200

    async def test_canceled_past_period_end_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = f"cancel-past-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session,
            sub_id=sub_id,
            status="canceled",
            current_period_end=datetime.now(timezone.utc) - timedelta(days=1),
            cancel_at_period_end=True,
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get("/api/v1/subscriber/alerts", headers=_AUTH)
        assert resp.status_code == 403

    async def test_past_due_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = f"pastdue-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session,
            sub_id=sub_id,
            status="past_due",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=5),
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get("/api/v1/subscriber/alerts", headers=_AUTH)
        assert resp.status_code == 403

    async def test_grace_seconds_extends_canceled_access(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = f"grace-{uuid.uuid4()}"
        # Period ended 30s ago; without grace → 403.
        await _seed_profile_with_subscription(
            db_session,
            sub_id=sub_id,
            status="canceled",
            current_period_end=datetime.now(timezone.utc) - timedelta(seconds=30),
            cancel_at_period_end=True,
        )
        original = settings.subscription_access_grace_seconds
        settings.subscription_access_grace_seconds = 3600  # 1h grace covers the gap
        try:
            with _patch_validator(_claims(sub=sub_id)):
                resp = await client.get("/api/v1/subscriber/alerts", headers=_AUTH)
            assert resp.status_code == 200
        finally:
            settings.subscription_access_grace_seconds = original


# ---------------------------------------------------------------------------
# Content equivalence with the public endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubscriberAlertsContent:
    async def test_published_present_unpublished_absent(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        published = await _seed_published_alert(db_session, signal_score=12)
        unpublished = await _seed_unpublished_alert(db_session, signal_score=12)
        sub_id = f"content-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                "/api/v1/subscriber/alerts?limit=500", headers=_AUTH
            )
        assert resp.status_code == 200
        ids = {a["id"] for a in resp.json()["alerts"]}
        assert published.id in ids
        assert unpublished.id not in ids

    async def test_shape_matches_public(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _seed_published_alert(db_session, signal_score=18)
        sub_id = f"shape-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        public = await client.get("/api/alerts?limit=500")
        with _patch_validator(_claims(sub=sub_id)):
            sub = await client.get("/api/v1/subscriber/alerts?limit=500", headers=_AUTH)
        assert public.status_code == 200 and sub.status_code == 200
        # Same DB state → byte-identical bodies.
        assert sub.json() == public.json()

    async def test_signal_score_is_0_100_and_risk_derived(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        alert = await _seed_published_alert(db_session, signal_score=18)
        sub_id = f"score-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                "/api/v1/subscriber/alerts?limit=500", headers=_AUTH
            )
        row = next(a for a in resp.json()["alerts"] if a["id"] == alert.id)
        assert row["signal_score"] == 72  # 18/25*100
        assert row["risk_level"] == "high"


@pytest.mark.asyncio
class TestSubscriberTopAlerts:
    async def test_shape_matches_public(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _seed_published_alert(db_session, signal_score=20)
        sub_id = f"top-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        public = await client.get("/api/alerts/top")
        with _patch_validator(_claims(sub=sub_id)):
            sub = await client.get("/api/v1/subscriber/alerts/top", headers=_AUTH)
        assert public.status_code == 200 and sub.status_code == 200
        assert sub.json() == public.json()

    async def test_requires_active_subscription(self, client: AsyncClient):
        with _patch_validator(_claims(sub=f"top-nosub-{uuid.uuid4()}")):
            resp = await client.get("/api/v1/subscriber/alerts/top", headers=_AUTH)
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestSubscriberAlertDetail:
    async def test_published_detail_matches_public(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        alert = await _seed_published_alert(db_session, signal_score=18)
        sub_id = f"detail-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        public = await client.get(f"/api/alerts/{alert.id}")
        with _patch_validator(_claims(sub=sub_id)):
            sub = await client.get(
                f"/api/v1/subscriber/alerts/{alert.id}", headers=_AUTH
            )
        assert public.status_code == 200 and sub.status_code == 200
        assert sub.json() == public.json()

    async def test_unpublished_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        alert = await _seed_unpublished_alert(db_session)
        sub_id = f"detail404-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                f"/api/v1/subscriber/alerts/{alert.id}", headers=_AUTH
            )
        assert resp.status_code == 404

    async def test_nonexistent_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = f"detail-missing-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                "/api/v1/subscriber/alerts/999999999", headers=_AUTH
            )
        assert resp.status_code == 404

    async def test_requires_active_subscription(self, client: AsyncClient):
        with _patch_validator(_claims(sub=f"detail-nosub-{uuid.uuid4()}")):
            resp = await client.get(
                "/api/v1/subscriber/alerts/1", headers=_AUTH
            )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestSubscriberStats:
    async def test_shape_matches_public(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _seed_published_alert(db_session, signal_score=18, category="Cybercrime")
        sub_id = f"stats-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        public = await client.get("/api/alerts/stats")
        with _patch_validator(_claims(sub=sub_id)):
            sub = await client.get("/api/v1/subscriber/alerts/stats", headers=_AUTH)
        assert public.status_code == 200 and sub.status_code == 200
        assert sub.json() == public.json()

    async def test_requires_active_subscription(self, client: AsyncClient):
        with _patch_validator(_claims(sub=f"stats-nosub-{uuid.uuid4()}")):
            resp = await client.get(
                "/api/v1/subscriber/alerts/stats", headers=_AUTH
            )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestSubscriberSearch:
    async def test_published_match_present_and_shape_matches_public(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = f"ztoken{uuid.uuid4().hex[:10]}"
        await _seed_published_alert(
            db_session, signal_score=18, summary=f"matter about {token} fraud"
        )
        sub_id = f"search-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        public = await client.get(f"/api/search/alerts?q={token}")
        with _patch_validator(_claims(sub=sub_id)):
            sub = await client.get(
                f"/api/v1/subscriber/search/alerts?q={token}", headers=_AUTH
            )
        assert public.status_code == 200 and sub.status_code == 200
        assert sub.json() == public.json()
        assert sub.json()["total_alerts"] >= 1

    async def test_empty_q_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = f"search-empty-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                "/api/v1/subscriber/search/alerts?q=%20%20", headers=_AUTH
            )
        assert resp.status_code == 422

    async def test_unpublished_excluded_from_search(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = f"ztok{uuid.uuid4().hex[:10]}"
        unpublished = await _seed_unpublished_alert(
            db_session, summary=f"secret {token} leak"
        )
        sub_id = f"search-unpub-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                f"/api/v1/subscriber/search/alerts?q={token}", headers=_AUTH
            )
        assert resp.status_code == 200
        ids = {a["id"] for a in resp.json()["alerts"]}
        assert unpublished.id not in ids

    async def test_requires_active_subscription(self, client: AsyncClient):
        with _patch_validator(_claims(sub=f"search-nosub-{uuid.uuid4()}")):
            resp = await client.get(
                "/api/v1/subscriber/search/alerts?q=test", headers=_AUTH
            )
        assert resp.status_code == 403
