"""Public read-only alerts feed — M3 Slice 4 + Frontend Completion.

No authentication required on any route in this module.
All queries are hard-filtered to published alerts only (is_published = True).
Unpublished alerts are never exposed, regardless of query parameters.

Routes (all mounted at /api/alerts — no /api/v1 prefix):
  GET /api/alerts            — paginated published alert feed
  GET /api/alerts/stats      — published alert aggregate counts + category breakdown
  GET /api/alerts/{id}       — enriched single published alert detail; 404 if absent
                               or unpublished. Returns Ken's approved frontend-facing
                               schema (confidence, why_it_matters, key_intelligence,
                               risk_assessment, sources, timeline, related_signals,
                               etc.) plus backward-compatibility fields.

Intentionally separate from:
  /api/v1/alerts             (internal/admin — returns all alerts, auth required)
  /api/v1/client/alerts      (subscriber — published only, auth required)

Route ordering note:
  /stats must be declared BEFORE /{id} so FastAPI does not try to
  interpret the literal string "stats" as an integer alert ID.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.event import EventSource
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

    Used by list/stats endpoints. The detail endpoint uses _detail_stmt which
    additionally loads event_sources for related-signals derivation.
    """
    return (
        select(ProcessedAlert)
        .where(ProcessedAlert.is_published.is_(True))
        .options(
            selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source)
        )
    )


def _detail_stmt():
    """Detail-endpoint base SELECT — eager-loads event_sources alongside raw_item/source."""
    return (
        select(ProcessedAlert)
        .where(ProcessedAlert.is_published.is_(True))
        .options(
            selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source),
            selectinload(ProcessedAlert.event_sources),
        )
    )


# ---------------------------------------------------------------------------
# Pure derivation helpers (frontend-facing detail enrichment)
# ---------------------------------------------------------------------------


def _title_case_level(level: str | None) -> str | None:
    """Convert lowercase risk-level value ('high'/'medium'/'low') to title case."""
    return level.capitalize() if level else None


def _credibility_label(score: int | None) -> str | None:
    """Map numeric source credibility (1–5) to a High/Medium/Low display label."""
    if score is None:
        return None
    if score >= 5:
        return "High"
    if score >= 4:
        return "Medium"
    return "Low"


def _confidence(alert: ProcessedAlert) -> str:
    """Derive confidence from source credibility + signal score + relevance flag.

    Rules:
      - With credibility known:
          High   if credibility >= 5 AND is_relevant AND signal_score >= 16
          Medium if credibility >= 4 OR signal_score >= 9
          Low    otherwise
      - Without credibility, fall back to score-only:
          High >= 16, Medium 9..15, Low otherwise
    """
    cred = (
        alert.raw_item.source.credibility_score
        if (alert.raw_item and alert.raw_item.source)
        else None
    )
    score = alert.signal_score_total or 0
    if cred is not None:
        if cred >= 5 and alert.is_relevant and score >= 16:
            return "High"
        if cred >= 4 or score >= 9:
            return "Medium"
        return "Low"
    if score >= 16:
        return "High"
    if score >= 9:
        return "Medium"
    return "Low"


def _affected_group(victim_scale_raw: str | None) -> str | None:
    """Translate the AI-extracted victim_scale_raw enum to a human display string.

    Returns None for unknown / missing values so the field is omitted upstream.
    """
    if not victim_scale_raw:
        return None
    norm = victim_scale_raw.strip().lower()
    return {
        "single": "Single victim or limited individual impact",
        "multiple": "Multiple victims or organizations",
        "nationwide": "Broad or nationwide affected population",
    }.get(norm)


def _published_date(alert: ProcessedAlert) -> datetime | None:
    """Pick the best display date: source-pub > platform-pub > processed."""
    if alert.raw_item and alert.raw_item.published_at:
        return alert.raw_item.published_at
    if alert.published_at:
        return alert.published_at
    return alert.processed_at


def _flat_entities(entities_json: Any) -> list[str]:
    """Unwrap internal {"names": [...]} entity structure into a flat list."""
    if not isinstance(entities_json, dict):
        return []
    raw = entities_json.get("names", [])
    if not isinstance(raw, list):
        return []
    return [str(e) for e in raw if e]


