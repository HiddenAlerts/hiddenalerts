"""V1 Slice 4 — distinct-outlet cross-source counting tests.

Covers the pure ``_distinct_outlet_count`` helper and the end-to-end behaviour
that repeated same-outlet coverage no longer inflates ``score_cross_source``,
while genuinely distinct outlets still raise it (2 → 3, 3 → 5).

Each integration test uses a unique entity so events don't bleed across tests in
the session-scoped in-memory SQLite engine.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.pipeline.event_grouper import _distinct_outlet_count, find_or_create_event


# --- Pure helper -------------------------------------------------------------


def _es(name):
    return SimpleNamespace(source_name=name)


def test_distinct_outlet_count_same_outlet_is_one():
    assert _distinct_outlet_count([_es("BleepingComputer")] * 5) == 1


def test_distinct_outlet_count_two_distinct():
    assert _distinct_outlet_count([_es("BleepingComputer"), _es("KrebsOnSecurity")]) == 2


def test_distinct_outlet_count_three_distinct():
    rows = [_es("BleepingComputer"), _es("KrebsOnSecurity"), _es("SEC Press Releases")]
    assert _distinct_outlet_count(rows) == 3


def test_distinct_outlet_count_normalizes_case_and_whitespace():
    rows = [_es("BleepingComputer"), _es("  bleepingcomputer "), _es("BLEEPINGCOMPUTER")]
    assert _distinct_outlet_count(rows) == 1


def test_distinct_outlet_count_ignores_blank_and_none():
    assert _distinct_outlet_count([_es(None), _es(""), _es("   "), _es("KrebsOnSecurity")]) == 1
    assert _distinct_outlet_count([_es(None), _es("")]) == 0


# --- Integration through the grouper -----------------------------------------


async def _source(session, name):
    s = Source(
        name=name,
        base_url="https://example.com",
        source_type="rss",
        credibility_score=4,
        adapter_class="RSSAdapter",
    )
    session.add(s)
    await session.flush()
    return s


async def _alert(session, source, entity, title):
    raw = RawItem(
        source_id=source.id,
        item_url=f"https://example.com/{title.replace(' ', '-').lower()}",
        title=title,
        raw_text="content",
        url_hash=f"hash_{title}",
    )
    session.add(raw)
    await session.flush()
    alert = ProcessedAlert(
        raw_item_id=raw.id,
        primary_category="Investment Fraud",
        entities_json={"names": [entity]},
        risk_level="medium",
        signal_score_total=10,
        score_source_credibility=4,
        score_financial_impact=2,
        score_victim_scale=1,
        score_cross_source=1,
        score_trend_acceleration=2,
        is_relevant=True,
        matched_keywords=["fraud"],
        processed_at=datetime.now(timezone.utc),
    )
    session.add(alert)
    await session.flush()
    alert.raw_item = raw
    return alert


async def _score_of(session, alert_id):
    res = await session.execute(select(ProcessedAlert).where(ProcessedAlert.id == alert_id))
    return res.scalar_one().score_cross_source


@pytest.mark.asyncio
async def test_same_outlet_does_not_inflate_cross_source(db_session):
    """Two alerts from the SAME outlet → one distinct source → score stays 1."""
    src = await _source(db_session, "BleepingComputer")
    a1 = await _alert(db_session, src, "SameOutletCo", "Same Outlet 1")
    await find_or_create_event(a1, db_session)
    await db_session.commit()

    a2 = await _alert(db_session, src, "SameOutletCo", "Same Outlet 2")
    await find_or_create_event(a2, db_session)
    await db_session.commit()

    assert await _score_of(db_session, a1.id) == 1  # not inflated to 3


@pytest.mark.asyncio
async def test_two_distinct_outlets_medium_cross_source(db_session):
    src1 = await _source(db_session, "BleepingComputer")
    src2 = await _source(db_session, "KrebsOnSecurity")
    a1 = await _alert(db_session, src1, "TwoDistinctCo", "Two Outlet 1")
    await find_or_create_event(a1, db_session)
    await db_session.commit()
    a2 = await _alert(db_session, src2, "TwoDistinctCo", "Two Outlet 2")
    await find_or_create_event(a2, db_session)
    await db_session.commit()

    assert await _score_of(db_session, a1.id) == 3


@pytest.mark.asyncio
async def test_three_distinct_outlets_max_cross_source(db_session):
    src1 = await _source(db_session, "BleepingComputer")
    src2 = await _source(db_session, "KrebsOnSecurity")
    src3 = await _source(db_session, "SEC Press Releases")
    a1 = await _alert(db_session, src1, "ThreeDistinctCo", "Three Outlet 1")
    await find_or_create_event(a1, db_session)
    await db_session.commit()
    a2 = await _alert(db_session, src2, "ThreeDistinctCo", "Three Outlet 2")
    await find_or_create_event(a2, db_session)
    await db_session.commit()
    a3 = await _alert(db_session, src3, "ThreeDistinctCo", "Three Outlet 3")
    await find_or_create_event(a3, db_session)
    await db_session.commit()

    assert await _score_of(db_session, a1.id) == 5
