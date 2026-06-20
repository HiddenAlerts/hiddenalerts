"""V1 Slice 7C — Candidate Backfill APPLY tool tests.

All tests use temporary CSVs + isolated test-DB rows (never Ken's real file).
A small ``expected_counts`` is injected so we don't need to seed 119 alerts; the
CLI default remains 48/44/27.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.review import AlertReview
from app.models.source import Source
from app.tools import v1_candidate_backfill_apply as APPLY
from app.tools.v1_candidate_backfill_apply import (
    CONFIRM_TOKEN,
    run_apply,
    validate_dry_run_report_for_apply,
)
from app.tools.v1_candidate_backfill_dry_run import run_dry_run

_EXPECTED = {"approved": 1, "rejected": 1, "keep_later": 1}


async def _seed(db_session, *, idx, is_relevant=True, is_published=False, score=22):
    src = Source(name=f"S{idx}", base_url=f"https://e{idx}.com", source_type="rss",
                 credibility_score=4, adapter_class="RSSAdapter")
    db_session.add(src)
    await db_session.flush()
    raw = RawItem(source_id=src.id, item_url=f"https://e{idx}.com/a", title=f"T{idx}", url_hash=f"h{idx}")
    db_session.add(raw)
    await db_session.flush()
    a = ProcessedAlert(
        raw_item_id=raw.id, primary_category="Cybercrime", risk_level="high",
        signal_score_total=score, is_relevant=is_relevant, is_published=is_published,
        matched_keywords=["fraud"], processed_at=datetime.now(timezone.utc),
        published_at=datetime.now(timezone.utc) if is_published else None,
    )
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)
    return a


def _write_csv(tmp_path, rows, name="decisions.csv"):
    p = tmp_path / name
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["alert_id", "decision"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


async def _seed_one_of_each(db_session, base=100):
    a = await _seed(db_session, idx=base + 1)             # approved (relevant, unpublished)
    r = await _seed(db_session, idx=base + 2)             # rejected
    k = await _seed(db_session, idx=base + 3)             # keep_later
    return a, r, k


def _csv_for(tmp_path, a, r, k, name="decisions.csv"):
    return _write_csv(tmp_path, [
        {"alert_id": a.id, "decision": "approved"},
        {"alert_id": r.id, "decision": "rejected"},
        {"alert_id": k.id, "decision": "keep_later"},
    ], name=name)


async def _make_prior_report(db_session, csv_path, path: Path):
    """Generate a passing full-DB dry-run report and write it to disk."""
    report = await run_dry_run(csv_path, session=db_session, expected_counts=_EXPECTED)
    assert report["passed"] is True
    path.write_text(json.dumps(report), encoding="utf-8")
    return report


async def _snapshot(db_session, alert_id):
    a = (await db_session.execute(select(ProcessedAlert).where(ProcessedAlert.id == alert_id))).scalar_one()
    await db_session.refresh(a)
    return a


# --- 1. Dry-run only (no --apply) does not mutate -----------------------------


@pytest.mark.asyncio
async def test_no_apply_is_dry_run_only(db_session, tmp_path):
    a, r, k = await _seed_one_of_each(db_session, base=100)
    csv_path = _csv_for(tmp_path, a, r, k)
    report = await run_apply(csv_path, session=db_session, apply=False, expected_counts=_EXPECTED)
    assert report["applied"] is False
    assert report["mode"] == "dry_run"
    assert (await _snapshot(db_session, a.id)).is_published is False  # unchanged


# --- 2-4. Flag gates ----------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_without_dry_run_report_refused(db_session, tmp_path):
    a, r, k = await _seed_one_of_each(db_session, base=110)
    csv_path = _csv_for(tmp_path, a, r, k)
    report = await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                             confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert report["applied"] is False
    assert "dry_run_report_required_for_apply" in report["errors"]


@pytest.mark.asyncio
async def test_apply_without_batch_id_refused(db_session, tmp_path):
    a, r, k = await _seed_one_of_each(db_session, base=120)
    csv_path = _csv_for(tmp_path, a, r, k)
    prior = tmp_path / "prior.json"
    await _make_prior_report(db_session, csv_path, prior)
    report = await run_apply(csv_path, session=db_session, apply=True,
                             dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert report["applied"] is False
    assert "batch_id_required_for_apply" in report["errors"]


@pytest.mark.asyncio
async def test_apply_without_confirm_refused(db_session, tmp_path):
    a, r, k = await _seed_one_of_each(db_session, base=130)
    csv_path = _csv_for(tmp_path, a, r, k)
    prior = tmp_path / "prior.json"
    await _make_prior_report(db_session, csv_path, prior)
    report = await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                             dry_run_report_path=prior, confirm="WRONG", expected_counts=_EXPECTED)
    assert report["applied"] is False
    assert any("confirm_required" in e for e in report["errors"])


# --- 5-8. Report validation gates --------------------------------------------


@pytest.mark.asyncio
async def test_parse_only_report_refused(db_session, tmp_path):
    a, r, k = await _seed_one_of_each(db_session, base=140)
    csv_path = _csv_for(tmp_path, a, r, k)
    prior = tmp_path / "prior.json"
    # Build a real passing report, then downgrade its mode to parse-only.
    rep = await _make_prior_report(db_session, csv_path, prior)
    rep["mode"] = "dry_run_file_parse_only"
    prior.write_text(json.dumps(rep), encoding="utf-8")
    report = await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                             dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert report["applied"] is False
    assert any("parse_only" in e for e in report["errors"])


@pytest.mark.asyncio
async def test_failed_report_refused(db_session, tmp_path):
    a, r, k = await _seed_one_of_each(db_session, base=150)
    csv_path = _csv_for(tmp_path, a, r, k)
    prior = tmp_path / "prior.json"
    rep = await _make_prior_report(db_session, csv_path, prior)
    rep["passed"] = False
    rep["blockers"] = ["something"]
    prior.write_text(json.dumps(rep), encoding="utf-8")
    report = await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                             dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert report["applied"] is False
    assert any("not_passed" in e or "has_blockers" in e for e in report["errors"])


@pytest.mark.asyncio
async def test_fresh_mismatch_refused(db_session, tmp_path):
    a, r, k = await _seed_one_of_each(db_session, base=160)
    csv_path = _csv_for(tmp_path, a, r, k)
    prior = tmp_path / "prior.json"
    rep = await _make_prior_report(db_session, csv_path, prior)
    # Tamper the prior report's approved id so it won't match the fresh run.
    rep["planned_actions"]["approved"][0]["alert_id"] = 999999
    prior.write_text(json.dumps(rep), encoding="utf-8")
    report = await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                             dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert report["applied"] is False
    assert any("id_drift_approved" in e for e in report["errors"])


@pytest.mark.asyncio
async def test_count_mismatch_refused(db_session, tmp_path):
    # File has 2 approved but expected says 1 → dry-run won't pass → refused.
    a = await _seed(db_session, idx=170)
    a2 = await _seed(db_session, idx=171)
    csv_path = _write_csv(tmp_path, [
        {"alert_id": a.id, "decision": "approved"},
        {"alert_id": a2.id, "decision": "approved"},
    ])
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps({"mode": "dry_run", "passed": True, "blockers": [],
                                 "db_validation": {"passed": True},
                                 "actual_counts": {"approved": 1, "rejected": 1, "keep_later": 1},
                                 "planned_actions": {"approved": [], "rejected": [], "keep_later": []}}),
                     encoding="utf-8")
    report = await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                             dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert report["applied"] is False


# --- 9-12, 15-16, 20. Successful apply ---------------------------------------


@pytest.mark.asyncio
async def test_successful_apply_states_and_audit(db_session, client, tmp_path):
    a, r, k = await _seed_one_of_each(db_session, base=200)
    csv_path = _csv_for(tmp_path, a, r, k)
    prior = tmp_path / "prior.json"
    await _make_prior_report(db_session, csv_path, prior)

    report = await run_apply(
        csv_path, session=db_session, apply=True, batch_id="batch-7c",
        dry_run_report_path=prior, confirm=CONFIRM_TOKEN, user_id=None, expected_counts=_EXPECTED,
    )
    assert report["applied"] is True
    assert report["counts"] == {"approved": 1, "rejected": 1, "keep_later": 1, "total": 3}
    assert report["review_records_created"] == 3
    assert report["updated_alert_ids"]["approved"] == [a.id]
    assert report["publication_state_source"] == "candidate_backfill"

    # 9. approved
    av = await _snapshot(db_session, a.id)
    assert av.is_published is True and av.published_by_rule is False
    assert av.publish_decision == "auto_publish"
    assert av.publish_decision_reason == "candidate_backfill_approved"
    assert av.pending_review_reason is None and av.is_excluded is False
    assert av.publication_state_source == "candidate_backfill"
    assert av.publishing_policy_version == "v1.0" and av.risk_band == "critical"
    # 10. rejected
    rv = await _snapshot(db_session, r.id)
    assert rv.is_published is False and rv.is_excluded is True
    assert rv.publish_decision == "exclude"
    assert rv.pending_review_reason == "manual_rejected"
    assert rv.excluded_reason == "candidate_backfill_rejected"
    assert rv.published_by_user_id is None
    # 11. keep_later
    kv = await _snapshot(db_session, k.id)
    assert kv.is_published is False and kv.is_manual_hold is True
    assert kv.publish_decision == "hold" and kv.pending_review_reason == "manual_hold"

    # 12. audit rows
    reviews = (await db_session.execute(
        select(AlertReview).where(AlertReview.review_batch_id == "batch-7c")
    )).scalars().all()
    assert len(reviews) == 3
    assert {rv.decision_source for rv in reviews} == {"candidate_backfill"}
    statuses = {rv.alert_id: rv.review_status for rv in reviews}
    assert statuses[a.id] == "approved"
    assert statuses[r.id] == "false_positive"
    assert statuses[k.id] == "manual_hold"

    # 15. public API does not return rejected/held/the rows
    pub = await client.get("/api/alerts")
    pub_ids = {x["id"] for x in pub.json()["alerts"]}
    assert r.id not in pub_ids and k.id not in pub_ids


# --- 13. Transaction rollback -------------------------------------------------


@pytest.mark.asyncio
async def test_apply_rolls_back_on_failure(db_session, tmp_path):
    a, r, k = await _seed_one_of_each(db_session, base=300)
    # Capture ids as plain ints: the rollback inside run_apply expires the seed
    # ORM objects, so reading a.id afterwards would trigger (forbidden) sync IO.
    ids = [a.id, r.id, k.id]
    csv_path = _csv_for(tmp_path, a, r, k)
    prior = tmp_path / "prior.json"
    await _make_prior_report(db_session, csv_path, prior)

    calls = {"n": 0}
    real = APPLY._apply_decision_to_alert

    def _boom(alert, decision, *, now, user_id):
        calls["n"] += 1
        if calls["n"] == 2:  # fail after the first row is mutated
            raise RuntimeError("simulated mid-apply failure")
        return real(alert, decision, now=now, user_id=user_id)

    with patch.object(APPLY, "_apply_decision_to_alert", _boom):
        report = await run_apply(
            csv_path, session=db_session, apply=True, batch_id="batch-fail",
            dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED,
        )
    assert report["applied"] is False
    assert any("apply_failed_rolled_back" in e for e in report["errors"])

    # No partial state: nothing published/excluded, no audit rows for the batch.
    for alert_id in ids:
        snap = await _snapshot(db_session, alert_id)
        assert snap.publish_decision is None
        assert snap.publication_state_source is None
        assert snap.is_published is False
    reviews = (await db_session.execute(
        select(AlertReview).where(AlertReview.review_batch_id == "batch-fail")
    )).scalars().all()
    assert reviews == []


# --- 14. Re-apply after success is refused ------------------------------------


@pytest.mark.asyncio
async def test_reapply_after_success_refused(db_session, tmp_path):
    a, r, k = await _seed_one_of_each(db_session, base=400)
    csv_path = _csv_for(tmp_path, a, r, k)
    prior = tmp_path / "prior.json"
    await _make_prior_report(db_session, csv_path, prior)

    first = await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                            dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert first["applied"] is True

    second = await run_apply(csv_path, session=db_session, apply=True, batch_id="b2",
                             dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert second["applied"] is False
    # approved alert is now already-published → fresh dry-run blocks it.
    assert any("already_published" in e for e in second["errors"])


# --- 16. Internal filter for candidate_backfill ------------------------------


@pytest.mark.asyncio
async def test_internal_filter_candidate_backfill(db_session, client, tmp_path):
    from app.auth import create_access_token, hash_password
    from app.models.user import User
    import uuid

    a, r, k = await _seed_one_of_each(db_session, base=500)
    csv_path = _csv_for(tmp_path, a, r, k)
    prior = tmp_path / "prior.json"
    await _make_prior_report(db_session, csv_path, prior)
    await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                    dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)

    user = User(email=f"adm_{uuid.uuid4().hex[:8]}@t.com", password_hash=hash_password("x"),
                is_active=True, role="admin")
    db_session.add(user)
    await db_session.commit()
    token = create_access_token({"sub": str(user.id)})
    resp = await client.get("/api/v1/alerts?publication_state_source=candidate_backfill",
                            headers={"Cookie": f"access_token={token}"})
    assert resp.status_code == 200
    rows = resp.json()
    assert all(x["publication_state_source"] == "candidate_backfill" for x in rows)
    assert {a.id, r.id, k.id}.issubset({x["id"] for x in rows})


# --- 17-19. Pre-mutation DB blockers refused ---------------------------------


@pytest.mark.asyncio
async def test_approved_irrelevant_refused(db_session, tmp_path):
    a = await _seed(db_session, idx=600, is_relevant=False)
    r = await _seed(db_session, idx=601)
    k = await _seed(db_session, idx=602)
    csv_path = _csv_for(tmp_path, a, r, k)
    # A "prior" report claiming pass — fresh dry-run must catch the irrelevant one.
    prior = tmp_path / "prior.json"
    rep = await run_dry_run(csv_path, session=db_session, expected_counts=_EXPECTED)
    rep["passed"] = True  # pretend it passed to test the fresh-run guard
    rep["blockers"] = []
    rep["db_validation"]["passed"] = True
    rep["db_validation"]["approved_irrelevant_ids"] = []
    prior.write_text(json.dumps(rep), encoding="utf-8")
    report = await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                             dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert report["applied"] is False
    assert any("approved_irrelevant" in e for e in report["errors"])
    assert (await _snapshot(db_session, a.id)).publish_decision is None


@pytest.mark.asyncio
async def test_missing_id_refused(db_session, tmp_path):
    r = await _seed(db_session, idx=610)
    k = await _seed(db_session, idx=611)
    csv_path = _write_csv(tmp_path, [
        {"alert_id": 9999999, "decision": "approved"},
        {"alert_id": r.id, "decision": "rejected"},
        {"alert_id": k.id, "decision": "keep_later"},
    ])
    prior = tmp_path / "prior.json"
    rep = await run_dry_run(csv_path, session=db_session, expected_counts=_EXPECTED)
    prior.write_text(json.dumps(rep), encoding="utf-8")
    report = await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                             dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert report["applied"] is False
    assert any("missing_ids" in e or "not_passed" in e for e in report["errors"])


@pytest.mark.asyncio
async def test_already_published_approved_refused(db_session, tmp_path):
    a = await _seed(db_session, idx=620, is_published=True)
    r = await _seed(db_session, idx=621)
    k = await _seed(db_session, idx=622)
    csv_path = _csv_for(tmp_path, a, r, k)
    prior = tmp_path / "prior.json"
    rep = await run_dry_run(csv_path, session=db_session, expected_counts=_EXPECTED)
    rep["passed"] = True
    rep["blockers"] = []
    rep["db_validation"]["passed"] = True
    rep["db_validation"]["approved_already_published_ids"] = []
    prior.write_text(json.dumps(rep), encoding="utf-8")
    report = await run_apply(csv_path, session=db_session, apply=True, batch_id="b1",
                             dry_run_report_path=prior, confirm=CONFIRM_TOKEN, expected_counts=_EXPECTED)
    assert report["applied"] is False
    assert any("already_published" in e for e in report["errors"])


# --- validate_dry_run_report_for_apply direct unit -----------------------------


def test_validate_rejects_parse_only_directly():
    prior = {"mode": "dry_run_file_parse_only", "passed": True, "blockers": [],
             "db_validation": {"passed": True}, "actual_counts": {"approved": 1, "rejected": 1, "keep_later": 1},
             "planned_actions": {"approved": [], "rejected": [], "keep_later": []}}
    errors = validate_dry_run_report_for_apply(prior, prior, expected_counts=_EXPECTED)
    assert any("parse_only" in e for e in errors)


# --- regression: reviewed_at must use the server default (naive column) --------


def test_make_review_row_omits_reviewed_at_for_server_default():
    """Regression for the Slice 8B Postgres apply failure: AlertReview.reviewed_at
    is mapped naive (default=func.now()), so the apply tool must NOT set it from a
    tz-aware datetime (asyncpg rejects that on Postgres; SQLite silently accepts).
    The ORM object leaves reviewed_at unset so the server default applies at flush.
    """
    for decision, status in (("approved", "approved"), ("rejected", "false_positive"),
                             ("keep_later", "manual_hold")):
        row = APPLY._make_review_row(5, decision, user_id=None, batch_id="b1")
        assert row.reviewed_at is None, "reviewed_at must be unset (server default)"
        assert row.review_status == status
        assert row.decision_source == "candidate_backfill"
        assert row.review_batch_id == "b1"
