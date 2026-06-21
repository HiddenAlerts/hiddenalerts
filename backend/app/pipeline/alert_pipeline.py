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
from app.pipeline.publishing.constants import (
    DecisionSource,
    PendingReviewReason,
    PublishDecisionValue,
    RiskBandValue,
)
from app.pipeline.publishing.publishing_policy import DEFAULT_V1_POLICY, PublishDecision
from app.pipeline.publishing.risk_bands import compute_risk_band
from app.pipeline.publishing.source_rules import (
    evaluate_source_rule,
    evaluate_v1_publish_decision,
)
from app.pipeline.publishing.topic_veto import should_route_to_review_by_topic
from app.pipeline.signal_scorer import compute_signal_score

log = logging.getLogger(__name__)

# Maximum items to process per pipeline run (prevents unbounded DB load)
BATCH_SIZE = 50

# Publish policy is the single source of truth (Slice 5). The old M3 tier1
# constants (ALLOWED_PUBLISH_CATEGORIES, _TIER1_MIN_SCORE) have been removed —
# all publish/review/exclude/hold decisions now come from
# evaluate_v1_publish_decision(...) + DEFAULT_V1_POLICY.

# Module-level lock to prevent concurrent pipeline runs from manual triggers
_processing_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# V1 publish-decision application helpers
# ---------------------------------------------------------------------------


def _apply_publish_decision(
    alert: ProcessedAlert,
    decision: PublishDecision,
    *,
    now: datetime,
) -> None:
    """Persist a V1 :class:`PublishDecision` onto the alert's publication state.

    Sets the common decision metadata, then the action-specific flags. This is
    the only place the auto-policy path writes ``is_published`` — always from the
    *final* (post-grouping) decision.
    """
    alert.risk_band = decision.risk_band.value
    alert.publish_decision = decision.action.value
    alert.publish_decision_reason = decision.reason
    alert.pending_review_reason = (
        decision.pending_review_reason.value
        if decision.pending_review_reason is not None
        else None
    )
    alert.publishing_policy_version = decision.policy_version
    alert.publication_state_source = DecisionSource.AUTO_POLICY.value
    alert.publication_state_updated_at = now

    action = decision.action
    if action is PublishDecisionValue.AUTO_PUBLISH:
        alert.is_published = True
        alert.published_at = now
        alert.published_by_rule = True
        alert.is_excluded = False
        alert.excluded_reason = None
        alert.is_manual_hold = False
    elif action is PublishDecisionValue.EXCLUDE:
        alert.is_published = False
        alert.published_at = None
        alert.published_by_rule = False
        alert.is_excluded = True
        alert.excluded_reason = decision.reason
        alert.is_manual_hold = False
    elif action is PublishDecisionValue.HOLD:
        alert.is_published = False
        alert.published_at = None
        alert.published_by_rule = False
        alert.is_excluded = False
        alert.excluded_reason = None
        alert.is_manual_hold = True
    else:  # REVIEW
        alert.is_published = False
        alert.published_at = None
        alert.published_by_rule = False
        alert.is_excluded = False
        alert.excluded_reason = None
        alert.is_manual_hold = False


