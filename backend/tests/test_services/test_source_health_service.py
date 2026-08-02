"""Pure health classification and metric derivation.

The classifier takes metrics, thresholds and a frozen clock, so every rule here
is exercised without a database or a network. The aggregation tests use the
in-memory test database only.
"""
import ast
import inspect
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source
from app.services import source_health_service as service
from app.services.source_health_service import (
    COLLECTION_OVERDUE,
    DISABLED,
    ERROR,
    HEALTHY,
    HIGH_INVALID_RATE,
    LATEST_RUN_FAILED,
    NEVER_COLLECTED,
    NO_SUCCESSFUL_RUN,
    NO_UPSTREAM_CONTENT,
    OK,
    REPEATED_FAILURES,
    SCHEDULER_OVERDUE,
    SOURCE_DISABLED,
    STALE_INGESTION,
    STALE_UPSTREAM,
    WARNING,
    SourceHealthMetrics,
    SourceHealthThresholds,
    classify_source_health,
    collect_source_metrics,
)

NOW = datetime(2026, 8, 1, 12, 0, 0)
INTERVAL = 6.0
T = SourceHealthThresholds()


def _metrics(**overrides) -> SourceHealthMetrics:
    """A healthy baseline: one recent successful run that stored something."""
    base = dict(
        source_id=1, name="Example Source", is_active=True,
        last_run_at=NOW - timedelta(hours=1), last_run_status="success",
        last_success_at=NOW - timedelta(hours=1),
        last_new_item_at=NOW - timedelta(hours=2),
        latest_upstream_published_at=NOW - timedelta(days=1),
        has_any_run=True, has_any_success=True,
    )
    base.update(overrides)
    return SourceHealthMetrics(**base)


def _classify(metrics, thresholds=T, now=NOW, interval=INTERVAL):
    return classify_source_health(
        metrics, thresholds, now=now, scheduler_interval_hours=interval
    )


# ===========================================================================
# Classification
# ===========================================================================


def test_healthy_baseline():
    result = _classify(_metrics())
    assert (result.state, result.reason_code) == (HEALTHY, OK)
    assert result.additional_reason_codes == []


def test_disabled_short_circuits_every_other_rule():
    """An inactive source is disabled even when everything else looks terrible."""
    result = _classify(_metrics(
        is_active=False, consecutive_failed_runs=99, last_run_status="failed",
        has_any_success=False, consecutive_zero_fetch_runs=99,
        last_new_item_at=NOW - timedelta(days=365),
        last_run_at=NOW - timedelta(days=365),
    ))
    assert (result.state, result.reason_code) == (DISABLED, SOURCE_DISABLED)


def test_repeated_failures_is_an_error():
    result = _classify(_metrics(
        consecutive_failed_runs=2, last_run_status="failed",
    ))
    assert (result.state, result.reason_code) == (ERROR, REPEATED_FAILURES)
    assert "2 consecutive" in result.reason_detail


def test_a_single_failure_with_no_prior_success_is_an_error():
    """The only run failed — nothing has ever worked."""
    result = _classify(_metrics(
        consecutive_failed_runs=1, last_run_status="failed", has_any_success=False,
        last_success_at=None,
    ))
    assert (result.state, result.reason_code) == (ERROR, NO_SUCCESSFUL_RUN)


def test_run_history_without_any_success_is_an_error():
    result = _classify(_metrics(
        has_any_run=True, has_any_success=False, last_success_at=None,
        last_run_status="running", consecutive_failed_runs=0,
    ))
    assert (result.state, result.reason_code) == (ERROR, NO_SUCCESSFUL_RUN)


def test_one_recent_failure_after_success_is_a_warning():
    result = _classify(_metrics(
        consecutive_failed_runs=1, last_run_status="failed", has_any_success=True,
    ))
    assert (result.state, result.reason_code) == (WARNING, LATEST_RUN_FAILED)


def test_a_valid_empty_upstream_is_a_warning_not_an_error():
    """Required for valid-empty sources — and stated generically, by metrics only."""
    result = _classify(_metrics(consecutive_zero_fetch_runs=3, items_fetched_24h=0))
    assert result.state == WARNING
    assert result.reason_code == NO_UPSTREAM_CONTENT
    assert result.state != ERROR


def test_known_url_only_successful_runs_stay_healthy():
    """Everything the listing offered was already stored: nothing is wrong."""
    result = _classify(_metrics(
        consecutive_zero_new_runs=10, items_fetched_24h=30, items_new_24h=0,
        items_skipped_invalid_24h=0,
    ))
    assert result.state == HEALTHY


def test_external_only_successful_runs_stay_healthy():
    """Every item belonged to another source. Policy working, not a fault."""
    result = _classify(_metrics(
        consecutive_zero_new_runs=8, items_fetched_24h=25, items_new_24h=0,
        items_skipped_external_24h=25, items_skipped_invalid_24h=0,
    ))
    assert result.state == HEALTHY


