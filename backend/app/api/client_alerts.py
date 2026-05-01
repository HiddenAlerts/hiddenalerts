"""Subscriber-safe published alert endpoints — client surface.

Only returns alerts where is_published = true. Authorization requires
subscriber or admin role. Intentionally separate from the internal admin
alert routes in alerts.py.

Routes (registered under /api/v1 prefix):
  GET /client/alerts          — paginated published alert feed
  GET /client/alerts/{id}     — published alert detail (404 if unpublished)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_subscriber_or_admin
from app.database import get_db
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.user import User
from app.schemas.alert import ClientAlertDetail, ClientAlertRead

log = logging.getLogger(__name__)
router = APIRouter(prefix="/client", tags=["client"])


# ---------------------------------------------------------------------------
# Helper: build subscriber-safe response objects from ORM
# ---------------------------------------------------------------------------


def _to_client_read(alert: ProcessedAlert) -> ClientAlertRead:
    """Map ORM ProcessedAlert to ClientAlertRead (same join pattern as _alert_to_read)."""
    title = source_name = item_url = None
    source_published_at = None
    if alert.raw_item:
        title = alert.raw_item.title
        item_url = alert.raw_item.item_url
        source_published_at = alert.raw_item.published_at
        if alert.raw_item.source:
            source_name = alert.raw_item.source.name

    return ClientAlertRead(
        id=alert.id,
        title=title,
        source_name=source_name,
        item_url=item_url,
        risk_level=alert.risk_level,
        primary_category=alert.primary_category,
        signal_score_total=alert.signal_score_total,
        summary=alert.summary,
        processed_at=alert.processed_at,
        source_published_at=source_published_at,
        published_at=alert.published_at,
        matched_keywords=alert.matched_keywords,
    )


def _to_client_detail(alert: ProcessedAlert) -> ClientAlertDetail:
    """Map ORM ProcessedAlert to ClientAlertDetail."""
    base = _to_client_read(alert)
    # Unwrap internal {"names": [...]} structure to a stable flat list
    entities: list[str] = []
    if isinstance(alert.entities_json, dict):
        raw = alert.entities_json.get("names", [])
        entities = [str(e) for e in raw if e] if isinstance(raw, list) else []

    return ClientAlertDetail(
        **base.model_dump(),
        secondary_category=alert.secondary_category,
        entities=entities,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/alerts", response_model=list[ClientAlertRead])
async def list_client_alerts(
    risk_level: str | None = Query(None, description="Filter by risk level: low, medium, high"),
    category: str | None = Query(None, description="Filter by primary_category"),
    source: str | None = Query(None, description="Filter by source name (partial match, case-insensitive)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_subscriber_or_admin),
) -> list[ClientAlertRead]:
    """Return published alerts visible to subscriber and admin users."""
    stmt = (
        select(ProcessedAlert)
        .where(ProcessedAlert.is_published.is_(True))
        .options(selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source))
        .order_by(ProcessedAlert.published_at.desc().nullslast(), ProcessedAlert.processed_at.desc())
    )

    if source is not None:
        stmt = (
            stmt
            .join(RawItem, RawItem.id == ProcessedAlert.raw_item_id)
            .join(Source, Source.id == RawItem.source_id)
            .where(Source.name.ilike(f"%{source}%"))
        )

    if risk_level is not None:
        stmt = stmt.where(ProcessedAlert.risk_level == risk_level.lower())
    if category is not None:
        stmt = stmt.where(ProcessedAlert.primary_category == category)

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return [_to_client_read(a) for a in result.scalars().all()]


@router.get("/alerts/{alert_id}", response_model=ClientAlertDetail)
async def get_client_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_subscriber_or_admin),
) -> ClientAlertDetail:
    """Return a single published alert. Returns 404 if unpublished or not found."""
    result = await db.execute(
        select(ProcessedAlert)
        .where(ProcessedAlert.id == alert_id)
        .where(ProcessedAlert.is_published.is_(True))
        .options(selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source))
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )
    return _to_client_detail(alert)
