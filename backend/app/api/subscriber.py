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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import public_alerts as public_alerts_api
from app.api import search as search_api
from app.api._alert_enrichment import (
    band_from_score100,
    build_risk_explanation,
    risk_band_for,
)
from app.auth.subscriber_access import (
    ActiveSubscriberContext,
    require_active_subscription,
)
from app.auth.supabase import SubscriberContext, get_current_subscriber
from app.config import settings
from app.database import get_db
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.subscription import Subscription
from app.schemas.alert import (
    PublicAlertsResponse,
    SubscriberAlertDetail,
    SubscriberAlertRead,
    SubscriberAlertsResponse,
    SubscriberAlertStatsResponse,
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
            subscription.status,
            subscription.current_period_end,
            grace_seconds=settings.subscription_access_grace_seconds,
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
        subscription.status,
        subscription.current_period_end,
        grace_seconds=settings.subscription_access_grace_seconds,
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


# Internal signal_score_total lower bounds per V1 risk band. Source of truth is
# app.pipeline.publishing.risk_bands.compute_risk_band; mirrored here so the SQL
# filter/counts bucket alerts exactly like the badges the subscriber UI renders
# (Critical 80–100, High 70–79, Medium 60–69 on the 0–100 scale). Kept in sync by
# tests/test_api/test_subscriber_content.py.
_BAND_CRITICAL_MIN = 20
_BAND_HIGH_MIN = 18
_BAND_MEDIUM_MIN = 15

# risk_level values the subscriber feed accepts (mutually exclusive V1 bands).
_SUBSCRIBER_RISK_LEVELS = frozenset({"critical", "high", "medium", "low"})


def _subscriber_risk_band_filter(risk_level: str):
    """Return a SQL predicate on ``signal_score_total`` for a subscriber risk band."""
    score = ProcessedAlert.signal_score_total
    rl = risk_level.strip().lower()
    if rl == "critical":
        return score >= _BAND_CRITICAL_MIN
    if rl == "high":
        return and_(score >= _BAND_HIGH_MIN, score < _BAND_CRITICAL_MIN)
    if rl == "medium":
        return and_(score >= _BAND_MEDIUM_MIN, score < _BAND_HIGH_MIN)
    # "low" == below_60
    return score < _BAND_MEDIUM_MIN


@router.get("/alerts/stats", response_model=SubscriberAlertStatsResponse)
async def subscriber_alert_stats(
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> SubscriberAlertStatsResponse:
    """Published-alert aggregate stats for subscribers.

    Counts use the V1 risk bands (adds ``critical_count``); ``total_alerts`` and
    ``category_breakdown`` reuse the shared published-stats implementation.
    """
    base = await public_alerts_api.published_stats_impl(db)

    score = ProcessedAlert.signal_score_total
    row = (
        await db.execute(
            select(
                func.count(case((score >= _BAND_CRITICAL_MIN, 1))).label("critical"),
                func.count(
                    case((and_(score >= _BAND_HIGH_MIN, score < _BAND_CRITICAL_MIN), 1))
                ).label("high"),
                func.count(
                    case((and_(score >= _BAND_MEDIUM_MIN, score < _BAND_HIGH_MIN), 1))
                ).label("medium"),
                func.count(case((score < _BAND_MEDIUM_MIN, 1))).label("low"),
            ).where(ProcessedAlert.is_published.is_(True))
        )
    ).one()

    return SubscriberAlertStatsResponse(
        total_alerts=base.total_alerts,
        critical_count=row.critical,
        high_count=row.high,
        medium_count=row.medium,
        low_count=row.low,
        category_breakdown=base.category_breakdown,
    )


@router.get("/alerts/top", response_model=PublicAlertsResponse)
async def subscriber_top_alerts(
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> PublicAlertsResponse:
    """Curated top alerts — mirrors GET /api/alerts/top."""
    return await public_alerts_api.top_alerts_impl(db)


@router.get("/alerts", response_model=SubscriberAlertsResponse)
async def subscriber_alerts(
    risk_level: str | None = Query(None, description="Filter by V1 band: critical, high, medium, low"),
    category: str | None = Query(None, description="Filter by category (exact match)"),
    source: str | None = Query(None, description="Partial source name search"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> SubscriberAlertsResponse:
    """Published-alerts feed with the V1 `risk_band` (Critical badge) on each item.

    The `risk_level` filter uses the V1 risk bands (critical/high/medium/low) so it
    matches the badges — Critical (score 80–100) is selectable and mutually
    exclusive from High (70–79). Ordering and visibility mirror the published feed.
    """
    if risk_level is not None and risk_level.strip().lower() not in _SUBSCRIBER_RISK_LEVELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid risk_level: {risk_level!r}. Allowed: {sorted(_SUBSCRIBER_RISK_LEVELS)}",
        )

    stmt = public_alerts_api._published_base_stmt().order_by(
        ProcessedAlert.published_at.desc().nullslast(),
        ProcessedAlert.processed_at.desc(),
    )
    if risk_level is not None:
        stmt = stmt.where(_subscriber_risk_band_filter(risk_level))
    if category is not None:
        stmt = stmt.where(ProcessedAlert.primary_category == category)
    if source is not None:
        stmt = (
            stmt.join(RawItem, RawItem.id == ProcessedAlert.raw_item_id)
            .join(Source, Source.id == RawItem.source_id)
            .where(Source.name.ilike(f"%{source}%"))
        )
    stmt = stmt.offset(offset).limit(limit)

    alerts = (await db.execute(stmt)).scalars().all()
    reads = [public_alerts_api._to_public_read(a) for a in alerts]
    return SubscriberAlertsResponse(
        alerts=[
            SubscriberAlertRead(**r.model_dump(), risk_band=band_from_score100(r.signal_score))
            for r in reads
        ]
    )


@router.get(
    "/alerts/{alert_id}",
    response_model=SubscriberAlertDetail,
    response_model_exclude_none=True,
)
async def subscriber_alert_detail(
    alert_id: int,
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> SubscriberAlertDetail:
    """Enriched published-alert detail — mirrors GET /api/alerts/{id}, plus the
    V1 `risk_band` and the curated `risk_explanation` (OPEN-6).

    404 if the alert does not exist or is not published. Reuses the public detail
    mapper (`_to_public_detail`) so the shared fields stay identical; the
    subscriber-only fields are added here, never on the public endpoint.
    """
    result = await db.execute(
        public_alerts_api._detail_stmt().where(ProcessedAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    base = await public_alerts_api._to_public_detail(db, alert)
    return SubscriberAlertDetail(
        **base.model_dump(),
        risk_band=risk_band_for(alert),
        risk_explanation=build_risk_explanation(alert),
    )


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
