"""Tests for app.tools.v1_risk_band_normalization.

All tests use isolated test-DB rows only. No production data, no AI, no
rescoring — this tool touches exactly one column (`risk_band`).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.tools import v1_risk_band_normalization as tool_module
from app.tools.v1_risk_band_normalization import CONFIRM_TOKEN, run


async def _seed(
    db_session,
    *,
    idx,
    score: int | None,
    risk_band: str | None = None,
    is_published: bool = False,
    is_relevant: bool = True,
):
    src = Source(
        name=f"NormSrc{idx}", base_url=f"https://norm{idx}.com", source_type="rss",
        credibility_score=4, adapter_class="RSSAdapter",
    )
    db_session.add(src)
    await db_session.flush()
    raw = RawItem(
        source_id=src.id, item_url=f"https://norm{idx}.com/a", title=f"T{idx}", url_hash=f"nh{idx}"
    )
    db_session.add(raw)
    await db_session.flush()
    a = ProcessedAlert(
        raw_item_id=raw.id, primary_category="Cybercrime", risk_level="medium",
        signal_score_total=score, risk_band=risk_band,
        is_relevant=is_relevant, is_published=is_published,
        matched_keywords=["fraud"], processed_at=datetime.now(timezone.utc),
        published_at=datetime.now(timezone.utc) if is_published else None,
        publish_decision="review", publication_state_source="auto_policy",
    )
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)
    return a


@pytest.mark.asyncio
class TestDryRun:
    async def test_dry_run_proposes_correct_bands_without_writing_anything(self, db_session):
        crit = await _seed(db_session, idx=1, score=21, risk_band=None)
        high = await _seed(db_session, idx=2, score=19, risk_band=None)
        med = await _seed(db_session, idx=3, score=16, risk_band=None)
        below = await _seed(db_session, idx=4, score=8, risk_band=None)
        already_set = await _seed(db_session, idx=5, score=21, risk_band="critical")

        report = await run(db_session, apply=False)

        assert report["mode"] == "dry_run"
        assert report["applied"] is False
        assert crit.id in report["alert_ids_by_band"]["critical"]
        assert high.id in report["alert_ids_by_band"]["high"]
        assert med.id in report["alert_ids_by_band"]["medium"]
        assert below.id in report["alert_ids_by_band"]["below_60"]
        # Rows that already have a risk_band are out of scope entirely.
        assert already_set.id not in (
            report["alert_ids_by_band"]["critical"] + report["alert_ids_by_band"]["high"]
        )

        # Nothing was written.
        for alert in (crit, high, med, below):
            await db_session.refresh(alert)
            assert alert.risk_band is None

    async def test_dry_run_never_touches_score_or_publication_state(self, db_session):
        alert = await _seed(db_session, idx=10, score=21, risk_band=None, is_published=True)
        original_score = alert.signal_score_total
        original_published_at = alert.published_at
        original_publish_decision = alert.publish_decision
        original_state_source = alert.publication_state_source

        await run(db_session, apply=False)
        await db_session.refresh(alert)

        assert alert.risk_band is None  # dry-run never writes
        assert alert.signal_score_total == original_score
        assert alert.is_published is True
        assert alert.published_at == original_published_at
        assert alert.publish_decision == original_publish_decision
        assert alert.publication_state_source == original_state_source

    async def test_unscored_report_counters_are_semantically_correct(self, db_session):
        """Matches confirmed live pipeline behavior: every current terminal
        path that completes with no score writes risk_band=below_60, so the
        default normalization treats equivalent legacy rows the same way.
        The report must distinguish "existed" from "included" from "excluded"
        — no field may claim a row was skipped when it was actually included.
        """
        unscored = await _seed(db_session, idx=20, score=None, risk_band=None)
        report = await run(db_session, apply=False)

        assert report["include_unscored"] is True
        assert unscored.id in report["alert_ids_by_band"]["below_60"]
        assert report["unscored_candidates"] >= 1
        assert report["unscored_included"] == report["unscored_candidates"]
        assert report["unscored_excluded"] == 0

    async def test_unscored_rows_excluded_when_requested(self, db_session):
        unscored = await _seed(db_session, idx=21, score=None, risk_band=None)
        report = await run(db_session, apply=False, include_unscored=False)

        all_proposed = [i for ids in report["alert_ids_by_band"].values() for i in ids]
        assert unscored.id not in all_proposed
        assert report["unscored_candidates"] >= 1
        assert report["unscored_included"] == 0
        assert report["unscored_excluded"] == report["unscored_candidates"]

    async def test_null_count_before_and_after_are_reported(self, db_session):
        await _seed(db_session, idx=22, score=21, risk_band=None)
        already_normalized = await _seed(db_session, idx=23, score=8, risk_band="below_60")

        included = await run(db_session, apply=False)
        assert included["risk_band_null_count_before"] >= 1
        assert included["risk_band_null_count_after_expected"] == 0
        assert already_normalized.id not in [
            i for ids in included["alert_ids_by_band"].values() for i in ids
        ]

        excluded = await run(db_session, apply=False, include_unscored=False)
        # Excluding unscored rows leaves them NULL — "after" must reflect that.
        unscored_present = await _seed(db_session, idx=24, score=None, risk_band=None)
        excluded2 = await run(db_session, apply=False, include_unscored=False)
        assert excluded2["risk_band_null_count_after_expected"] >= 1
        assert unscored_present.id not in [
            i for ids in excluded2["alert_ids_by_band"].values() for i in ids
        ]


@pytest.mark.asyncio
class TestApply:
    async def test_apply_without_confirm_is_refused_and_writes_nothing(self, db_session):
        alert = await _seed(db_session, idx=30, score=21, risk_band=None)
        report = await run(db_session, apply=True, confirm=None)

        assert report["mode"] == "apply_refused"
        assert "errors" in report
        await db_session.refresh(alert)
        assert alert.risk_band is None

    async def test_apply_with_wrong_confirm_token_is_refused(self, db_session):
        alert = await _seed(db_session, idx=31, score=21, risk_band=None)
        report = await run(db_session, apply=True, confirm="WRONG_TOKEN")

        assert report["mode"] == "apply_refused"
        await db_session.refresh(alert)
        assert alert.risk_band is None

    async def test_apply_writes_only_risk_band(self, db_session):
        alert = await _seed(
            db_session, idx=32, score=19, risk_band=None, is_published=True, is_relevant=True
        )
        original_score = alert.signal_score_total
        original_published_at = alert.published_at
        original_is_published = alert.is_published
        original_publish_decision = alert.publish_decision
        original_state_source = alert.publication_state_source

        report = await run(db_session, apply=True, confirm=CONFIRM_TOKEN)

        assert report["mode"] == "apply"
        assert report["applied"] is True
        await db_session.refresh(alert)
        assert alert.risk_band == "high"
        # Nothing else moved.
        assert alert.signal_score_total == original_score
        assert alert.published_at == original_published_at
        assert alert.is_published == original_is_published
        assert alert.publish_decision == original_publish_decision
        assert alert.publication_state_source == original_state_source

    async def test_apply_is_idempotent(self, db_session):
        alert = await _seed(db_session, idx=33, score=21, risk_band=None)

        first = await run(db_session, apply=True, confirm=CONFIRM_TOKEN)
        assert first["proposed_assignments_total"] >= 1
        await db_session.refresh(alert)
        assert alert.risk_band == "critical"

        second = await run(db_session, apply=True, confirm=CONFIRM_TOKEN)
        assert alert.id not in [
            i for ids in second["alert_ids_by_band"].values() for i in ids
        ], "already-normalized rows must not be re-selected"
        await db_session.refresh(alert)
        assert alert.risk_band == "critical", "second run must not alter an already-set band"

    async def test_apply_never_touches_rows_that_already_have_a_band(self, db_session):
        alert = await _seed(db_session, idx=34, score=8, risk_band="medium")
        await run(db_session, apply=True, confirm=CONFIRM_TOKEN)
        await db_session.refresh(alert)
        assert alert.risk_band == "medium", "pre-existing band must never be overwritten"

    async def test_apply_with_nothing_to_do_succeeds_as_a_noop(self, db_session):
        await _seed(db_session, idx=35, score=21, risk_band="critical")
        report = await run(db_session, apply=True, confirm=CONFIRM_TOKEN)
        assert report["applied"] is True
        assert report["proposed_assignments_total"] == 0

    async def test_second_dry_run_after_full_normalization_finds_zero_candidates(
        self, db_session
    ):
        await _seed(db_session, idx=36, score=21, risk_band=None)
        await _seed(db_session, idx=37, score=None, risk_band=None)  # unscored, included by default

        applied = await run(db_session, apply=True, confirm=CONFIRM_TOKEN)
        assert applied["applied"] is True

        second = await run(db_session, apply=False)
        assert second["candidates_considered"] == 0
        assert second["proposed_assignments_total"] == 0
        assert second["risk_band_null_count_before"] == 0


@pytest.mark.asyncio
class TestConcurrencySafety:
    """SELECT ... FOR UPDATE plus the defensive re-check together close the
    race between the planning read (`_select_candidates`) and apply's own
    locked re-fetch/write. A real second concurrent session isn't practical
    against the isolated in-memory SQLite test DB (no cross-connection
    row locking, and `_maybe_lock` deliberately skips FOR UPDATE there — see
    the tool's own docstring). These tests instead drive the exact code path
    a genuine concurrent writer would produce: they patch the planning read to
    return the state as it existed *before* a concurrent commit, while the row
    actually committed to the DB has already moved — proving apply's locked
    re-fetch, not the stale plan, is what governs the write.
    """

    async def test_concurrent_risk_band_change_is_not_overwritten(self, db_session, monkeypatch):
        alert = await _seed(db_session, idx=40, score=21, risk_band=None)

        async def _stale_select(session):
            return [(alert.id, 21, False)]  # the pre-concurrency snapshot

        # A concurrent writer (e.g. manual review) sets the band directly.
        alert.risk_band = "high"
        await db_session.commit()

        monkeypatch.setattr(tool_module, "_select_candidates", _stale_select)
        report = await tool_module.run(db_session, apply=True, confirm=CONFIRM_TOKEN)

        assert report["mode"] == "apply_refused"
        await db_session.refresh(alert)
        assert alert.risk_band == "high", "the concurrently-written band must survive untouched"

    async def test_concurrent_score_change_does_not_produce_a_stale_band(
        self, db_session, monkeypatch
    ):
        alert = await _seed(db_session, idx=41, score=21, risk_band=None)  # -> critical

        async def _stale_select(session):
            return [(alert.id, 21, False)]  # stale: planning saw score=21 (critical)

        # A concurrent writer corrects the score before apply's locked re-fetch.
        alert.signal_score_total = 10  # -> below_60
        await db_session.commit()

        monkeypatch.setattr(tool_module, "_select_candidates", _stale_select)
        report = await tool_module.run(db_session, apply=True, confirm=CONFIRM_TOKEN)

        assert report["mode"] == "apply_refused"
        await db_session.refresh(alert)
        assert alert.risk_band is None, (
            "must not apply the stale 'critical' plan to a now-below_60-scoring row"
        )

    async def test_validation_failure_rolls_back_the_entire_batch(self, db_session, monkeypatch):
        """One bad row in a multi-row apply must not let the other, still-valid
        rows partially commit — the whole apply is one transaction."""
        good = await _seed(db_session, idx=42, score=21, risk_band=None)   # critical
        bad = await _seed(db_session, idx=43, score=19, risk_band=None)    # high

        async def _stale_select(session):
            return [(good.id, 21, False), (bad.id, 19, False)]

        # Concurrent writer only touches `bad`.
        bad.risk_band = "medium"
        await db_session.commit()

        monkeypatch.setattr(tool_module, "_select_candidates", _stale_select)
        report = await tool_module.run(db_session, apply=True, confirm=CONFIRM_TOKEN)

        assert report["mode"] == "apply_refused"
        await db_session.refresh(good)
        await db_session.refresh(bad)
        assert good.risk_band is None, "the valid row in the same batch must also roll back"
        assert bad.risk_band == "medium", "the concurrently-written row keeps its real value"
