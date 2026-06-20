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
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import Text, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api._risk import risk_level_from_score, risk_score_100
from app.auth import get_current_user
from app.database import get_db, AsyncSessionLocal
from app.models.review import AlertReview
from app.models.event import Event, EventSource
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.user import User
from app.pipeline.publishing.constants import (
    DECISION_SOURCES,
    PENDING_REVIEW_REASONS,
    PUBLISH_DECISIONS,
    RISK_BANDS,
    DecisionSource,
    PendingReviewReason,
    PublishDecisionValue,
)
from app.pipeline.publishing.publishing_policy import DEFAULT_V1_POLICY
from app.pipeline.publishing.risk_bands import compute_risk_band
from app.schemas.alert import (
    AlertReviewCreate,
    AlertReviewRead,
    EventDetail,
    EventRead,
    ProcessedAlertDetail,
    ProcessedAlertRead,
    RiskExplanation,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["alerts"])


# ---------------------------------------------------------------------------
# Shared publish helper — used by both API review and dashboard review flows
# ---------------------------------------------------------------------------


def publish_alert(alert: ProcessedAlert, user_id: int) -> None:
    """Mark an alert as published. Idempotent — safe to call if already published.

    Sets is_published=True, records published_at (if not already set), and
    records the user who triggered publication. Caller must commit the session.
    """
    alert.is_published = True
    if alert.published_at is None:
        alert.published_at = datetime.now(timezone.utc)
    if alert.published_by_user_id is None:
        alert.published_by_user_id = user_id


# ---------------------------------------------------------------------------
# Manual review → V1 publication-state reconciliation (Slice 7A)
# ---------------------------------------------------------------------------


def _risk_band_for_alert(alert: ProcessedAlert) -> str:
    """Risk band derived from the alert's stored internal score (read-only)."""
    return compute_risk_band(alert.signal_score_total).value


def apply_manual_approval_state(
    alert: ProcessedAlert, user_id: int, *, now: datetime | None = None
) -> None:
    """Publish an alert via manual admin approval and reconcile its V1 state.

    Distinguished from policy auto-publishing by ``publication_state_source =
    "manual_admin"`` and ``published_by_rule = False`` (we deliberately reuse the
    existing ``auto_publish`` action rather than add a new enum value this slice).

    Idempotent: preserves an existing ``published_at`` / ``published_by_user_id``
    so re-approving an already-published alert just refreshes (reconciles) the V1
    metadata. Caller must commit.
    """
    now = now or datetime.now(timezone.utc)
    alert.is_published = True
    if alert.published_at is None:
        alert.published_at = now
    if alert.published_by_user_id is None:
        alert.published_by_user_id = user_id
    alert.published_by_rule = False
    alert.is_excluded = False
    alert.excluded_reason = None
    alert.is_manual_hold = False
    alert.risk_band = _risk_band_for_alert(alert)
    alert.publish_decision = PublishDecisionValue.AUTO_PUBLISH.value
    alert.publish_decision_reason = "manual_admin_approved"
    alert.pending_review_reason = None
    alert.publishing_policy_version = DEFAULT_V1_POLICY.version
    alert.publication_state_source = DecisionSource.MANUAL_ADMIN.value
    alert.publication_state_updated_at = now


def apply_manual_false_positive_state(
    alert: ProcessedAlert, *, now: datetime | None = None
) -> None:
    """Mark an alert as a manual false positive: exclude + unpublish.

    A false positive must not remain visible in public/subscriber feeds, so an
    already-published alert is unpublished (intentional safety correction). The
    row, review history, and score fields are preserved. Caller must commit.
    """
    now = now or datetime.now(timezone.utc)
    alert.is_published = False
    alert.published_at = None
    alert.published_by_user_id = None  # clear stale publisher — no longer published
    alert.published_by_rule = False
    alert.publish_decision = PublishDecisionValue.EXCLUDE.value
    alert.publish_decision_reason = "manual_false_positive"
    alert.pending_review_reason = PendingReviewReason.MANUAL_REJECTED.value
    alert.is_excluded = True
    alert.excluded_reason = "manual_false_positive"
    alert.is_manual_hold = False
    alert.risk_band = _risk_band_for_alert(alert)
    alert.publishing_policy_version = DEFAULT_V1_POLICY.version
    alert.publication_state_source = DecisionSource.MANUAL_ADMIN.value
    alert.publication_state_updated_at = now


# ---------------------------------------------------------------------------
# Helper: enrich alert with joined fields
# ---------------------------------------------------------------------------


# Internal-score equivalents of Ken's M3 final 0–100 bands
# (>=70 high, 40-69 medium, 1-39 low). Centralized in app.api._risk too, but
# duplicated here for filter expressions that operate on the raw column.
_RISK_HIGH_INTERNAL = 18
_RISK_MEDIUM_INTERNAL = 10


