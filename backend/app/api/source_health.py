"""Source Health — read-only observability for collection, admin only.

Three endpoints answer one question: *is each source working, and if not, why?*

Every route is a `GET` that only reads. Nothing here triggers a collection,
changes configuration, or remediates anything — a `warning` is a pointer for an
operator, not an action the system takes. In particular, an intentional external
destination exclusion is a policy outcome, not a defect, and is reported apart
from invalid content so a busy FBI source reads as *running fine, mostly not ours*
rather than as broken.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import settings
from app.database import get_db
from app.models.run_log import RunLog
from app.models.source import Source
from app.models.user import User
from app.schemas.run_log import RunLogRead
from app.schemas.source_health import (
    AttentionSource,
    SourceHealthDetail,
    SourceHealthRead,
    SystemHealthSummary,
)
from app.services.source_health_service import (
    DEFAULT_THRESHOLDS,
    ERROR,
    STATE_SEVERITY,
    WARNING,
    SourceHealthMetrics,
    classify_source_health,
    collect_source_metrics,
    get_alembic_revision,
    load_sources,
    system_totals,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["source-health"])

DEFAULT_RUN_LIMIT = 20
MAX_RUN_LIMIT = 100


def _scheduler_interval_hours() -> float:
    """The interval the scheduler actually uses.

    Deliberately *not* ``Source.polling_frequency_minutes``: that column exists but
    nothing reads it — the scheduler runs one global interval job for every source.
    Health cadence must reflect what really happens.
    """
    return float(settings.scheduler_interval_hours)


def _scheduler_running() -> bool:
    from app.scheduler.jobs import scheduler

    return bool(getattr(scheduler, "running", False))


def _to_read_model(metrics: SourceHealthMetrics, classification) -> SourceHealthRead:
    return SourceHealthRead(
        state=classification.state,
        reason_code=classification.reason_code,
        reason_detail=classification.reason_detail,
        additional_reason_codes=classification.additional_reason_codes,
        **{
            field: getattr(metrics, field)
            for field in (
                "source_id", "name", "source_type", "adapter_class", "is_active",
                "credibility_score", "last_run_at", "last_run_status",
                "last_run_duration_seconds", "last_success_at", "last_error_at",
                "last_error_message", "last_new_item_at",
                "latest_upstream_published_at", "consecutive_failed_runs",
                "consecutive_zero_fetch_runs", "consecutive_zero_new_runs",
                "runs_24h", "items_fetched_24h", "items_new_24h", "items_new_7d",
                "items_new_30d", "items_skipped_invalid_24h",
                "latest_run_items_skipped_external", "items_skipped_external_24h",
                "items_skipped_external_7d", "total_raw_items",
                "total_published_alerts",
            )
        },
    )


async def _health_records(
    session: AsyncSession, sources: list[Source], now: datetime
) -> list[SourceHealthRead]:
    """Metrics + classification for every source, in bounded queries."""
    interval = _scheduler_interval_hours()
    metrics = await collect_source_metrics(session, sources, now=now)
    return [
        _to_read_model(
            entry,
            classify_source_health(
                entry, DEFAULT_THRESHOLDS, now=now, scheduler_interval_hours=interval
            ),
        )
        for entry in metrics
    ]


def _by_severity(records: list[SourceHealthRead]) -> list[SourceHealthRead]:
    """Worst first, then source id — stable and deterministic."""
    return sorted(records, key=lambda r: (STATE_SEVERITY.get(r.state, 99), r.source_id))


# The static path is declared before the parameterised one so it is never
# captured as a source id.
@router.get("/sources/health", response_model=list[SourceHealthRead])
async def list_source_health(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> list[SourceHealthRead]:
    """Health for every source, worst state first. Read-only."""
    sources = await load_sources(db)
    if not sources:
        return []
    return _by_severity(await _health_records(db, sources, datetime.utcnow()))


@router.get("/sources/{source_id}/health", response_model=SourceHealthDetail)
async def get_source_health(
    source_id: int,
    limit: int = Query(DEFAULT_RUN_LIMIT, ge=1, le=MAX_RUN_LIMIT),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> SourceHealthDetail:
    """One source's health plus its recent runs, newest first. Read-only."""
    source = await db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    records = await _health_records(db, [source], datetime.utcnow())
    runs = (
        await db.execute(
            select(RunLog)
            .where(RunLog.source_id == source_id)
            .order_by(RunLog.run_started_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    return SourceHealthDetail(
        health=records[0],
        recent_runs=[RunLogRead.model_validate(run) for run in runs],
    )


@router.get("/system/health-summary", response_model=SystemHealthSummary)
async def get_system_health_summary(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> SystemHealthSummary:
    """Instance-wide collection health. Read-only."""
    now = datetime.utcnow()
    sources = await load_sources(db)
    records = _by_severity(await _health_records(db, sources, now))

    by_state = {state: 0 for state in STATE_SEVERITY}
    for record in records:
        by_state[record.state] = by_state.get(record.state, 0) + 1

    attention = [
        AttentionSource(
            source_id=r.source_id, name=r.name, state=r.state, reason_code=r.reason_code
        )
        for r in records
        if r.state in (ERROR, WARNING)
    ][: DEFAULT_THRESHOLDS.max_attention_sources]

    totals = await system_totals(db, now)

    return SystemHealthSummary(
        sources_total=len(records),
        by_state=by_state,
        sources_needing_attention=attention,
        scheduler_running=_scheduler_running(),
        scheduler_interval_hours=_scheduler_interval_hours(),
        alembic_revision=await get_alembic_revision(db),
        **totals,
    )