def test_a_high_external_ratio_alone_never_degrades_health():
    for external in (10, 50, 300):
        result = _classify(_metrics(
            items_fetched_24h=external, items_skipped_external_24h=external,
            items_new_24h=0, items_skipped_invalid_24h=0,
        ))
        assert result.state == HEALTHY, external


def test_high_invalid_ratio_is_a_warning():
    result = _classify(_metrics(items_fetched_24h=20, items_skipped_invalid_24h=10))
    assert (result.state, result.reason_code) == (WARNING, HIGH_INVALID_RATE)


def test_invalid_ratio_is_ignored_below_the_sample_floor():
    """Two of three items failing is noise, not a signal."""
    result = _classify(_metrics(items_fetched_24h=3, items_skipped_invalid_24h=3))
    assert result.state == HEALTHY


def test_external_exclusions_do_not_inflate_the_invalid_ratio():
    """45 external + 5 invalid of 50 fetched is a 10% invalid rate, not 100%."""
    result = _classify(_metrics(
        items_fetched_24h=50, items_skipped_external_24h=45,
        items_skipped_invalid_24h=5,
    ))
    assert result.state == HEALTHY


@pytest.mark.parametrize("hours,expected_state,expected_code", [
    (11.9, HEALTHY, OK),                     # just inside 2x
    (12.1, WARNING, COLLECTION_OVERDUE),     # past 2x
    (23.9, WARNING, COLLECTION_OVERDUE),     # just inside 4x
    (24.1, ERROR, SCHEDULER_OVERDUE),        # past 4x
])
def test_overdue_boundaries(hours, expected_state, expected_code):
    result = _classify(_metrics(
        last_run_at=NOW - timedelta(hours=hours),
        last_success_at=NOW - timedelta(hours=hours),
        last_new_item_at=NOW - timedelta(hours=hours),
    ))
    assert (result.state, result.reason_code) == (expected_state, expected_code)


def test_stale_ingestion_is_a_warning():
    result = _classify(_metrics(last_new_item_at=NOW - timedelta(days=15)))
    assert result.state == WARNING
    assert STALE_INGESTION in [result.reason_code, *result.additional_reason_codes]


def test_stale_upstream_is_a_warning():
    result = _classify(_metrics(
        latest_upstream_published_at=NOW - timedelta(days=31),
    ))
    assert result.state == WARNING
    assert STALE_UPSTREAM in [result.reason_code, *result.additional_reason_codes]


@pytest.mark.parametrize("days,expected", [
    (13.9, HEALTHY), (14.1, WARNING),
])
def test_stale_ingestion_boundary(days, expected):
    assert _classify(_metrics(
        last_new_item_at=NOW - timedelta(days=days)
    )).state == expected


@pytest.mark.parametrize("streak,expected", [(2, HEALTHY), (3, WARNING)])
def test_zero_fetch_streak_boundary(streak, expected):
    assert _classify(_metrics(consecutive_zero_fetch_runs=streak)).state == expected


@pytest.mark.parametrize("failures,expected", [(1, WARNING), (2, ERROR)])
def test_consecutive_failure_boundary(failures, expected):
    assert _classify(_metrics(
        consecutive_failed_runs=failures, last_run_status="failed",
    )).state == expected


def test_an_active_source_that_never_ran_is_a_warning():
    result = _classify(_metrics(
        has_any_run=False, has_any_success=False, last_run_at=None,
        last_success_at=None, last_new_item_at=None,
        latest_upstream_published_at=None,
    ))
    assert (result.state, result.reason_code) == (WARNING, NEVER_COLLECTED)


def test_every_matching_warning_is_reported():
    result = _classify(_metrics(
        consecutive_zero_fetch_runs=5,
        last_new_item_at=NOW - timedelta(days=20),
        latest_upstream_published_at=NOW - timedelta(days=40),
    ))
    assert result.state == WARNING
    codes = {result.reason_code, *result.additional_reason_codes}
    assert {NO_UPSTREAM_CONTENT, STALE_INGESTION, STALE_UPSTREAM} <= codes


def test_classification_is_deterministic_at_a_frozen_instant():
    metrics = _metrics(consecutive_failed_runs=1, last_run_status="failed")
    first, second = _classify(metrics), _classify(metrics)
    assert (first.state, first.reason_code, first.reason_detail) == (
        second.state, second.reason_code, second.reason_detail
    )


def test_thresholds_are_injectable_and_immutable():
    strict = SourceHealthThresholds(consecutive_failures_for_error=1)
    metrics = _metrics(consecutive_failed_runs=1, last_run_status="failed")

    assert _classify(metrics, strict).state == ERROR
    assert _classify(metrics, T).state == WARNING

    with pytest.raises(Exception):
        strict.consecutive_failures_for_error = 5


