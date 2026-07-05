"""Tests for the V1 review-queue decisions apply tool (Ken's reviewed sheet)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.review import AlertReview
from app.models.source import Source
from app.tools.v1_review_queue_decisions_apply import (
    CONFIRM_TOKEN,
    EXPECTED,
    EXPECTED_COUNTS,
    normalize_decision,
    run_apply,
    run_dry_run,
    validate_parsed,
)


@pytest_asyncio.fixture(autouse=True)
async def _isolate(db_session):
    for model in (AlertReview, ProcessedAlert, RawItem, Source):
        await db_session.execute(delete(model))
    await db_session.commit()
    yield


# --- pure: decision normalization -------------------------------------------


@pytest.mark.parametrize("raw,expected", [
    ("Approve / Publish", "approve_publish"),
    ("Approve/Publish", "approve_publish"),
    ("Approve", "approve_publish"),
    ("Publish", "approve_publish"),
    ("Publish as Analyst Observation", "publish_as_analyst_observation"),
    ("Analyst Observation", "publish_as_analyst_observation"),
    ("Reject /False Positive ", "reject_false_positive"),
    ("Reject / False Positive", "reject_false_positive"),
    ("False Positive", "reject_false_positive"),
    ("Reject / Duplicate", "reject_duplicate"),
    ("Duplicate", "reject_duplicate"),
    ("", None),
    (None, None),
    ("maybe later", None),
])
def test_normalize_decision(raw, expected):
    assert normalize_decision(raw) == expected


def test_duplicate_takes_precedence_over_reject():
    # "Reject / Duplicate" contains "reject" but must map to duplicate.
    assert normalize_decision("Reject / Duplicate") == "reject_duplicate"


def test_analyst_observation_takes_precedence_over_publish():
    assert normalize_decision("Publish as Analyst Observation") == "publish_as_analyst_observation"


# --- pure: parsed validation -------------------------------------------------


def _good_parsed():
    return {"decisions": dict(EXPECTED), "blank_ids": [], "non_integer_ids": [],
            "duplicate_ids": [], "blank_decisions": [], "unknown_decisions": []}


def test_validate_good():
    assert validate_parsed(_good_parsed()) == []


def test_validate_rejects_duplicate_ids():
    p = _good_parsed(); p["duplicate_ids"] = [89]
    assert any("duplicate_ids" in e for e in validate_parsed(p))


def test_validate_rejects_unknown_decision():
    p = _good_parsed(); p["unknown_decisions"] = [{"alert_id": 89, "raw_decision": "huh"}]
    assert any("unknown_decisions" in e for e in validate_parsed(p))


def test_validate_rejects_blank_decision():
    p = _good_parsed(); p["blank_decisions"] = [{"alert_id": 89, "raw_decision": ""}]
    assert any("blank_decisions" in e for e in validate_parsed(p))


def test_validate_rejects_wrong_count():
    p = _good_parsed(); p["decisions"] = {k: v for k, v in list(EXPECTED.items())[:28]}
    errs = validate_parsed(p)
    assert any("expected_29" in e for e in errs) or any("id_set_mismatch" in e for e in errs)


def test_validate_rejects_decision_flip():
    p = _good_parsed()
    p["decisions"] = dict(EXPECTED); p["decisions"][89] = "approve_publish"  # was reject_false_positive
    assert any("decision_mismatch_vs_expected" in e for e in validate_parsed(p))


# --- DB: dry-run (no mutation) then guarded apply ----------------------------


_DEC_TEXT = {
    "approve_publish": "Approve / Publish",
    "publish_as_analyst_observation": "Publish as Analyst Observation",
    "reject_false_positive": "Reject /False Positive ",
    "reject_duplicate": "Reject / Duplicate",
}


def _make_xlsx(path, decisions):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Review Queue"
    ws.append(["alert_id", "title", "Your Review", "Your Notes"])
    for aid, dec in decisions.items():
        ws.append([aid, f"T{aid}", _DEC_TEXT[dec], f"note for {aid}"])
    wb.save(path)


async def _seed(db_session, aid):
    src = Source(name=f"S{aid}", base_url=f"https://e{aid}.com", source_type="rss",
                 credibility_score=4, adapter_class="RSSAdapter")
    db_session.add(src); await db_session.flush()
    raw = RawItem(source_id=src.id, item_url=f"https://e{aid}.com/a", title=f"T{aid}", url_hash=f"h{aid}")
    db_session.add(raw); await db_session.flush()
    a = ProcessedAlert(id=aid, raw_item_id=raw.id, primary_category="Cybercrime", risk_level="high",
                       signal_score_total=18, is_relevant=True, is_published=False,
                       publish_decision="review", pending_review_reason="blocked_by_score",
                       processed_at=datetime.now(timezone.utc))
    db_session.add(a); await db_session.commit()


async def _get(db_session, aid):
    a = (await db_session.execute(select(ProcessedAlert).where(ProcessedAlert.id == aid))).scalar_one()
    await db_session.refresh(a)
    return a


@pytest.mark.asyncio
async def test_dry_run_no_mutation_then_apply(db_session, tmp_path):
    for aid in EXPECTED:
        await _seed(db_session, aid)
    xlsx = tmp_path / "ken.xlsx"
    _make_xlsx(xlsx, EXPECTED)

    dry = await run_dry_run(xlsx, session=db_session, batch_id="b")
    assert dry["passed"] is True
    assert dry["counts_by_decision"] == EXPECTED_COUNTS
    assert dry["db_changes_made"] is False
    assert (await _get(db_session, 843)).publish_decision == "review"  # untouched

    rpt = tmp_path / "dry.json"; rpt.write_text(json.dumps(dry), encoding="utf-8")
    out = await run_apply(xlsx, session=db_session, apply=True, dry_run_report_path=rpt,
                          batch_id="b", confirm=CONFIRM_TOKEN)
    assert out["applied"] is True
    assert out["counts"]["total_applied"] == 29
    assert out["counts"] == {"approve_publish": 13, "publish_as_analyst_observation": 3,
                             "reject_false_positive": 11, "reject_duplicate": 2,
                             "total_applied": 29, "skipped": 0}

    pub = await _get(db_session, 843)  # approve
    assert pub.is_published is True and pub.publish_decision == "auto_publish"
    assert pub.publish_decision_reason == "manual_admin_approved" and pub.publication_state_source == "manual_admin"

    ao = await _get(db_session, 905)  # analyst observation → published as normal
    assert ao.is_published is True and ao.publish_decision == "auto_publish"

    fp = await _get(db_session, 89)  # false positive
    assert fp.is_published is False and fp.publish_decision == "exclude"
    assert fp.pending_review_reason == "manual_rejected" and fp.excluded_reason == "manual_false_positive"

    dup = await _get(db_session, 469)  # duplicate → FP workflow + manual_duplicate reason
    assert dup.is_published is False and dup.publish_decision == "exclude"
    assert dup.publish_decision_reason == "manual_duplicate" and dup.excluded_reason == "manual_duplicate"
    assert dup.pending_review_reason == "manual_rejected"  # enum-valid

    rows = (await db_session.execute(select(AlertReview).where(AlertReview.review_batch_id == "b"))).scalars().all()
    assert len(rows) == 29
    statuses = {r.alert_id: r.review_status for r in rows}
    assert statuses[905] == "analyst_observation" and statuses[469] == "duplicate"
    assert all(r.decision_source == "manual_admin" for r in rows)


@pytest.mark.asyncio
async def test_apply_refused_without_confirm(db_session, tmp_path):
    for aid in EXPECTED:
        await _seed(db_session, aid)
    xlsx = tmp_path / "ken.xlsx"; _make_xlsx(xlsx, EXPECTED)
    dry = await run_dry_run(xlsx, session=db_session, batch_id="b")
    rpt = tmp_path / "dry.json"; rpt.write_text(json.dumps(dry), encoding="utf-8")

    out = await run_apply(xlsx, session=db_session, apply=True, dry_run_report_path=rpt, batch_id="b")
    assert out["mode"] == "apply_refused" and any("confirm_required" in e for e in out["errors"])
    assert (await _get(db_session, 843)).publish_decision == "review"  # nothing changed


@pytest.mark.asyncio
async def test_dry_run_flags_alert_not_in_review(db_session, tmp_path):
    for aid in EXPECTED:
        await _seed(db_session, aid)
    # flip one out of review
    a = await _get(db_session, 89); a.publish_decision = "exclude"; await db_session.commit()
    xlsx = tmp_path / "ken.xlsx"; _make_xlsx(xlsx, EXPECTED)
    dry = await run_dry_run(xlsx, session=db_session, batch_id="b")
    assert dry["passed"] is False
    assert any("not_in_review" in e for e in dry["errors"])