def _score_filter_for_risk_level(risk_level: str):
    """Return a SQLAlchemy filter clause matching alerts whose *displayed*
    risk level (derived from signal_score_total via M3 final bands) equals
    the requested value. Falls back to a no-op for unknown values so the
    endpoint still returns rather than 422-ing.
    """
    norm = risk_level.lower().strip()
    if norm == "high":
        return ProcessedAlert.signal_score_total >= _RISK_HIGH_INTERNAL
    if norm == "medium":
        return (ProcessedAlert.signal_score_total >= _RISK_MEDIUM_INTERNAL) & (
            ProcessedAlert.signal_score_total < _RISK_HIGH_INTERNAL
        )
    if norm == "low":
        return ProcessedAlert.signal_score_total < _RISK_MEDIUM_INTERNAL
    # Unknown filter value — fall back to stored column to keep behaviour
    # explicit instead of silently returning everything.
    return ProcessedAlert.risk_level == norm


def _alert_to_read(alert: ProcessedAlert) -> ProcessedAlertRead:
    """Map ORM ProcessedAlert to ProcessedAlertRead schema with joined fields."""
    title = None
    source_name = None
    item_url = None
    source_published_at = None

    if alert.raw_item:
        title = alert.raw_item.title
        item_url = alert.raw_item.item_url
        source_published_at = alert.raw_item.published_at
        if alert.raw_item.source:
            source_name = alert.raw_item.source.name

    # `relevance_score` stays computed from the internal 5–25 sum so legacy
    # consumers see the same 0.0–1.0 ratio they always have.
    relevance_score = (
        round(alert.signal_score_total / 25, 2)
        if alert.signal_score_total is not None
        else None
    )

    # Re-derive risk_level from the internal score so admin views always
    # reflect the M3 final 0–100 bands, even for alerts processed before the
    # band shift (stored risk_level may be stale). Falls back to stored value
    # when score is missing entirely.
    derived_risk_level = (
        risk_level_from_score(alert.signal_score_total) or alert.risk_level
    )

    return ProcessedAlertRead(
        id=alert.id,
        raw_item_id=alert.raw_item_id,
        title=title,
        source_name=source_name,
        item_url=item_url,
        risk_level=derived_risk_level,
        primary_category=alert.primary_category,
        # `signal_score_total` is exposed on the 0–100 frontend scale here.
        # The DB column remains the internal 5–25 sum.
        signal_score_total=risk_score_100(alert.signal_score_total),
        relevance_score=relevance_score,
        matched_keywords=alert.matched_keywords,
        is_relevant=alert.is_relevant,
        processed_at=alert.processed_at,
        source_published_at=source_published_at,
        is_published=alert.is_published,
        published_at=alert.published_at,
        # V1 publication state (Slice 6) — straight off the ORM columns so review
        # queues can filter/inspect without opening the detail page.
        risk_band=alert.risk_band,
        publish_decision=alert.publish_decision,
        publish_decision_reason=alert.publish_decision_reason,
        pending_review_reason=alert.pending_review_reason,
        is_excluded=alert.is_excluded,
        excluded_reason=alert.excluded_reason,
        is_manual_hold=alert.is_manual_hold,
        published_by_rule=alert.published_by_rule,
        publishing_policy_version=alert.publishing_policy_version,
        publication_state_source=alert.publication_state_source,
        publication_state_updated_at=alert.publication_state_updated_at,
    )


def _build_risk_explanation(alert: ProcessedAlert) -> RiskExplanation:
    """Deterministic risk/decision explanation from already-stored fields.

    Pure read-only: `score_total` is the raw internal 5–25 sum and `score_100`
    its 0–100 normalization (reusing the shared helper). `risk_band` falls back
    to a computed band when the column is null — this fallback is response-only
    and is NEVER written back to the DB.
    """
    source_name = None
    source_credibility = None
    if alert.raw_item and alert.raw_item.source:
        source_name = alert.raw_item.source.name
        source_credibility = alert.raw_item.source.credibility_score

    band = alert.risk_band or compute_risk_band(alert.signal_score_total).value

    return RiskExplanation(
        score_total=alert.signal_score_total,  # raw internal 5–25
        score_100=risk_score_100(alert.signal_score_total),
        risk_level=risk_level_from_score(alert.signal_score_total),
        risk_band=band,
        factors={
            "source_credibility": alert.score_source_credibility,
            "financial_impact": alert.score_financial_impact,
            "victim_scale": alert.score_victim_scale,
            "cross_source": alert.score_cross_source,
            "trend_acceleration": alert.score_trend_acceleration,
        },
        publication_decision=alert.publish_decision,
        publication_reason=alert.publish_decision_reason,
        pending_review_reason=alert.pending_review_reason,
        source=source_name,
        source_credibility=source_credibility,
    )