def _key_intelligence(alert: ProcessedAlert) -> list[dict] | None:
    """Build Ken's key_intelligence list — structured {label, value} data points only.

    Items are added only when their underlying data is non-empty so the frontend
    never has to filter blanks. Returns None when no items qualify.
    """
    items: list[dict] = []

    fraud_type = alert.secondary_category or alert.primary_category
    if fraud_type:
        items.append({"label": "Fraud Type", "value": fraud_type})

    fi = alert.financial_impact_estimate
    if fi and fi.strip().lower() not in ("", "unknown", "none"):
        items.append({"label": "Financial Impact", "value": fi})

    ag = _affected_group(alert.victim_scale_raw)
    if ag:
        items.append({"label": "Affected Group", "value": ag})

    cred = (
        alert.raw_item.source.credibility_score
        if (alert.raw_item and alert.raw_item.source)
        else None
    )
    cred_label = _credibility_label(cred)
    if cred_label:
        items.append({"label": "Source Credibility", "value": cred_label})

    ents = _flat_entities(alert.entities_json)
    if ents:
        items.append({"label": "Named Entities", "value": ", ".join(ents[:5])})

    if alert.matched_keywords:
        kw = ", ".join(str(k) for k in alert.matched_keywords[:5] if k)
        if kw:
            items.append({"label": "Signals", "value": kw})

    return items or None


def _why_it_matters(alert: ProcessedAlert) -> list[str] | None:
    """Build 1–3 short, deterministic bullets that justify why the alert matters.

    Uses only existing structured data — no AI calls. Returns None when no
    bullets qualify.
    """
    bullets: list[str] = []

    cred = (
        alert.raw_item.source.credibility_score
        if (alert.raw_item and alert.raw_item.source)
        else None
    )
    if cred is not None and cred >= 4:
        bullets.append("Reported by a trusted source.")

    fi = alert.financial_impact_estimate
    if fi and fi.strip().lower() not in ("", "unknown", "none"):
        bullets.append(f"Financial impact reported as {fi}.")

    if alert.victim_scale_raw:
        bullets.append(f"Victim scope indicated as {alert.victim_scale_raw.lower()}.")

    if alert.primary_category:
        bullets.append(f"Classified as {alert.primary_category}.")

    if (alert.signal_score_total or 0) >= 13:
        bullets.append("Elevated score indicates stronger fraud signal.")

    return bullets[:3] or None


def _risk_assessment(alert: ProcessedAlert) -> str:
    """Short one-to-two-line explanation tied to risk_level. Deterministic — no AI."""
    risk = (alert.risk_level or "low").lower()
    if risk == "high":
        return (
            "High risk based on credible source reporting and strong supporting "
            "fraud signals indicating broad or significant impact."
        )
    if risk == "medium":
        return (
            "Medium risk based on credible source reporting and confirmed fraud "
            "indicators, with limited evidence of large-scale impact."
        )
    return (
        "Low risk because available indicators suggest limited scale or "
        "incomplete supporting signals."
    )


def _timeline(alert: ProcessedAlert) -> list[dict] | None:
    """Build the optional timeline. Returns None when no timestamps qualify.

    Includes:
      - source publication timestamp (raw_item.published_at) if available
      - platform publication timestamp (alert.published_at) if available
    Order: source-pub first, platform-pub second. processed_at is intentionally
    excluded for MVP to keep the timeline scannable.
    """
    items: list[dict] = []
    if alert.raw_item and alert.raw_item.published_at:
        items.append(
            {
                "date": alert.raw_item.published_at.isoformat(),
                "event": "Source published the alert",
            }
        )
    if alert.published_at:
        items.append(
            {
                "date": alert.published_at.isoformat(),
                "event": "Alert published to dashboard",
            }
        )
    return items or None


def _sources_list(alert: ProcessedAlert) -> list[dict] | None:
    """Build the sources array (one entry — the current source) for MVP."""
    if not (alert.raw_item and alert.raw_item.source):
        return None
    return [
        {
            "name": alert.raw_item.source.name,
            "url": alert.raw_item.item_url,
        }
    ]


