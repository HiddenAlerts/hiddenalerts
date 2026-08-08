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
        # OPEN-6: subscriber list = public list PLUS a V1 `risk_band` per item
        # (Critical badge). Every other field stays identical to public.
        pub_alerts = public.json()["alerts"]
        sub_alerts = sub.json()["alerts"]
        assert len(sub_alerts) == len(pub_alerts)
        for s, p in zip(sub_alerts, pub_alerts):
            # `risk_band` is derived from `signal_score`, which is legitimately
            # None for an alert that was never scored. The session-scoped test
            # database accumulates such rows from other modules, so the band is
            # only asserted where a score exists — the mapping itself is what
            # this guards, not the seeded corpus.
            if s["signal_score"] is None:
                assert s["risk_band"] is None
            else:
                assert s["risk_band"] in ("critical", "high", "medium", "below_60")
            assert {k: v for k, v in s.items() if k != "risk_band"} == p

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
    """Slice 3B.2J: the subscriber widget is "this week", the public one is all-time.

    The payload *shape* stays identical so the frontend needs no change, but the
    two selections are intentionally allowed to diverge during this transition —
    this class no longer asserts payload equality.
    """

    async def test_payload_shape_matches_public(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Public feed item shape PLUS the V1 `risk_band`.

        The public Top Alerts route was removed in Slice 3B.2P, so the reference
        shape now comes from the retained Landing feed — both are rendered by the
        shared `_to_public_read` mapper, which is what this guards.

        Slice 3B.2Y: Top Alerts moved from the public schema to the subscriber
        one so the Critical badge has a canonical field to read. The change is
        additive, and this test now pins that precisely — every public key must
        still be present with the same type, and `risk_band` is the only
        addition. That is the same convention the subscriber list uses above.
        """
        await _seed_published_alert(db_session, signal_score=20)
        sub_id = f"top-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        public = await client.get("/api/alerts?limit=500")
        with _patch_validator(_claims(sub=sub_id)):
            sub = await client.get("/api/v1/subscriber/alerts/top", headers=_AUTH)

        assert public.status_code == 200 and sub.status_code == 200
        assert set(sub.json()) == set(public.json()) == {"alerts"}

        sub_alerts, public_alerts = sub.json()["alerts"], public.json()["alerts"]
        assert sub_alerts, "a freshly published Critical alert qualifies this week"
        assert public_alerts, "the landing feed provides the reference shape"
        assert set(sub_alerts[0]) - set(public_alerts[0]) == {"risk_band"}, (
            "risk_band is the only addition"
        )
        assert not set(public_alerts[0]) - set(sub_alerts[0]), "nothing was dropped"
        assert sub_alerts[0]["risk_band"] in ("critical", "high", "medium", "below_60")
        for key, value in sub_alerts[0].items():
            if key == "risk_band":
                continue
            assert type(value) is type(public_alerts[0][key]) or value is None, key

    async def test_diverges_from_public_on_an_old_alert(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """A high-scoring alert outside the seven-day window is excluded.

        This used to be phrased as "public keeps it, subscriber does not". The
        public Top Alerts route is gone, so the assertion is now made directly
        against the weekly contract: the alert is published and visible on the
        all-time landing feed, yet absent from this week's curated set.
        """
        old = await _seed_published_alert(
            db_session, signal_score=25,
            published_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
        sub_id = f"top-old-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        landing = await client.get("/api/alerts?limit=500")
        with _patch_validator(_claims(sub=sub_id)):
            sub = await client.get("/api/v1/subscriber/alerts/top", headers=_AUTH)

        assert old.id in [a["id"] for a in landing.json()["alerts"]], (
            "the alert is published and still served by the retained public feed"
        )
        assert old.id not in [a["id"] for a in sub.json()["alerts"]], (
            "but it falls outside the rolling seven-day window"
        )

    async def test_out_of_window_alert_is_never_a_fallback(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """An old alert stays out even when it would fill an unused position.

        The session-scoped test database carries alerts from earlier tests, so
        this asserts on *this* alert rather than an exact empty payload — the
        empty-list contract itself is pinned in the service tests.
        """
        old = await _seed_published_alert(
            db_session, signal_score=25,
            published_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        sub_id = f"top-empty-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get("/api/v1/subscriber/alerts/top", headers=_AUTH)

        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"alerts"} and isinstance(body["alerts"], list)
        assert len(body["alerts"]) <= 3
        assert old.id not in [a["id"] for a in body["alerts"]]

    async def test_requires_active_subscription(self, client: AsyncClient):
        with _patch_validator(_claims(sub=f"top-nosub-{uuid.uuid4()}")):
            resp = await client.get("/api/v1/subscriber/alerts/top", headers=_AUTH)
        assert resp.status_code == 403

    async def test_unauthenticated_is_rejected(self, client: AsyncClient):
        assert (await client.get("/api/v1/subscriber/alerts/top")).status_code == 401

    async def test_route_no_longer_delegates_to_the_legacy_implementation(self):
        import ast
        import inspect

        from app.api import subscriber

        tree = ast.parse(inspect.getsource(subscriber.subscriber_top_alerts))
        called = {
            node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        } | {
            node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "top_alerts_impl" not in called
        assert "get_top_alerts" in called

    async def test_no_cache_is_applied_to_the_subscriber_route(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Each call re-evaluates the window; nothing is memoised."""
        sub_id = f"top-cache-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        with _patch_validator(_claims(sub=sub_id)):
            first = await client.get("/api/v1/subscriber/alerts/top", headers=_AUTH)
        assert "cache-control" not in {k.lower() for k in first.headers}

        # A top-scoring alert published now must outrank whatever was there.
        fresh = await _seed_published_alert(db_session, signal_score=25)
        assert fresh.id not in [a["id"] for a in first.json()["alerts"]]

        with _patch_validator(_claims(sub=sub_id)):
            second = await client.get("/api/v1/subscriber/alerts/top", headers=_AUTH)

        assert fresh.id in [a["id"] for a in second.json()["alerts"]], (
            "a newly published alert must appear immediately — no memoisation"
        )


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
        with _patch_validator(_claims(sub=sub_id)):
            sub = await client.get(
                f"/api/v1/subscriber/alerts/{alert.id}", headers=_AUTH
            )
        assert sub.status_code == 200
        sub_body = sub.json()
        # OPEN-6: subscriber detail = the shared public detail mapping PLUS
        # `risk_band` + the curated `risk_explanation`. The public detail route
        # was removed in Slice 3B.2P, so the reference now comes from the shared
        # `_to_public_detail` helper the subscriber route still uses.
        assert sub_body["risk_band"] in ("critical", "high", "medium", "below_60")
        assert "risk_explanation" in sub_body
        rest = {
            k: v for k, v in sub_body.items()
            if k not in ("risk_band", "risk_explanation")
        }

        from app.api.public_alerts import _detail_stmt, _to_public_detail
        from app.models.processed_alert import ProcessedAlert

        row = (
            await db_session.execute(_detail_stmt().where(ProcessedAlert.id == alert.id))
        ).scalars().first()
        shared = await _to_public_detail(db_session, row)
        shared_json = shared.model_dump(mode="json")

        # The route's response_model filters a few optional fields out of the
        # payload, so compare on the keys the API actually returns: every one of
        # them must come from the shared mapper unchanged.
        assert set(rest) <= set(shared_json)
        assert rest == {k: shared_json[k] for k in rest}

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
    async def test_reuses_public_total_and_categories_adds_critical(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _seed_published_alert(db_session, signal_score=18, category="Cybercrime")
        sub_id = f"stats-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session, sub_id=sub_id, status="active"
        )
        with _patch_validator(_claims(sub=sub_id)):
            sub = await client.get("/api/v1/subscriber/alerts/stats", headers=_AUTH)
        assert sub.status_code == 200
        sub_j = sub.json()

        # The public stats route was removed in Slice 3B.2P, but the shared
        # `published_stats_impl` still supplies total_alerts and
        # category_breakdown here; the subscriber layer adds V1 critical_count.
        from app.api.public_alerts import published_stats_impl

        shared = await published_stats_impl(db_session)
        assert "critical_count" in sub_j
        assert sub_j["total_alerts"] == shared.total_alerts
        assert sub_j["category_breakdown"] == [
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in shared.category_breakdown
        ]

    async def test_requires_active_subscription(self, client: AsyncClient):
        with _patch_validator(_claims(sub=f"stats-nosub-{uuid.uuid4()}")):
            resp = await client.get(
                "/api/v1/subscriber/alerts/stats", headers=_AUTH
            )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestGraceWindowConsistency:
    """All access-reporting endpoints must agree under a nonzero grace window.

    Regression for the bug where /me, /access, /billing/status decided access
    without the grace window while the content guard applied it — a canceled
    subscription inside grace could return 200 content but "locked" status.
    """

    async def test_me_access_billing_and_content_agree_inside_grace(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = f"grace-agree-{uuid.uuid4()}"
        # Canceled, period ended 30s ago → only a nonzero grace grants access.
        await _seed_profile_with_subscription(
            db_session,
            sub_id=sub_id,
            status="canceled",
            current_period_end=datetime.now(timezone.utc) - timedelta(seconds=30),
            cancel_at_period_end=True,
        )
        original = settings.subscription_access_grace_seconds
        settings.subscription_access_grace_seconds = 3600
        try:
            with _patch_validator(_claims(sub=sub_id)):
                me = await client.get("/api/v1/subscriber/me", headers=_AUTH)
                access = await client.get(
                    "/api/v1/subscriber/access", headers=_AUTH
                )
                billing = await client.get(
                    "/api/v1/billing/status", headers=_AUTH
                )
                content = await client.get(
                    "/api/v1/subscriber/alerts", headers=_AUTH
                )
        finally:
            settings.subscription_access_grace_seconds = original

        # Every endpoint must agree the user HAS access during the grace window.
        assert me.json()["has_active_subscription"] is True
        assert me.json()["access_level"] == "subscriber"
        assert access.json()["can_access_full_content"] is True
        assert billing.json()["has_active_access"] is True
        assert content.status_code == 200

    async def test_all_agree_when_grace_too_small(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = f"grace-deny-{uuid.uuid4()}"
        await _seed_profile_with_subscription(
            db_session,
            sub_id=sub_id,
            status="canceled",
            current_period_end=datetime.now(timezone.utc) - timedelta(seconds=600),
            cancel_at_period_end=True,
        )
        original = settings.subscription_access_grace_seconds
        settings.subscription_access_grace_seconds = 60  # too small to cover 600s
        try:
            with _patch_validator(_claims(sub=sub_id)):
                me = await client.get("/api/v1/subscriber/me", headers=_AUTH)
                access = await client.get(
                    "/api/v1/subscriber/access", headers=_AUTH
                )
                billing = await client.get(
                    "/api/v1/billing/status", headers=_AUTH
                )
                content = await client.get(
                    "/api/v1/subscriber/alerts", headers=_AUTH
                )
        finally:
            settings.subscription_access_grace_seconds = original

        assert me.json()["has_active_subscription"] is False
        assert access.json()["can_access_full_content"] is False
        assert billing.json()["has_active_access"] is False
        assert content.status_code == 403


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
        with _patch_validator(_claims(sub=sub_id)):
            sub = await client.get(
                f"/api/v1/subscriber/search/alerts?q={token}", headers=_AUTH
            )
        assert sub.status_code == 200

        # The public search route was removed; the subscriber route is now the
        # only caller of the shared `search_alerts_impl`, so compare against it.
        from app.api.search import search_alerts_impl

        shared = await search_alerts_impl(db_session, token, 0, 50, 20)
        assert sub.json() == shared.model_dump(mode="json", by_alias=True)
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


# ---------------------------------------------------------------------------
# Risk-band filter + stats (Critical/High/Medium/Low, matching the badges)
# ---------------------------------------------------------------------------

from app.api import public_alerts as public_alerts_api  # noqa: E402
from app.api.subscriber import (  # noqa: E402
    _BAND_CRITICAL_MIN,
    _BAND_HIGH_MIN,
    _BAND_MEDIUM_MIN,
    _to_top_alert_read,
)
from app.pipeline.publishing.risk_bands import compute_risk_band  # noqa: E402


def test_subscriber_band_constants_match_risk_bands():
    # The mirrored SQL thresholds must agree with the canonical band logic.
    assert compute_risk_band(_BAND_CRITICAL_MIN).value == "critical"
    assert compute_risk_band(_BAND_CRITICAL_MIN - 1).value == "high"
    assert compute_risk_band(_BAND_HIGH_MIN).value == "high"
    assert compute_risk_band(_BAND_HIGH_MIN - 1).value == "medium"
    assert compute_risk_band(_BAND_MEDIUM_MIN).value == "medium"
    assert compute_risk_band(_BAND_MEDIUM_MIN - 1).value == "below_60"


@pytest.mark.asyncio
class TestSubscriberRiskBandFilter:
    async def _active(self, db_session):
        sub_id = f"band-{uuid.uuid4()}"
        await _seed_profile_with_subscription(db_session, sub_id=sub_id, status="active")
        return sub_id

    @pytest.mark.parametrize(
        "risk_level, score, band",
        [("critical", 21, "critical"), ("high", 19, "high"),
         ("medium", 16, "medium"), ("low", 10, "below_60")],
    )
    async def test_band_filter_selects_only_its_band(
        self, client: AsyncClient, db_session: AsyncSession, risk_level, score, band
    ):
        cat = f"BandCat-{uuid.uuid4().hex[:8]}"
        # One published alert in each band, all under a unique category.
        crit = await _seed_published_alert(db_session, category=cat, signal_score=21)
        high = await _seed_published_alert(db_session, category=cat, signal_score=19)
        med = await _seed_published_alert(db_session, category=cat, signal_score=16)
        low = await _seed_published_alert(db_session, category=cat, signal_score=10)
        wanted = {"critical": crit, "high": high, "medium": med, "low": low}[risk_level]

        sub_id = await self._active(db_session)
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                f"/api/v1/subscriber/alerts?category={cat}&risk_level={risk_level}",
                headers=_AUTH,
            )
        assert resp.status_code == 200
        alerts = resp.json()["alerts"]
        assert [a["id"] for a in alerts] == [wanted.id]
        assert alerts[0]["risk_band"] == band

    async def test_critical_is_excluded_from_high(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"BandCat-{uuid.uuid4().hex[:8]}"
        crit = await _seed_published_alert(db_session, category=cat, signal_score=22)
        high = await _seed_published_alert(db_session, category=cat, signal_score=18)
        sub_id = await self._active(db_session)
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                f"/api/v1/subscriber/alerts?category={cat}&risk_level=high", headers=_AUTH
            )
        ids = [a["id"] for a in resp.json()["alerts"]]
        assert high.id in ids and crit.id not in ids

    async def test_invalid_risk_level_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = await self._active(db_session)
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                "/api/v1/subscriber/alerts?risk_level=extreme", headers=_AUTH
            )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestSubscriberStatsCritical:
    async def _active(self, db_session):
        sub_id = f"stats-{uuid.uuid4()}"
        await _seed_profile_with_subscription(db_session, sub_id=sub_id, status="active")
        return sub_id

    async def test_stats_exposes_critical_count(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = await self._active(db_session)
        # Delta-based so leaked committed rows from other tests don't matter.
        with _patch_validator(_claims(sub=sub_id)):
            before = (await client.get("/api/v1/subscriber/alerts/stats", headers=_AUTH)).json()
        assert "critical_count" in before

        await _seed_published_alert(db_session, signal_score=21)  # critical band
        await _seed_published_alert(db_session, signal_score=19)  # high band

        with _patch_validator(_claims(sub=sub_id)):
            after = (await client.get("/api/v1/subscriber/alerts/stats", headers=_AUTH)).json()

        assert after["critical_count"] == before["critical_count"] + 1
        assert after["high_count"] == before["high_count"] + 1  # critical not double-counted


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalise a model datetime to UTC for comparison.

    ``RawItem.published_at`` is a naive-mapped column while
    ``ProcessedAlert.published_at`` is ``DateTime(timezone=True)``, so the display
    date arrives naive and the fallback arrives aware.
    """
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _instant(value: str | None) -> datetime | None:
    """Parse an API timestamp, treating a naive value as UTC.

    ``RawItem.published_at`` is a naive-mapped column while
    ``ProcessedAlert.published_at`` is ``DateTime(timezone=True)``, so the same
    JSON field serialises with or without an offset depending on which date it
    carries. These tests compare instants, not string forms.
    """
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@pytest.mark.asyncio
class TestSubscriberTopAlertsDisplayDate:
    """Selection uses HiddenAlerts publication time; display prefers the source date.

    Two distinct timestamps, deliberately:

    * ``ProcessedAlert.published_at`` — ours. Decides the seven-day window and the
      ordering. Never shown when a source date exists.
    * ``source_published_at`` — the original article date. What the Dashboard
      shows, with our timestamp as the fallback.

    An alert we published this week may therefore display an older article date.
    That is expected and is not evidence the weekly filter failed.

    Selection assertions go through the service with a wide limit and filter to
    the alerts each test created: the session-scoped database carries alerts from
    every other test in the module, and only three positions exist.
    """

    async def _alert(self, db_session, *, source_date, our_date, score=25):
        source = await _seed_source(db_session, name=f"Src {uuid.uuid4()}")
        raw = await _seed_raw_item(
            db_session, source, url=f"https://x/{uuid.uuid4()}", published_at=source_date
        )
        alert = await _seed_alert(
            db_session, raw, is_published=True, signal_score=score,
            published_at=our_date or datetime.now(timezone.utc),
        )
        if our_date is None:
            # _seed_alert coalesces None to "now"; force the NULL we actually want.
            alert.published_at = None
            await db_session.commit()

        # Load the relationships the mapper reads, exactly as the service does —
        # a lazy load would fail under asyncio.
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.processed_alert import ProcessedAlert
        from app.models.raw_item import RawItem

        loaded = (
            await db_session.execute(
                select(ProcessedAlert)
                .where(ProcessedAlert.id == alert.id)
                .options(
                    selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source)
                )
            )
        ).scalar_one()
        return loaded

    async def _selected_ids(self, db_session, *ids):
        from app.services.top_alerts_service import get_top_alerts

        alerts = await get_top_alerts(db_session, now=datetime.now(timezone.utc), limit=200)
        wanted = set(ids)
        return [a.id for a in alerts if a.id in wanted]

    # --- display date ----------------------------------------------------

    async def test_display_date_prefers_the_source_article_date(self, db_session):
        source_date = datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc)
        ours = datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc)
        alert = await self._alert(db_session, source_date=source_date, our_date=ours)

        read = _to_top_alert_read(alert)
        assert _as_utc(read.published_at) == source_date
        assert _as_utc(read.published_at) != ours

    async def test_source_published_at_remains_exposed_separately(self, db_session):
        source_date = datetime(2026, 7, 30, 8, 0, tzinfo=timezone.utc)
        alert = await self._alert(
            db_session, source_date=source_date,
            our_date=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        )

        read = _to_top_alert_read(alert)
        assert _as_utc(read.source_published_at) == source_date
        assert read.published_at == read.source_published_at

    async def test_falls_back_to_our_publication_time_without_a_source_date(
        self, db_session
    ):
        ours = datetime(2026, 8, 1, 11, 0, tzinfo=timezone.utc)
        alert = await self._alert(db_session, source_date=None, our_date=ours)

        read = _to_top_alert_read(alert)
        assert read.source_published_at is None
        assert _as_utc(read.published_at) == ours

    async def test_every_other_field_survives_the_copy(self, db_session):
        alert = await self._alert(
            db_session, source_date=datetime(2026, 7, 28, tzinfo=timezone.utc),
            our_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        base = public_alerts_api._to_public_read(alert)
        top = _to_top_alert_read(alert)

        differing = {
            k for k in base.model_dump()
            if getattr(base, k) != getattr(top, k)
        }
        assert differing == {"published_at"}, differing

    async def test_the_mapper_does_not_mutate_the_orm_instance(self, db_session):
        source_date = datetime(2026, 7, 15, 5, 0, tzinfo=timezone.utc)
        ours = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
        alert = await self._alert(db_session, source_date=source_date, our_date=ours)

        read = _to_top_alert_read(alert)
        assert _as_utc(read.published_at) == source_date

        # The ORM row is untouched, in memory and after a refresh.
        assert _as_utc(alert.published_at) == ours
        assert _as_utc(alert.raw_item.published_at) == source_date
        await db_session.refresh(alert)
        assert _as_utc(alert.published_at) == ours

    # --- eligibility is unaffected by the display date -------------------

    async def test_an_old_article_published_by_us_this_week_qualifies(self, db_session):
        alert = await self._alert(
            db_session, source_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
            our_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert await self._selected_ids(db_session, alert.id) == [alert.id]
        assert _as_utc(_to_top_alert_read(alert).published_at).year == 2025

    async def test_a_recent_article_published_by_us_long_ago_is_excluded(
        self, db_session
    ):
        alert = await self._alert(
            db_session, source_date=datetime.now(timezone.utc) - timedelta(hours=2),
            our_date=datetime.now(timezone.utc) - timedelta(days=40),
        )
        assert await self._selected_ids(db_session, alert.id) == []

    async def test_a_source_date_cannot_rescue_a_null_publication_time(self, db_session):
        alert = await self._alert(
            db_session, source_date=datetime.now(timezone.utc), our_date=None
        )
        assert alert.published_at is None
        assert await self._selected_ids(db_session, alert.id) == []

    async def test_ordering_follows_our_timestamp_while_display_follows_the_source(
        self, db_session
    ):
        """Same band, same score — A wins on our timestamp despite an older article."""
        now = datetime.now(timezone.utc)
        alert_a = await self._alert(                       # older article, newer by us
            db_session, source_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
            our_date=now - timedelta(hours=1),
        )
        alert_b = await self._alert(                       # newer article, older by us
            db_session, source_date=datetime(2026, 7, 31, tzinfo=timezone.utc),
            our_date=now - timedelta(days=3),
        )

        assert await self._selected_ids(db_session, alert_a.id, alert_b.id) == [
            alert_a.id, alert_b.id
        ], "ordering must use HiddenAlerts publication time, not the displayed date"

        assert _as_utc(_to_top_alert_read(alert_a).published_at).month == 6
        assert _as_utc(_to_top_alert_read(alert_b).published_at).month == 7

    # --- nothing else changed --------------------------------------------

    async def test_the_public_mapper_still_reports_our_timestamp(self, db_session):
        source_date = datetime(2026, 7, 20, 7, 0, tzinfo=timezone.utc)
        ours = datetime(2026, 8, 1, 13, 0, tzinfo=timezone.utc)
        alert = await self._alert(db_session, source_date=source_date, our_date=ours)

        public = public_alerts_api._to_public_read(alert)
        assert _as_utc(public.published_at) == ours, "public behaviour is unchanged"
        assert _as_utc(public.source_published_at) == source_date

    async def test_other_subscriber_endpoints_keep_the_shared_mapper(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Only /alerts/top uses the display-date mapper in this refinement."""
        source_date = datetime(2026, 7, 21, 6, 0, tzinfo=timezone.utc)
        ours = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
        alert = await self._alert(db_session, source_date=source_date, our_date=ours)
        sub_id = f"othermap-{uuid.uuid4()}"
        await _seed_profile_with_subscription(db_session, sub_id=sub_id, status="active")

        with _patch_validator(_claims(sub=sub_id)):
            listing = await client.get(
                "/api/v1/subscriber/alerts?limit=500", headers=_AUTH
            )
        row = next(a for a in listing.json()["alerts"] if a["id"] == alert.id)
        assert _instant(row["published_at"]) == ours, "unchanged on the feed"
        assert _instant(row["source_published_at"]) == source_date

    async def test_the_shared_public_mapper_is_unchanged(self):
        import inspect

        from app.api import public_alerts, subscriber

        assert "source_published_at or" not in inspect.getsource(
            public_alerts._to_public_read
        )
        wrapper = inspect.getsource(subscriber._to_top_alert_read)
        assert "_to_public_read" in wrapper
        assert "model_copy" in wrapper

    async def test_response_model_carries_risk_band_and_stays_backward_compatible(self):
        """Top Alerts now answers with the subscriber schema, not the public one.

        It previously returned ``PublicAlertsResponse``, which has no
        ``risk_band``; the Dashboard fell back to the legacy ``risk_level`` and a
        Critical alert rendered as "high". The change is purely additive —
        ``SubscriberAlertRead`` extends ``PublicAlertRead``, so every field the
        old contract promised is still there.
        """
        from app.main import app

        spec = app.openapi()
        operation = spec["paths"]["/api/v1/subscriber/alerts/top"]["get"]
        schema_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema_ref["$ref"].endswith("SubscriberAlertsResponse")

        schemas = spec["components"]["schemas"]
        alert_schema = schemas["SubscriberAlertRead"]["properties"]
        assert "published_at" in alert_schema
        assert "source_published_at" in alert_schema
        # The canonical V1 field is now part of the published contract.
        assert "risk_band" in alert_schema

        # Backward compatibility: nothing the public item promised was dropped.
        public_fields = set(schemas["PublicAlertRead"]["properties"])
        assert public_fields <= set(alert_schema)

        # The unauthenticated public feed must NOT gain risk_band.
        public_op = spec["paths"]["/api/alerts"]["get"]
        public_ref = public_op["responses"]["200"]["content"]["application/json"]["schema"]
        assert public_ref["$ref"].endswith("PublicAlertsResponse")
        assert "risk_band" not in schemas["PublicAlertRead"]["properties"]

    async def test_authorization_and_empty_shape_are_unchanged(
        self, client: AsyncClient
    ):
        with _patch_validator(_claims(sub=f"top-noauth-{uuid.uuid4()}")):
            denied = await client.get("/api/v1/subscriber/alerts/top", headers=_AUTH)
        assert denied.status_code == 403
        assert (await client.get("/api/v1/subscriber/alerts/top")).status_code == 401



# ---------------------------------------------------------------------------
# Slice 3B.2Y — canonical V1 `risk_band` on the subscriber contract.
#
# Production alert 1312 was banded `critical` by the V1 policy while its legacy
# `risk_level` column still said `high`. Top Alerts answered with the *public*
# schema, which carries no `risk_band`, so the Dashboard fell back to the legacy
# field — and that fallback deliberately never invents Critical. A Critical alert
# therefore rendered as "high" beside a score of 80.
#
# Band assertions go through the mapper with an ORM-loaded alert, mirroring
# TestSubscriberTopAlertsDisplayDate: the session-scoped database carries alerts
# from every other test in this module and Top Alerts has only three positions,
# so a freshly seeded row is not reliably in the API response.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubscriberRiskBandContract:
    async def _loaded(self, db_session, *, score, stored_band=None, risk_level="medium"):
        """Seed a published alert and reload it with the mapper's relationships."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.processed_alert import ProcessedAlert
        from app.models.raw_item import RawItem

        alert = await _seed_published_alert(
            db_session, signal_score=score, risk_level=risk_level
        )
        if stored_band is not None:
            alert.risk_band = stored_band
            await db_session.commit()

        return (
            await db_session.execute(
                select(ProcessedAlert)
                .where(ProcessedAlert.id == alert.id)
                .options(
                    selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source)
                )
            )
        ).scalar_one()

    async def _active(self, db_session) -> str:
        sub_id = f"band-contract-{uuid.uuid4()}"
        await _seed_profile_with_subscription(db_session, sub_id=sub_id, status="active")
        return sub_id

    # --- Top Alerts band ---------------------------------------------------

    @pytest.mark.parametrize("score, expected", [(21, "critical"), (18, "high")])
    async def test_top_alerts_exposes_the_band_for_each_publishable_score(
        self, db_session: AsyncSession, score, expected
    ):
        alert = await self._loaded(db_session, score=score)
        assert _to_top_alert_read(alert).risk_band == expected

    async def test_top_alerts_keeps_the_canonical_band_when_legacy_level_disagrees(
        self, db_session: AsyncSession
    ):
        """The production alert-1312 shape: stored critical, legacy level high."""
        alert = await self._loaded(
            db_session, score=20, stored_band="critical", risk_level="high"
        )
        read = _to_top_alert_read(alert)
        assert read.risk_band == "critical", "canonical V1 band must survive"
        assert read.risk_level == "high", "legacy field preserved, not rewritten"

    async def test_stored_band_wins_over_the_score_derived_fallback(
        self, db_session: AsyncSession
    ):
        """Proves the column is read, not recomputed.

        Score 18 alone would compute to `high`; the stored column says
        `critical`, and the stored value is what the contract must return.
        """
        alert = await self._loaded(db_session, score=18, stored_band="critical")
        assert _to_top_alert_read(alert).risk_band == "critical"

    async def test_band_falls_back_to_the_score_when_the_column_is_null(
        self, db_session: AsyncSession
    ):
        alert = await self._loaded(db_session, score=21)
        assert alert.risk_band is None, "seed leaves the column unset"
        assert _to_top_alert_read(alert).risk_band == "critical"

    async def test_top_alerts_item_keeps_every_public_field(
        self, db_session: AsyncSession
    ):
        from app.schemas.alert import PublicAlertRead

        alert = await self._loaded(db_session, score=19)
        read = _to_top_alert_read(alert)
        assert set(PublicAlertRead.model_fields) <= set(type(read).model_fields), (
            "contract must stay additive"
        )
        assert read.model_dump().keys() >= set(PublicAlertRead.model_fields)

    async def test_top_alerts_api_items_all_carry_a_band(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Whatever wins the three positions, each item must expose risk_band."""
        await self._loaded(db_session, score=25)
        sub_id = await self._active(db_session)

        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get("/api/v1/subscriber/alerts/top", headers=_AUTH)
        assert resp.status_code == 200
        alerts = resp.json()["alerts"]
        assert alerts, "seeded a top-scoring alert, so the widget cannot be empty"
        for item in alerts:
            assert "risk_band" in item
            assert item["risk_band"] in ("critical", "high", "medium", "below_60")

    # --- list / detail ------------------------------------------------------

    async def test_subscriber_list_exposes_the_canonical_band(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"BandContract-{uuid.uuid4().hex[:8]}"
        alert = await _seed_published_alert(
            db_session, category=cat, signal_score=20, risk_level="high"
        )
        alert.risk_band = "critical"
        await db_session.commit()
        sub_id = await self._active(db_session)

        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                f"/api/v1/subscriber/alerts?category={cat}", headers=_AUTH
            )
        assert resp.status_code == 200
        row = next(a for a in resp.json()["alerts"] if a["id"] == alert.id)
        assert row["risk_band"] == "critical"
        assert row["risk_level"].lower() == "high", "legacy field still present"

    async def test_subscriber_detail_exposes_the_canonical_band(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        alert = await _seed_published_alert(
            db_session, signal_score=20, risk_level="high"
        )
        alert.risk_band = "critical"
        await db_session.commit()
        sub_id = await self._active(db_session)

        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(f"/api/v1/subscriber/alerts/{alert.id}", headers=_AUTH)
        assert resp.status_code == 200
        body = resp.json()
        assert body["risk_band"] == "critical"
        assert body["risk_level"].lower() == "high"

    # --- the public feed must not change ------------------------------------

    async def test_public_feed_never_gains_the_subscriber_band(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        alert = await _seed_published_alert(db_session, signal_score=21)

        resp = await client.get("/api/alerts?limit=500")
        assert resp.status_code == 200
        row = next((a for a in resp.json()["alerts"] if a["id"] == alert.id), None)
        assert row is not None
        assert "risk_band" not in row
