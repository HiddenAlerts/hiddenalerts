"""REST API endpoints for processed alerts and events.

All endpoints require authentication via JWT cookie (get_current_user dependency).

Routes:
  GET  /api/v1/alerts                  — list processed alerts with filters
  GET  /api/v1/alerts/{id}             — alert detail with score breakdown
  POST /api/v1/alerts/process          — manually trigger AI pipeline (202)
  POST /api/v1/alerts/{id}/review      — submit review action
  GET  /api/v1/events                  — list grouped events
  GET  /api/v1/events/{id}             — event detail with linked alerts
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import Text, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.database import get_db, AsyncSessionLocal
from app.models.review import AlertReview
from app.models.event import Event, EventSource
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.user import User
from app.schemas.alert import (
    AlertReviewCreate,
    AlertReviewRead,
    EventDetail,
    EventRead,
    ProcessedAlertDetail,
    ProcessedAlertRead,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["alerts"])


# ---------------------------------------------------------------------------
# Helper: enrich alert with joined fields
# ---------------------------------------------------------------------------


def _alert_to_read(alert: ProcessedAlert) -> ProcessedAlertRead:
    """Map ORM ProcessedAlert to ProcessedAlertRead schema with joined fields."""
    title = None
    source_name = None
    item_url = None

    if alert.raw_item:
        title = alert.raw_item.title
        item_url = alert.raw_item.item_url
        if alert.raw_item.source:
            source_name = alert.raw_item.source.name

    relevance_score = (
        round(alert.signal_score_total / 25, 2)
        if alert.signal_score_total is not None
        else None
    )

    return ProcessedAlertRead(
        id=alert.id,
        raw_item_id=alert.raw_item_id,
        title=title,
        source_name=source_name,
        item_url=item_url,
        risk_level=alert.risk_level,
        primary_category=alert.primary_category,
        signal_score_total=alert.signal_score_total,
        relevance_score=relevance_score,
        matched_keywords=alert.matched_keywords,
        is_relevant=alert.is_relevant,
        processed_at=alert.processed_at,
    )


def _alert_to_detail(
    alert: ProcessedAlert,
    event: Event | None = None,
    review_status: str | None = None,
) -> ProcessedAlertDetail:
    """Map ORM ProcessedAlert to ProcessedAlertDetail schema."""
    base = _alert_to_read(alert)
    return ProcessedAlertDetail(
        **base.model_dump(),
        summary=alert.summary,
        secondary_category=alert.secondary_category,
        entities_json=alert.entities_json,
        financial_impact_estimate=alert.financial_impact_estimate,
        victim_scale_raw=alert.victim_scale_raw,
        ai_model=alert.ai_model,
        score_source_credibility=alert.score_source_credibility,
        score_financial_impact=alert.score_financial_impact,
        score_victim_scale=alert.score_victim_scale,
        score_cross_source=alert.score_cross_source,
        score_trend_acceleration=alert.score_trend_acceleration,
        event_id=event.id if event else None,
        event_title=event.title if event else None,
        review_status=review_status,
    )


# ---------------------------------------------------------------------------
# Alert endpoints
# ---------------------------------------------------------------------------


@router.get("/alerts", response_model=list[ProcessedAlertRead])
async def list_alerts(
    risk_level: str | None = Query(None, description="Filter by risk level: low, medium, high"),
    category: str | None = Query(None, description="Filter by primary_category"),
    source_id: int | None = Query(None, description="Filter by source ID"),
    source: str | None = Query(None, description="Filter by source name (partial match, case-insensitive)"),
    keyword: str | None = Query(None, description="Filter by keyword present in title or matched_keywords"),
    since: datetime | None = Query(None, alias="start_date", description="Only alerts processed after this datetime (alias: start_date)"),
    end_date: datetime | None = Query(None, description="Only alerts processed before this datetime"),
    is_relevant: bool | None = Query(None, description="Filter by relevance flag"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ProcessedAlertRead]:
    """List processed alerts with optional filtering."""
    raw_item_join_needed = source_id is not None or source is not None or keyword is not None
    stmt = (
        select(ProcessedAlert)
        .options(
            selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source)
        )
        .order_by(ProcessedAlert.processed_at.desc())
    )

    if raw_item_join_needed:
        stmt = stmt.join(RawItem, RawItem.id == ProcessedAlert.raw_item_id)

    if risk_level is not None:
        stmt = stmt.where(ProcessedAlert.risk_level == risk_level.lower())
    if category is not None:
        stmt = stmt.where(ProcessedAlert.primary_category == category)
    if since is not None:
        stmt = stmt.where(ProcessedAlert.processed_at >= since)
    if end_date is not None:
        stmt = stmt.where(ProcessedAlert.processed_at <= end_date)
    if is_relevant is not None:
        stmt = stmt.where(ProcessedAlert.is_relevant == is_relevant)
    if source_id is not None:
        stmt = stmt.where(RawItem.source_id == source_id)
    if source is not None:
        stmt = stmt.join(Source, Source.id == RawItem.source_id).where(
            Source.name.ilike(f"%{source}%")
        )
    if keyword is not None:
        # Title OR matched_keywords JSON text contains the keyword (case-insensitive)
        stmt = stmt.where(
            or_(
                RawItem.title.ilike(f"%{keyword}%"),
                ProcessedAlert.matched_keywords.cast(Text).ilike(f"%{keyword}%"),
            )
        )

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    return [_alert_to_read(a) for a in alerts]


@router.get("/alerts/{alert_id}", response_model=ProcessedAlertDetail)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ProcessedAlertDetail:
    """Get full alert detail including score breakdown, event linkage, and review status."""
    result = await db.execute(
        select(ProcessedAlert)
        .where(ProcessedAlert.id == alert_id)
        .options(
            selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source),
            selectinload(ProcessedAlert.event_sources).selectinload(EventSource.event),
            selectinload(ProcessedAlert.reviews),
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    # Get linked event (first event_source's event)
    event = None
    for es in alert.event_sources:
        if es.event:
            event = es.event
            break

    # Get latest review status
    review_status = None
    if alert.reviews:
        latest_review = max(alert.reviews, key=lambda r: r.reviewed_at)
        review_status = latest_review.review_status

    return _alert_to_detail(alert, event=event, review_status=review_status)


@router.post("/alerts/process", status_code=status.HTTP_202_ACCEPTED)
async def trigger_processing(
    background_tasks: BackgroundTasks,
    _user: User = Depends(get_current_user),
) -> dict:
    """Manually trigger the AI processing pipeline for unprocessed items.

    Returns 409 if a pipeline run is already in progress.
    """
    from app.pipeline.alert_pipeline import is_processing

    if is_processing():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Processing already in progress",
        )

    background_tasks.add_task(_run_pipeline_in_background)
    return {"message": "Alert processing started", "status": "accepted"}


async def _run_pipeline_in_background() -> None:
    """Run the alert pipeline in a background task with its own DB session."""
    from app.pipeline.alert_pipeline import process_unprocessed_items

    async with AsyncSessionLocal() as session:
        try:
            stats = await process_unprocessed_items(session)
            log.info(
                f"Background pipeline complete: processed={stats.items_processed}, "
                f"failed={stats.items_failed}"
            )
        except Exception as exc:
            log.error(f"Background pipeline error: {exc}", exc_info=True)


@router.post("/alerts/{alert_id}/review", response_model=AlertReviewRead)
async def submit_review(
    alert_id: int,
    payload: AlertReviewCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AlertReviewRead:
    """Submit a review action for an alert (approve, mark false positive, or edit)."""
    valid_statuses = {"approved", "false_positive", "edited"}
    if payload.review_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"review_status must be one of: {', '.join(sorted(valid_statuses))}",
        )

    # Verify alert exists
    alert_result = await db.execute(
        select(ProcessedAlert).where(ProcessedAlert.id == alert_id)
    )
    alert = alert_result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    review = AlertReview(
        alert_id=alert_id,
        user_id=user.id,
        review_status=payload.review_status,
        edited_summary=payload.edited_summary,
        adjusted_risk_level=payload.adjusted_risk_level,
    )
    db.add(review)

    # If edited summary provided, update the alert's summary
    if payload.edited_summary:
        alert.summary = payload.edited_summary

    # If risk level override provided, update the alert
    if payload.adjusted_risk_level:
        alert.risk_level = payload.adjusted_risk_level.lower()

    await db.commit()
    await db.refresh(review)
    return AlertReviewRead.model_validate(review)


# ---------------------------------------------------------------------------
# Event endpoints
# ---------------------------------------------------------------------------


@router.get("/events", response_model=list[EventRead])
async def list_events(
    category: str | None = Query(None),
    risk_level: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[EventRead]:
    """List grouped events with optional filtering."""
    stmt = (
        select(Event)
        .options(selectinload(Event.event_sources))
        .order_by(Event.last_updated_at.desc())
    )

    if category:
        stmt = stmt.where(Event.category == category)
    if risk_level:
        stmt = stmt.where(Event.risk_level == risk_level.lower())

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    events = result.scalars().all()

    return [
        EventRead(
            id=e.id,
            title=e.title,
            risk_level=e.risk_level,
            category=e.category,
            primary_entity=e.primary_entity,
            first_detected_at=e.first_detected_at,
            last_updated_at=e.last_updated_at,
            source_count=len(e.event_sources),
        )
        for e in events
    ]


@router.get("/events/{event_id}", response_model=EventDetail)
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> EventDetail:
    """Get full event detail including all linked alerts."""
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.event_sources).selectinload(EventSource.alert).selectinload(
                ProcessedAlert.raw_item
            ).selectinload(RawItem.source)
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    linked_alerts = [
        _alert_to_read(es.alert)
        for es in event.event_sources
        if es.alert is not None
    ]

    return EventDetail(
        id=event.id,
        title=event.title,
        risk_level=event.risk_level,
        category=event.category,
        primary_entity=event.primary_entity,
        first_detected_at=event.first_detected_at,
        last_updated_at=event.last_updated_at,
        source_count=len(event.event_sources),
        alerts=linked_alerts,
    )
