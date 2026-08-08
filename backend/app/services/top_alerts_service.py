"""Subscriber "Top Alerts This Week" — a rolling seven-day selection.

The Dashboard widget was showing January 2026 and 2025 alerts while the Landing
and Alerts pages showed current data. The cause: the subscriber endpoint
delegated to the legacy all-time implementation, which ranks the highest-scored
published alerts with no time window at all, so a high-scoring alert from last
year outranks everything published this week and never ages out.

This service answers a different, narrower question: **what did HiddenAlerts
publish in the last seven days that a paying subscriber should see first?**

Every decision is made in SQL and is fully deterministic — no candidate pool, no
Python reranking, no entity suppression.

Three positions, filled by the rolling-window rules below. A window that fills
only one or two positions is left partially filled: padding with older alerts
would present them as equally current, which is the bug this service was written
to fix.

When the window yields **nothing at all**, the widget would otherwise be blank,
so :func:`get_latest_qualifying_alerts` supplies the most recently published
qualifying alerts instead. That is a different question, answered by a different
query and ordering, and the caller labels it explicitly so the reader is never
told last month's intelligence is from this week.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.pipeline.publishing.constants import DecisionSource
from app.pipeline.publishing.risk_bands import (
    _CRITICAL_MIN_INTERNAL,
    _HIGH_MIN_INTERNAL,
)

log = logging.getLogger(__name__)

#: The rolling window, in days. Inclusive at the boundary.
WINDOW_DAYS = 7

#: Positions in the Dashboard widget.
DEFAULT_LIMIT = 3

#: Canonical internal-score floors, re-exported from the publishing risk bands so
#: this module holds no second copy of the thresholds. Critical ≥ 20, High ≥ 18
#: on the internal 5–25 scale (0–100: 80 and ~72). Medium (15–17) never qualifies.
CRITICAL_MIN_SCORE = _CRITICAL_MIN_INTERNAL
HIGH_MIN_SCORE = _HIGH_MIN_INTERNAL

#: Publication decisions that represent historical bulk operations rather than a
#: current editorial act. Their ``published_at`` reflects when the backfill ran,
#: not when HiddenAlerts decided the alert mattered, so they must not surface in
#: a "this week" widget. Current publications — automatic policy and manual admin
#: — stay eligible, as do legacy NULL rows.
EXCLUDED_DECISION_SOURCES = (
    DecisionSource.CANDIDATE_BACKFILL.value,
    DecisionSource.SYSTEM_MIGRATION.value,
)


def _as_utc(moment: datetime) -> datetime:
    """Treat a naive instant as UTC.

    ``ProcessedAlert.published_at`` is ``DateTime(timezone=True)`` and is written
    aware, so the cutoff must be aware too or PostgreSQL will refuse the
    comparison.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def window_start(now: datetime) -> datetime:
    """The inclusive lower bound of the rolling window."""
    return _as_utc(now) - timedelta(days=WINDOW_DAYS)


def eligibility_predicates() -> list:
    """Everything an alert must satisfy to be shown, except the time window.

    Shared by the rolling-window selection and the historical fallback so the two
    can never disagree about what "qualifying" means — the fallback widens *only*
    the date range, never the publication, band or exclusion rules.
    """
    return [
        ProcessedAlert.is_published.is_(True),
        ProcessedAlert.signal_score_total >= HIGH_MIN_SCORE,
        ProcessedAlert.published_at.is_not(None),
        or_(
            ProcessedAlert.publication_state_source.is_(None),
            ProcessedAlert.publication_state_source.not_in(EXCLUDED_DECISION_SOURCES),
        ),
    ]


async def get_top_alerts(
    session: AsyncSession,
    *,
    now: datetime,
    limit: int = DEFAULT_LIMIT,
) -> list[ProcessedAlert]:
    """The alerts the subscriber Top Alerts widget should show, best first.

    Eligibility — all of:

    * published by HiddenAlerts (``is_published``);
    * ``published_at`` present and within the last :data:`WINDOW_DAYS` days;
    * ``signal_score_total`` at or above the canonical **High** floor, so only
      Critical and High qualify;
    * not published by a historical bulk operation.

    Ordering — Critical band first, then score descending, then HiddenAlerts
    publication time descending, then id descending so equal alerts still come
    back in a stable order.

    ``now`` is injected so the window is testable at a frozen instant.
    """
    cutoff = window_start(now)

    # 0 sorts before 1, so Critical precedes High regardless of score ties.
    band_rank = case((ProcessedAlert.signal_score_total >= CRITICAL_MIN_SCORE, 0), else_=1)

    statement = (
        select(ProcessedAlert)
        .where(*eligibility_predicates(), ProcessedAlert.published_at >= cutoff)
        .options(selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source))
        .order_by(
            band_rank,
            ProcessedAlert.signal_score_total.desc(),
            ProcessedAlert.published_at.desc(),
            ProcessedAlert.id.desc(),
        )
        .limit(limit)
    )

    result = await session.execute(statement)
    alerts = list(result.scalars().unique().all())
    log.debug(
        "Top alerts: %d selected from the window opening %s", len(alerts), cutoff
    )
    return alerts


async def get_latest_qualifying_alerts(
    session: AsyncSession,
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[ProcessedAlert]:
    """The most recently published qualifying alerts, with no time window.

    Used **only** when the rolling window returns nothing at all. A partially
    filled window is left partially filled: padding two current alerts with a
    third from months ago would misrepresent them as equally current, which is
    the failure the window exists to prevent.

    Ordering is publication time first — not band or score — so the result is
    genuinely "the latest published intelligence" rather than an all-time
    leaderboard. Ties break on id descending for determinism.
    """
    statement = (
        select(ProcessedAlert)
        .where(*eligibility_predicates())
        .options(selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source))
        .order_by(
            ProcessedAlert.published_at.desc(),
            ProcessedAlert.id.desc(),
        )
        .limit(limit)
    )

    result = await session.execute(statement)
    alerts = list(result.scalars().unique().all())
    log.debug("Top alerts fallback: %d selected with no window", len(alerts))
    return alerts
