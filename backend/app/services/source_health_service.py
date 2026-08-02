"""Read-only source health: derive metrics, then classify them.

Two halves, deliberately separable. :func:`classify_source_health` is pure — it
takes metrics, thresholds and a clock and returns a verdict, with no database and
no I/O — so every rule is testable at a frozen instant. Everything above it is
bounded SQL aggregation.

The service is **observational only**. It never collects, never mutates, and holds
no knowledge of any particular source: no source name, id or adapter class appears
in a rule. A source is judged on what its runs did, which is what makes "valid but
empty upstream" a warning for any source rather than a special case for one.

Two distinctions the classification exists to preserve:

* a **collector failure** is not an **empty upstream** — the first is an error, the
  second a warning;
* an **intentional external exclusion** is not **invalid content** — content that
  another source owns was never ours to collect, so it never counts against health.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source

log = logging.getLogger(__name__)

# --- Health states ---------------------------------------------------------
HEALTHY = "healthy"
WARNING = "warning"
ERROR = "error"
DISABLED = "disabled"

#: Worst first. Drives the list endpoint's ordering and the attention list.
STATE_SEVERITY = {ERROR: 0, WARNING: 1, DISABLED: 2, HEALTHY: 3}

# --- Reason codes ----------------------------------------------------------
SOURCE_DISABLED = "source_disabled"
REPEATED_FAILURES = "repeated_failures"
NO_SUCCESSFUL_RUN = "no_successful_run"
SCHEDULER_OVERDUE = "scheduler_overdue"
LATEST_RUN_FAILED = "latest_run_failed"
NO_UPSTREAM_CONTENT = "no_upstream_content"
HIGH_INVALID_RATE = "high_invalid_rate"
STALE_INGESTION = "stale_ingestion"
STALE_UPSTREAM = "stale_upstream"
COLLECTION_OVERDUE = "collection_overdue"
NEVER_COLLECTED = "never_collected"
OK = "ok"

#: What each code means, for the API documentation and the detail payload.
REASON_DESCRIPTIONS = {
    SOURCE_DISABLED: "The source is switched off; no other rule is evaluated.",
    REPEATED_FAILURES: "Consecutive runs failed — the collector cannot reach or parse this source.",
    NO_SUCCESSFUL_RUN: "This source has run history but has never completed successfully.",
    SCHEDULER_OVERDUE: "No run for far longer than the scheduler interval.",
    LATEST_RUN_FAILED: "The most recent run failed, but an earlier run succeeded.",
    NO_UPSTREAM_CONTENT: "Runs succeed but the upstream listing has been empty for several runs.",
    HIGH_INVALID_RATE: "A large share of fetched items yielded no usable content.",
    STALE_INGESTION: "Runs succeed but nothing new has been stored for some time.",
    STALE_UPSTREAM: "The newest item the upstream offers is old.",
    COLLECTION_OVERDUE: "No run for longer than the scheduler interval allows.",
    NEVER_COLLECTED: "The source is active but has never been collected.",
    OK: "No disabled, error or warning condition applies.",
}


@dataclass(frozen=True)
class SourceHealthThresholds:
    """Every tunable in one immutable place. Injectable so tests pin behaviour.

    Defaults are deliberately forgiving: this API tells an operator where to look,
    and a warning that fires constantly tells them nothing.
    """

    #: Consecutive failed runs before a source is an error rather than a warning.
    consecutive_failures_for_error: int = 2
    #: Successful runs in a row fetching zero items before warning. Three runs at
    #: the 6-hour interval is ~18 hours of genuine upstream silence.
    zero_fetch_warning_streak: int = 3
    #: Multiples of the scheduler interval before overdue warns / errors.
    overdue_warning_multiplier: float = 2.0
    overdue_error_multiplier: float = 4.0
    #: Successful collection but nothing stored for this long.
    stale_ingestion_days: int = 14
    #: The newest item upstream offers is older than this.
    stale_upstream_days: int = 30
    #: Share of fetched items yielding no usable content before warning.
    high_invalid_rate: float = 0.5
    #: Below this many fetched items the ratio is noise, so it is not applied.
    min_fetched_for_invalid_rate: int = 10
    #: How many recent runs the streak calculations look back over.
    recent_runs_considered: int = 20
    #: Cap on the system summary's attention list.
    max_attention_sources: int = 20


DEFAULT_THRESHOLDS = SourceHealthThresholds()


@dataclass
class SourceHealthMetrics:
    """Everything derived for one source. Plain data — no database handle."""

    source_id: int
    name: str
    source_type: str | None = None
    adapter_class: str | None = None
    is_active: bool = True
    credibility_score: int | None = None

    last_run_at: datetime | None = None
    last_run_status: str | None = None
    last_run_duration_seconds: float | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None
    last_new_item_at: datetime | None = None
    latest_upstream_published_at: datetime | None = None

    consecutive_failed_runs: int = 0
    consecutive_zero_fetch_runs: int = 0
    consecutive_zero_new_runs: int = 0
    total_runs_considered: int = 0
    has_any_run: bool = False
    has_any_success: bool = False

    runs_24h: int = 0
    items_fetched_24h: int = 0
    items_new_24h: int = 0
    items_new_7d: int = 0
    items_new_30d: int = 0
    items_skipped_invalid_24h: int = 0
    items_skipped_external_24h: int = 0
    items_skipped_external_7d: int = 0
    latest_run_items_skipped_external: int = 0

    total_raw_items: int = 0
    total_published_alerts: int = 0


@dataclass
class HealthClassification:
    state: str
    reason_code: str
    reason_detail: str = ""
    #: Every condition that matched, worst first. The first is ``reason_code``.
    additional_reason_codes: list[str] = field(default_factory=list)


def _age_days(moment: datetime | None, now: datetime) -> float | None:
    if moment is None:
        return None
    return (now - moment).total_seconds() / 86400.0


def classify_source_health(
    metrics: SourceHealthMetrics,
    thresholds: SourceHealthThresholds = DEFAULT_THRESHOLDS,
    *,
    now: datetime,
    scheduler_interval_hours: float,
) -> HealthClassification:
    """Deterministic first-match verdict for one source.

    Pure: same inputs, same output, no clock of its own. Rules are evaluated
    disabled → error → warning → healthy, and every matching warning is reported
    so an operator sees the whole picture, not only the first problem.
    """
    if not metrics.is_active:
        return HealthClassification(
            DISABLED, SOURCE_DISABLED, REASON_DESCRIPTIONS[SOURCE_DISABLED]
        )

    interval = timedelta(hours=scheduler_interval_hours)
    since_last_run = (
        now - metrics.last_run_at if metrics.last_run_at is not None else None
    )

    # --- Error: demonstrated collector or scheduling failure ---------------
    if metrics.consecutive_failed_runs >= thresholds.consecutive_failures_for_error:
        return HealthClassification(
            ERROR, REPEATED_FAILURES,
            f"{metrics.consecutive_failed_runs} consecutive runs failed",
        )

    if metrics.has_any_run and not metrics.has_any_success:
        return HealthClassification(
            ERROR, NO_SUCCESSFUL_RUN, REASON_DESCRIPTIONS[NO_SUCCESSFUL_RUN]
        )

    if (
        since_last_run is not None
        and since_last_run > interval * thresholds.overdue_error_multiplier
    ):
        return HealthClassification(
            ERROR, SCHEDULER_OVERDUE,
            f"last run {since_last_run.total_seconds() / 3600:.1f}h ago, "
            f"interval is {scheduler_interval_hours}h",
        )

    # --- Warning: degraded but operational ---------------------------------
    warnings: list[tuple[str, str]] = []

    if metrics.last_run_status == "failed" and metrics.has_any_success:
        warnings.append((LATEST_RUN_FAILED, REASON_DESCRIPTIONS[LATEST_RUN_FAILED]))

    if not metrics.has_any_run:
        # Active, but nothing has ever collected it. Worth a look; not a
        # demonstrated failure, so not an error.
        warnings.append((NEVER_COLLECTED, REASON_DESCRIPTIONS[NEVER_COLLECTED]))
    elif (
        since_last_run is not None
        and since_last_run > interval * thresholds.overdue_warning_multiplier
    ):
        warnings.append((
            COLLECTION_OVERDUE,
            f"last run {since_last_run.total_seconds() / 3600:.1f}h ago",
        ))

    # A valid but empty upstream. Generic on purpose: any source whose listing
    # legitimately holds nothing lands here, and none of them is an error.
    if metrics.consecutive_zero_fetch_runs >= thresholds.zero_fetch_warning_streak:
        warnings.append((
            NO_UPSTREAM_CONTENT,
            f"{metrics.consecutive_zero_fetch_runs} successful runs fetched nothing",
        ))

    # Invalid content only. External exclusions are excluded from both sides of
    # this ratio by construction — they are policy outcomes, not defects.
    if metrics.items_fetched_24h >= thresholds.min_fetched_for_invalid_rate:
        invalid_rate = metrics.items_skipped_invalid_24h / metrics.items_fetched_24h
        if invalid_rate >= thresholds.high_invalid_rate:
            warnings.append((
                HIGH_INVALID_RATE,
                f"{invalid_rate:.0%} of items fetched in 24h yielded no usable content",
            ))

    ingest_age = _age_days(metrics.last_new_item_at, now)
    if (
        metrics.has_any_success
        and ingest_age is not None
        and ingest_age > thresholds.stale_ingestion_days
    ):
        warnings.append((
            STALE_INGESTION, f"nothing new stored for {ingest_age:.0f} days"
        ))

    upstream_age = _age_days(metrics.latest_upstream_published_at, now)
    if upstream_age is not None and upstream_age > thresholds.stale_upstream_days:
        warnings.append((
            STALE_UPSTREAM, f"newest upstream item is {upstream_age:.0f} days old"
        ))

    if warnings:
        primary_code, primary_detail = warnings[0]
        return HealthClassification(
            WARNING, primary_code, primary_detail,
            additional_reason_codes=[code for code, _ in warnings[1:]],
        )

    return HealthClassification(HEALTHY, OK, REASON_DESCRIPTIONS[OK])


# ---------------------------------------------------------------------------
# Aggregation — bounded queries, never one per source
# ---------------------------------------------------------------------------


def _window_sum(column, since_column, cutoff):
    """SUM(column) restricted to rows at or after ``cutoff``."""
    return func.coalesce(
        func.sum(case((since_column >= cutoff, column), else_=0)), 0
    )


@dataclass
class _RunHistory:
    """What one source's run history says, at two different depths.

    ``recent`` is bounded — streaks are a statement about *now*, and walking all
    history to compute them would be unbounded work for no extra meaning.

    ``latest_success`` and ``latest_failed`` are **not** bounded. Whether a source
    has ever succeeded is a fact about its whole life: a success thirty runs ago is
    still a success, and treating it as absent would report a working source as
    ``no_successful_run``.
    """

    recent: list[RunLog] = field(default_factory=list)
    latest_success: RunLog | None = None
    latest_failed: RunLog | None = None


#: Statuses whose most recent occurrence is tracked across all history.
_TRACKED_STATUSES = ("success", "failed")


async def _run_history_by_source(
    session: AsyncSession, source_ids: list[int], limit_per_source: int
) -> dict[int, _RunHistory]:
    """Bounded recent runs *and* all-history success/failure, in one query.

    Two window functions over the same scan:

    * ``overall_rank`` — newest-first position within the source, for the streak
      window;
    * ``status_rank`` — newest-first position within (source, status), so the
      latest success and the latest failure are reachable however old they are.

    A row is returned when it is inside the recent window **or** it is the most
    recent run of a tracked status. That adds at most two rows per source beyond
    the window, and keeps the query count at one however many sources exist.
    """
    if not source_ids:
        return {}

    ranked = (
        select(
            RunLog.id.label("run_id"),
            func.row_number()
            .over(
                partition_by=RunLog.source_id,
                order_by=RunLog.run_started_at.desc(),
            )
            .label("overall_rank"),
            func.row_number()
            .over(
                partition_by=(RunLog.source_id, RunLog.status),
                order_by=RunLog.run_started_at.desc(),
            )
            .label("status_rank"),
        )
        .where(RunLog.source_id.in_(source_ids))
        .subquery()
    )
    statement = (
        select(RunLog, ranked.c.overall_rank)
        .join(ranked, RunLog.id == ranked.c.run_id)
        .where(
            or_(
                ranked.c.overall_rank <= limit_per_source,
                and_(
                    ranked.c.status_rank == 1,
                    RunLog.status.in_(_TRACKED_STATUSES),
                ),
            )
        )
        .order_by(RunLog.source_id, RunLog.run_started_at.desc())
    )

    grouped: dict[int, _RunHistory] = {}
    for run, overall_rank in (await session.execute(statement)).all():
        history = grouped.setdefault(run.source_id, _RunHistory())
        if overall_rank <= limit_per_source:
            history.recent.append(run)
        # Rows arrive newest-first per source, so the first of each status wins.
        if run.status == "success" and history.latest_success is None:
            history.latest_success = run
        elif run.status == "failed" and history.latest_failed is None:
            history.latest_failed = run
    return grouped


async def _run_window_totals(
    session: AsyncSession, source_ids: list[int], now: datetime
) -> dict[int, dict[str, int]]:
    """24h / 7d / 30d run counters per source, in one grouped aggregate."""
    if not source_ids:
        return {}

    day, week, month = (
        now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)
    )
    started = RunLog.run_started_at
    statement = (
        select(
            RunLog.source_id,
            func.coalesce(
                func.sum(case((started >= day, 1), else_=0)), 0
            ).label("runs_24h"),
            _window_sum(RunLog.items_fetched, started, day).label("items_fetched_24h"),
            _window_sum(RunLog.items_new, started, day).label("items_new_24h"),
            _window_sum(RunLog.items_new, started, week).label("items_new_7d"),
            _window_sum(RunLog.items_new, started, month).label("items_new_30d"),
            _window_sum(RunLog.items_skipped_invalid, started, day)
            .label("items_skipped_invalid_24h"),
            _window_sum(RunLog.items_skipped_external, started, day)
            .label("items_skipped_external_24h"),
            _window_sum(RunLog.items_skipped_external, started, week)
            .label("items_skipped_external_7d"),
        )
        .where(RunLog.source_id.in_(source_ids))
        .group_by(RunLog.source_id)
    )
    return {
        row.source_id: {
            key: int(getattr(row, key) or 0)
            for key in (
                "runs_24h", "items_fetched_24h", "items_new_24h", "items_new_7d",
                "items_new_30d", "items_skipped_invalid_24h",
                "items_skipped_external_24h", "items_skipped_external_7d",
            )
        }
        for row in (await session.execute(statement)).all()
    }


async def _raw_item_totals(
    session: AsyncSession, source_ids: list[int]
) -> dict[int, dict[str, object]]:
    """Stored-item count, newest stored-at and newest upstream date, per source."""
    if not source_ids:
        return {}

    statement = (
        select(
            RawItem.source_id,
            func.count(RawItem.id).label("total"),
            func.max(RawItem.fetched_at).label("last_new_item_at"),
            func.max(RawItem.published_at).label("latest_upstream_published_at"),
        )
        .where(RawItem.source_id.in_(source_ids))
        .group_by(RawItem.source_id)
    )
    return {
        row.source_id: {
            "total_raw_items": int(row.total or 0),
            "last_new_item_at": row.last_new_item_at,
            "latest_upstream_published_at": row.latest_upstream_published_at,
        }
        for row in (await session.execute(statement)).all()
    }


async def _published_alert_totals(
    session: AsyncSession, source_ids: list[int]
) -> dict[int, int]:
    """Published alerts per source.

    The relationship is proven, not inferred: ``processed_alerts.raw_item_id`` →
    ``raw_items.id`` → ``raw_items.source_id``.
    """
    if not source_ids:
        return {}

    statement = (
        select(RawItem.source_id, func.count(ProcessedAlert.id))
        .join(ProcessedAlert, ProcessedAlert.raw_item_id == RawItem.id)
        .where(RawItem.source_id.in_(source_ids), ProcessedAlert.is_published.is_(True))
        .group_by(RawItem.source_id)
    )
    return {
        source_id: int(count or 0)
        for source_id, count in (await session.execute(statement)).all()
    }


def _streaks_and_latest(metrics: SourceHealthMetrics, history: _RunHistory) -> None:
    """Fill latest-activity fields and streaks from one source's history.

    All-history facts come from ``latest_success``/``latest_failed``; streaks come
    from the bounded ``recent`` window only.
    """
    runs = history.recent
    metrics.total_runs_considered = len(runs)
    metrics.has_any_run = bool(runs)

    # Across the whole run history, however deep.
    if history.latest_success is not None:
        metrics.has_any_success = True
        metrics.last_success_at = history.latest_success.run_started_at
    if history.latest_failed is not None:
        metrics.last_error_at = history.latest_failed.run_started_at
        metrics.last_error_message = history.latest_failed.error_message

    if not runs:
        return

    latest = runs[0]
    metrics.last_run_at = latest.run_started_at
    metrics.last_run_status = latest.status
    metrics.latest_run_items_skipped_external = latest.items_skipped_external or 0
    if latest.run_finished_at and latest.run_started_at:
        metrics.last_run_duration_seconds = (
            latest.run_finished_at - latest.run_started_at
        ).total_seconds()

    # Streaks stop at the first run that does not match, within the window only.
    for run in runs:
        if run.status == "failed":
            metrics.consecutive_failed_runs += 1
        else:
            break
    for run in runs:
        if run.status == "success" and (run.items_fetched or 0) == 0:
            metrics.consecutive_zero_fetch_runs += 1
        else:
            break
    for run in runs:
        if run.status == "success" and (run.items_new or 0) == 0:
            metrics.consecutive_zero_new_runs += 1
        else:
            break


async def collect_source_metrics(
    session: AsyncSession,
    sources: list[Source],
    *,
    now: datetime,
    thresholds: SourceHealthThresholds = DEFAULT_THRESHOLDS,
) -> list[SourceHealthMetrics]:
    """Derive metrics for every source in ``sources`` using four bounded queries.

    Query count is constant in the number of sources: recent runs, run-window
    totals, raw-item totals, published-alert totals.
    """
    if not sources:
        return []

    source_ids = [source.id for source in sources]
    histories = await _run_history_by_source(
        session, source_ids, thresholds.recent_runs_considered
    )
    windows = await _run_window_totals(session, source_ids, now)
    raw_totals = await _raw_item_totals(session, source_ids)
    published = await _published_alert_totals(session, source_ids)

    results = []
    for source in sources:
        metrics = SourceHealthMetrics(
            source_id=source.id,
            name=source.name,
            source_type=source.source_type,
            adapter_class=source.adapter_class,
            is_active=bool(source.is_active),
            credibility_score=source.credibility_score,
        )
        _streaks_and_latest(metrics, histories.get(source.id) or _RunHistory())

        for key, value in (windows.get(source.id) or {}).items():
            setattr(metrics, key, value)

        totals = raw_totals.get(source.id) or {}
        metrics.total_raw_items = totals.get("total_raw_items", 0)
        metrics.last_new_item_at = totals.get("last_new_item_at")
        metrics.latest_upstream_published_at = totals.get("latest_upstream_published_at")
        metrics.total_published_alerts = published.get(source.id, 0)

        results.append(metrics)
    return results


async def load_sources(session: AsyncSession) -> list[Source]:
    result = await session.execute(select(Source).order_by(Source.id))
    return list(result.scalars().all())


async def get_alembic_revision(session: AsyncSession) -> str | None:
    """The applied migration revision, or ``None`` where the table is absent.

    Same read-only lookup the recovery-preview tool uses. The unit-test database
    is built from metadata and has no ``alembic_version`` table, so absence is a
    normal answer rather than an error.
    """
    try:
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        return result.scalar()
    except Exception:
        return None


async def system_totals(session: AsyncSession, now: datetime) -> dict[str, object]:
    """Instance-wide counters for the summary endpoint, in three queries."""
    day, week = now - timedelta(days=1), now - timedelta(days=7)

    run_totals = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(case((RunLog.run_started_at >= day, RunLog.items_new), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(case((RunLog.run_started_at >= week, RunLog.items_new), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(
                        case((RunLog.run_started_at >= day, RunLog.items_skipped_external), else_=0)
                    ), 0
                ),
                func.coalesce(
                    func.sum(
                        case((RunLog.run_started_at >= week, RunLog.items_skipped_external), else_=0)
                    ), 0
                ),
                func.max(RunLog.run_started_at),
            )
        )
    ).one()

    raw_total = (
        await session.execute(select(func.count()).select_from(RawItem))
    ).scalar_one()

    alert_totals = (
        await session.execute(
            select(
                func.count(ProcessedAlert.id),
                func.coalesce(
                    func.sum(case((ProcessedAlert.is_published.is_(True), 1), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ProcessedAlert.is_published.is_(True)
                                & (ProcessedAlert.published_at >= week),
                                1,
                            ),
                            else_=0,
                        )
                    ), 0
                ),
            )
        )
    ).one()

    return {
        "items_new_24h": int(run_totals[0] or 0),
        "items_new_7d": int(run_totals[1] or 0),
        "items_skipped_external_24h": int(run_totals[2] or 0),
        "items_skipped_external_7d": int(run_totals[3] or 0),
        "last_collection_cycle_at": run_totals[4],
        "raw_items_total": int(raw_total or 0),
        "processed_alerts_total": int(alert_totals[0] or 0),
        "published_alerts_total": int(alert_totals[1] or 0),
        "published_last_7d": int(alert_totals[2] or 0),
    }
