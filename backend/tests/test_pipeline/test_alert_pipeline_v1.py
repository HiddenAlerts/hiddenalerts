"""V1 Slice 5 — alert-pipeline publish-ordering integration tests (real DB).

Exercise the full ``_process_single_item`` flow against the in-memory SQLite
session (real event grouping + real V1 policy), with only the keyword filter,
AI call, and initial signal scoring patched so inputs are deterministic and no
OpenAI calls happen.

The headline guarantee (test 12): the publish decision is made on the FINAL
post-grouping score, not the pre-grouping score.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.pipeline.ai_processor import AIAnalysisResult, AIProcessingError
from app.pipeline.alert_pipeline import _process_single_item, ProcessingStats
from app.pipeline.signal_scorer import SignalScoreResult

_PATH = "app.pipeline.alert_pipeline"


async def _make_source(session, name, credibility):
    s = Source(
        name=name,
        base_url="https://example.com",
        source_type="rss",
        credibility_score=credibility,
        adapter_class="RSSAdapter",
        keywords=["fraud"],
    )
    session.add(s)
    await session.flush()
    return s


async def _make_raw(session, source, title):
    raw = RawItem(
        source_id=source.id,
        item_url=f"https://example.com/{title.replace(' ', '-').lower()}",
        title=title,
        raw_text="Fraud " * 40,
        url_hash=f"hash_{title}",
    )
    session.add(raw)
    await session.flush()
    raw.source = source  # attach for the pipeline (no async lazy-load)
    return raw


def _ai(category, entities, *, is_relevant=True, summary="A fraud event occurred."):
    return AIAnalysisResult(
        summary=summary,
        primary_category=category,
        secondary_category=None,
        entities=entities,
        financial_impact_estimate="$5 million",
        victim_scale="multiple",
        is_relevant=is_relevant,
        ai_model="test-model",
    )


def _score(total, *, cross=1, cred=5, fin=3, victim=4, trend=2, level="medium"):
    return SignalScoreResult(
        signal_score_total=total,
        risk_level=level,
        score_source_credibility=cred,
        score_financial_impact=fin,
        score_victim_scale=victim,
        score_cross_source=cross,
        score_trend_acceleration=trend,
    )


async def _process(session, source, raw, ai_result, score_result=None, *, raise_ai=False,
                   keywords=("fraud",)):
    """Run the real pipeline for one raw item with patched filter/AI/scoring."""
    stats = ProcessingStats()
    cm_kw = patch(f"{_PATH}.filter_by_keywords", return_value=list(keywords))
    if raise_ai:
        cm_ai = patch(f"{_PATH}.analyze_article", side_effect=AIProcessingError("boom"))
    else:
        cm_ai = patch(f"{_PATH}.analyze_article", return_value=ai_result)
    with cm_kw, cm_ai:
        if score_result is not None:
            with patch(f"{_PATH}.compute_signal_score", return_value=score_result):
                await _process_single_item(raw, session, stats)
        else:
            await _process_single_item(raw, session, stats)
    return stats


async def _get_alert(session, raw_id):
    res = await session.execute(
        select(ProcessedAlert).where(ProcessedAlert.raw_item_id == raw_id)
    )
    return res.scalar_one()


# --- 1. High/Critical + approved + credibility passes → auto_publish ---------


@pytest.mark.asyncio
async def test_high_approved_auto_publishes(db_session):
    src = await _make_source(db_session, "FBI Press", 5)
    raw = await _make_raw(db_session, src, "High Auto One")
    await _process(db_session, src, raw, _ai("Cybercrime", ["AutoHighCo"]), _score(18, level="high"))
    a = await _get_alert(db_session, raw.id)
    assert a.is_published is True
    assert a.published_by_rule is True
    assert a.publish_decision == "auto_publish"
    assert a.risk_band in ("high", "critical")
    assert a.publishing_policy_version == "v1.0"
    assert a.publication_state_source == "auto_policy"


# --- 2. Medium → review / blocked_by_score -----------------------------------


@pytest.mark.asyncio
async def test_medium_routes_to_review(db_session):
    src = await _make_source(db_session, "FBI Press M", 5)
    raw = await _make_raw(db_session, src, "Medium Review One")
    await _process(db_session, src, raw, _ai("Cybercrime", ["MedReviewCo"]), _score(16, level="medium"))
    a = await _get_alert(db_session, raw.id)
    assert a.is_published is False
    assert a.publish_decision == "review"
    assert a.pending_review_reason == "blocked_by_score"


# --- 3. below-60 → exclude / excluded_low_score ------------------------------


@pytest.mark.asyncio
async def test_below_60_excluded(db_session):
    src = await _make_source(db_session, "FBI Press L", 5)
    raw = await _make_raw(db_session, src, "Below Excl One")
    await _process(db_session, src, raw, _ai("Cybercrime", ["BelowCo"]), _score(8, level="low"))
    a = await _get_alert(db_session, raw.id)
    assert a.is_published is False
    assert a.publish_decision == "exclude"
    assert a.is_excluded is True
    assert a.pending_review_reason == "excluded_low_score"
    assert a.risk_band == "below_60"


# --- 4. Other category → review / manual_review_only -------------------------


@pytest.mark.asyncio
async def test_other_category_manual_review(db_session):
    src = await _make_source(db_session, "FBI Press O", 5)
    raw = await _make_raw(db_session, src, "Other Cat One")
    await _process(db_session, src, raw, _ai("Other", ["OtherCo"]), _score(20, level="high"))
    a = await _get_alert(db_session, raw.id)
    assert a.is_published is False
    assert a.publish_decision == "review"
    assert a.pending_review_reason == "manual_review_only"


# --- 5. Credibility below threshold → review / blocked_by_credibility --------


@pytest.mark.asyncio
async def test_low_credibility_blocked(db_session):
    # A generic credibility-3 source (not Krebs/Bleeping) with a High score.
    src = await _make_source(db_session, "Random Blog", 3)
    raw = await _make_raw(db_session, src, "Low Cred One")
    await _process(db_session, src, raw, _ai("Cybercrime", ["LowCredCo"]), _score(20, cred=3, level="high"))
    a = await _get_alert(db_session, raw.id)
    assert a.is_published is False
    assert a.publish_decision == "review"
    assert a.pending_review_reason == "blocked_by_credibility"


# --- 6. Krebs stored cred 3 → auto via effective 4 ---------------------------


@pytest.mark.asyncio
async def test_krebs_stored3_auto_via_effective4(db_session):
    src = await _make_source(db_session, "KrebsOnSecurity", 3)
    raw = await _make_raw(db_session, src, "Krebs Auto One")
    await _process(db_session, src, raw, _ai("Cybercrime", ["KrebsAutoCo"]), _score(18, cred=3, level="high"))
    a = await _get_alert(db_session, raw.id)
    assert a.is_published is True
    assert a.publish_decision == "auto_publish"


# --- 7. BleepingComputer stored cred 3 + fraud signal → auto -----------------


@pytest.mark.asyncio
async def test_bleeping_stored3_fraud_signal_auto(db_session):
    src = await _make_source(db_session, "BleepingComputer", 3)
    raw = await _make_raw(db_session, src, "Phishing campaign steals banking credentials")
    await _process(
        db_session, src, raw,
        _ai("Cybercrime", ["BleepAutoCo"], summary="A phishing account takeover scam."),
        _score(18, cred=3, level="high"),
    )
    a = await _get_alert(db_session, raw.id)
    assert a.is_published is True
    assert a.publish_decision == "auto_publish"


# --- 8. BleepingComputer stored cred 3, no fraud signal → review/source_rule --


@pytest.mark.asyncio
async def test_bleeping_stored3_no_signal_review_source_rule(db_session):
    src = await _make_source(db_session, "BleepingComputer", 3)
    raw = await _make_raw(db_session, src, "Microsoft releases security patch")
    # Matched on a NON-fraud keyword and purely technical text → no fraud signal.
    await _process(
        db_session, src, raw,
        _ai("Cybercrime", ["BleepReviewCo"], summary="A routine product patch update."),
        _score(18, cred=3, level="high"),
        keywords=("patch",),
    )
    a = await _get_alert(db_session, raw.id)
    assert a.is_published is False
    assert a.publish_decision == "review"
    assert a.pending_review_reason == "blocked_by_source_rule"


# --- 9. No keyword match → exclude / ai_rejected -----------------------------


@pytest.mark.asyncio
async def test_no_keyword_excluded(db_session):
    src = await _make_source(db_session, "FBI Press NK", 5)
    raw = await _make_raw(db_session, src, "No Keyword One")
    await _process(db_session, src, raw, _ai("Cybercrime", ["x"]), keywords=[])
    a = await _get_alert(db_session, raw.id)
    assert a.is_relevant is False
    assert a.is_published is False
    assert a.publish_decision == "exclude"
    assert a.is_excluded is True
    assert a.excluded_reason == "no_keyword_match"
    assert a.pending_review_reason == "ai_rejected"


# --- 10. AI marked irrelevant → exclude / ai_rejected ------------------------


@pytest.mark.asyncio
async def test_ai_irrelevant_excluded(db_session):
    src = await _make_source(db_session, "FBI Press IR", 5)
    raw = await _make_raw(db_session, src, "AI Irrelevant One")
    await _process(db_session, src, raw, _ai("Other", [], is_relevant=False))
    a = await _get_alert(db_session, raw.id)
    assert a.is_relevant is False
    assert a.is_published is False
    assert a.publish_decision == "exclude"
    assert a.excluded_reason == "ai_marked_irrelevant"
    assert a.pending_review_reason == "ai_rejected"


# --- 11. AI failure → hold / manual_hold (system failure, not rejection) -----


@pytest.mark.asyncio
async def test_ai_failure_holds(db_session):
    src = await _make_source(db_session, "FBI Press AF", 5)
    raw = await _make_raw(db_session, src, "AI Fail One")
    await _process(db_session, src, raw, ai_result=None, raise_ai=True)
    a = await _get_alert(db_session, raw.id)
    assert a.is_relevant is False
    assert a.is_published is False
    assert a.publish_decision == "hold"
    assert a.is_manual_hold is True
    assert a.is_excluded is False
    assert a.pending_review_reason == "manual_hold"


# --- 12. Decision uses FINAL post-grouping score, not pre-grouping ------------


@pytest.mark.asyncio
async def test_decision_uses_post_grouping_score(db_session):
    """Pre-grouping score is Medium (15 → 60/100). Joining a 2-outlet event lifts
    cross-source to 5 (3 distinct outlets), pushing the final score to 19 (High),
    so the alert auto-publishes — proving the decision uses the final score."""
    entity = "GroupingBumpCo"
    a_src = await _make_source(db_session, "OutletA", 5)
    b_src = await _make_source(db_session, "OutletB", 5)
    c_src = await _make_source(db_session, "OutletC", 5)

    # Seed an event with TWO distinct outlets (so a 3rd outlet → cross-source 5).
    from app.pipeline.event_grouper import find_or_create_event

    async def _seed(src, title):
        raw = await _make_raw(db_session, src, title)
        alert = ProcessedAlert(
            raw_item_id=raw.id, primary_category="Cybercrime",
            entities_json={"names": [entity]}, risk_level="high",
            signal_score_total=19, score_source_credibility=5, score_financial_impact=3,
            score_victim_scale=4, score_cross_source=5, score_trend_acceleration=2,
            is_relevant=True, matched_keywords=["fraud"],
            processed_at=datetime.now(timezone.utc),
        )
        db_session.add(alert)
        await db_session.flush()
        alert.raw_item = raw
        await find_or_create_event(alert, db_session)
        await db_session.commit()

    await _seed(a_src, "Seed A")
    await _seed(b_src, "Seed B")

    # Now process the 3rd-outlet alert. Pre-grouping factors sum (cross=1) to 15
    # → Medium. After joining the event (3 distinct outlets → cross 5) the recalc
    # makes the total 5+3+4+5+2 = 19 → High → auto_publish.
    raw_c = await _make_raw(db_session, c_src, "Bump Trigger")
    await _process(
        db_session, c_src, raw_c,
        _ai("Cybercrime", [entity]),
        _score(15, cross=1, cred=5, fin=3, victim=4, trend=2, level="medium"),
    )
    a = await _get_alert(db_session, raw_c.id)
    assert a.signal_score_total == 19  # lifted by event grouping
    assert a.risk_band == "high"
    assert a.is_published is True
    assert a.publish_decision == "auto_publish"
