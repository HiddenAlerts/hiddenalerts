"""Public search API — GET /api/search/alerts.

No authentication required. Search is hard-filtered to published alerts only;
unpublished alerts are never exposed regardless of how the query matches.

Matching:
  - Case-insensitive ILIKE %q% on RawItem.title, ProcessedAlert.summary,
    Source.name, and cast(ProcessedAlert.entities_json AS TEXT). The JSON-text
    match is only a SQL candidate filter — the response's `matched_entity` is
    sourced from the parsed entity list, never from the raw JSON text.
  - Multi-word `q` is treated as a literal phrase (no tokenization, no fuzzy /
    typo / semantic search).

Grouping (entity-first, mixed):
  - Alerts whose parsed entities contain `q` produce one `group_type="entity"`
    group per distinct matched entity (lowercased + trimmed). An alert tagged
    with multiple matching entities appears in each relevant entity group.
  - Alerts that match `q` only via title / summary / source name (no parsed
    entity match) collect into a single `group_type="keyword"` fallback group
    keyed by the normalized query — they are NOT dropped.
  - When no candidate has a parsed entity match, only the keyword fallback
    group is returned.
  - `total_alerts` counts unique matching alerts. Because an alert with
    multiple matched entities appears in multiple entity groups, the sum of
    `alertCount` across groups may exceed `total_alerts`. The top-level
    `alerts` list is unique-by-id.

Ranking (groups and full alerts list):
  1. signal_score (0–100, normalized) DESC
  2. effective recency DESC (= raw_item.published_at ?? published_at ?? processed_at)
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api._risk import risk_score_100
from app.api.public_alerts import _flat_entities, _to_public_read
from app.database import get_db
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.schemas.search import SearchAlertItem, SearchGroup, SearchResponse

router = APIRouter(prefix="/api/search", tags=["public"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LIMIT_DEFAULT = 50
_LIMIT_MAX = 100
_GROUP_LIMIT_DEFAULT = 20
_GROUP_LIMIT_MAX = 50
_MIN_SCORE_DEFAULT = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _effective_recency(alert: ProcessedAlert) -> datetime | None:
    """Best ranking timestamp: source-pub > platform-pub > processed."""
    if alert.raw_item and alert.raw_item.published_at:
        return alert.raw_item.published_at
    if alert.published_at:
        return alert.published_at
    return alert.processed_at


def _recency_sort_value(item: SearchAlertItem) -> float:
    """Sortable timestamp for a mapped item; missing dates fall to the bottom."""
    dt = item.source_published_at or item.published_at
    return dt.timestamp() if dt else float("-inf")


def _alert_sort_key(item: SearchAlertItem) -> tuple[int, float]:
    """Primary ranking: signal_score DESC, then recency DESC."""
    return (-(item.signal_score or 0), -_recency_sort_value(item))


def _matched_entities(entities_json: Any, q_lower: str) -> list[str]:
    """All parsed entities (deduped, normalized lowercase) containing `q_lower`.

    Sourced from `_flat_entities()` — never from the raw JSON text. Order is
    insertion order from `entities_json["names"]` so the first match is stable.
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in _flat_entities(entities_json):
        norm = str(raw).strip().lower()
        if norm and q_lower in norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _internal_threshold(min_score: int) -> int:
    """Convert public 0–100 min_score to the internal 5–25 threshold.

    Because `signal_score_100 = signal_score_total * 4` exactly for integer s,
    the equivalent internal threshold is `ceil(min_score / 4)`.
    """
    return math.ceil(min_score / 4)


def _validate_q(q: str) -> str:
    """Trim `q` and reject empty / whitespace-only with 422."""
    norm = (q or "").strip()
    if not norm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Query parameter 'q' must not be empty.",
        )
    return norm


def _clamp(value: int, *, low: int, high: int) -> int:
    return max(low, min(high, value))


