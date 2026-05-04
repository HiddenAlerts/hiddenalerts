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
import re
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

# M3 thresholds — public endpoints derive risk_level from signal_score_total
# rather than reading the stored risk_level column. This guards against stale
# values on alerts that were processed before threshold recalibration.
_RISK_HIGH_THRESHOLD = 16
_RISK_MEDIUM_THRESHOLD = 9


def _risk_from_score(score: int | None, *, title_case: bool = False) -> str | None:
    """Derive displayed risk level from signal_score_total per current M3 thresholds.

    Thresholds:
      score >= 16 -> high
      9 <= score <= 15 -> medium
      score < 9 -> low

    Returns None when score is None — frontend treats absence as unknown.
    Used by all public endpoints; do NOT use the stored risk_level column for
    public display.
    """
    if score is None:
        return None
    if score >= _RISK_HIGH_THRESHOLD:
        return "High" if title_case else "high"
    if score >= _RISK_MEDIUM_THRESHOLD:
        return "Medium" if title_case else "medium"
    return "Low" if title_case else "low"


def _title_case_level(level: str | None) -> str | None:
    """Convert lowercase risk-level value ('high'/'medium'/'low') to title case."""
    return level.capitalize() if level else None


# Lowercase phrases that identify a prosecutor / regulator / law-enforcement
# agency or program rather than a *subject* of the alert. Agencies appear in
# almost every fraud article (FBI, DOJ, etc.) so allowing them to drive
# dedup or related-signals overlap collapses thematically distinct alerts
# together — e.g. a CSAM case and a securities-fraud case both naming "FBI".
# Match is whole-word/phrase via regex \b boundaries so substrings inside
# real names ("sec" in "securities") don't false-positive.
_AGENCY_PATTERNS: tuple[str, ...] = (
    "fbi",
    "federal bureau of investigation",
    "doj",
    "department of justice",
    "justice department",
    "criminal division",
    "antitrust division",
    "u.s. attorney",
    "us attorney",
    "attorney general",
    "sec",
    "securities and exchange commission",
    "ftc",
    "federal trade commission",
    "fincen",
    "financial crimes enforcement network",
    "ofac",
    "office of foreign assets control",
    "ic3",
    "internet crime complaint center",
    "irs",
    "irs-ci",
    "internal revenue service",
    "hhs",
    "hhs-oig",
    "office of inspector general",
    "atf",
    "drug enforcement administration",
    "dea",
    "secret service",
    "u.s. secret service",
    "cisa",
    "homeland security",
    "department of homeland security",
    "dhs",
    "u.s. postal",
    "postal inspection service",
    "u.s. postal inspection service",
    "fraud control unit",
    "task force",
    "project safe childhood",
    "operation",  # "Operation Winter SHIELD" etc.
)

_AGENCY_REGEX = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in _AGENCY_PATTERNS) + r")\b",
    flags=re.IGNORECASE,
)


def _is_agency_name(name: str) -> bool:
    """Return True if the entity name refers to a prosecutor / regulator / agency.

    Used to exclude agency mentions from primary-entity dedup
    (`_primary_entity_key`) and from entity-overlap matching (`_entity_set`),
    so two unrelated alerts that happen to both name "FBI" don't collapse
    together in /top dedup or surface as related_signals peers.
    """
    if not name or not name.strip():
        return False
    return _AGENCY_REGEX.search(name) is not None


def _entity_set(entities_json: Any) -> set[str]:
    """Extract a normalized entity-name set from entities_json.

    Excludes agency names so overlap reflects shared *subjects* (companies,
    individuals, domains), not shared prosecutors. Otherwise nearly every
    DOJ/FBI alert would overlap with every other DOJ/FBI alert and
    `related_signals` would surface thematically unrelated peers.
    """
    return {
        e.strip().lower()
        for e in _flat_entities(entities_json)
        if e and e.strip() and not _is_agency_name(e)
    }


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