async def _related_signals(
    db: AsyncSession,
    alert: ProcessedAlert,
    max_items: int = 4,
) -> list[dict] | None:
    """Find up to `max_items` other published alerts linked to the same event(s).

    Linkage is via the event_sources bridge table (events ↔ processed_alerts).
    Returns None when the alert has no event linkage or no published peers.
    """
    event_ids = [
        es.event_id for es in (alert.event_sources or []) if es.event_id is not None
    ]
    if not event_ids:
        return None

    stmt = (
        select(ProcessedAlert)
        .join(EventSource, EventSource.alert_id == ProcessedAlert.id)
        .where(
            EventSource.event_id.in_(event_ids),
            ProcessedAlert.id != alert.id,
            ProcessedAlert.is_published.is_(True),
        )
        .options(selectinload(ProcessedAlert.raw_item))
        .order_by(ProcessedAlert.published_at.desc().nullslast())
        .limit(max_items)
    )
    result = await db.execute(stmt)
    related = []
    seen_ids: set[int] = set()
    for a in result.scalars().all():
        if a.id in seen_ids:
            continue
        seen_ids.add(a.id)
        related.append(a)
        if len(related) >= max_items:
            break

    if not related:
        return None

    return [
        {
            "id": a.id,
            "title": a.raw_item.title if a.raw_item else None,
            "score": a.signal_score_total,
            "risk_level": _title_case_level(a.risk_level),
        }
        for a in related
    ]


# ---------------------------------------------------------------------------
# ORM → schema mappers
# ---------------------------------------------------------------------------


def _to_public_read(alert: ProcessedAlert) -> PublicAlertRead:
    """Map ORM alert to the flat public list schema."""
    title = source_name = source_url = None
    source_published_at = None
    if alert.raw_item:
        title = alert.raw_item.title
        source_url = alert.raw_item.item_url
        source_published_at = alert.raw_item.published_at
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
        source_published_at=source_published_at,
        published_at=alert.published_at,
    )


async def _to_public_detail(
    db: AsyncSession, alert: ProcessedAlert
) -> PublicAlertDetail:
    """Map ORM alert to Ken's approved enriched public detail schema.

    Async because related_signals requires a DB lookup. All other helpers
    are synchronous and operate on already-loaded relationships.
    """
    title = source_name = source_url = None
    source_published_at = None
    if alert.raw_item:
        title = alert.raw_item.title
        source_url = alert.raw_item.item_url
        source_published_at = alert.raw_item.published_at
        if alert.raw_item.source:
            source_name = alert.raw_item.source.name

    return PublicAlertDetail(
        # Ken's primary fields
        id=alert.id,
        title=title,
        score=alert.signal_score_total,
        risk_level=_title_case_level(alert.risk_level),
        confidence=_confidence(alert),
        summary=alert.summary,
        why_it_matters=_why_it_matters(alert),
        key_intelligence=_key_intelligence(alert),
        risk_assessment=_risk_assessment(alert),
        sources=_sources_list(alert),
        published_date=_published_date(alert),
        category=alert.primary_category,
        subcategory=alert.secondary_category,
        affected_group=_affected_group(alert.victim_scale_raw),
        timeline=_timeline(alert),
        related_signals=await _related_signals(db, alert),
        # Backward-compatibility additive fields
        signal_score=alert.signal_score_total,
        secondary_category=alert.secondary_category,
        source_name=source_name,
        source_url=source_url,
        source_published_at=source_published_at,
        published_at=alert.published_at,
        processed_at=alert.processed_at,
        entities=_flat_entities(alert.entities_json),
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
    """
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


@router.get(
    "/{alert_id}",
    response_model=PublicAlertDetail,
    response_model_exclude_none=True,
)
async def get_public_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
) -> PublicAlertDetail:
    """Return Ken's enriched public alert detail.

    No authentication required.

    - Returns 200 + enriched detail schema if the alert exists and is published.
    - Returns 404 if the alert does not exist OR is not published.
      (Unpublished alerts must not be distinguishable from non-existent ones.)

    response_model_exclude_none=True ensures optional sections (timeline,
    related_signals, why_it_matters, key_intelligence, affected_group, etc.)
    are omitted from the JSON when their underlying data is empty.
    """
    result = await db.execute(
        _detail_stmt().where(ProcessedAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )
    return await _to_public_detail(db, alert)
