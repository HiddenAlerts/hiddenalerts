"""Tests for app/pipeline/event_grouper.py — uses in-memory SQLite DB."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.event import Event, EventSource
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.pipeline.event_grouper import find_or_create_event


async def _make_source(session, name="Test Source", credibility=4):
    source = Source(
        name=name,
        base_url="https://example.com",
        source_type="rss",
        credibility_score=credibility,
        adapter_class="RSSAdapter",
    )
    session.add(source)
    await session.flush()
    return source


async def _make_raw_item(session, source, title="Test Article"):
    raw = RawItem(
        source_id=source.id,
        item_url=f"https://example.com/{title.replace(' ', '-').lower()}",
        title=title,
        raw_text="Article content about fraud.",
        url_hash=f"hash_{title}",
    )
    session.add(raw)
    await session.flush()
    return raw


async def _make_alert(
    session,
    raw_item,
    category="Cybercrime",
    entities=None,
    risk_level="medium",
    signal_score_total=10,
    processed_at=None,
):
    if processed_at is None:
        processed_at = datetime.now(timezone.utc)
    alert = ProcessedAlert(
        raw_item_id=raw_item.id,
        primary_category=category,
        entities_json={"names": entities or []},
        risk_level=risk_level,
        signal_score_total=signal_score_total,
        score_source_credibility=4,
        score_financial_impact=2,
        score_victim_scale=1,
        score_cross_source=1,
        score_trend_acceleration=2,
        is_relevant=True,
        matched_keywords=["fraud"],
        processed_at=processed_at,
    )
    session.add(alert)
    await session.flush()
    # Attach raw_item for event_grouper
    alert.raw_item = raw_item
    return alert


@pytest.mark.asyncio
async def test_creates_new_event_for_first_alert(db_session):
    """First alert with no existing events should create a new Event."""
    source = await _make_source(db_session)
    raw = await _make_raw_item(db_session, source)
    alert = await _make_alert(db_session, raw, entities=["ACME Corp"], category="Cybercrime")

    event = await find_or_create_event(alert, db_session)
    await db_session.commit()

    assert event.id is not None
    assert event.category == "Cybercrime"
    assert event.primary_entity == "ACME Corp"


@pytest.mark.asyncio
async def test_links_to_existing_event_same_category_entity(db_session):
    """Alert with same category + entity should link to existing event."""
    source = await _make_source(db_session, name="Source2")
    raw1 = await _make_raw_item(db_session, source, title="Article One")
    raw2 = await _make_raw_item(db_session, source, title="Article Two")

    alert1 = await _make_alert(db_session, raw1, entities=["Evil Corp"], category="Money Laundering")
    event1 = await find_or_create_event(alert1, db_session)
    await db_session.commit()

    alert2 = await _make_alert(db_session, raw2, entities=["Evil Corp", "FBI"], category="Money Laundering")
    event2 = await find_or_create_event(alert2, db_session)
    await db_session.commit()

    # Both alerts should link to the same event
    assert event1.id == event2.id


@pytest.mark.asyncio
async def test_no_match_different_category(db_session):
    """Same entity but different category should create a new event."""
    source = await _make_source(db_session, name="Source3")
    raw1 = await _make_raw_item(db_session, source, title="Cat Test 1")
    raw2 = await _make_raw_item(db_session, source, title="Cat Test 2")

    alert1 = await _make_alert(db_session, raw1, entities=["XYZ Corp"], category="Cybercrime")
    event1 = await find_or_create_event(alert1, db_session)
    await db_session.commit()

    alert2 = await _make_alert(db_session, raw2, entities=["XYZ Corp"], category="Investment Fraud")
    event2 = await find_or_create_event(alert2, db_session)
    await db_session.commit()

    # Different categories → different events
    assert event1.id != event2.id


@pytest.mark.asyncio
async def test_no_match_outside_7_day_window(db_session):
    """Event older than 7 days should not match — creates a new event."""
    source = await _make_source(db_session, name="Source4")
    raw1 = await _make_raw_item(db_session, source, title="Old Article")
    raw2 = await _make_raw_item(db_session, source, title="New Article")

    # Create old alert (8 days ago) and its event, then manually backdate
    old_time = datetime.now(timezone.utc) - timedelta(days=8)
    alert1 = await _make_alert(
        db_session, raw1, entities=["BadActor Inc"], category="Consumer Scam",
        processed_at=old_time
    )
    event1 = await find_or_create_event(alert1, db_session)
    # Backdate the event's last_updated_at so it falls outside the 7-day window
    event1.last_updated_at = old_time
    await db_session.flush()
    await db_session.commit()

    alert2 = await _make_alert(
        db_session, raw2, entities=["BadActor Inc"], category="Consumer Scam"
    )
    event2 = await find_or_create_event(alert2, db_session)
    await db_session.commit()

    # Event is too old — should create a new one
    assert event1.id != event2.id


@pytest.mark.asyncio
async def test_event_source_created(db_session):
    """find_or_create_event should create an EventSource record linking alert to event."""
    from sqlalchemy import select

    source = await _make_source(db_session, name="Source5")
    raw = await _make_raw_item(db_session, source, title="EventSource Test")
    alert = await _make_alert(db_session, raw, entities=["Target LLC"])

    event = await find_or_create_event(alert, db_session)
    await db_session.commit()

    # Check EventSource was created
    es_result = await db_session.execute(
        select(EventSource)
        .where(EventSource.event_id == event.id)
        .where(EventSource.alert_id == alert.id)
    )
    event_source = es_result.scalar_one_or_none()
    assert event_source is not None


@pytest.mark.asyncio
async def test_cross_source_score_recalculated(db_session):
    """Linking second alert to same event should update cross_source score to 3."""
    from sqlalchemy import select

    source = await _make_source(db_session, name="Source6")
    raw1 = await _make_raw_item(db_session, source, title="Cross Test 1")
    raw2 = await _make_raw_item(db_session, source, title="Cross Test 2")

    alert1 = await _make_alert(
        db_session, raw1, entities=["Scammer LLC"], category="Investment Fraud"
    )
    await find_or_create_event(alert1, db_session)
    await db_session.commit()

    alert2 = await _make_alert(
        db_session, raw2, entities=["Scammer LLC"], category="Investment Fraud"
    )
    await find_or_create_event(alert2, db_session)
    await db_session.commit()

    # Reload alert1 and check cross_source score was updated to 3 (2 sources)
    result = await db_session.execute(
        select(ProcessedAlert).where(ProcessedAlert.id == alert1.id)
    )
    updated_alert1 = result.scalar_one()
    assert updated_alert1.score_cross_source == 3
