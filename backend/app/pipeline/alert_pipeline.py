"""Alert processing pipeline orchestrator — M2 core.

Processes raw_items that haven't yet been turned into processed_alerts by:
  1. Keyword filtering (gate before AI)
  2. AI analysis (OpenAI GPT-4o-mini structured output)
  3. Signal scoring (5-factor arithmetic)
  4. Event grouping (entity overlap + category matching)

Designed to be called:
  - By the scheduler every 30 minutes
  - Immediately after each collection run completes
  - Manually via POST /api/v1/alerts/process

Each item is committed individually to minimize lock contention.
One item failing does NOT stop the others.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import outerjoin, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.pipeline.ai_processor import AIProcessingError, analyze_article
from app.pipeline.event_grouper import find_or_create_event
from app.pipeline.keyword_filter import filter_by_keywords
from app.pipeline.signal_scorer import compute_signal_score

log = logging.getLogger(__name__)

# Maximum items to process per pipeline run (prevents unbounded DB load)
BATCH_SIZE = 50

# Categories allowed to auto-publish if score requirements are met
ALLOWED_PUBLISH_CATEGORIES = {
    "Investment Fraud",
    "Cybercrime",
    "Consumer Scam",
    "Money Laundering",
    "Cryptocurrency Fraud",
}

# Module-level lock to prevent concurrent pipeline runs from manual triggers
_processing_lock = asyncio.Lock()


@dataclass
class ProcessingStats:
    items_examined: int = 0
    items_skipped_no_keywords: int = 0
    items_skipped_ai_irrelevant: int = 0
    items_processed: int = 0
    items_failed: int = 0
    errors: list[str] = field(default_factory=list)


def is_processing() -> bool:
    """Check if a pipeline run is currently in progress."""
    return _processing_lock.locked()


async def process_unprocessed_items(
    session: AsyncSession,
    limit: int | None = None,
) -> ProcessingStats:
    """Main pipeline orchestrator.

    Finds raw_items with no corresponding processed_alert and runs each through
    the full M2 processing pipeline.

    Args:
        session: Async DB session. Caller should NOT wrap in a transaction —
                 this function commits per-item.
        limit: Override the default BATCH_SIZE (useful for testing/manual runs).

    Returns:
        ProcessingStats summary of the run.
    """
    if not settings.ai_processing_enabled:
        log.info("AI processing disabled (AI_PROCESSING_ENABLED=false), skipping")
        return ProcessingStats()

    async with _processing_lock:
        return await _run_pipeline(session, limit=limit)


async def _run_pipeline(session: AsyncSession, limit: int | None = None) -> ProcessingStats:
    stats = ProcessingStats()
    log.info("Alert pipeline: starting processing run")

    # Fetch batch of unprocessed raw_items
    raw_items = await _get_unprocessed_raw_items(session, limit or BATCH_SIZE)
    stats.items_examined = len(raw_items)

    if not raw_items:
        log.info("Alert pipeline: no unprocessed items found")
        return stats

    log.info(f"Alert pipeline: processing {len(raw_items)} unprocessed items")

    for raw_item in raw_items:
        try:
            await _process_single_item(raw_item, session, stats)
        except Exception as exc:
            stats.items_failed += 1
            # Rollback FIRST — clears any aborted transaction state and re-enables
            # attribute access on expired ORM objects before we try to read raw_item.id.
            await session.rollback()
            err_msg = f"Unexpected error processing raw_item {raw_item.id}: {exc}"
            stats.errors.append(err_msg)
            log.error(err_msg, exc_info=True)

    log.info(
        f"Alert pipeline complete: examined={stats.items_examined}, "
        f"processed={stats.items_processed}, "
        f"no_keywords={stats.items_skipped_no_keywords}, "
        f"ai_irrelevant={stats.items_skipped_ai_irrelevant}, "
        f"failed={stats.items_failed}"
    )
    return stats


async def _process_single_item(
    raw_item: RawItem,
    session: AsyncSession,
    stats: ProcessingStats,
) -> None:
    """Process one raw_item through the full pipeline.

    Commits to DB after each item (not batch) to minimize lock duration.
    """
    source = raw_item.source
    if source is None:
        log.warning(f"raw_item {raw_item.id} has no source, skipping")
        return

    keywords: list[str] = source.keywords or []
    text = raw_item.raw_text or ""
    title = raw_item.title or ""

    # --- Step 1: Keyword filtering ---
    matched_keywords = filter_by_keywords(text, keywords)

    if not matched_keywords:
        # No keyword match — mark as not relevant, no AI call
        alert = ProcessedAlert(
            raw_item_id=raw_item.id,
            is_relevant=False,
            matched_keywords=[],
            is_published=False,
            processed_at=datetime.now(timezone.utc),
        )
        session.add(alert)
        await session.commit()
        stats.items_skipped_no_keywords += 1
        log.debug(f"raw_item {raw_item.id}: no keyword match, marked not relevant")
        return

    # --- Step 2: AI analysis ---
    try:
        ai_result = await analyze_article(
            title=title,
            text=text,
            matched_keywords=matched_keywords,
        )
    except AIProcessingError as exc:
        # AI failed after retries — store partial alert so we don't retry endlessly
        log.error(f"AI processing failed for raw_item {raw_item.id}: {exc}")
        alert = ProcessedAlert(
            raw_item_id=raw_item.id,
            is_relevant=False,
            matched_keywords=matched_keywords,
            is_published=False,
            processed_at=datetime.now(timezone.utc),
        )
        session.add(alert)
        await session.commit()
        stats.items_failed += 1
        stats.errors.append(f"raw_item {raw_item.id}: {exc}")
        return

    if not ai_result.is_relevant:
        # AI confirmed not relevant — store with summary but skip scoring/grouping
        alert = ProcessedAlert(
            raw_item_id=raw_item.id,
            summary=ai_result.summary,
            primary_category=ai_result.primary_category,
            secondary_category=ai_result.secondary_category,
            entities_json={"names": ai_result.entities},
            matched_keywords=matched_keywords,
            financial_impact_estimate=ai_result.financial_impact_estimate,
            victim_scale_raw=ai_result.victim_scale,
            ai_model=ai_result.ai_model,
            is_relevant=False,
            is_published=False,
            processed_at=datetime.now(timezone.utc),
        )
        session.add(alert)
        await session.commit()
        stats.items_skipped_ai_irrelevant += 1
        log.debug(f"raw_item {raw_item.id}: AI marked not relevant")
        return

    # --- Step 3: Signal scoring (initial cross_source=1 for new alert) ---
    score_result = await compute_signal_score(
        source_credibility=source.credibility_score,
        financial_impact_estimate=ai_result.financial_impact_estimate,
        victim_scale=ai_result.victim_scale,
        event_source_count=1,
        keywords=matched_keywords,
        session=session,
    )

    # --- Step 4: Create ProcessedAlert ---
    # Tier 1 auto-publish: relevant + score >= 16 + source credibility >= 4 + allowed category.
    # Uses source.credibility_score directly (authoritative) rather than the
    # derived score_source_credibility field which maps the same value 1-5.
    
    _now = datetime.now(timezone.utc)
    tier1 = (
        ai_result.is_relevant
        and score_result.signal_score_total >= 16
        and (source.credibility_score or 0) >= 4
        and ai_result.primary_category in ALLOWED_PUBLISH_CATEGORIES
    )

    alert = ProcessedAlert(
        raw_item_id=raw_item.id,
        summary=ai_result.summary,
        risk_level=score_result.risk_level,
        primary_category=ai_result.primary_category,
        secondary_category=ai_result.secondary_category,
        entities_json={"names": ai_result.entities},
        matched_keywords=matched_keywords,
        financial_impact_estimate=ai_result.financial_impact_estimate,
        victim_scale_raw=ai_result.victim_scale,
        ai_model=ai_result.ai_model,
        is_relevant=True,
        processed_at=_now,
        score_source_credibility=score_result.score_source_credibility,
        score_financial_impact=score_result.score_financial_impact,
        score_victim_scale=score_result.score_victim_scale,
        score_cross_source=score_result.score_cross_source,
        score_trend_acceleration=score_result.score_trend_acceleration,
        signal_score_total=score_result.signal_score_total,
        is_published=tier1,
        published_at=_now if tier1 else None,
    )
    session.add(alert)
    await session.flush()  # Get alert.id for event grouping

    # Reload alert with relationships needed by event_grouper
    await session.refresh(alert)
    # Re-attach source relationship for event_grouper
    alert.raw_item = raw_item

    # --- Step 5: Event grouping ---
    try:
        await find_or_create_event(alert, session)
    except Exception as exc:
        log.warning(
            f"Event grouping failed for alert {alert.id} (raw_item {raw_item.id}): {exc}. "
            "Alert saved without event link."
        )

    await session.commit()
    stats.items_processed += 1
    log.info(
        f"raw_item {raw_item.id} → alert {alert.id} "
        f"[{score_result.risk_level.upper()} score={score_result.signal_score_total}]"
    )


async def _get_unprocessed_raw_items(
    session: AsyncSession,
    batch_size: int,
) -> list[RawItem]:
    """Query raw_items that have no corresponding processed_alert.

    Excludes duplicates (is_duplicate=True) since they carry no new content.
    Uses LEFT JOIN to find the gap efficiently.
    """
    stmt = (
        select(RawItem)
        .outerjoin(ProcessedAlert, ProcessedAlert.raw_item_id == RawItem.id)
        .where(ProcessedAlert.id.is_(None))
        .where(RawItem.is_duplicate.is_(False))
        .options(
            selectinload(RawItem.source),
        )
        .order_by(RawItem.fetched_at.asc())  # Process oldest first
        .limit(batch_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