def test_the_service_holds_no_source_specific_conditional():
    """Generic by construction: no source name, id or adapter drives a rule."""
    tree = ast.parse(inspect.getsource(service))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef))
        and node.body and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    literals = [
        node.value.lower() for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docstrings
    ]
    for token in ("fbi", "doj", "ftc", "sec_press", "ic3", "fincen", "krebs",
                  "bleeping", "justice.gov", "adapter"):
        assert not [t for t in literals if token in t], token


def test_health_never_reads_the_decorative_polling_field():
    """Cadence comes from the scheduler, not Source.polling_frequency_minutes.

    Checked on attribute access, not prose — both modules name the field in a
    comment precisely to record that it is deliberately unused.
    """
    from app.api import source_health

    for module in (service, source_health):
        tree = ast.parse(inspect.getsource(module))
        reads = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr == "polling_frequency_minutes"
        ]
        assert reads == [], module.__name__

    # And the scheduler setting is the one that is read.
    assert "scheduler_interval_hours" in inspect.getsource(source_health)


# ===========================================================================
# Metric derivation
# ===========================================================================


@pytest.fixture
async def health_source(db_session):
    created: list[int] = []

    async def _make(name="Health Source", is_active=True):
        src = Source(
            name=name, base_url="https://health.test", source_type="rss",
            adapter_class="krebs.KrebsAdapter", is_active=is_active,
            credibility_score=4,
        )
        db_session.add(src)
        await db_session.commit()
        await db_session.refresh(src)
        created.append(src.id)
        return src

    yield _make

    await db_session.rollback()
    for source_id in created:
        items = (await db_session.execute(
            RawItem.__table__.select().where(RawItem.source_id == source_id)
        )).all()
        await db_session.execute(delete(ProcessedAlert).where(
            ProcessedAlert.raw_item_id.in_([i.id for i in items] or [-1])
        ))
        await db_session.execute(delete(RawItem).where(RawItem.source_id == source_id))
        await db_session.execute(delete(RunLog).where(RunLog.source_id == source_id))
        await db_session.execute(delete(Source).where(Source.id == source_id))
    await db_session.commit()


_UNFINISHED = object()


def _run(source, *, started, status="success", finished=_UNFINISHED, fetched=0, new=0,
         invalid=0, external=0, error=None):
    """One run. ``finished=None`` means it never finished; omit it for a 30s run."""
    return RunLog(
        source_id=source.id, run_started_at=started,
        run_finished_at=started + timedelta(seconds=30) if finished is _UNFINISHED else finished,
        status=status, items_fetched=fetched, items_new=new, items_duplicate=0,
        items_skipped_url=0, items_skipped_content=0, items_skipped_invalid=invalid,
        items_skipped_external=external, error_message=error,
    )


async def _metrics_for(db_session, source):
    results = await collect_source_metrics(db_session, [source], now=NOW)
    return results[0]


@pytest.mark.asyncio
async def test_latest_run_status_and_duration(db_session, health_source):
    source = await health_source()
    db_session.add_all([
        _run(source, started=NOW - timedelta(hours=8)),
        _run(source, started=NOW - timedelta(hours=2),
             finished=NOW - timedelta(hours=2) + timedelta(seconds=45), fetched=5, new=2),
    ])
    await db_session.commit()

    metrics = await _metrics_for(db_session, source)
    assert metrics.last_run_at == NOW - timedelta(hours=2)
    assert metrics.last_run_status == "success"
    assert metrics.last_run_duration_seconds == 45.0
    assert metrics.last_success_at == NOW - timedelta(hours=2)


@pytest.mark.asyncio
async def test_last_error_is_the_most_recent_failure(db_session, health_source):
    source = await health_source()
    db_session.add_all([
        _run(source, started=NOW - timedelta(hours=9), status="failed", error="old boom"),
        _run(source, started=NOW - timedelta(hours=6), status="failed", error="recent boom"),
        _run(source, started=NOW - timedelta(hours=3), fetched=4, new=1),
    ])
    await db_session.commit()

    metrics = await _metrics_for(db_session, source)
    assert metrics.last_error_at == NOW - timedelta(hours=6)
    assert metrics.last_error_message == "recent boom"
    assert metrics.consecutive_failed_runs == 0, "the newest run succeeded"


@pytest.mark.asyncio
async def test_streaks_stop_at_the_first_non_matching_run(db_session, health_source):
    source = await health_source()
    db_session.add_all([
        _run(source, started=NOW - timedelta(hours=12), status="failed"),
        _run(source, started=NOW - timedelta(hours=9), fetched=3, new=1),
        _run(source, started=NOW - timedelta(hours=6), status="failed"),
        _run(source, started=NOW - timedelta(hours=3), status="failed"),
    ])
    await db_session.commit()

    metrics = await _metrics_for(db_session, source)
    assert metrics.consecutive_failed_runs == 2, "stops at the success"
    assert metrics.consecutive_zero_fetch_runs == 0, "newest run is not a success"


