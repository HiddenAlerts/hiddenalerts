"""OPEN-4 — V1 historical re-classification tool tests.

Isolated in-memory rows only. Verifies selection, full re-score (effective
credibility + distinct-outlet cross-source), the NEVER-auto-publish invariant,
topic-veto routing, transactional apply + audit rows, drift refusal, and
idempotency.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.models.event import Event, EventSource
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.review import AlertReview
from app.models.source import Source
from app.tools import v1_historical_reclassification as HRC
from app.tools.v1_historical_reclassification import (
    CONFIRM_TOKEN,
    run_apply,
    run_dry_run,
    run_recorrect,
)

_IDX = [0]


@pytest_asyncio.fixture(autouse=True)
async def _isolate_backlog(db_session):
    """The tool selects the backlog broadly, but the test engine shares one
    StaticPool SQLite DB across tests (committed rows persist). Clear the relevant
    tables before each test so selection/count assertions see only this test's rows.
    """
    for model in (AlertReview, EventSource, Event, ProcessedAlert, RawItem, Source):
        await db_session.execute(delete(model))
    await db_session.commit()
    yield


async def _seed(
    db_session,
    *,
    category="Cybercrime",
    is_relevant=True,
    is_published=False,
    publish_decision=None,
    cred=4,
    score_total=22,
    cred_factor=4,
    cross_factor=5,
    fin=5,
    vic=4,
    trend=4,
    title="Fraud ring busted",
    summary="A fraud scheme defrauded victims.",
    keywords=("fraud",),
):
    _IDX[0] += 1
    idx = _IDX[0]
    src = Source(name=f"S{idx}", base_url=f"https://e{idx}.com", source_type="rss",
                 credibility_score=cred, adapter_class="RSSAdapter")
    db_session.add(src)
    await db_session.flush()
    raw = RawItem(source_id=src.id, item_url=f"https://e{idx}.com/a", title=title, url_hash=f"h{idx}")
    db_session.add(raw)
    await db_session.flush()
    a = ProcessedAlert(
        raw_item_id=raw.id, primary_category=category, risk_level="high",
        signal_score_total=score_total, score_source_credibility=cred_factor,
        score_cross_source=cross_factor, score_financial_impact=fin,
        score_victim_scale=vic, score_trend_acceleration=trend,
        is_relevant=is_relevant, is_published=is_published, publish_decision=publish_decision,
        summary=summary, matched_keywords=list(keywords),
        processed_at=datetime.now(timezone.utc),
        published_at=datetime.now(timezone.utc) if is_published else None,
    )
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)
    return a


async def _link_event(db_session, alert, outlet_names):
    """Attach the alert to an event with the given distinct outlet names."""
    ev = Event(title="E", category="Cybercrime")
    db_session.add(ev)
    await db_session.flush()
    for name in outlet_names:
        db_session.add(EventSource(event_id=ev.id, alert_id=alert.id, source_name=name))
    await db_session.commit()


async def _snapshot(db_session, alert_id):
    a = (await db_session.execute(select(ProcessedAlert).where(ProcessedAlert.id == alert_id))).scalar_one()
    await db_session.refresh(a)
    return a


async def _reviews_for(db_session, alert_id):
    return (await db_session.execute(select(AlertReview).where(AlertReview.alert_id == alert_id))).scalars().all()


async def _prior_report(db_session, path: Path, **filters):
    report = await run_dry_run(db_session, **filters)
    assert report["passed"] is True
    path.write_text(json.dumps(report), encoding="utf-8")
    return report


# --- 1. Selection -------------------------------------------------------------


@pytest.mark.asyncio
async def test_selection_only_relevant_unclassified_unpublished(db_session):
    keep = await _seed(db_session)                                  # selected
    await _seed(db_session, is_published=True)                      # already published
    await _seed(db_session, publish_decision="review")             # already classified
    await _seed(db_session, is_relevant=False)                     # irrelevant
    report = await run_dry_run(db_session)
    ids = {p["alert_id"] for p in report["planned"]}
    assert ids == {keep.id}
    assert report["selected"] == 1


@pytest.mark.asyncio
async def test_in_scope_and_min_score_filters(db_session):
    in_scope_hi = await _seed(db_session, category="Cybercrime", score_total=18)
    await _seed(db_session, category="Other", score_total=18)       # out of scope
    await _seed(db_session, category="Cybercrime", score_total=12)  # below min score
    report = await run_dry_run(db_session, in_scope_only=True, min_internal_score=15)
    assert {p["alert_id"] for p in report["planned"]} == {in_scope_hi.id}


# --- 2. Never auto-publish (the core guard) -----------------------------------


@pytest.mark.asyncio
async def test_publishable_history_is_redirected_to_review(db_session, tmp_path):
    # In-scope, cred-4, very high score → would auto_publish in the live pipeline.
    a = await _seed(db_session, category="Cybercrime", score_total=24,
                    cred_factor=4, cross_factor=5, fin=5, vic=5, trend=5)
    rpt = tmp_path / "dry.json"
    report = await _prior_report(db_session, rpt)
    plan = report["planned"][0]
    assert plan["would_auto_publish"] is True
    assert report["redirected_auto_publish"] == 1
    # The plan NEVER contains auto_publish.
    assert all(p["publish_decision"] != "auto_publish" for p in report["planned"])
    assert plan["bucket"] == "review"
    assert plan["publish_decision"] == "review"
    assert plan["publish_decision_reason"] == "historical_reclassified_publishable"
    assert plan["pending_review_reason"] == "manual_review_only"

    out = await run_apply(db_session, apply=True, dry_run_report_path=rpt,
                          batch_id="b-redirect", confirm=CONFIRM_TOKEN)
    assert out["applied"] is True
    snap = await _snapshot(db_session, a.id)
    assert snap.is_published is False
    assert snap.publish_decision == "review"
    assert snap.publication_state_source == "system_migration"


# --- 3. Full re-score: distinct-outlet cross-source correction ----------------


@pytest.mark.asyncio
async def test_cross_source_recompute_lowers_inflated_score(db_session):
    # Stored cross=5 (3+ outlets) but the event really has ONE distinct outlet.
    a = await _seed(db_session, score_total=18, cred_factor=4, cross_factor=5,
                    fin=3, vic=3, trend=3)
    await _link_event(db_session, a, ["Same Outlet", "same outlet", " Same Outlet "])  # 1 distinct
    report = await run_dry_run(db_session)
    plan = report["planned"][0]
    assert plan["rescored"] is True
    assert plan["new_score"] < plan["stored_score"]   # cross 5 → 1 lowers the total
    assert report["rescored"] == 1


@pytest.mark.asyncio
async def test_cross_source_recompute_keeps_multi_outlet_high(db_session):
    a = await _seed(db_session, score_total=18, cred_factor=4, cross_factor=5,
                    fin=3, vic=3, trend=3)
    await _link_event(db_session, a, ["Reuters", "AP", "BBC"])  # 3 distinct → cross stays 5
    report = await run_dry_run(db_session)
    plan = report["planned"][0]
    assert plan["new_score"] == plan["stored_score"]  # unchanged (cred 4→4, cross 5→5)


# --- 4. Topic veto routing ----------------------------------------------------


@pytest.mark.asyncio
async def test_topic_vetoed_history_routed_to_review(db_session):
    a = await _seed(db_session, category="Cybercrime", score_total=22,
                    title="Nation-state espionage breaches a defense network",
                    summary="A foreign intelligence operation.", keywords=("espionage",))
    report = await run_dry_run(db_session)
    plan = report["planned"][0]
    assert plan["topic_vetoed"] is True
    assert plan["bucket"] == "review"
    assert plan["publish_decision_reason"] == "blocked_by_topic_scope"
    assert plan["pending_review_reason"] == "blocked_by_topic_scope"
    assert report["topic_vetoed"] == 1


@pytest.mark.asyncio
async def test_offtopic_below60_is_excluded_not_reviewed(db_session):
    """OPEN-4 policy: an out-of-scope item that scores below-60 is EXCLUDED, not
    pulled into the review queue (exclude wins over the topic veto)."""
    a = await _seed(db_session, category="Cybercrime", score_total=12,
                    cred_factor=4, cross_factor=1, fin=3, vic=2, trend=2,
                    title="Nation-state espionage breaches a defense network",
                    summary="A foreign intelligence operation.", keywords=("espionage",))
    report = await run_dry_run(db_session)
    plan = report["planned"][0]
    assert plan["topic_vetoed"] is True          # still flagged out-of-scope
    assert plan["bucket"] == "exclude"           # but excluded, not reviewed
    assert plan["new_band"] == "below_60"


# --- 5. Exclude (below-60) ----------------------------------------------------


@pytest.mark.asyncio
async def test_below_60_excluded(db_session):
    a = await _seed(db_session, score_total=12, cred_factor=4, cross_factor=1,
                    fin=3, vic=2, trend=2)
    report = await run_dry_run(db_session)
    plan = report["planned"][0]
    assert plan["bucket"] == "exclude"
    assert plan["publish_decision"] == "exclude"
    assert plan["new_band"] == "below_60"


# --- 6. Apply: state + audit rows + no-publish invariant ----------------------


@pytest.mark.asyncio
async def test_apply_writes_state_and_audit_rows(db_session, tmp_path):
    a = await _seed(db_session, score_total=22)               # → review
    b = await _seed(db_session, score_total=12, cred_factor=4, cross_factor=1,
                    fin=3, vic=2, trend=2)                    # → exclude
    rpt = tmp_path / "dry.json"
    await _prior_report(db_session, rpt)

    out = await run_apply(db_session, apply=True, dry_run_report_path=rpt,
                          batch_id="v1-historical-test", confirm=CONFIRM_TOKEN)
    assert out["applied"] is True
    assert out["counts"]["total"] == 2
    assert out["review_records_created"] == 2

    for alert in (a, b):
        snap = await _snapshot(db_session, alert.id)
        assert snap.is_published is False                     # invariant: never published
        assert snap.publication_state_source == "system_migration"
        assert snap.publish_decision in ("review", "exclude", "hold")
        rows = await _reviews_for(db_session, alert.id)
        assert len(rows) == 1
        assert rows[0].decision_source == "system_migration"
        assert rows[0].review_batch_id == "v1-historical-test"
        assert rows[0].review_status.startswith("historical_")


@pytest.mark.asyncio
async def test_apply_is_idempotent(db_session, tmp_path):
    await _seed(db_session, score_total=22)
    rpt = tmp_path / "dry.json"
    await _prior_report(db_session, rpt)
    await run_apply(db_session, apply=True, dry_run_report_path=rpt,
                    batch_id="b-idem", confirm=CONFIRM_TOKEN)
    # Re-run: the now-classified row is no longer selected.
    again = await run_dry_run(db_session)
    assert again["selected"] == 0


# --- 7. Transactional rollback ------------------------------------------------


@pytest.mark.asyncio
async def test_apply_rolls_back_on_error(db_session, tmp_path):
    a = await _seed(db_session, score_total=22)
    b = await _seed(db_session, score_total=21)
    a_id, b_id = a.id, b.id  # capture before run_apply's rollback expires the ORM objects
    rpt = tmp_path / "dry.json"
    await _prior_report(db_session, rpt)

    calls = {"n": 0}

    def _boom(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("injected failure")
        return HRC.AlertReview(alert_id=args[0], decision_source="system_migration",
                               review_status="historical_review", review_batch_id=kwargs.get("batch_id"))

    with patch.object(HRC, "_make_review_row", side_effect=_boom):
        out = await run_apply(db_session, apply=True, dry_run_report_path=rpt,
                              batch_id="b-rollback", confirm=CONFIRM_TOKEN)
    assert out["mode"] == "apply_refused"
    assert any("rolled_back" in e for e in out["errors"])
    # No partial state: both alerts unchanged, no audit rows.
    for alert_id in (a_id, b_id):
        snap = await _snapshot(db_session, alert_id)
        assert snap.publish_decision is None
        assert await _reviews_for(db_session, alert_id) == []


# --- 8. Guard refusals + drift ------------------------------------------------


@pytest.mark.asyncio
async def test_apply_guards(db_session, tmp_path):
    await _seed(db_session, score_total=22)
    rpt = tmp_path / "dry.json"
    await _prior_report(db_session, rpt)

    no_confirm = await run_apply(db_session, apply=True, dry_run_report_path=rpt, batch_id="b")
    assert no_confirm["mode"] == "apply_refused" and any("confirm_required" in e for e in no_confirm["errors"])

    no_report = await run_apply(db_session, apply=True, batch_id="b", confirm=CONFIRM_TOKEN)
    assert any("dry_run_report_required" in e for e in no_report["errors"])

    no_batch = await run_apply(db_session, apply=True, dry_run_report_path=rpt, confirm=CONFIRM_TOKEN)
    assert any("batch_id_required" in e for e in no_batch["errors"])


@pytest.mark.asyncio
async def test_apply_refuses_on_drift(db_session, tmp_path):
    await _seed(db_session, category="Cybercrime", score_total=18)
    rpt = tmp_path / "dry.json"
    await _prior_report(db_session, rpt, in_scope_only=True, min_internal_score=15)
    # New in-scope alert added AFTER the prior report → selection set drifts.
    await _seed(db_session, category="Investment Fraud", score_total=19)
    out = await run_apply(db_session, apply=True, dry_run_report_path=rpt,
                          batch_id="b-drift", confirm=CONFIRM_TOKEN,
                          in_scope_only=True, min_internal_score=15)
    assert out["mode"] == "apply_refused"
    assert any("id_drift" in e for e in out["errors"])


@pytest.mark.asyncio
async def test_dry_run_does_not_mutate(db_session):
    a = await _seed(db_session, score_total=22)
    await run_dry_run(db_session)
    snap = await _snapshot(db_session, a.id)
    assert snap.publish_decision is None
    assert snap.publication_state_source is None


# --- 9. Re-scored score/factors are persisted (score/band/factors agree) -------


@pytest.mark.asyncio
async def test_apply_persists_rescored_score_and_factors(db_session, tmp_path):
    from app.pipeline.publishing.risk_bands import compute_risk_band
    from app.pipeline.signal_scorer import derive_risk_level
    a = await _seed(db_session, score_total=22, cred_factor=4, cross_factor=5, fin=5, vic=4, trend=4)
    await _link_event(db_session, a, ["Solo Outlet"])  # 1 distinct outlet → cross 5→1
    a_id = a.id
    rpt = tmp_path / "dry.json"
    dry = await _prior_report(db_session, rpt)
    plan = next(p for p in dry["planned"] if p["alert_id"] == a_id)
    assert plan["rescored"] is True
    new_score = plan["new_score"]
    assert new_score == 22 - 4 - 5 + 4 + 1  # cred 4→4 (generic src), cross 5→1

    await run_apply(db_session, apply=True, dry_run_report_path=rpt, batch_id="b-persist", confirm=CONFIRM_TOKEN)
    snap = await _snapshot(db_session, a_id)
    assert snap.signal_score_total == new_score
    assert snap.score_source_credibility == 4
    assert snap.score_cross_source == 1
    assert snap.risk_band == compute_risk_band(new_score).value          # band agrees
    assert snap.risk_level == derive_risk_level(new_score)               # legacy level agrees


@pytest.mark.asyncio
async def test_recorrect_fixes_diverged_band_and_audits(db_session, tmp_path):
    from app.pipeline.publishing.risk_bands import compute_risk_band
    a = await _seed(db_session, score_total=22)
    a_id = a.id
    rpt = tmp_path / "dry.json"
    await _prior_report(db_session, rpt)
    await run_apply(db_session, apply=True, dry_run_report_path=rpt, batch_id="b-src", confirm=CONFIRM_TOKEN)

    # simulate a pre-fix divergence: tamper the band so it disagrees with the score
    snap = await _snapshot(db_session, a_id)
    snap.risk_band = "critical"
    await db_session.commit()

    # recorrect dry-run reports the change and never plans an auto_publish
    dry = await run_recorrect(db_session, source_batch_id="b-src")
    assert dry["mode"] == "recorrect_dry_run"
    assert dry["auto_publish_in_plan"] == []
    assert any(c["alert_id"] == a_id for c in dry["changes"])

    # guard: confirm required for apply
    refused = await run_recorrect(db_session, source_batch_id="b-src", apply=True)
    assert refused["mode"] == "apply_refused"

    out = await run_recorrect(db_session, source_batch_id="b-src", apply=True, confirm=CONFIRM_TOKEN)
    assert out["applied"] is True and out["corrected"] == 1
    snap2 = await _snapshot(db_session, a_id)
    assert snap2.is_published is False
    assert snap2.risk_band == compute_risk_band(snap2.signal_score_total).value  # band fixed
    rows = await _reviews_for(db_session, a_id)
    assert any(r.review_batch_id == "b-src-recorrect" for r in rows)

    # idempotent: a second recorrect finds nothing to change
    again = await run_recorrect(db_session, source_batch_id="b-src")
    assert again["changes"] == []