def _alert_to_detail(
    alert: ProcessedAlert,
    event: Event | None = None,
    review_status: str | None = None,
) -> ProcessedAlertDetail:
    """Map ORM ProcessedAlert to ProcessedAlertDetail schema."""
    base = _alert_to_read(alert)
    # NOTE: the flat `signal_score_total` on the detail stays normalized to 0–100
    # (unchanged behavior). `risk_explanation.score_total` deliberately carries
    # the RAW internal 5–25 value for transparency — that difference is
    # intentional, not a duplicate-field bug.
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
        # V1 internal detail extras (Slice 6): raw publishing user id (no join)
        # + structured risk explanation.
        published_by_user_id=alert.published_by_user_id,
        risk_explanation=_build_risk_explanation(alert),
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
    is_published: bool | None = Query(None, description="Filter by publication state (admin convenience)"),
    # V1 publication-state filters (Slice 6) — additive review-queue filters.
    publish_decision: str | None = Query(None, description="V1: auto_publish|review|exclude|hold"),
    pending_review_reason: str | None = Query(None, description="V1 pending-review reason"),
    risk_band: str | None = Query(None, description="V1 risk band: critical|high|medium|below_60"),
    is_excluded: bool | None = Query(None, description="V1: filter excluded alerts"),
    is_manual_hold: bool | None = Query(None, description="V1: filter manually-held alerts"),
    published_by_rule: bool | None = Query(None, description="V1: filter auto-policy-published alerts"),
    publication_state_source: str | None = Query(
        None, description="V1 decision source: auto_policy|manual_admin|candidate_backfill|system_migration"
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ProcessedAlertRead]:
    """List processed alerts with optional filtering."""
    # Validate enum-like V1 filters against the canonical vocabularies (422 on a
    # bad value rather than silently returning an empty/wrong result). Reuses the
    # exported frozensets — no hardcoded value lists here.
    for value, allowed, field in (
        (publish_decision, PUBLISH_DECISIONS, "publish_decision"),
        (pending_review_reason, PENDING_REVIEW_REASONS, "pending_review_reason"),
        (risk_band, RISK_BANDS, "risk_band"),
        (publication_state_source, DECISION_SOURCES, "publication_state_source"),
    ):
        if value is not None and value not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid {field}: {value!r}. Allowed: {sorted(allowed)}",
            )

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
        stmt = stmt.where(_score_filter_for_risk_level(risk_level))
    if category is not None:
        stmt = stmt.where(ProcessedAlert.primary_category == category)
    if since is not None:
        stmt = stmt.where(ProcessedAlert.processed_at >= since)
    if end_date is not None:
        stmt = stmt.where(ProcessedAlert.processed_at <= end_date)
    if is_relevant is not None:
        stmt = stmt.where(ProcessedAlert.is_relevant == is_relevant)
    if is_published is not None:
        stmt = stmt.where(ProcessedAlert.is_published == is_published)
    if publish_decision is not None:
        stmt = stmt.where(ProcessedAlert.publish_decision == publish_decision)
    if pending_review_reason is not None:
        stmt = stmt.where(ProcessedAlert.pending_review_reason == pending_review_reason)
    if risk_band is not None:
        stmt = stmt.where(ProcessedAlert.risk_band == risk_band)
    if is_excluded is not None:
        stmt = stmt.where(ProcessedAlert.is_excluded == is_excluded)
    if is_manual_hold is not None:
        stmt = stmt.where(ProcessedAlert.is_manual_hold == is_manual_hold)
    if published_by_rule is not None:
        stmt = stmt.where(ProcessedAlert.published_by_rule == published_by_rule)
    if publication_state_source is not None:
        stmt = stmt.where(ProcessedAlert.publication_state_source == publication_state_source)
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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

    # Content edits apply regardless of decision (existing behavior preserved):
    # editing summary/risk_level is NOT a publish/reject decision and must not
    # touch V1 publication state.
    if payload.edited_summary:
        alert.summary = payload.edited_summary
    if payload.adjusted_risk_level:
        alert.risk_level = payload.adjusted_risk_level.lower()

    # Slice 7A — reconcile the manual decision into V1 publication state.
    if payload.review_status == "approved":
        # Irrelevant alerts are never published (existing behavior) and do NOT
        # receive an auto_publish decision state.
        if alert.is_relevant:
            apply_manual_approval_state(alert, user_id=user.id)
    elif payload.review_status == "false_positive":
        # Exclude + unpublish (safety): a false positive must not stay visible.
        apply_manual_false_positive_state(alert)
    # "edited" → content already updated above; V1 publication state untouched.

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
