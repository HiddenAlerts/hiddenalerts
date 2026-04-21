"""Signal scoring module — 5-factor arithmetic scoring system.

Computes a structured risk score for each processed alert based on:
  1. Source Credibility (from source.credibility_score)
  2. Financial Impact (parsed from AI's dollar estimate)
  3. Victim Scale (from AI's victim_scale output)
  4. Cross-Source Confirmation (count of sources reporting same event)
  5. Trend Acceleration (keyword frequency comparison: last 7d vs prior 7d)

Score range: 5–24 (source/cross/trend 1–5; financial 1/2/3/5; victim 1/2/4)
Risk levels: ≤8 → low, 9–15 → medium, ≥16 → high
Tier 1 auto-publish threshold (M3 Slice 2): ≥16 — aligned with HIGH threshold.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import String

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class SignalScoreResult:
    score_source_credibility: int  # 1-5
    score_financial_impact: int  # 1-5
    score_victim_scale: int  # 1-5
    score_cross_source: int  # 1-5
    score_trend_acceleration: int  # 1-5
    signal_score_total: int  # 5-25
    risk_level: str  # "low" | "medium" | "high"


# ---------------------------------------------------------------------------
# Individual factor calculators
# ---------------------------------------------------------------------------


def compute_financial_impact_score(financial_impact_estimate: str) -> int:
    """Parse dollar amount from free-text AI output and bucket into 1/3/5.

    Handles: "$4.2 million", "$50M", "over $10 million", "$1M-$5M" (lower bound),
             "hundreds of thousands", "billions", "unknown", "none", empty string.
    Returns 1 on parse failure or unknown.
    """
    if not financial_impact_estimate:
        return 1

    text_lower = financial_impact_estimate.lower().strip()

    # Explicit non-values
    if text_lower in ("unknown", "none", "n/a", "not stated", "undisclosed"):
        return 1

    # Check for billions first (always → 5)
    if "billion" in text_lower or re.search(r"\$[\d,.]+\s*b\b", text_lower):
        return 5

    # Extract first dollar amount from text
    # Matches: $4.2 million, $50M, $1,000,000, $900K, $1.5B
    amount = _parse_dollar_amount(text_lower)
    if amount is None:
        # Heuristic for text like "hundreds of thousands"
        if "hundreds of thousands" in text_lower or "hundreds of million" in text_lower:
            return 1
        if "millions" in text_lower or "multi-million" in text_lower:
            return 2  # vague "millions" — moderate, not exceptional
        log.warning(f"Could not parse financial impact: {financial_impact_estimate!r}, defaulting to 1")
        return 1

    if amount >= 100_000_000:  # > $100M → exceptional impact
        return 5
    elif amount >= 10_000_000:  # $10M – $100M → meaningful but not exceptional
        return 3
    elif amount >= 1_000_000:   # $1M – $10M → moderate
        return 2
    else:
        return 1


def _parse_dollar_amount(text_lower: str) -> float | None:
    """Extract and normalize dollar amount to raw number.

    For ranges like "$1M-$5M", uses the lower bound.
    Returns None if no parseable amount found.
    """
    # For ranges, take the first (lower) value
    # Pattern: optional $, digits with optional commas/decimals, optional multiplier
    pattern = r"\$?([\d,]+(?:\.\d+)?)\s*(million|billion|thousand|m|b|k)?"
    matches = re.findall(pattern, text_lower)

    if not matches:
        return None

    # Use the first match (lower bound for ranges)
    raw_num_str, multiplier = matches[0]

    try:
        raw_num = float(raw_num_str.replace(",", ""))
    except ValueError:
        return None

    multiplier = multiplier.strip().lower()
    if multiplier in ("million", "m"):
        return raw_num * 1_000_000
    elif multiplier in ("billion", "b"):
        return raw_num * 1_000_000_000
    elif multiplier in ("thousand", "k"):
        return raw_num * 1_000
    else:
        return raw_num


def compute_victim_scale_score(victim_scale: str) -> int:
    """Map AI's victim_scale output to 1/2/4.

    single → 1, multiple → 2, nationwide → 4, unknown → 1 (defensive default).

    Reduced from 1/3/5 (M2) to prevent routine enforcement actions from
    inflating scores into HIGH solely via the common "multiple" default.
    The AI prompt also instructs the model to be conservative with "nationwide".
    """
    if not victim_scale:
        return 1

    normalized = victim_scale.lower().strip()
    if normalized == "nationwide":
        return 4
    elif normalized == "multiple":
        return 2
    elif normalized == "single":
        return 1
    else:
        log.warning(f"Unexpected victim_scale value: {victim_scale!r}, defaulting to 1")
        return 1


def compute_cross_source_score(event_source_count: int) -> int:
    """Map number of sources reporting the same event to 1/3/5.

    1 source → 1, 2 sources → 3, 3+ sources → 5.
    """
    if event_source_count >= 3:
        return 5
    elif event_source_count == 2:
        return 3
    else:
        return 1  # 0 or 1 sources


def derive_risk_level(signal_score_total: int) -> str:
    """Derive risk level from total signal score.

    ≤8 → low, 9–15 → medium, ≥16 → high.
    Aligned with Tier 1 auto-publish threshold (≥16) from M3 Slice 2.
    """
    if signal_score_total >= 16:
        return "high"
    elif signal_score_total >= 9:
        return "medium"
    else:
        return "low"


# ---------------------------------------------------------------------------
# Trend acceleration (requires DB query — async)
# ---------------------------------------------------------------------------


async def compute_trend_score(keywords: list[str], session: AsyncSession) -> int:
    """Compare keyword frequency in last 7 days vs prior 7 days.

    Returns:
        1 = stable or decreasing (< 25% increase)
        3 = noticeable increase (25-99% increase) or new keyword with no prior
        5 = rapid surge (100%+ increase)

    Uses PostgreSQL JSONB ?| operator to check keyword overlap.
    Falls back to score=3 on query error to avoid blocking pipeline.
    """
    # Import here to avoid circular import at module load time
    from app.models.processed_alert import ProcessedAlert  # noqa: PLC0415

    if not keywords:
        return 1

    try:
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        fourteen_days_ago = now - timedelta(days=14)

        # Use ORM + literal() so SQLAlchemy binds the array correctly for asyncpg.
        # The ?| JSONB operator checks whether any element of a text[] appears
        # as a top-level key/element in the JSONB value.
        # literal(list, ARRAY(String)) lets asyncpg encode the Python list as text[].
        kw_array = literal(keywords, ARRAY(String))

        last_7d_q = (
            select(func.count())
            .where(ProcessedAlert.processed_at >= seven_days_ago)
            .where(ProcessedAlert.matched_keywords.op("?|")(kw_array))
            .where(ProcessedAlert.is_relevant.is_(True))
        )
        last_7d = (await session.execute(last_7d_q)).scalar() or 0

        prior_7d_q = (
            select(func.count())
            .where(ProcessedAlert.processed_at >= fourteen_days_ago)
            .where(ProcessedAlert.processed_at < seven_days_ago)
            .where(ProcessedAlert.matched_keywords.op("?|")(kw_array))
            .where(ProcessedAlert.is_relevant.is_(True))
        )
        prior_7d = (await session.execute(prior_7d_q)).scalar() or 0

        if last_7d == 0 and prior_7d == 0:
            return 1  # Stable / new topic with no history
        elif prior_7d == 0 and last_7d > 0:
            return 3  # New surge — no prior baseline; potentially significant
        elif last_7d == 0:
            return 1  # Topic went quiet
        else:
            increase_pct = ((last_7d - prior_7d) / prior_7d) * 100
            if increase_pct >= 100:
                return 5  # Rapid surge: doubled or more
            elif increase_pct >= 25:
                return 3  # Noticeable increase
            else:
                return 1  # Stable

    except Exception as exc:
        log.warning(f"Trend score query failed, defaulting to 3: {exc}")
        # Rollback to clear any aborted transaction state so the caller's
        # session remains usable for subsequent writes.
        try:
            await session.rollback()
        except Exception:
            pass
        return 3  # Safe middle default on error


# ---------------------------------------------------------------------------
# Main scoring orchestrator
# ---------------------------------------------------------------------------


async def compute_signal_score(
    source_credibility: int,
    financial_impact_estimate: str,
    victim_scale: str,
    event_source_count: int,
    keywords: list[str],
    session: AsyncSession,
) -> SignalScoreResult:
    """Orchestrate all 5 factor calculations and return a complete SignalScoreResult.

    Args:
        source_credibility: source.credibility_score (1-5, hard-coded per source).
        financial_impact_estimate: Raw AI output string (e.g., "$2.5 million").
        victim_scale: Raw AI output string (single/multiple/nationwide).
        event_source_count: Number of sources reporting the same event (usually 1 for new alerts).
        keywords: Matched keywords for trend comparison query.
        session: Async DB session for trend acceleration query.

    Returns:
        SignalScoreResult with all 5 scores, total, and risk level.
    """
    score_credibility = max(1, min(5, source_credibility))  # Clamp to 1-5
    score_financial = compute_financial_impact_score(financial_impact_estimate)
    score_victim = compute_victim_scale_score(victim_scale)
    score_cross = compute_cross_source_score(event_source_count)
    score_trend = await compute_trend_score(keywords, session)

    total = score_credibility + score_financial + score_victim + score_cross + score_trend
    risk = derive_risk_level(total)

    return SignalScoreResult(
        score_source_credibility=score_credibility,
        score_financial_impact=score_financial,
        score_victim_scale=score_victim,
        score_cross_source=score_cross,
        score_trend_acceleration=score_trend,
        signal_score_total=total,
        risk_level=risk,
    )