def _to_search_item(
    alert: ProcessedAlert, *, matched_entity: str | None
) -> SearchAlertItem:
    """Reuse public-feed mapper, then extend with `matched_entity`."""
    public = _to_public_read(alert)
    return SearchAlertItem(
        id=public.id,
        title=public.title,
        summary=public.summary,
        category=public.category,
        risk_level=public.risk_level,
        signal_score=public.signal_score,
        source_name=public.source_name,
        source_url=public.source_url,
        source_published_at=public.source_published_at,
        published_at=public.published_at,
        matched_entity=matched_entity,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


async def search_alerts_impl(
    db: AsyncSession,
    q: str,
    min_score: int,
    limit: int,
    group_limit: int,
) -> SearchResponse:
    """Shared implementation for published-alert search.

    Used by public ``GET /api/search/alerts`` and subscriber
    ``GET /api/v1/subscriber/search/alerts`` so they behave identically.
    Frontend-safe response shape — never exposes review history, score factor
    breakdowns, raw entities_json, ai_model, or other admin metadata.
    """
    norm_q = _validate_q(q)
    q_lower = norm_q.lower()
    pattern = f"%{norm_q}%"

    min_score_eff = _clamp(min_score, low=0, high=100)
    limit_eff = _clamp(limit, low=1, high=_LIMIT_MAX)
    group_limit_eff = _clamp(group_limit, low=1, high=_GROUP_LIMIT_MAX)

    # Candidate query — ILIKE across the four fields, published-only.
    stmt = (
        select(ProcessedAlert)
        .join(RawItem, RawItem.id == ProcessedAlert.raw_item_id)
        .outerjoin(Source, Source.id == RawItem.source_id)
        .where(ProcessedAlert.is_published.is_(True))
        .where(
            or_(
                RawItem.title.ilike(pattern),
                ProcessedAlert.summary.ilike(pattern),
                Source.name.ilike(pattern),
                cast(ProcessedAlert.entities_json, String).ilike(pattern),
            )
        )
        .options(
            selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source)
        )
    )

    if min_score_eff > 0:
        stmt = stmt.where(
            ProcessedAlert.signal_score_total >= _internal_threshold(min_score_eff)
        )

    result = await db.execute(stmt)
    candidates = list(result.scalars().unique().all())

    # Defensive post-filter — keep min_score honest if a future refactor ever
    # changes the query path.
    if min_score_eff > 0:
        candidates = [
            a
            for a in candidates
            if (risk_score_100(a.signal_score_total) or 0) >= min_score_eff
        ]

    # Per-alert payload + matched-entity table.
    items_by_id: dict[int, SearchAlertItem] = {}
    matched_by_id: dict[int, list[str]] = {}
    for a in candidates:
        matches = _matched_entities(a.entities_json, q_lower)
        primary_match = matches[0] if matches else None
        items_by_id[a.id] = _to_search_item(a, matched_entity=primary_match)
        matched_by_id[a.id] = matches

    sorted_items = sorted(items_by_id.values(), key=_alert_sort_key)

    candidates_by_id = {a.id: a for a in candidates}

    # Bucket alerts: entity-matched go to per-entity groups, the rest collect
    # into a keyword fallback group.
    entity_to_ids: dict[str, list[int]] = {}
    unmatched_ids: list[int] = []
    for alert_id, ents in matched_by_id.items():
        if ents:
            for ent in ents:
                entity_to_ids.setdefault(ent, []).append(alert_id)
        else:
            unmatched_ids.append(alert_id)

    groups: list[SearchGroup] = []

    # Entity groups — one per distinct matched entity.
    entity_groups: list[SearchGroup] = []
    for ent, alert_ids in entity_to_ids.items():
        id_set = set(alert_ids)
        group_alerts = sorted(
            (items_by_id[aid] for aid in id_set),
            key=_alert_sort_key,
        )
        sources = sorted({a.source_name for a in group_alerts if a.source_name})
        recencies = [
            _effective_recency(candidates_by_id[aid]) for aid in id_set
        ]
        recencies = [r for r in recencies if r is not None]
        earliest = min(recencies) if recencies else None
        latest = max(recencies) if recencies else None

        # Each alert in this group reflects this group's entity. The same
        # alert in another group reflects that group's entity.
        display_alerts = [
            a.model_copy(update={"matched_entity": ent})
            for a in group_alerts[:group_limit_eff]
        ]

        entity_groups.append(
            SearchGroup(
                entity=ent,
                group_type="entity",
                alert_count=len(group_alerts),
                source_count=len(sources),
                sources=sources,
                earliest=earliest,
                latest=latest,
                alerts=display_alerts,
            )
        )

    entity_groups.sort(
        key=lambda g: (
            -g.alert_count,
            -(g.alerts[0].signal_score or 0) if g.alerts else 0,
        )
    )
    groups.extend(entity_groups)

    # Keyword fallback group — captures alerts that matched on
    # title/summary/source but had no parsed entity matching `q`. Appended
    # after entity groups (entity-first ordering).
    if unmatched_ids:
        group_alerts = sorted(
            (items_by_id[aid] for aid in unmatched_ids),
            key=_alert_sort_key,
        )
        sources = sorted({a.source_name for a in group_alerts if a.source_name})
        recencies = [
            _effective_recency(candidates_by_id[aid]) for aid in unmatched_ids
        ]
        recencies = [r for r in recencies if r is not None]
        earliest = min(recencies) if recencies else None
        latest = max(recencies) if recencies else None
        display_alerts = group_alerts[:group_limit_eff]
        groups.append(
            SearchGroup(
                entity=q_lower,
                group_type="keyword",
                alert_count=len(group_alerts),
                source_count=len(sources),
                sources=sources,
                earliest=earliest,
                latest=latest,
                alerts=display_alerts,
            )
        )

    return SearchResponse(
        query=q,
        normalized_query=q_lower,
        total_alerts=len(sorted_items),
        group_count=len(groups),
        groups=groups,
        alerts=sorted_items[:limit_eff],
    )


@router.get(
    "/alerts",
    response_model=SearchResponse,
    response_model_by_alias=True,
)
async def search_alerts(
    q: str = Query(..., description="Search text (required, trimmed)."),
    min_score: int = Query(
        _MIN_SCORE_DEFAULT,
        description=(
            "Minimum normalized signal score (0–100). Default 0. Values "
            "outside 0–100 are clamped."
        ),
    ),
    limit: int = Query(
        _LIMIT_DEFAULT,
        ge=1,
        description=(
            "Cap on the full alerts list. Default 50, max 100. Values above "
            "max are clamped; values <1 are rejected."
        ),
    ),
    group_limit: int = Query(
        _GROUP_LIMIT_DEFAULT,
        ge=1,
        description=(
            "Cap on alerts inside each group. Default 20, max 50. Values "
            "above max are clamped; values <1 are rejected."
        ),
    ),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search published alerts; group by extracted entities, fallback to keyword."""
    return await search_alerts_impl(db, q, min_score, limit, group_limit)
