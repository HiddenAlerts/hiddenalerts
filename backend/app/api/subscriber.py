"""Subscriber-facing API — Authentication & Payment Phase 1, Slices 2 & 5.

Mounted at ``/api/v1/subscriber/*`` in ``app.main``. Every route requires a
valid Supabase Bearer token (enforced by :func:`get_current_subscriber`).

Identity / access endpoints (``/me``, ``/access``) need only a valid token.
Paid content endpoints (``/alerts*``, ``/search/alerts``) additionally require
an active subscription via :func:`require_active_subscription`, and delegate to
the same shared implementations the public endpoints use so the response shapes
are identical.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import public_alerts as public_alerts_api
from app.api import search as search_api
from app.auth.subscriber_access import (
    ActiveSubscriberContext,
    require_active_subscription,
)
from app.auth.supabase import SubscriberContext, get_current_subscriber
from app.database import get_db
from app.models.subscription import Subscription
from app.schemas.alert import (
    PublicAlertDetail,
    PublicAlertStatsResponse,
    PublicAlertsResponse,
)
from app.schemas.search import SearchResponse
from app.schemas.subscriber import (
    SubscriberAccessResponse,
    SubscriberMeResponse,
    SubscriptionMeRead,
)
from app.services.subscription_service import has_active_subscription_access

log = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriber", tags=["subscriber"])


async def _latest_subscription(
    db: AsyncSession, subscriber_profile_id: int
) -> Subscription | None:
    """Return the most recent subscription row for this profile, if any.

    "Most recent" = highest ``id`` — subscriptions are append-only from the
    webhook in later slices, so newest id wins.
    """
    result = await db.execute(
        select(Subscription)
        .where(Subscription.subscriber_profile_id == subscriber_profile_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/me", response_model=SubscriberMeResponse)
async def get_subscriber_me(
    subscriber: SubscriberContext = Depends(get_current_subscriber),
    db: AsyncSession = Depends(get_db),
) -> SubscriberMeResponse:
    """Return the authenticated subscriber's identity + access state.

    For Slice 2 (Stripe not yet wired) most authenticated users will see
    ``has_active_subscription=false`` and ``access_level="locked"``. Once a
    subscription row exists for the profile (created by the webhook in a later
    slice) and ``has_active_subscription_access`` agrees, the response flips to
    ``access_level="subscriber"``.
    """
    subscription = await _latest_subscription(db, subscriber.profile.id)
    has_access = False
    sub_payload: SubscriptionMeRead | None = None
    if subscription is not None:
        has_access = has_active_subscription_access(
            subscription.status, subscription.current_period_end
        )
        sub_payload = SubscriptionMeRead.model_validate(subscription)

    return SubscriberMeResponse(
        authenticated=True,
        has_active_subscription=has_access,
        access_level="subscriber" if has_access else "locked",
        email=subscriber.email,
        subscription=sub_payload,
    )


@router.get("/access", response_model=SubscriberAccessResponse)
async def get_subscriber_access(
    subscriber: SubscriberContext = Depends(get_current_subscriber),
    db: AsyncSession = Depends(get_db),
) -> SubscriberAccessResponse:
    """Lightweight route-guard helper for the frontend.

    Returns ``can_access_full_content`` plus a machine-readable ``reason``
    string so Hasnain can render different paywall messaging
    (``subscription_required`` vs ``active_subscription``).
    """
    subscription = await _latest_subscription(db, subscriber.profile.id)
    if subscription is None:
        return SubscriberAccessResponse(
            can_access_full_content=False,
            reason="subscription_required",
        )
    has_access = has_active_subscription_access(
        subscription.status, subscription.current_period_end
    )
    return SubscriberAccessResponse(
        can_access_full_content=has_access,
        reason="active_subscription" if has_access else "subscription_required",
    )


# ---------------------------------------------------------------------------
# Paid content (Slice 5) — require an active subscription. These delegate to
# the same shared implementations as the public endpoints, so response shapes
# match field-for-field. Route ordering note: /alerts/stats and /alerts/top
# are declared BEFORE /alerts/{alert_id} so the literals aren't parsed as ids.
# ---------------------------------------------------------------------------


@router.get("/alerts/stats", response_model=PublicAlertStatsResponse)
async def subscriber_alert_stats(
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> PublicAlertStatsResponse:
    """Published-alert aggregate stats — mirrors GET /api/alerts/stats."""
    return await public_alerts_api.published_stats_impl(db)


@router.get("/alerts/top", response_model=PublicAlertsResponse)
async def subscriber_top_alerts(
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> PublicAlertsResponse:
    """Curated top alerts — mirrors GET /api/alerts/top."""
    return await public_alerts_api.top_alerts_impl(db)


@router.get("/alerts", response_model=PublicAlertsResponse)
async def subscriber_alerts(
    risk_level: str | None = Query(None, description="Filter: low, medium, high"),
    category: str | None = Query(None, description="Filter by category (exact match)"),
    source: str | None = Query(None, description="Partial source name search"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> PublicAlertsResponse:
    """Published-alerts feed — mirrors GET /api/alerts."""
    return await public_alerts_api.list_published_alerts_impl(
        db, risk_level, category, source, limit, offset
    )


@router.get(
    "/alerts/{alert_id}",
    response_model=PublicAlertDetail,
    response_model_exclude_none=True,
)
async def subscriber_alert_detail(
    alert_id: int,
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> PublicAlertDetail:
    """Enriched published-alert detail — mirrors GET /api/alerts/{id}.

    404 if the alert does not exist or is not published.
    """
    return await public_alerts_api.published_alert_detail_impl(db, alert_id)


@router.get(
    "/search/alerts",
    response_model=SearchResponse,
    response_model_by_alias=True,
)
async def subscriber_search_alerts(
    q: str = Query(..., description="Search text (required, trimmed)."),
    min_score: int = Query(
        0,
        description=(
            "Minimum normalized signal score (0–100). Default 0. Values "
            "outside 0–100 are clamped."
        ),
    ),
    limit: int = Query(
        50,
        ge=1,
        description=(
            "Cap on the full alerts list. Default 50, max 100. Values above "
            "max are clamped; values <1 are rejected."
        ),
    ),
    group_limit: int = Query(
        20,
        ge=1,
        description=(
            "Cap on alerts inside each group. Default 20, max 50. Values "
            "above max are clamped; values <1 are rejected."
        ),
    ),
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Published-alert search — mirrors GET /api/search/alerts."""
    return await search_api.search_alerts_impl(db, q, min_score, limit, group_limit)