def _apply_terminal_state(
    alert: ProcessedAlert,
    *,
    now: datetime,
    action: PublishDecisionValue,
    reason: str,
    pending_reason: PendingReviewReason | None,
    is_excluded: bool,
    excluded_reason: str | None,
    is_manual_hold: bool,
    risk_band: RiskBandValue = RiskBandValue.BELOW_60,
) -> None:
    """Populate V1 publication state for rows that skip the scoring/grouping path
    (no-keyword, AI-irrelevant, AI-failure). Never publishes.
    """
    alert.risk_band = risk_band.value
    alert.publish_decision = action.value
    alert.publish_decision_reason = reason
    alert.pending_review_reason = pending_reason.value if pending_reason is not None else None
    alert.publishing_policy_version = DEFAULT_V1_POLICY.version
    alert.publication_state_source = DecisionSource.AUTO_POLICY.value
    alert.publication_state_updated_at = now
    alert.is_published = False
    alert.published_at = None
    alert.published_by_rule = False
    alert.is_excluded = is_excluded
    alert.excluded_reason = excluded_reason
    alert.is_manual_hold = is_manual_hold


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
    _now = datetime.now(timezone.utc)

    # --- Step 1: Keyword filtering ---
    matched_keywords = filter_by_keywords(text, keywords)

    if not matched_keywords:
        # No keyword match — not relevant, no AI call. Terminal exclude state.
        alert = ProcessedAlert(
            raw_item_id=raw_item.id,
            is_relevant=False,
            matched_keywords=[],
            processed_at=_now,
        )
        _apply_terminal_state(
            alert,
            now=_now,
            action=PublishDecisionValue.EXCLUDE,
            reason="no_keyword_match",
            pending_reason=PendingReviewReason.AI_REJECTED,
            is_excluded=True,
            excluded_reason="no_keyword_match",
            is_manual_hold=False,
        )
        session.add(alert)
        await session.commit()
        stats.items_skipped_no_keywords += 1
        log.debug(f"raw_item {raw_item.id}: no keyword match, excluded")
        return

    # --- Step 2: AI analysis ---
    try:
        ai_result = await analyze_article(
            title=title,
            text=text,
            matched_keywords=matched_keywords,
        )
    except AIProcessingError as exc:
        # AI failed after retries — this is a SYSTEM failure, not a content
        # rejection. Hold for manual attention so it isn't silently excluded.
        log.error(f"AI processing failed for raw_item {raw_item.id}: {exc}")
        alert = ProcessedAlert(
            raw_item_id=raw_item.id,
            is_relevant=False,
            matched_keywords=matched_keywords,
            processed_at=_now,
        )
        _apply_terminal_state(
            alert,
            now=_now,
            action=PublishDecisionValue.HOLD,
            reason="ai_processing_failed",
            pending_reason=PendingReviewReason.MANUAL_HOLD,
            is_excluded=False,
            excluded_reason=None,
            is_manual_hold=True,
        )
        session.add(alert)
        await session.commit()
        stats.items_failed += 1
        stats.errors.append(f"raw_item {raw_item.id}: {exc}")
        return

    if not ai_result.is_relevant:
        # AI confirmed not relevant — store with summary, skip scoring/grouping.
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
            processed_at=_now,
        )
        _apply_terminal_state(
            alert,
            now=_now,
            action=PublishDecisionValue.EXCLUDE,
            reason="ai_marked_irrelevant",
            pending_reason=PendingReviewReason.AI_REJECTED,
            is_excluded=True,
            excluded_reason="ai_marked_irrelevant",
            is_manual_hold=False,
        )
        session.add(alert)
        await session.commit()
        stats.items_skipped_ai_irrelevant += 1
        log.debug(f"raw_item {raw_item.id}: AI marked not relevant, excluded")
        return

    # --- Step 2.5: Effective source credibility (V1 source rules) ---
    # KrebsOnSecurity is floored to 4, and a fraud-signal BleepingComputer item is
    # conditionally lifted to 4. This effective value feeds BOTH the risk SCORE
    # (the source-credibility factor in Step 3) AND the publish gate (Step 6) — so
    # the source promotion can actually raise an alert's band, not only pass the
    # credibility gate (OPEN-1 fix). A non-special source keeps its stored value.
    source_rule = evaluate_source_rule(
        source_name=source.name,
        stored_credibility=source.credibility_score,
        title=title,
        summary=ai_result.summary,
        matched_keywords=matched_keywords,
        entities_json={"names": ai_result.entities},
        primary_category=ai_result.primary_category,
    )
    effective_credibility = (
        source_rule.effective_credibility
        if source_rule.effective_credibility is not None
        else source.credibility_score
    )

    # --- Step 3: Initial signal scoring (cross_source=1 for a brand-new alert) ---
    score_result = await compute_signal_score(
        source_credibility=effective_credibility,
        financial_impact_estimate=ai_result.financial_impact_estimate,
        victim_scale=ai_result.victim_scale,
        event_source_count=1,
        keywords=matched_keywords,
        session=session,
    )

    # --- Step 4: Create ProcessedAlert WITHOUT a publish decision yet. ---
    # The V1 publish decision is made AFTER event grouping so it reflects the
    # final, post-grouping cross-source score (Slice 5 ordering fix).
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
        is_published=False,
        published_at=None,
    )
    session.add(alert)
    await session.flush()  # Get alert.id for event grouping

    # Reload alert with relationships needed by event_grouper
    await session.refresh(alert)
    # Re-attach source relationship for event_grouper
    alert.raw_item = raw_item

    # --- Step 5: Event grouping inside a SAVEPOINT ---
    # The new ProcessedAlert was already flushed above (before this savepoint), so
    # it survives. begin_nested() isolates grouping's side effects (new
    # Event/EventSource rows + cross-source recalc): if grouping raises, only
    # those are rolled back to the savepoint, never the alert, and the outer
    # transaction stays valid for the hold + commit below.
    try:
        async with session.begin_nested():
            await find_or_create_event(alert, session)
    except Exception as exc:
        # Grouping failed → FINAL post-grouping state is unknown, so under V1 we
        # must NOT auto-publish on a possibly-stale score. The savepoint rollback
        # EXPIRES the alert (its attrs would otherwise trigger implicit async IO),
        # so refresh FIRST — before reading alert.id or any field — to restore the
        # pre-grouping (savepoint) values. score_*/signal_score_total/risk_level
        # are thus the initial scored values (any partial recalc was rolled back).
        await session.refresh(alert)
        alert.raw_item = raw_item
        log.warning(
            f"Event grouping failed for alert {alert.id} (raw_item {raw_item.id}): {exc}. "
            "Grouping side effects rolled back; alert put on manual hold "
            "(event_grouping_failed)."
        )
        _apply_terminal_state(
            alert,
            now=_now,
            action=PublishDecisionValue.HOLD,
            reason="event_grouping_failed",
            pending_reason=PendingReviewReason.MANUAL_HOLD,
            is_excluded=False,
            excluded_reason=None,
            is_manual_hold=True,
            # Relevant + scored alert: keep the band from its preserved score
            # rather than the below_60 default used by content-rejection rows.
            risk_band=compute_risk_band(alert.signal_score_total),
        )
        await session.commit()
        stats.items_processed += 1  # saved successfully, held for review
        log.info(
            f"raw_item {raw_item.id} → alert {alert.id} "
            f"[score={alert.signal_score_total} decision=hold reason=event_grouping_failed]"
        )
        return

    # Ensure the post-grouping score is flushed/visible before deciding.
    await session.flush()

    # --- Step 5b: Topic-scope veto (OPEN-5, deterministic defense-in-depth) ---
    # Behind the AI relevance prompt: if the text is clearly out-of-scope
    # (terrorism / espionage / drug / homicide / gang / weapons / …) and carries
    # no direct fraud signal, route to review instead of risking an auto-publish.
    if should_route_to_review_by_topic(
        title=title,
        summary=alert.summary,
        primary_category=alert.primary_category,
        matched_keywords=alert.matched_keywords,
    ):
        _apply_terminal_state(
            alert,
            now=_now,
            action=PublishDecisionValue.REVIEW,
            reason="blocked_by_topic_scope",
            pending_reason=PendingReviewReason.BLOCKED_BY_TOPIC_SCOPE,
            is_excluded=False,
            excluded_reason=None,
            is_manual_hold=False,
            risk_band=compute_risk_band(alert.signal_score_total),
        )
        await session.commit()
        stats.items_processed += 1
        log.info(
            f"raw_item {raw_item.id} → alert {alert.id} "
            f"[topic_veto decision=review reason=blocked_by_topic_scope]"
        )
        return

    # --- Step 6: V1 publish decision on the FINAL (post-grouping) score ---
    # NOTE (Slice 5): only the current alert is (re-)evaluated here. Sibling
    # alerts already linked to the same event are intentionally NOT re-evaluated
    # in this slice — see the implementation summary for the rationale and the
    # deferred-rescore plan. Cross-source only ever increases as an event gains
    # outlets, so deferring sibling re-eval cannot publish anything incorrectly.
    decision = evaluate_v1_publish_decision(
        signal_score_total=alert.signal_score_total,
        primary_category=alert.primary_category,
        source_name=source.name,
        source_credibility=source.credibility_score,
        title=title,
        summary=alert.summary,
        matched_keywords=alert.matched_keywords,
        entities_json=alert.entities_json,
    )
    _apply_publish_decision(alert, decision, now=_now)

    await session.commit()
    stats.items_processed += 1
    log.info(
        f"raw_item {raw_item.id} → alert {alert.id} "
        f"[band={decision.risk_band.value} score={alert.signal_score_total} "
        f"decision={decision.action.value} reason={decision.reason}]"
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
