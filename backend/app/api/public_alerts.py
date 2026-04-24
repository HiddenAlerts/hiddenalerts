"""Public read-only alerts feed — M3 Slice 4 extension.

No authentication required on any route in this module.
All queries are hard-filtered to published alerts only (is_published = True).
Unpublished alerts are never exposed, regardless of query parameters.

Routes (all mounted at /api/alerts — no /api/v1 prefix):
  GET /api/alerts            — paginated published alert feed (existing)
  GET /api/alerts/stats      — published alert aggregate counts + category breakdown (NEW)
  GET /api/alerts/{id}       — single published alert detail; 404 if absent or unpublished (NEW)

Intentionally separate from:
  /api/v1/alerts             (internal/admin — returns all alerts, auth required)
  /api/v1/client/alerts      (subscriber — published only, auth required; reserved for future use)

Route ordering note:
  /stats must be declared BEFORE /{id} so FastAPI does not try to
  interpret the literal string "stats" as an integer alert ID.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.schemas.alert import (
    PublicAlertDetail,
    PublicAlertRead,
    PublicAlertsResponse,
    PublicAlertStatsResponse,
    PublicCategoryBreakdown,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["public"])


# ---------------------------------------------------------------------------
# Shared query helpers
# ---------------------------------------------------------------------------


def _published_base_stmt():
    """Return a base SELECT for published alerts with raw_item + source eager-loaded.

    Every public endpoint MUST start from this statement so the
    is_published=True guard is never accidentally omitted.
    """
    return (
        select(ProcessedAlert)
        .where(ProcessedAlert.is_published.is_(True))
        .options(
            selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source)
        )
    )


# ---------------------------------------------------------------------------
# ORM → schema helpers
# ---------------------------------------------------------------------------


def _to_public_read(alert: ProcessedAlert) -> PublicAlertRead:
    """Map ORM alert to the flat public list schema."""
    title = source_name = source_url = None
    if alert.raw_item:
        title = alert.raw_item.title
        source_url = alert.raw_item.item_url
        if alert.raw_item.source:
            source_name = alert.raw_item.source.name

    return PublicAlertRead(
        id=alert.id,
        title=title,
        summary=alert.summary,
        category=alert.primary_category,
        risk_level=alert.risk_level,
        signal_score=alert.signal_score_total,
        source_name=source_name,
        source_url=source_url,
        published_at=alert.published_at,
    )


def _to_public_detail(alert: ProcessedAlert) -> PublicAlertDetail:
    """Map ORM alert to the richer public detail schema.

    Adds processed_at, secondary_category, and a safe flat entities list on
    top of the base read fields. Internal scoring fields, moderation state,
    and raw AI structures are deliberately excluded.
    """
    base = _to_public_read(alert)

    # Unwrap internal {"names": [...]} to a stable flat list.
    entities: list[str] = []
    if isinstance(alert.entities_json, dict):
        raw = alert.entities_json.get("names", [])
        if isinstance(raw, list):
            entities = [str(e) for e in raw if e]

    return PublicAlertDetail(
        **base.model_dump(),
        processed_at=alert.processed_at,
        secondary_category=alert.secondary_category,
        entities=entities,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=PublicAlertsResponse)
async def list_public_alerts(
    risk_level: str | None = Query(None, description="Filter: low, medium, high"),
    category: str | None = Query(None, description="Filter by category (exact match)"),
    source: str | None = Query(None, description="Partial source name search"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> PublicAlertsResponse:
    """Return published alerts for the public frontend feed.

    No authentication required. Only published alerts are ever returned.
    Sorted newest-published first; unpublished-but-published_at=null rows
    fall safely to the end via nullslast ordering.
    """
    stmt = _published_base_stmt().order_by(
        ProcessedAlert.published_at.desc().nullslast(),
        ProcessedAlert.processed_at.desc(),
    )

    # Optional filters — is_published guard is already applied in the base stmt
    if risk_level is not None:
        stmt = stmt.where(ProcessedAlert.risk_level == risk_level.lower())

    if category is not None:
        stmt = stmt.where(ProcessedAlert.primary_category == category)

    if source is not None:
        stmt = (
            stmt
            .join(RawItem, RawItem.id == ProcessedAlert.raw_item_id)
            .join(Source, Source.id == RawItem.source_id)
            .where(Source.name.ilike(f"%{source}%"))
        )

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    alerts = [_to_public_read(a) for a in result.scalars().all()]
    return PublicAlertsResponse(alerts=alerts)


@router.get("/stats", response_model=PublicAlertStatsResponse)
async def get_public_stats(
    db: AsyncSession = Depends(get_db),
) -> PublicAlertStatsResponse:
    """Return aggregate counts for published alerts only.

    No authentication required.

    Returns:
    - total_alerts: total published alert count
    - high_count / medium_count / low_count: counts by risk level
    - category_breakdown: per-primary_category counts, ordered by count DESC
      then category ASC. Rows with null primary_category are excluded.

    All aggregates are derived exclusively from published alerts.
    No internal operational metadata is exposed.
    """
    # Single-query aggregate: total + per-risk-level counts
    count_stmt = select(
        func.count().label("total"),
        func.count(
            case((ProcessedAlert.risk_level == "high", 1), else_=None)
        ).label("high"),
        func.count(
            case((ProcessedAlert.risk_level == "medium", 1), else_=None)
        ).label("medium"),
        func.count(
            case((ProcessedAlert.risk_level == "low", 1), else_=None)
        ).label("low"),
    ).where(ProcessedAlert.is_published.is_(True))

    row = (await db.execute(count_stmt)).one()
    total = row.total
    high = row.high
    medium = row.medium
    low = row.low

    # Category breakdown — exclude null categories for a clean public response
    cat_stmt = (
        select(
            ProcessedAlert.primary_category.label("category"),
            func.count().label("count"),
        )
        .where(ProcessedAlert.is_published.is_(True))
        .where(ProcessedAlert.primary_category.isnot(None))
        .group_by(ProcessedAlert.primary_category)
        .order_by(func.count().desc(), ProcessedAlert.primary_category.asc())
    )
    cat_rows = (await db.execute(cat_stmt)).all()
    breakdown = [
        PublicCategoryBreakdown(category=r.category, count=r.count)
        for r in cat_rows
    ]

    return PublicAlertStatsResponse(
        total_alerts=total,
        high_count=high,
        medium_count=medium,
        low_count=low,
        category_breakdown=breakdown,
    )


@router.get("/{alert_id}", response_model=PublicAlertDetail)
async def get_public_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
) -> PublicAlertDetail:
    """Return a single published alert detail.

    No authentication required.

    - Returns 200 + public detail schema if the alert exists and is published.
    - Returns 404 if the alert does not exist OR is not published.
      (Unpublished alerts must not be distinguishable from non-existent ones
      through this public route.)
    """
    result = await db.execute(
        _published_base_stmt().where(ProcessedAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )
    return _to_public_detail(alert)