@pytest.mark.asyncio
async def test_zero_fetch_and_zero_new_streaks(db_session, health_source):
    source = await health_source()
    db_session.add_all([
        _run(source, started=NOW - timedelta(hours=12), fetched=5, new=2),
        _run(source, started=NOW - timedelta(hours=9), fetched=0, new=0),
        _run(source, started=NOW - timedelta(hours=6), fetched=0, new=0),
        _run(source, started=NOW - timedelta(hours=3), fetched=0, new=0),
    ])
    await db_session.commit()

    metrics = await _metrics_for(db_session, source)
    assert metrics.consecutive_zero_fetch_runs == 3
    assert metrics.consecutive_zero_new_runs == 3


@pytest.mark.asyncio
async def test_time_windows_exclude_older_rows(db_session, health_source):
    source = await health_source()
    db_session.add_all([
        _run(source, started=NOW - timedelta(hours=2), fetched=10, new=4,
             invalid=1, external=3),
        _run(source, started=NOW - timedelta(days=3), fetched=8, new=5, external=2),
        _run(source, started=NOW - timedelta(days=20), fetched=6, new=6, external=9),
        _run(source, started=NOW - timedelta(days=90), fetched=99, new=99, external=99),
    ])
    await db_session.commit()

    metrics = await _metrics_for(db_session, source)
    assert metrics.runs_24h == 1
    assert metrics.items_fetched_24h == 10
    assert metrics.items_new_24h == 4
    assert metrics.items_new_7d == 9
    assert metrics.items_new_30d == 15
    assert metrics.items_skipped_invalid_24h == 1
    assert metrics.items_skipped_external_24h == 3
    assert metrics.items_skipped_external_7d == 5


@pytest.mark.asyncio
async def test_invalid_and_external_totals_stay_distinct(db_session, health_source):
    source = await health_source()
    db_session.add(_run(source, started=NOW - timedelta(hours=1), fetched=50,
                        new=5, invalid=2, external=43))
    await db_session.commit()

    metrics = await _metrics_for(db_session, source)
    assert metrics.items_skipped_invalid_24h == 2
    assert metrics.items_skipped_external_24h == 43
    assert metrics.latest_run_items_skipped_external == 43


@pytest.mark.asyncio
async def test_raw_item_and_published_totals(db_session, health_source):
    source = await health_source()
    items = [
        RawItem(source_id=source.id, item_url=f"https://health.test/{n}",
                title=f"Item {n}", published_at=NOW - timedelta(days=n),
                raw_text="text", raw_html="", content_hash=f"c{n}", url_hash=f"u{n}",
                is_duplicate=False, fetched_at=NOW - timedelta(days=n))
        for n in range(3)
    ]
    db_session.add_all(items)
    await db_session.commit()
    for item in items:
        await db_session.refresh(item)

    db_session.add_all([
        ProcessedAlert(raw_item_id=items[0].id, is_relevant=True, is_published=True),
        ProcessedAlert(raw_item_id=items[1].id, is_relevant=True, is_published=False),
    ])
    await db_session.commit()

    metrics = await _metrics_for(db_session, source)
    assert metrics.total_raw_items == 3
    assert metrics.total_published_alerts == 1, "the proven raw_item join"
    assert metrics.last_new_item_at == NOW
    assert metrics.latest_upstream_published_at == NOW


@pytest.mark.asyncio
async def test_a_source_with_no_history_does_not_crash(db_session, health_source):
    source = await health_source()
    metrics = await _metrics_for(db_session, source)

    assert metrics.has_any_run is False
    assert metrics.last_run_at is None
    assert metrics.total_raw_items == 0
    assert metrics.total_published_alerts == 0
    assert _classify(metrics).state == WARNING


@pytest.mark.asyncio
async def test_null_dates_do_not_crash(db_session, health_source):
    source = await health_source()
    db_session.add(RawItem(
        source_id=source.id, item_url="https://health.test/undated", title="Undated",
        published_at=None, raw_text="t", raw_html="", content_hash="cx", url_hash="ux",
        is_duplicate=False, fetched_at=NOW,
    ))
    db_session.add(_run(source, started=NOW - timedelta(hours=1), finished=None,
                        fetched=1, new=1))
    await db_session.commit()

    metrics = await _metrics_for(db_session, source)
    assert metrics.latest_upstream_published_at is None
    assert metrics.last_run_duration_seconds is None
    assert _classify(metrics) is not None


@pytest.mark.asyncio
async def test_no_sources_returns_no_metrics(db_session):
    assert await collect_source_metrics(db_session, [], now=NOW) == []
