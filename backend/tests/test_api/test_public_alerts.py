"""Tests for GET /api/alerts — public read-only feed.

Covers:
- No auth required
- Only published alerts returned
- Unpublished alerts never returned
- Correct response shape: { "alerts": [...] }
- Correct field mapping
- Ordering: newest published_at first
- Empty feed returns 200 with { "alerts": [] }
- Optional filters work without exposing unpublished data
- Existing protected endpoints unchanged
"""
from __future__ import annotations

import pytest

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.user import User
from app.auth import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_source(db_session) -> Source:
    source = Source(
        name="Test Source",
        base_url="https://example.com",
        source_type="rss",
        is_active=True,
        polling_frequency_minutes=60,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source


async def _seed_raw_item(db_session, source: Source, title: str = "Test Alert Title") -> RawItem:
    item = RawItem(
        source_id=source.id,
        item_url="https://example.com/article",
        title=title,
        is_duplicate=False,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


async def _seed_alert(
    db_session,
    raw_item: RawItem,
    *,
    is_published: bool,
    risk_level: str = "medium",
    category: str = "Cybercrime",
    signal_score: int = 12,
    summary: str = "Test summary",
    published_at=None,
) -> ProcessedAlert:
    from datetime import datetime, timezone
    alert = ProcessedAlert(
        raw_item_id=raw_item.id,
        risk_level=risk_level,
        primary_category=category,
        signal_score_total=signal_score,
        summary=summary,
        is_relevant=True,
        is_published=is_published,
        published_at=published_at or (datetime.now(timezone.utc) if is_published else None),
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert


# ---------------------------------------------------------------------------
# Public feed — basic behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_feed_requires_no_auth(client):
    """GET /api/alerts must succeed without any auth header or cookie."""
    response = await client.get("/api/alerts")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_public_feed_empty_returns_wrapper(client):
    """When no published alerts exist, response is {"alerts": []} with 200."""
    response = await client.get("/api/alerts")
    assert response.status_code == 200
    body = response.json()
    assert "alerts" in body
    assert isinstance(body["alerts"], list)


@pytest.mark.asyncio
async def test_public_feed_only_returns_published(client, db_session):
    """Unpublished alerts must never appear in the public feed."""
    source = await _seed_source(db_session)
    item_pub = await _seed_raw_item(db_session, source, title="Published Alert")
    item_unpub = await _seed_raw_item(db_session, source, title="Unpublished Alert")

    await _seed_alert(db_session, item_pub, is_published=True)
    await _seed_alert(db_session, item_unpub, is_published=False)

    response = await client.get("/api/alerts")
    assert response.status_code == 200
    titles = [a["title"] for a in response.json()["alerts"]]
    assert "Published Alert" in titles
    assert "Unpublished Alert" not in titles


@pytest.mark.asyncio
async def test_public_feed_response_shape(client, db_session):
    """Response must be wrapped in {"alerts": [...]} and each alert has required fields."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Shape Test")
    await _seed_alert(db_session, item, is_published=True, summary="Shape summary")

    response = await client.get("/api/alerts")
    assert response.status_code == 200
    body = response.json()
    assert "alerts" in body

    alert = next((a for a in body["alerts"] if a["title"] == "Shape Test"), None)
    assert alert is not None

    # All expected public fields present
    for field in ("id", "title", "summary", "category", "risk_level",
                  "signal_score", "source_name", "source_url", "published_at"):
        assert field in alert, f"Missing field: {field}"

    # Internal fields must NOT be present
    for internal_field in ("is_published", "is_relevant", "raw_item_id",
                           "score_source_credibility", "score_financial_impact",
                           "entities_json", "review_status", "published_by_user_id"):
        assert internal_field not in alert, f"Internal field leaked: {internal_field}"


@pytest.mark.asyncio
async def test_public_feed_field_mapping(client, db_session):
    """Fields must map correctly from DB columns to the public schema."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Mapping Test")
    alert = await _seed_alert(
        db_session, item,
        is_published=True,
        risk_level="high",
        category="Investment Fraud",
        signal_score=19,
        summary="Mapped summary",
    )

    response = await client.get("/api/alerts")
    body = response.json()
    match = next((a for a in body["alerts"] if a["id"] == alert.id), None)
    assert match is not None
    assert match["title"] == "Mapping Test"
    assert match["summary"] == "Mapped summary"
    assert match["category"] == "Investment Fraud"
    assert match["risk_level"] == "high"
    assert match["signal_score"] == 19
    assert match["source_name"] == "Test Source"
    assert match["source_url"] == "https://example.com/article"
    assert match["published_at"] is not None


@pytest.mark.asyncio
async def test_public_feed_ordering_newest_first(client, db_session):
    """Alerts must be ordered by published_at descending (newest first)."""
    from datetime import datetime, timedelta, timezone

    source = await _seed_source(db_session)
    item_old = await _seed_raw_item(db_session, source, title="Old Alert")
    item_new = await _seed_raw_item(db_session, source, title="New Alert")

    now = datetime.now(timezone.utc)
    await _seed_alert(db_session, item_old, is_published=True,
                      published_at=now - timedelta(days=2))
    await _seed_alert(db_session, item_new, is_published=True,
                      published_at=now - timedelta(hours=1))

    response = await client.get("/api/alerts")
    alerts = response.json()["alerts"]
    titles = [a["title"] for a in alerts]
    assert titles.index("New Alert") < titles.index("Old Alert")


# ---------------------------------------------------------------------------
# Optional filters — must never expose unpublished alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_feed_filter_risk_level(client, db_session):
    """risk_level filter narrows results but never exposes unpublished alerts."""
    source = await _seed_source(db_session)
    item_high = await _seed_raw_item(db_session, source, title="High Risk")
    item_medium = await _seed_raw_item(db_session, source, title="Medium Risk")
    item_unpub = await _seed_raw_item(db_session, source, title="Unpublished High")

    await _seed_alert(db_session, item_high, is_published=True, risk_level="high")
    await _seed_alert(db_session, item_medium, is_published=True, risk_level="medium")
    await _seed_alert(db_session, item_unpub, is_published=False, risk_level="high")

    response = await client.get("/api/alerts?risk_level=high")
    assert response.status_code == 200
    titles = [a["title"] for a in response.json()["alerts"]]
    assert "High Risk" in titles
    assert "Medium Risk" not in titles
    assert "Unpublished High" not in titles


@pytest.mark.asyncio
async def test_public_feed_filter_category(client, db_session):
    """category filter works and never exposes unpublished alerts."""
    source = await _seed_source(db_session)
    item_cyber = await _seed_raw_item(db_session, source, title="Cyber Alert")
    item_invest = await _seed_raw_item(db_session, source, title="Investment Alert")

    await _seed_alert(db_session, item_cyber, is_published=True, category="Cybercrime")
    await _seed_alert(db_session, item_invest, is_published=True, category="Investment Fraud")

    response = await client.get("/api/alerts?category=Cybercrime")
    assert response.status_code == 200
    titles = [a["title"] for a in response.json()["alerts"]]
    assert "Cyber Alert" in titles
    assert "Investment Alert" not in titles


@pytest.mark.asyncio
async def test_public_feed_pagination(client, db_session):
    """limit and offset params work correctly."""
    source = await _seed_source(db_session)
    for i in range(5):
        item = await _seed_raw_item(db_session, source, title=f"Alert {i}")
        await _seed_alert(db_session, item, is_published=True)

    r1 = await client.get("/api/alerts?limit=2&offset=0")
    r2 = await client.get("/api/alerts?limit=2&offset=2")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert len(r1.json()["alerts"]) == 2
    assert len(r2.json()["alerts"]) == 2
    ids1 = {a["id"] for a in r1.json()["alerts"]}
    ids2 = {a["id"] for a in r2.json()["alerts"]}
    assert ids1.isdisjoint(ids2), "Pages must not overlap"


# ---------------------------------------------------------------------------
# Backwards compatibility — existing protected endpoints still work
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_alerts_endpoint_still_requires_auth(client):
    """/api/v1/alerts still requires authentication after this slice."""
    response = await client.get("/api/v1/alerts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_client_alerts_endpoint_still_requires_auth(client):
    """/api/v1/client/alerts still requires authentication after this slice."""
    response = await client.get("/api/v1/client/alerts")
    assert response.status_code == 401
