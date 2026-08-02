"""Subscriber Top Alerts — rolling seven-day selection.

Every test uses a frozen ``now``: the window is the point of this service, so it
must never depend on the machine clock.
"""
import ast
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.pipeline.publishing.constants import DecisionSource
from app.pipeline.publishing.risk_bands import RiskBandValue, compute_risk_band
from app.services import top_alerts_service as service
from app.services.top_alerts_service import (
    CRITICAL_MIN_SCORE,
    DEFAULT_LIMIT,
    HIGH_MIN_SCORE,
    WINDOW_DAYS,
    get_top_alerts,
    window_start,
)

NOW = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def seed(db_session):
    """Create published alerts with full control over every eligibility field."""
    source = Source(
        name="Top Alerts Source", base_url="https://top.test", source_type="rss",
        adapter_class="krebs.KrebsAdapter", is_active=True,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    source_id = source.id  # the teardown rollback detaches `source`

    created_alerts: list[int] = []
    created_items: list[int] = []
    counter = {"n": 0}

    async def _make(
        *, score=20, published_at=NOW - timedelta(days=1), is_published=True,
        decision_source=DecisionSource.AUTO_POLICY.value,
        source_published_at=None, title=None,
    ):
        counter["n"] += 1
        n = counter["n"]
        item = RawItem(
            source_id=source_id, item_url=f"https://top.test/{n}",
            title=title or f"Alert {n}", published_at=source_published_at,
            raw_text="body", raw_html="", content_hash=f"c{n:04d}",
            url_hash=f"u{n:04d}", is_duplicate=False, fetched_at=NOW,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        created_items.append(item.id)

        alert = ProcessedAlert(
            raw_item_id=item.id, summary=f"Summary {n}", primary_category="Fraud",
            is_relevant=True, signal_score_total=score, is_published=is_published,
            published_at=published_at, publication_state_source=decision_source,
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)
        created_alerts.append(alert.id)
        return alert

    _make.ids = created_alerts
    yield _make

    await db_session.rollback()
    await db_session.execute(
        delete(ProcessedAlert).where(ProcessedAlert.id.in_(created_alerts or [-1]))
    )
    await db_session.execute(delete(RawItem).where(RawItem.id.in_(created_items or [-1])))
    await db_session.execute(delete(Source).where(Source.id == source_id))
    await db_session.commit()


#: Wide enough that this module's alerts are never pushed out by rows other test
#: modules leave in the session-scoped database. The three-position limit itself
#: is asserted separately, against the real default.
_WIDE = 100


async def _top_ids(db_session, seed, limit=_WIDE):
    """Ids this module seeded, in the service's order, ignoring foreign rows."""
    alerts = await get_top_alerts(db_session, now=NOW, limit=limit)
    mine = set(seed.ids)
    return [a.id for a in alerts if a.id in mine]


async def _top(db_session, limit=_WIDE):
    return await get_top_alerts(db_session, now=NOW, limit=limit)


# ===========================================================================
# Risk band eligibility
# ===========================================================================


@pytest.mark.asyncio
async def test_a_critical_alert_inside_the_window_is_returned(db_session, seed):
    alert = await seed(score=CRITICAL_MIN_SCORE)
    assert compute_risk_band(CRITICAL_MIN_SCORE) is RiskBandValue.CRITICAL
    assert await _top_ids(db_session, seed) == [alert.id]


@pytest.mark.asyncio
async def test_a_high_alert_inside_the_window_is_returned(db_session, seed):
    alert = await seed(score=HIGH_MIN_SCORE)
    assert compute_risk_band(HIGH_MIN_SCORE) is RiskBandValue.HIGH
    assert await _top_ids(db_session, seed) == [alert.id]


@pytest.mark.asyncio
async def test_a_medium_alert_is_excluded(db_session, seed):
    await seed(score=HIGH_MIN_SCORE - 1)
    assert compute_risk_band(HIGH_MIN_SCORE - 1) is RiskBandValue.MEDIUM
    assert await _top_ids(db_session, seed) == []


@pytest.mark.asyncio
async def test_an_unpublished_alert_is_excluded(db_session, seed):
    await seed(score=25, is_published=False)
    assert await _top_ids(db_session, seed) == []


def test_thresholds_come_from_the_canonical_risk_bands():
    """No second copy of the band floors lives in this service."""
    from app.pipeline.publishing import risk_bands

    assert CRITICAL_MIN_SCORE == risk_bands._CRITICAL_MIN_INTERNAL == 20
    assert HIGH_MIN_SCORE == risk_bands._HIGH_MIN_INTERNAL == 18

    literals = [
        node.value for node in ast.walk(ast.parse(inspect.getsource(service)))
        if isinstance(node, ast.Constant) and isinstance(node.value, int)
    ]
    assert 20 not in literals and 18 not in literals, "thresholds must be imported"


# ===========================================================================
# The seven-day window
# ===========================================================================


@pytest.mark.asyncio
async def test_an_alert_older_than_the_window_is_excluded(db_session, seed):
    await seed(score=25, published_at=NOW - timedelta(days=WINDOW_DAYS, seconds=1))
    assert await _top_ids(db_session, seed) == []


@pytest.mark.asyncio
async def test_the_seven_day_boundary_is_inclusive(db_session, seed):
    alert = await seed(score=25, published_at=NOW - timedelta(days=WINDOW_DAYS))
    assert await _top_ids(db_session, seed) == [alert.id]


@pytest.mark.asyncio
async def test_a_null_publication_time_is_excluded(db_session, seed):
    await seed(score=25, published_at=None)
    assert await _top_ids(db_session, seed) == []


@pytest.mark.asyncio
async def test_a_january_alert_never_surfaces(db_session, seed):
    """The reported symptom: January 2026 and 2025 alerts in a weekly widget."""
    await seed(score=25, published_at=datetime(2026, 1, 5, tzinfo=timezone.utc))
    await seed(score=25, published_at=datetime(2025, 11, 20, tzinfo=timezone.utc))
    assert await _top_ids(db_session, seed) == []


@pytest.mark.asyncio
async def test_the_source_article_date_does_not_decide_eligibility(db_session, seed):
    """RawItem.published_at is the upstream date; only ours governs the window."""
    inside = await seed(
        score=25, published_at=NOW - timedelta(days=1),
        source_published_at=datetime(2019, 3, 1, tzinfo=timezone.utc),
    )
    await seed(
        score=25, published_at=NOW - timedelta(days=30),
        source_published_at=NOW - timedelta(hours=1),
    )
    assert await _top_ids(db_session, seed) == [inside.id]


def test_window_start_is_seven_days_and_utc_normalised():
    assert window_start(NOW) == NOW - timedelta(days=7)
    naive = datetime(2026, 8, 2, 12, 0, 0)
    assert window_start(naive) == NOW - timedelta(days=7)
    assert window_start(naive).tzinfo is not None


# ===========================================================================
# Historical publication decisions
# ===========================================================================


@pytest.mark.parametrize("decision_source", [
    DecisionSource.CANDIDATE_BACKFILL.value,
    DecisionSource.SYSTEM_MIGRATION.value,
])
@pytest.mark.asyncio
async def test_historical_bulk_publications_are_excluded(db_session, seed, decision_source):
    await seed(score=25, decision_source=decision_source)
    assert await _top_ids(db_session, seed) == []


@pytest.mark.parametrize("decision_source", [
    DecisionSource.AUTO_POLICY.value,
    DecisionSource.MANUAL_ADMIN.value,
    None,
])
@pytest.mark.asyncio
async def test_current_and_legacy_publications_are_eligible(
    db_session, seed, decision_source
):
    alert = await seed(score=25, decision_source=decision_source)
    assert await _top_ids(db_session, seed) == [alert.id]


def test_excluded_sources_use_the_shared_enum():
    assert set(service.EXCLUDED_DECISION_SOURCES) == {
        DecisionSource.CANDIDATE_BACKFILL.value,
        DecisionSource.SYSTEM_MIGRATION.value,
    }
    assert DecisionSource.MANUAL_ADMIN.value not in service.EXCLUDED_DECISION_SOURCES
    assert DecisionSource.AUTO_POLICY.value not in service.EXCLUDED_DECISION_SOURCES


# ===========================================================================
# Ordering
# ===========================================================================


@pytest.mark.asyncio
async def test_critical_precedes_high_even_on_a_lower_score_gap(db_session, seed):
    high = await seed(score=19, published_at=NOW - timedelta(minutes=1))
    critical = await seed(score=20, published_at=NOW - timedelta(days=6))
    assert await _top_ids(db_session, seed) == [critical.id, high.id]


@pytest.mark.asyncio
async def test_score_orders_descending_inside_a_band(db_session, seed):
    low = await seed(score=20)
    high = await seed(score=25)
    mid = await seed(score=22)
    assert await _top_ids(db_session, seed) == [high.id, mid.id, low.id]


@pytest.mark.asyncio
async def test_publication_time_breaks_a_score_tie_newest_first(db_session, seed):
    older = await seed(score=22, published_at=NOW - timedelta(days=5))
    newer = await seed(score=22, published_at=NOW - timedelta(hours=2))
    middle = await seed(score=22, published_at=NOW - timedelta(days=2))
    assert await _top_ids(db_session, seed) == [newer.id, middle.id, older.id]


@pytest.mark.asyncio
async def test_id_is_the_final_deterministic_tiebreaker(db_session, seed):
    same = NOW - timedelta(hours=3)
    first = await seed(score=22, published_at=same)
    second = await seed(score=22, published_at=same)
    third = await seed(score=22, published_at=same)

    ordered = await _top_ids(db_session, seed)
    assert ordered == sorted([first.id, second.id, third.id], reverse=True)
    assert ordered == await _top_ids(db_session, seed), "stable across calls"


# ===========================================================================
# Limit and the empty contract
# ===========================================================================


@pytest.mark.asyncio
async def test_at_most_three_alerts_are_returned(db_session, seed):
    """The real default limit, against the whole database."""
    for n in range(6):
        await seed(score=25, published_at=NOW - timedelta(hours=n))

    assert DEFAULT_LIMIT == 3
    assert len(await get_top_alerts(db_session, now=NOW)) == DEFAULT_LIMIT


@pytest.mark.asyncio
async def test_fewer_than_three_never_triggers_a_historical_fallback(db_session, seed):
    """One qualifying alert plus a pile of old high-scorers returns exactly one."""
    current = await seed(score=25, published_at=NOW - timedelta(days=1))
    for n in range(5):
        await seed(score=25, published_at=NOW - timedelta(days=30 + n))

    assert await _top_ids(db_session, seed) == [current.id]


@pytest.mark.asyncio
async def test_nothing_qualifying_returns_an_empty_list(db_session, seed):
    await seed(score=25, published_at=NOW - timedelta(days=60))
    await seed(score=10)
    assert await _top_ids(db_session, seed) == []


@pytest.mark.asyncio
async def test_duplicate_entities_are_not_suppressed(db_session, seed):
    """Entity dedup is gone: it could under-fill the three positions."""
    a = await seed(score=25, title="Acme Corp breach", published_at=NOW - timedelta(hours=1))
    b = await seed(score=24, title="Acme Corp fined", published_at=NOW - timedelta(hours=2))
    c = await seed(score=23, title="Acme Corp sued", published_at=NOW - timedelta(hours=3))

    assert await _top_ids(db_session, seed) == [a.id, b.id, c.id]


# ===========================================================================
# Determinism and shape
# ===========================================================================


@pytest.mark.asyncio
async def test_the_service_never_reads_the_machine_clock():
    tree = ast.parse(inspect.getsource(service))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") in ("utcnow", "now", "today")
    ]
    assert calls == [], "now must be injected, never read inside the service"


@pytest.mark.asyncio
async def test_no_python_reranking_or_candidate_pool(db_session, seed):
    source = inspect.getsource(service)
    for token in ("_select_top_alerts", "CANDIDATE_POOL", "credibility",
                  "event_sources", "entities"):
        assert token not in source, token


@pytest.mark.asyncio
async def test_raw_item_and_source_are_eager_loaded(db_session, seed):
    """The mapper reads raw_item.source; a lazy load would fail under asyncio."""
    mine = await seed(score=25)
    alerts = await _top(db_session)
    loaded = next(a for a in alerts if a.id == mine.id)

    from app.api.public_alerts import _to_public_read

    read = _to_public_read(loaded)
    assert read.source_name == "Top Alerts Source"
    assert read.title