def _comma_and_join(items: list[str]) -> str:
    """Join phrases as 'A', 'A and B', or 'A, B, and C' (Oxford-comma style)."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _risk_factor_phrases(alert: ProcessedAlert) -> list[str]:
    """Pick out which strong factors are driving this alert's risk level.

    Returns 0..N short reason phrases derived from the per-factor scores and
    raw AI fields. Pure function — no DB, no AI. Order is meaningful: the
    most decision-relevant factors come first so we can take the top few when
    composing a one-line risk_assessment.
    """
    phrases: list[str] = []

    if (alert.score_source_credibility or 0) >= 4:
        phrases.append("trusted source reporting")

    fi_raw = (alert.financial_impact_estimate or "").strip().lower()
    fi_meaningful = bool(fi_raw) and fi_raw not in ("unknown", "none", "n/a")
    if (alert.score_financial_impact or 0) >= 4 or fi_meaningful:
        phrases.append("notable financial impact")

    vs_raw = (alert.victim_scale_raw or "").strip().lower()
    if (alert.score_victim_scale or 0) >= 4 or vs_raw == "nationwide":
        phrases.append("broad victim scope")

    if (alert.score_cross_source or 0) >= 3:
        phrases.append("cross-source support")

    if (alert.score_trend_acceleration or 0) >= 3:
        phrases.append("rising trend signal")

    return phrases


def _risk_assessment(alert: ProcessedAlert) -> str:
    """Short, deterministic one-line explanation of risk tied to actual factors.

    Pulls strong factors via `_risk_factor_phrases` and composes a single
    sentence using the *derived* public risk level (M3 thresholds applied to
    `signal_score_total`). Falls back to the prior generic copy when no strong
    factors qualify, so a concise sentence is always returned.

    Per-factor raw values (`score_*`, `financial_impact_estimate`,
    `victim_scale_raw`) are NEVER returned to the public — only the derived
    natural-language phrases are.
    """
    risk = _risk_from_score(alert.signal_score_total) or "low"
    label = {"high": "High risk", "medium": "Medium risk", "low": "Low risk"}[risk]

    phrases = _risk_factor_phrases(alert)
    if phrases:
        # Cap at 3 to keep the sentence scannable even for fully-loaded alerts.
        return f"{label} due to {_comma_and_join(phrases[:3])}."

    # Generic fallbacks — concise, single sentence each.
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


_RELATED_SIGNALS_MIN = 2
_RELATED_SIGNALS_MAX = 4

# Top Alerts — Ken's "risk >= 60" maps to signal_score_total >= 15 on the 0-25
# scale (60% of 25). Sits intentionally below the high threshold (16) so genuinely
# strong medium-high alerts qualify.
_TOP_ALERTS_MIN_SCORE = 15
_TOP_ALERTS_LIMIT = 3
# SQL fetches this many candidates; Python applies the full multi-key sort and
# duplicate-entity suppression. Larger pool gives the dedup more room without
# adding a noticeable query cost.
_TOP_ALERTS_CANDIDATE_POOL = 30


async def _related_signals(
    db: AsyncSession,
    alert: ProcessedAlert,
    max_items: int = _RELATED_SIGNALS_MAX,
) -> list[dict] | None:
    """Find 2-4 other published alerts that are *cleanly* related to the current one.

    Cleanness rule (Ken's spec, M3 cleanup): a candidate must
      - share at least one event_id with the current alert (via event_sources), AND
      - share at least one named entity with the current alert
        (case-insensitive overlap on entities_json["names"]).

    Event-grouping alone proved too broad in live QA — co-grouped alerts could
    drift semantically. The entity-overlap requirement keeps the section to
    alerts that genuinely share a named subject (company, individual, domain).

    Quantity rule: returns None unless **at least 2** qualifying peers exist
    (Ken: "two to four items max"). A single peer is rendered as the "Related"
    section by the frontend even though it offers little value, so we omit
    the section entirely below the min.

    Returns None when the alert has no event linkage, no entities of its own to
    overlap on, or fewer than 2 qualifying published peers. Risk level on each
    related item is derived from signal_score_total (M3 thresholds), not the
    stored column.
    """
    event_ids = [
        es.event_id for es in (alert.event_sources or []) if es.event_id is not None
    ]
    if not event_ids:
        return None

    current_entities = _entity_set(alert.entities_json)
    if not current_entities:
        # No entity set on the current alert — overlap cannot be evaluated, so
        # we omit the section rather than risk surfacing semantically unrelated
        # peers that only share an event grouping.
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
    )
    result = await db.execute(stmt)

    related: list[ProcessedAlert] = []
    seen_ids: set[int] = set()
    for a in result.scalars().all():
        if a.id in seen_ids:
            continue
        seen_ids.add(a.id)
        if not (current_entities & _entity_set(a.entities_json)):
            continue  # event-grouped but semantically unrelated — skip
        related.append(a)
        if len(related) >= max_items:
            break

    if len(related) < _RELATED_SIGNALS_MIN:
        return None

    return [
        {
            "id": a.id,
            "title": a.raw_item.title if a.raw_item else None,
            "score": a.signal_score_total,
            "risk_level": _risk_from_score(a.signal_score_total, title_case=True),
        }
        for a in related
    ]


# ---------------------------------------------------------------------------
# Top Alerts ranking helpers
# ---------------------------------------------------------------------------


def _primary_entity_key(alert: ProcessedAlert) -> str:
    """Pick a stable dedup key for top-alerts.

    First non-empty *non-agency* entity name from entities_json, normalized
    lowercase + stripped. Agency names (FBI, DOJ, U.S. Attorney's Office, …)
    are skipped because they appear in nearly every fraud alert and would
    otherwise collapse unrelated alerts together. Falls back to "alert:{id}"
    when the alert has no usable subject entity, so it remains unique rather
    than silently dropped.
    """
    for name in _flat_entities(alert.entities_json):
        norm = name.strip().lower()
        if norm and not _is_agency_name(name):
            return norm
    return f"alert:{alert.id}"


def _signal_strength(alert: ProcessedAlert) -> int:
    """Number of event_sources bridges attached to this alert.

    Higher means the alert participates in a multi-source event cluster, which
    Ken counts as stronger corroboration. Requires event_sources eager-loaded.
    """
    return len(alert.event_sources or [])


def _credibility_for_ranking(alert: ProcessedAlert) -> int:
    """Source credibility (1-5) or 0 when unknown."""
    if alert.raw_item and alert.raw_item.source:
        return alert.raw_item.source.credibility_score or 0
    return 0


def _recency_for_ranking(alert: ProcessedAlert) -> float:
    """Sortable timestamp; -inf when no date is available."""
    dt = _published_date(alert)
    return dt.timestamp() if dt else float("-inf")


def _select_top_alerts(
    candidates: list[ProcessedAlert],
    *,
    limit: int = _TOP_ALERTS_LIMIT,
) -> list[ProcessedAlert]:
    """Apply the full multi-key sort + duplicate-entity suppression."""
    ranked = sorted(
        candidates,
        key=lambda a: (
            -(a.signal_score_total or 0),
            -_signal_strength(a),
            -_credibility_for_ranking(a),
            -_recency_for_ranking(a),
            a.id,
        ),
    )
    selected: list[ProcessedAlert] = []
    seen_keys: set[str] = set()
    for a in ranked:
        key = _primary_entity_key(a)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        selected.append(a)
        if len(selected) >= limit:
            break
    return selected


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
        # Derived from signal_score_total (M3 thresholds) — not the stored
        # risk_level column. Older alerts may have stale stored values.
        risk_level=_risk_from_score(alert.signal_score_total),
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
        # Title case + derived from signal_score_total (M3 thresholds).
        risk_level=_risk_from_score(alert.signal_score_total, title_case=True),
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
        # Filter on derived score buckets, matching how risk_level is displayed.
        # Unknown values match nothing (consistent with prior behaviour where an
        # invalid value matched no rows in the stored column).
        rl = risk_level.lower()
        if rl == "high":
            stmt = stmt.where(
                ProcessedAlert.signal_score_total >= _RISK_HIGH_THRESHOLD
            )
        elif rl == "medium":
            stmt = stmt.where(
                ProcessedAlert.signal_score_total >= _RISK_MEDIUM_THRESHOLD,
                ProcessedAlert.signal_score_total < _RISK_HIGH_THRESHOLD,
            )
        elif rl == "low":
            stmt = stmt.where(
                ProcessedAlert.signal_score_total < _RISK_MEDIUM_THRESHOLD
            )
        else:
            stmt = stmt.where(ProcessedAlert.id == -1)  # no rows

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
    # Counts are derived from signal_score_total (M3 thresholds), matching how
    # risk_level is displayed on list/detail. Alerts with null scores are
    # counted in `total` but fall outside every bucket — same behaviour as
    # null-risk_level rows had previously.
    count_stmt = select(
        func.count().label("total"),
        func.count(
            case(
                (ProcessedAlert.signal_score_total >= _RISK_HIGH_THRESHOLD, 1),
                else_=None,
            )
        ).label("high"),
        func.count(
            case(
                (
                    (ProcessedAlert.signal_score_total >= _RISK_MEDIUM_THRESHOLD)
                    & (ProcessedAlert.signal_score_total < _RISK_HIGH_THRESHOLD),
                    1,
                ),
                else_=None,
            )
        ).label("medium"),
        func.count(
            case(
                (ProcessedAlert.signal_score_total < _RISK_MEDIUM_THRESHOLD, 1),
                else_=None,
            )
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


@router.get("/top", response_model=PublicAlertsResponse)
async def list_top_alerts(
    db: AsyncSession = Depends(get_db),
) -> PublicAlertsResponse:
    """Curated top alerts for the dashboard hero panel.

    Public, no auth. At most 3 published alerts with signal_score_total >= 15
    (Ken's "risk >= 60" mapped to the 0-25 scale), ranked by:

      1. signal_score_total (desc)
      2. signal strength = len(event_sources) (desc)
      3. source credibility (desc)
      4. recency = source-pub > platform-pub > processed (desc)
      5. id asc — final deterministic tiebreaker

    Duplicate primary entities are suppressed: if alert A's primary entity is
    already in the selected set, alert B claiming the same entity is skipped.
    Alerts with no entities use a per-alert fallback key so they are never
    silently dropped — they're just unique against each other.

    Returns {"alerts": []} when no alerts qualify (200 OK, empty list).
    """
    stmt = (
        select(ProcessedAlert)
        .where(
            ProcessedAlert.is_published.is_(True),
            ProcessedAlert.signal_score_total >= _TOP_ALERTS_MIN_SCORE,
        )
        .options(
            selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source),
            selectinload(ProcessedAlert.event_sources),
        )
        .order_by(
            ProcessedAlert.signal_score_total.desc().nullslast(),
            ProcessedAlert.published_at.desc().nullslast(),
            ProcessedAlert.processed_at.desc(),
        )
        .limit(_TOP_ALERTS_CANDIDATE_POOL)
    )
    result = await db.execute(stmt)
    candidates = list(result.scalars().unique().all())
    selected = _select_top_alerts(candidates)
    return PublicAlertsResponse(alerts=[_to_public_read(a) for a in selected])


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
