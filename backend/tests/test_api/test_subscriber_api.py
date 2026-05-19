"""Endpoint tests for /api/v1/subscriber/* — Auth/Payment Phase 1 Slice 2.

We bypass real Supabase networking by patching ``validate_supabase_token``
on the supabase auth module. The Authorization-header parsing, profile
upsert flow, and access logic all run for real against the in-memory DB.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import supabase as supabase_auth
from app.models.subscriber_profile import SubscriberProfile
from app.models.subscription import Subscription


def _claims(**overrides):
    base = {
        "sub": "supabase-user-001",
        "email": "user@example.com",
        "aud": "authenticated",
        "iss": "https://test.supabase.co/auth/v1",
    }
    base.update(overrides)
    return base


def _patch_validator(claims):
    async def _fake_validate(token):
        return claims

    return patch.object(
        supabase_auth, "validate_supabase_token", side_effect=_fake_validate
    )


# ---------------------------------------------------------------------------
# Authorization header failure paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuthorizationHeader:
    async def test_missing_authorization_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/subscriber/me")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "missing_authorization_header"

    async def test_non_bearer_scheme_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/subscriber/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "invalid_authorization_scheme"

    async def test_bearer_without_token_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/subscriber/me",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        # validator raises 401 → endpoint should propagate.
        from fastapi import HTTPException

        async def _reject(token):
            raise HTTPException(status_code=401, detail="invalid_token")

        with patch.object(
            supabase_auth, "validate_supabase_token", side_effect=_reject
        ):
            resp = await client.get(
                "/api/v1/subscriber/me",
                headers={"Authorization": "Bearer broken.jwt"},
            )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "invalid_token"

    async def test_access_endpoint_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/subscriber/access")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Profile upsert flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubscriberProfileLifecycle:
    async def test_valid_token_creates_profile(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        with _patch_validator(_claims(sub="new-user", email="new@example.com")):
            resp = await client.get(
                "/api/v1/subscriber/me",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200

        result = await db_session.execute(
            select(SubscriberProfile).where(
                SubscriberProfile.supabase_user_id == "new-user"
            )
        )
        profile = result.scalar_one()
        assert profile.email == "new@example.com"
        assert profile.role == "subscriber"
        assert profile.last_seen_at is not None

    async def test_valid_token_reuses_existing_profile(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        existing = SubscriberProfile(
            supabase_user_id="reuse-user",
            email="reuse@example.com",
            role="subscriber",
        )
        db_session.add(existing)
        await db_session.commit()
        existing_id = existing.id

        with _patch_validator(_claims(sub="reuse-user", email="reuse@example.com")):
            resp = await client.get(
                "/api/v1/subscriber/me",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200

        # Refresh from DB
        result = await db_session.execute(
            select(SubscriberProfile).where(
                SubscriberProfile.supabase_user_id == "reuse-user"
            )
        )
        profiles = result.scalars().all()
        assert len(profiles) == 1
        assert profiles[0].id == existing_id

    async def test_valid_token_updates_last_seen_at(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        stale_time = datetime.now(timezone.utc) - timedelta(days=30)
        existing = SubscriberProfile(
            supabase_user_id="lastseen-user",
            email="lastseen@example.com",
            role="subscriber",
            last_seen_at=stale_time,
        )
        db_session.add(existing)
        await db_session.commit()

        with _patch_validator(_claims(sub="lastseen-user", email="lastseen@example.com")):
            resp = await client.get(
                "/api/v1/subscriber/me",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200

        await db_session.refresh(existing)
        # SQLite drops tzinfo on roundtrip; compare as naive UTC.
        seen = existing.last_seen_at
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        assert seen > stale_time

    async def test_email_change_in_token_updates_profile(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        existing = SubscriberProfile(
            supabase_user_id="email-user",
            email="old@example.com",
            role="subscriber",
        )
        db_session.add(existing)
        await db_session.commit()

        with _patch_validator(_claims(sub="email-user", email="new@example.com")):
            resp = await client.get(
                "/api/v1/subscriber/me",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200

        await db_session.refresh(existing)
        assert existing.email == "new@example.com"


# ---------------------------------------------------------------------------
# /me response shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubscriberMeResponse:
    async def test_locked_when_no_subscription_row(self, client: AsyncClient):
        with _patch_validator(
            _claims(sub="locked-user", email="locked@example.com")
        ):
            resp = await client.get(
                "/api/v1/subscriber/me",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["authenticated"] is True
        assert body["has_active_subscription"] is False
        assert body["access_level"] == "locked"
        assert body["email"] == "locked@example.com"
        assert body["subscription"] is None

    async def test_subscriber_when_active_subscription_exists(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        profile = SubscriberProfile(
            supabase_user_id="active-user",
            email="active@example.com",
            role="subscriber",
            stripe_customer_id="cus_test_active",
        )
        db_session.add(profile)
        await db_session.flush()
        sub = Subscription(
            subscriber_profile_id=profile.id,
            stripe_customer_id="cus_test_active",
            stripe_subscription_id="sub_active",
            stripe_price_id="price_monthly_test",
            plan_type="monthly",
            status="active",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=20),
            cancel_at_period_end=False,
        )
        db_session.add(sub)
        await db_session.commit()

        with _patch_validator(
            _claims(sub="active-user", email="active@example.com")
        ):
            resp = await client.get(
                "/api/v1/subscriber/me",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["authenticated"] is True
        assert body["has_active_subscription"] is True
        assert body["access_level"] == "subscriber"
        assert body["subscription"]["status"] == "active"
        assert body["subscription"]["plan_type"] == "monthly"
        assert body["subscription"]["cancel_at_period_end"] is False

    async def test_locked_when_subscription_canceled_in_past(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        profile = SubscriberProfile(
            supabase_user_id="canceled-user",
            email="canceled@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.flush()
        sub = Subscription(
            subscriber_profile_id=profile.id,
            stripe_customer_id="cus_canceled",
            stripe_subscription_id="sub_canceled",
            plan_type="monthly",
            status="canceled",
            current_period_end=datetime.now(timezone.utc) - timedelta(days=1),
            cancel_at_period_end=True,
            canceled_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.add(sub)
        await db_session.commit()

        with _patch_validator(
            _claims(sub="canceled-user", email="canceled@example.com")
        ):
            resp = await client.get(
                "/api/v1/subscriber/me",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active_subscription"] is False
        assert body["access_level"] == "locked"
        # Subscription details are still returned so the frontend can show
        # "your subscription expired on …" messaging.
        assert body["subscription"]["status"] == "canceled"


# ---------------------------------------------------------------------------
# /access response shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubscriberAccessResponse:
    async def test_no_subscription_returns_locked(self, client: AsyncClient):
        with _patch_validator(_claims(sub="no-sub-user")):
            resp = await client.get(
                "/api/v1/subscriber/access",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["can_access_full_content"] is False
        assert body["reason"] == "subscription_required"

    async def test_active_subscription_returns_allowed(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        profile = SubscriberProfile(
            supabase_user_id="ok-user",
            email="ok@example.com",
            role="subscriber",
        )
        db_session.add(profile)
        await db_session.flush()
        sub = Subscription(
            subscriber_profile_id=profile.id,
            stripe_customer_id="cus_ok",
            stripe_subscription_id="sub_ok",
            plan_type="annual",
            status="active",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=200),
            cancel_at_period_end=False,
        )
        db_session.add(sub)
        await db_session.commit()

        with _patch_validator(_claims(sub="ok-user", email="ok@example.com")):
            resp = await client.get(
                "/api/v1/subscriber/access",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["can_access_full_content"] is True
        assert body["reason"] == "active_subscription"
