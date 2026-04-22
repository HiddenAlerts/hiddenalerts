"""Public read-only alerts feed.

No authentication required. Returns only published alerts.
This is the endpoint Hasnain should use for the current frontend MVP.

Route:
  GET /api/alerts   — paginated published alert feed

Intentionally separate from:
  - /api/v1/alerts            (admin — returns all alerts, auth required)
  - /api/v1/client/alerts     (subscriber — published only, auth required)

This public endpoint has no auth guard so Hasnain can display real alerts
in the frontend without implementing a login flow in this phase.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.schemas.alert import PublicAlertRead, PublicAlertsResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["public"])


def _to_public(alert: ProcessedAlert) -> PublicAlertRead:
    """Map ORM alert to the flat public schema."""
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
    stmt = (
        select(ProcessedAlert)
        .where(ProcessedAlert.is_published.is_(True))
        .options(
            selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source)
        )
        .order_by(
            ProcessedAlert.published_at.desc().nullslast(),
            ProcessedAlert.processed_at.desc(),
        )
    )

    # Optional filters — never expose unpublished records regardless of params
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
    alerts = [_to_public(a) for a in result.scalars().all()]
    return PublicAlertsResponse(alerts=alerts)
