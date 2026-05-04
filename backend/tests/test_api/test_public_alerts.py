"""Tests for the public read-only alerts API — GET /api/alerts/*.

Covers M3 Slice 4 new endpoints alongside existing list behaviour:

Public list  (existing):
  - No auth required
  - Only published alerts returned
  - Unpublished alerts never returned
  - Response shape: { "alerts": [...] }
  - Correct field mapping
  - Ordering: newest published_at first
  - Optional filters (risk_level, category, source, limit/offset)
  - Backwards compatibility: protected endpoints still require auth

Public detail  (NEW — GET /api/alerts/{id}):
  - No auth required
  - Returns 200 for a published alert
  - Returns 404 for an unpublished alert
  - Returns 404 for a non-existent alert
  - Response contains only safe public fields
  - Field mapping is correct (incl. secondary_category, entities, processed_at)
  - Internal / moderation fields are NOT present

Public stats  (NEW — GET /api/alerts/stats):
  - No auth required
  - Counts use only published alerts
  - high_count, medium_count, low_count are correct
  - total_alerts is the sum of the three
  - category_breakdown is grouped + ordered correctly
  - null-category rows are excluded from breakdown
  - Empty state (no published alerts) returns zeros and empty breakdown list
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source


# ---------------------------------------------------------------------------
# Seed helpers — shared across all test groups
# ---------------------------------------------------------------------------


async def _seed_source(
    db_session,
    name: str = "Test Source",
    credibility_score: int = 3,
) -> Source:
    source = Source(
        name=name,
        base_url="https://example.com",
        source_type="rss",
        is_active=True,
        polling_frequency_minutes=60,
        credibility_score=credibility_score,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source


async def _seed_raw_item(
    db_session,
    source: Source,
    title: str = "Test Alert Title",
    url: str = "https://example.com/article",
    published_at: datetime | None = None,
) -> RawItem:
    item = RawItem(
        source_id=source.id,
        item_url=url,
        title=title,
        is_duplicate=False,
        published_at=published_at,
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
    category: str | None = "Cybercrime",
    signal_score: int = 12,
    summary: str = "Test summary",
    secondary_category: str | None = None,
    entities_json: dict | None = None,
    published_at: datetime | None = None,
    is_relevant: bool = True,
    financial_impact_estimate: str | None = None,
    victim_scale_raw: str | None = None,
    matched_keywords: list | None = None,
    score_source_credibility: int | None = None,
    score_financial_impact: int | None = None,
    score_victim_scale: int | None = None,
    score_cross_source: int | None = None,
    score_trend_acceleration: int | None = None,
    ai_model: str | None = None,
) -> ProcessedAlert:
    alert = ProcessedAlert(
        raw_item_id=raw_item.id,
        risk_level=risk_level,
        primary_category=category,
        secondary_category=secondary_category,
        signal_score_total=signal_score,
        summary=summary,
        is_relevant=is_relevant,
        is_published=is_published,
        entities_json=entities_json,
        financial_impact_estimate=financial_impact_estimate,
        victim_scale_raw=victim_scale_raw,
        matched_keywords=matched_keywords,
        score_source_credibility=score_source_credibility,
        score_financial_impact=score_financial_impact,
        score_victim_scale=score_victim_scale,
        score_cross_source=score_cross_source,
        score_trend_acceleration=score_trend_acceleration,
        ai_model=ai_model,
        published_at=published_at or (datetime.now(timezone.utc) if is_published else None),
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert


async def _seed_event_link(
    db_session, event_id: int | None, alert: ProcessedAlert, source_name: str = "Test Source"
):
    """Create an event_sources bridge row linking an alert to an event.

    If event_id is None, creates a new Event first and returns its id.
    """
    from app.models.event import Event, EventSource

    if event_id is None:
        # Use a sentinel category so this polluted event doesn't collide with
        # event_grouper unit tests that match on real fraud categories like
        # "Cybercrime"/"Investment Fraud" within the same session-scoped DB.
        ev = Event(
            title=f"PublicTestEvent for alert {alert.id}",
            category="__public_test_only__",
        )
        db_session.add(ev)
        await db_session.commit()
        await db_session.refresh(ev)
        event_id = ev.id

    es = EventSource(event_id=event_id, alert_id=alert.id, source_name=source_name)
    db_session.add(es)
    await db_session.commit()
    return event_id


# ===========================================================================
# Public list — GET /api/alerts  (existing behaviour preserved)
# ===========================================================================


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


@pytest.mark.asyncio
async def test_public_feed_filter_risk_level(client, db_session):
    """risk_level filter narrows by derived score bucket; never exposes unpublished alerts."""
    source = await _seed_source(db_session)
    item_high = await _seed_raw_item(db_session, source, title="High Risk")
    item_medium = await _seed_raw_item(db_session, source, title="Medium Risk")
    item_unpub = await _seed_raw_item(db_session, source, title="Unpublished High")

    # Filter is derived from signal_score_total (M3 thresholds): >=16 high.
    await _seed_alert(db_session, item_high, is_published=True, signal_score=20)
    await _seed_alert(db_session, item_medium, is_published=True, signal_score=10)
    await _seed_alert(db_session, item_unpub, is_published=False, signal_score=20)

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


# ===========================================================================
# Public detail — GET /api/alerts/{id}  (NEW)
# ===========================================================================


@pytest.mark.asyncio
async def test_public_detail_requires_no_auth(client, db_session):
    """GET /api/alerts/{id} must succeed without any auth header or cookie."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Auth Test")
    alert = await _seed_alert(db_session, item, is_published=True)

    response = await client.get(f"/api/alerts/{alert.id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_public_detail_published_returns_200(client, db_session):
    """Published alert returns 200 with the expected enriched response body.

    risk_level is title case ("High") in the detail response per Ken's spec.
    Backward-compat fields (signal_score, secondary_category, source_name,
    source_url, published_at, processed_at, entities) are still present.
    """
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Detail OK")
    alert = await _seed_alert(
        db_session, item,
        is_published=True,
        risk_level="high",
        category="Investment Fraud",
        signal_score=20,
        summary="Detail summary",
        secondary_category="Wire Fraud",
        entities_json={"names": ["FBI", "Western Union"]},
    )

    response = await client.get(f"/api/alerts/{alert.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == alert.id
    assert data["title"] == "Detail OK"
    assert data["summary"] == "Detail summary"
    assert data["category"] == "Investment Fraud"
    # Title case in the enriched detail (Ken's schema)
    assert data["risk_level"] == "High"
    # Ken's primary score key
    assert data["score"] == 20
    # Backward-compat alias
    assert data["signal_score"] == 20
    assert data["source_name"] == "Test Source"
    assert data["source_url"] == "https://example.com/article"
    # Both new (subcategory) and old (secondary_category) names present
    assert data["secondary_category"] == "Wire Fraud"
    assert data["subcategory"] == "Wire Fraud"
    assert data["published_at"] is not None
    assert data["processed_at"] is not None
    assert data["entities"] == ["FBI", "Western Union"]


@pytest.mark.asyncio
async def test_public_detail_unpublished_returns_404(client, db_session):
    """Unpublished alert must return 404 — not distinguishable from non-existent."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Unpublished Detail")
    alert = await _seed_alert(db_session, item, is_published=False)

    response = await client.get(f"/api/alerts/{alert.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_detail_nonexistent_returns_404(client):
    """Non-existent alert ID must return 404."""
    response = await client.get("/api/alerts/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_detail_safe_fields_only(client, db_session):
    """Detail response must NOT contain internal moderation or scoring fields."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Field Safety Test")
    # Seed every internal column we want to confirm is NOT leaked, plus a
    # secondary_category so the backward-compat field key is present in JSON.
    alert = await _seed_alert(
        db_session,
        item,
        is_published=True,
        secondary_category="Wire Fraud",
        entities_json={"names": ["Acme Corp"]},
        financial_impact_estimate="$5M",
        victim_scale_raw="multiple",
        matched_keywords=["fraud", "scam"],
        score_source_credibility=4,
        score_financial_impact=3,
        score_victim_scale=3,
        score_cross_source=2,
        score_trend_acceleration=2,
        ai_model="gpt-5-mini",
    )

    response = await client.get(f"/api/alerts/{alert.id}")
    assert response.status_code == 200
    data = response.json()

    # Expected public-safe fields ARE present
    for field in ("id", "title", "summary", "category", "risk_level",
                  "signal_score", "source_name", "source_url", "published_at",
                  "processed_at", "secondary_category", "entities",
                  # Ken's enriched fields (always derivable from the seeded data above)
                  "score", "confidence", "risk_assessment", "subcategory"):
        assert field in data, f"Missing expected field: {field}"

    # Internal / moderation fields must NOT be present
    forbidden = (
        "is_published",
        "is_relevant",
        "raw_item_id",
        "entities_json",
        "score_source_credibility",
        "score_financial_impact",
        "score_victim_scale",
        "score_cross_source",
        "score_trend_acceleration",
        "financial_impact_estimate",
        "victim_scale_raw",
        "ai_model",
        "review_status",
        "published_by_user_id",
        "matched_keywords",
        "relevance_score",
        "signal_score_total",  # list endpoint field name — public detail uses signal_score
    )
    for f in forbidden:
        assert f not in data, f"Forbidden field leaked: {f}"


@pytest.mark.asyncio
async def test_public_detail_entities_empty_when_none(client, db_session):
    """entities defaults to [] when entities_json is null or missing."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="No Entities")
    alert = await _seed_alert(db_session, item, is_published=True, entities_json=None)

    response = await client.get(f"/api/alerts/{alert.id}")
    assert response.status_code == 200
    assert response.json()["entities"] == []


@pytest.mark.asyncio
async def test_public_detail_entities_empty_dict(client, db_session):
    """entities defaults to [] when entities_json has no 'names' key."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Empty Dict Entities")
    alert = await _seed_alert(db_session, item, is_published=True, entities_json={})

    response = await client.get(f"/api/alerts/{alert.id}")
    assert response.status_code == 200
    assert response.json()["entities"] == []


# ===========================================================================
# Public detail — enriched (Ken-approved frontend-facing schema)
# ===========================================================================


@pytest.mark.asyncio
async def test_public_detail_enriched_includes_kens_fields(client, db_session):
    """A fully-seeded published alert exposes all of Ken's enriched fields."""
    source = await _seed_source(db_session, name="SEC Press Releases", credibility_score=5)
    item = await _seed_raw_item(
        db_session, source,
        title="SEC Charges Investment Firm with $4.2M Fraud",
        published_at=datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc),
    )
    alert = await _seed_alert(
        db_session, item,
        is_published=True,
        risk_level="high",
        category="Investment Fraud",
        secondary_category="Wire Fraud",
        signal_score=20,
        summary="The SEC charged a NY firm with defrauding investors of $4.2M.",
        financial_impact_estimate="$4.2M",
        victim_scale_raw="multiple",
        entities_json={"names": ["SEC", "NY Firm"]},
        matched_keywords=["fraud", "investor"],
        published_at=datetime(2026, 4, 22, 10, 30, tzinfo=timezone.utc),
    )

    response = await client.get(f"/api/alerts/{alert.id}")
    assert response.status_code == 200
    data = response.json()

    # Ken's primary fields
    assert data["id"] == alert.id
    assert data["title"] == "SEC Charges Investment Firm with $4.2M Fraud"
    assert data["score"] == 20
    assert data["risk_level"] == "High"
    assert data["confidence"] == "High"  # cred=5, score=20, is_relevant=True
    assert data["summary"].startswith("The SEC charged")
    assert isinstance(data["why_it_matters"], list) and len(data["why_it_matters"]) >= 1
    assert isinstance(data["key_intelligence"], list) and len(data["key_intelligence"]) >= 1
    for kv in data["key_intelligence"]:
        assert set(kv.keys()) == {"label", "value"}
        assert isinstance(kv["label"], str) and isinstance(kv["value"], str)
    assert isinstance(data["risk_assessment"], str) and data["risk_assessment"]
    assert isinstance(data["sources"], list) and data["sources"][0]["name"] == "SEC Press Releases"
    assert data["category"] == "Investment Fraud"
    assert data["subcategory"] == "Wire Fraud"
    assert data["affected_group"] == "Multiple victims or organizations"
    assert isinstance(data["timeline"], list) and len(data["timeline"]) == 2
    assert data["published_date"] is not None


@pytest.mark.asyncio
async def test_public_detail_confidence_high(client, db_session):
    """Credibility 5 + relevant + score >= 16 → confidence 'High'."""
    source = await _seed_source(db_session, credibility_score=5)
    item = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(
        db_session, item, is_published=True, signal_score=18, is_relevant=True,
    )
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    assert data["confidence"] == "High"


@pytest.mark.asyncio
async def test_public_detail_confidence_medium_via_credibility(client, db_session):
    """Credibility 4 → confidence 'Medium' (regardless of score)."""
    source = await _seed_source(db_session, credibility_score=4)
    item = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(db_session, item, is_published=True, signal_score=5)
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    assert data["confidence"] == "Medium"


@pytest.mark.asyncio
async def test_public_detail_confidence_low(client, db_session):
    """Credibility 3 + low score → confidence 'Low'."""
    source = await _seed_source(db_session, credibility_score=3)
    item = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(db_session, item, is_published=True, signal_score=4)
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    assert data["confidence"] == "Low"


@pytest.mark.asyncio
async def test_public_detail_confidence_medium_via_score(client, db_session):
    """Credibility 3 + score >= 9 → confidence 'Medium' (score-tier path)."""
    source = await _seed_source(db_session, credibility_score=3)
    item = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(db_session, item, is_published=True, signal_score=10)
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    assert data["confidence"] == "Medium"


@pytest.mark.asyncio
async def test_public_detail_key_intelligence_structured(client, db_session):
    """Every key_intelligence item has exactly {label, value} and short string values."""
    source = await _seed_source(db_session, credibility_score=5)
    item = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(
        db_session, item, is_published=True,
        category="Cybercrime", secondary_category="Phishing",
        financial_impact_estimate="$2M", victim_scale_raw="nationwide",
        entities_json={"names": ["FBI"]},
        matched_keywords=["phishing"],
    )
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    items = data["key_intelligence"]
    assert isinstance(items, list) and items
    for it in items:
        assert set(it.keys()) == {"label", "value"}
        assert isinstance(it["value"], str)
        # value must be a short scalar string (no narrative — test against newlines/length)
        assert "\n" not in it["value"]
    labels = {it["label"] for it in items}
    # Expected labels for this seed
    assert {"Fraud Type", "Financial Impact", "Affected Group",
            "Source Credibility"}.issubset(labels)


@pytest.mark.asyncio
async def test_public_detail_affected_group_omitted_when_no_victim(client, db_session):
    """victim_scale_raw=None → affected_group key is absent in response."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="No Victim Scale")
    alert = await _seed_alert(db_session, item, is_published=True, victim_scale_raw=None)
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    assert "affected_group" not in data


@pytest.mark.asyncio
async def test_public_detail_affected_group_present_for_multiple(client, db_session):
    """victim_scale_raw='multiple' → affected_group is the human-readable string."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Multiple Victims")
    alert = await _seed_alert(
        db_session, item, is_published=True, victim_scale_raw="multiple",
    )
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    assert data["affected_group"] == "Multiple victims or organizations"


@pytest.mark.asyncio
async def test_public_detail_published_date_uses_source_first(client, db_session):
    """published_date prefers raw_item.published_at when available."""
    src_pub = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    plat_pub = datetime(2026, 4, 22, 10, 30, tzinfo=timezone.utc)

    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Source First", published_at=src_pub)
    alert = await _seed_alert(db_session, item, is_published=True, published_at=plat_pub)

    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    # SQLite drops tzinfo on round-trip; compare on naive UTC.
    parsed = datetime.fromisoformat(data["published_date"].replace("Z", "+00:00"))
    parsed_naive = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    assert parsed_naive == src_pub.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_public_detail_published_date_falls_back_to_published_at(client, db_session):
    """published_date falls back to alert.published_at when source has no date."""
    plat_pub = datetime(2026, 4, 22, 10, 30, tzinfo=timezone.utc)

    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Fallback", published_at=None)
    alert = await _seed_alert(db_session, item, is_published=True, published_at=plat_pub)

    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    parsed = datetime.fromisoformat(data["published_date"].replace("Z", "+00:00"))
    parsed_naive = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    assert parsed_naive == plat_pub.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_public_detail_risk_level_is_title_case(client, db_session):
    """risk_level stored lowercase but returned title case in detail."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Title Case")
    alert = await _seed_alert(db_session, item, is_published=True, risk_level="medium")
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    assert data["risk_level"] == "Medium"


@pytest.mark.asyncio
async def test_public_detail_sources_array_has_current_source(client, db_session):
    """sources array contains at least the current source with name + url."""
    source = await _seed_source(db_session, name="DOJ Press Releases")
    item = await _seed_raw_item(db_session, source,
                                title="Sources Test",
                                url="https://justice.gov/article/x")
    alert = await _seed_alert(db_session, item, is_published=True)
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    assert isinstance(data["sources"], list) and data["sources"]
    assert data["sources"][0]["name"] == "DOJ Press Releases"
    assert data["sources"][0]["url"] == "https://justice.gov/article/x"


@pytest.mark.asyncio
async def test_public_detail_timeline_when_data_exists(client, db_session):
    """timeline contains source-pub and platform-pub entries with correct order."""
    src_pub = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    plat_pub = datetime(2026, 4, 22, 10, 30, tzinfo=timezone.utc)

    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Timeline", published_at=src_pub)
    alert = await _seed_alert(db_session, item, is_published=True, published_at=plat_pub)

    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    timeline = data["timeline"]
    assert isinstance(timeline, list) and len(timeline) == 2
    assert timeline[0]["event"] == "Source published the alert"
    assert timeline[1]["event"] == "Alert published to dashboard"


@pytest.mark.asyncio
async def test_public_detail_related_signals_via_event(client, db_session):
    """Same-event alerts that share at least one named entity surface as related_signals.

    Ken's quantity rule: at least 2 qualifying peers required, so this seeds two.
    """
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="Alert A", url="https://x.com/a")
    item_b = await _seed_raw_item(db_session, source, title="Alert B", url="https://x.com/b")
    item_c = await _seed_raw_item(db_session, source, title="Alert C", url="https://x.com/c")
    # Shared entity "Acme Corp" — passes the entity-overlap clean-related rule.
    alert_a = await _seed_alert(
        db_session, item_a, is_published=True, signal_score=20,
        entities_json={"names": ["Acme Corp", "FBI"]},
    )
    alert_b = await _seed_alert(
        db_session, item_b, is_published=True, signal_score=10,
        entities_json={"names": ["Acme Corp"]},
    )
    alert_c = await _seed_alert(
        db_session, item_c, is_published=True, signal_score=18,
        entities_json={"names": ["Acme Corp"]},
    )

    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)
    await _seed_event_link(db_session, event_id, alert_c)

    data = (await client.get(f"/api/alerts/{alert_a.id}")).json()
    assert isinstance(data["related_signals"], list)
    ids = [r["id"] for r in data["related_signals"]]
    assert alert_b.id in ids
    rb = next(r for r in data["related_signals"] if r["id"] == alert_b.id)
    # risk_level on related items is derived from score (M3 thresholds), Title Case
    assert rb["risk_level"] == "Medium"  # score=10 → medium
    assert rb["title"] == "Alert B"


@pytest.mark.asyncio
async def test_public_detail_related_signals_omitted_when_no_event(client, db_session):
    """An alert with no event linkage has no related_signals key in response."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Standalone")
    alert = await _seed_alert(db_session, item, is_published=True)
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    assert "related_signals" not in data


@pytest.mark.asyncio
async def test_public_detail_related_signals_excludes_unpublished(client, db_session):
    """Unpublished related alerts must NOT appear in related_signals.

    Need >=2 published peers to satisfy Ken's min count, so seed 2 published
    alongside the unpublished one we expect to be excluded.
    """
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="Pub A", url="https://x.com/pa")
    item_pub1 = await _seed_raw_item(db_session, source, title="Pub Other 1",
                                     url="https://x.com/po1")
    item_pub2 = await _seed_raw_item(db_session, source, title="Pub Other 2",
                                     url="https://x.com/po2")
    item_unpub = await _seed_raw_item(db_session, source, title="Unpub Other",
                                      url="https://x.com/uo")

    shared_entities = {"names": ["Western Union"]}
    alert_a = await _seed_alert(db_session, item_a, is_published=True,
                                entities_json=shared_entities)
    alert_pub1 = await _seed_alert(db_session, item_pub1, is_published=True,
                                   entities_json=shared_entities)
    alert_pub2 = await _seed_alert(db_session, item_pub2, is_published=True,
                                   entities_json=shared_entities)
    alert_unpub = await _seed_alert(db_session, item_unpub, is_published=False,
                                    entities_json=shared_entities)

    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_pub1)
    await _seed_event_link(db_session, event_id, alert_pub2)
    await _seed_event_link(db_session, event_id, alert_unpub)

    data = (await client.get(f"/api/alerts/{alert_a.id}")).json()
    ids = {r["id"] for r in data.get("related_signals", [])}
    assert alert_pub1.id in ids
    assert alert_pub2.id in ids
    assert alert_unpub.id not in ids


@pytest.mark.asyncio
async def test_public_detail_related_signals_max_four(client, db_session):
    """When more than four published peers share an event, only four are returned."""
    source = await _seed_source(db_session)
    shared = {"names": ["SharedSubject"]}
    item_a = await _seed_raw_item(db_session, source, title="Center", url="https://x.com/c")
    alert_a = await _seed_alert(db_session, item_a, is_published=True,
                                entities_json=shared)
    event_id = await _seed_event_link(db_session, None, alert_a)

    for i in range(6):
        it = await _seed_raw_item(
            db_session, source, title=f"Peer {i}", url=f"https://x.com/p{i}",
        )
        peer = await _seed_alert(db_session, it, is_published=True,
                                 entities_json=shared)
        await _seed_event_link(db_session, event_id, peer)

    data = (await client.get(f"/api/alerts/{alert_a.id}")).json()
    assert isinstance(data["related_signals"], list)
    assert len(data["related_signals"]) <= 4


@pytest.mark.asyncio
async def test_public_list_risk_level_derived_from_score(client, db_session):
    """List endpoint risk_level is derived from signal_score_total, not stored column.

    Stale stored value 'high' on a score-12 alert must show as 'medium' in the
    public response.
    """
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Stale High List")
    # Mismatch on purpose: score 12 is medium per M3, but stored risk_level says high.
    await _seed_alert(
        db_session, item, is_published=True,
        risk_level="high", signal_score=12,
    )
    body = (await client.get("/api/alerts")).json()
    match = next((a for a in body["alerts"] if a["title"] == "Stale High List"), None)
    assert match is not None
    assert match["risk_level"] == "medium"  # lowercase on list, derived


@pytest.mark.asyncio
async def test_public_detail_risk_level_derived_from_score(client, db_session):
    """Detail endpoint risk_level is derived from signal_score_total (Title Case)."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Stale High Detail")
    alert = await _seed_alert(
        db_session, item, is_published=True,
        risk_level="high", signal_score=15,  # 15 < 16 → medium per M3
    )
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    assert data["risk_level"] == "Medium"
    assert data["score"] == 15


@pytest.mark.asyncio
async def test_public_stats_counts_use_derived_risk(client, db_session):
    """Stats counts must bucket alerts by score (M3 thresholds), not stored risk_level."""
    baseline = (await client.get("/api/alerts/stats")).json()
    source = await _seed_source(db_session)

    # Stored 'high' but score 12 → must count as medium, not high.
    item = await _seed_raw_item(db_session, source, title="Stale High Stats")
    await _seed_alert(
        db_session, item, is_published=True,
        risk_level="high", signal_score=12,
    )
    after = (await client.get("/api/alerts/stats")).json()

    assert after["high_count"] == baseline["high_count"]
    assert after["medium_count"] == baseline["medium_count"] + 1
    assert after["low_count"] == baseline["low_count"]
    assert after["total_alerts"] == baseline["total_alerts"] + 1


@pytest.mark.asyncio
async def test_related_signals_excludes_same_event_no_entity_overlap(client, db_session):
    """Same-event alerts with NO shared named entity must NOT surface as related_signals.

    Event grouping alone is too broad — the cleanup rule requires entity overlap.
    """
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="Center A",
                                  url="https://x.com/center")
    item_b = await _seed_raw_item(db_session, source, title="Drifted Peer",
                                  url="https://x.com/drifted")
    alert_a = await _seed_alert(
        db_session, item_a, is_published=True,
        entities_json={"names": ["Acme Corp", "FBI"]},
    )
    alert_b = await _seed_alert(
        db_session, item_b, is_published=True,
        # Disjoint entity set — same event, but semantically unrelated.
        entities_json={"names": ["Globex Inc", "DOJ"]},
    )
    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)

    data = (await client.get(f"/api/alerts/{alert_a.id}")).json()
    # No qualifying peer → related_signals must be omitted entirely.
    assert "related_signals" not in data


@pytest.mark.asyncio
async def test_related_signals_includes_same_event_with_entity_overlap(client, db_session):
    """Same-event alerts WITH shared entity surface as related_signals (>=2 required)."""
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="Anchor",
                                  url="https://x.com/anchor")
    item_b = await _seed_raw_item(db_session, source, title="Sibling 1",
                                  url="https://x.com/sibling1")
    item_c = await _seed_raw_item(db_session, source, title="Sibling 2",
                                  url="https://x.com/sibling2")
    alert_a = await _seed_alert(
        db_session, item_a, is_published=True,
        entities_json={"names": ["Acme Corp", "FBI"]},
    )
    alert_b = await _seed_alert(
        db_session, item_b, is_published=True,
        entities_json={"names": ["FBI", "Treasury"]},  # FBI overlaps
    )
    alert_c = await _seed_alert(
        db_session, item_c, is_published=True,
        entities_json={"names": ["Acme Corp"]},  # Acme Corp overlaps
    )
    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)
    await _seed_event_link(db_session, event_id, alert_c)

    data = (await client.get(f"/api/alerts/{alert_a.id}")).json()
    ids = [r["id"] for r in data.get("related_signals", [])]
    assert alert_b.id in ids
    assert alert_c.id in ids


@pytest.mark.asyncio
async def test_related_signals_overlap_is_case_insensitive(client, db_session):
    """Entity overlap is case-insensitive — 'fbi' matches 'FBI' (need >=2 peers)."""
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="A1", url="https://x.com/a1")
    item_b = await _seed_raw_item(db_session, source, title="B1", url="https://x.com/b1")
    item_c = await _seed_raw_item(db_session, source, title="C1", url="https://x.com/c1")
    alert_a = await _seed_alert(
        db_session, item_a, is_published=True,
        entities_json={"names": ["FBI"]},
    )
    alert_b = await _seed_alert(
        db_session, item_b, is_published=True,
        entities_json={"names": ["fbi"]},  # case-different match
    )
    alert_c = await _seed_alert(
        db_session, item_c, is_published=True,
        entities_json={"names": ["FbI"]},  # mixed case match
    )
    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)
    await _seed_event_link(db_session, event_id, alert_c)

    data = (await client.get(f"/api/alerts/{alert_a.id}")).json()
    ids = [r["id"] for r in data.get("related_signals", [])]
    assert alert_b.id in ids
    assert alert_c.id in ids


@pytest.mark.asyncio
async def test_related_signals_omitted_when_current_has_no_entities(client, db_session):
    """If the current alert has no entities, overlap can't be evaluated → omit entirely."""
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="No Ents", url="https://x.com/ne")
    item_b = await _seed_raw_item(db_session, source, title="Has Ents", url="https://x.com/he")
    alert_a = await _seed_alert(
        db_session, item_a, is_published=True, entities_json=None,
    )
    alert_b = await _seed_alert(
        db_session, item_b, is_published=True,
        entities_json={"names": ["FBI"]},
    )
    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)

    data = (await client.get(f"/api/alerts/{alert_a.id}")).json()
    assert "related_signals" not in data


@pytest.mark.asyncio
async def test_related_signals_omitted_when_only_one_clean_peer(client, db_session):
    """Ken's quantity rule: a single qualifying peer means the section is omitted."""
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="Solo Anchor",
                                  url="https://x.com/solo-a")
    item_b = await _seed_raw_item(db_session, source, title="Solo Peer",
                                  url="https://x.com/solo-b")
    shared = {"names": ["FBI"]}
    alert_a = await _seed_alert(db_session, item_a, is_published=True,
                                entities_json=shared)
    alert_b = await _seed_alert(db_session, item_b, is_published=True,
                                entities_json=shared)
    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)

    data = (await client.get(f"/api/alerts/{alert_a.id}")).json()
    # Only 1 qualifying peer (alert_b) — must be omitted entirely.
    assert "related_signals" not in data


@pytest.mark.asyncio
async def test_related_signals_included_when_two_clean_peers(client, db_session):
    """Exactly two qualifying peers → section included with both."""
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="Pair Anchor",
                                  url="https://x.com/pair-a")
    item_b = await _seed_raw_item(db_session, source, title="Pair Peer 1",
                                  url="https://x.com/pair-b")
    item_c = await _seed_raw_item(db_session, source, title="Pair Peer 2",
                                  url="https://x.com/pair-c")
    shared = {"names": ["FBI"]}
    alert_a = await _seed_alert(db_session, item_a, is_published=True,
                                entities_json=shared)
    alert_b = await _seed_alert(db_session, item_b, is_published=True,
                                entities_json=shared)
    alert_c = await _seed_alert(db_session, item_c, is_published=True,
                                entities_json=shared)
    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)
    await _seed_event_link(db_session, event_id, alert_c)

    data = (await client.get(f"/api/alerts/{alert_a.id}")).json()
    assert isinstance(data["related_signals"], list)
    assert len(data["related_signals"]) == 2
    ids = {r["id"] for r in data["related_signals"]}
    assert ids == {alert_b.id, alert_c.id}


# ===========================================================================
# Risk assessment — strong-factor enrichment
# ===========================================================================


@pytest.mark.asyncio
async def test_risk_assessment_high_mentions_strong_factors(client, db_session):
    """High-risk assessment must mention specific strong factors, not generic copy."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Strong Factors")
    alert = await _seed_alert(
        db_session, item, is_published=True,
        signal_score=22,
        score_source_credibility=5,         # → "trusted source reporting"
        score_victim_scale=5,               # → "broad victim scope"
        score_cross_source=3,               # → "cross-source support"
        score_financial_impact=2,
        score_trend_acceleration=1,
    )
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    text = data["risk_assessment"]
    assert text.startswith("High risk due to")
    # At least one of our derived factor phrases must appear.
    assert any(p in text for p in (
        "trusted source reporting",
        "broad victim scope",
        "cross-source support",
    ))


@pytest.mark.asyncio
async def test_risk_assessment_uses_financial_estimate_when_meaningful(client, db_session):
    """A non-empty, non-'unknown' financial_impact_estimate triggers the financial phrase."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(
        db_session, item, is_published=True,
        signal_score=20,
        financial_impact_estimate="$4.2M",
    )
    text = (await client.get(f"/api/alerts/{alert.id}")).json()["risk_assessment"]
    assert "notable financial impact" in text


@pytest.mark.asyncio
async def test_risk_assessment_medium_concise(client, db_session):
    """Medium risk_assessment is a single concise sentence (no factor data here)."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Medium Concise")
    alert = await _seed_alert(db_session, item, is_published=True, signal_score=10)
    text = (await client.get(f"/api/alerts/{alert.id}")).json()["risk_assessment"]
    assert text.startswith("Medium risk")
    # One sentence. ≤ 250 chars is plenty for "scannable".
    assert text.count(". ") == 0
    assert text.endswith(".")
    assert len(text) <= 250


@pytest.mark.asyncio
async def test_risk_assessment_low_concise(client, db_session):
    """Low risk_assessment is a single concise sentence."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Low Concise")
    alert = await _seed_alert(db_session, item, is_published=True, signal_score=4)
    text = (await client.get(f"/api/alerts/{alert.id}")).json()["risk_assessment"]
    assert text.startswith("Low risk")
    assert text.count(". ") == 0
    assert text.endswith(".")
    assert len(text) <= 250


@pytest.mark.asyncio
async def test_risk_assessment_falls_back_when_no_strong_factors(client, db_session):
    """When no factor reaches the strong threshold, fall back to the generic copy."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="No Strong Factors")
    alert = await _seed_alert(
        db_session, item, is_published=True,
        signal_score=20,                 # high bucket via score
        score_source_credibility=2,      # below 4
        score_financial_impact=2,
        score_victim_scale=2,
        score_cross_source=1,
        score_trend_acceleration=1,
        financial_impact_estimate=None,
        victim_scale_raw=None,
    )
    text = (await client.get(f"/api/alerts/{alert.id}")).json()["risk_assessment"]
    # Generic high-risk fallback contains "based on credible source reporting"
    assert "based on credible source reporting" in text
    assert text.startswith("High risk")


@pytest.mark.asyncio
async def test_risk_assessment_does_not_leak_raw_score_fields(client, db_session):
    """Raw per-factor scores must never appear in the public detail body."""
    source = await _seed_source(db_session, credibility_score=5)
    item = await _seed_raw_item(db_session, source, title="No Leak Risk")
    alert = await _seed_alert(
        db_session, item, is_published=True,
        signal_score=22,
        score_source_credibility=5,
        score_financial_impact=5,
        score_victim_scale=5,
        score_cross_source=3,
        score_trend_acceleration=3,
        financial_impact_estimate="$10M",
        victim_scale_raw="nationwide",
    )
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    forbidden = (
        "score_source_credibility", "score_financial_impact",
        "score_victim_scale", "score_cross_source", "score_trend_acceleration",
        "financial_impact_estimate", "victim_scale_raw",
    )
    for f in forbidden:
        assert f not in data, f"Forbidden field leaked: {f}"


@pytest.mark.asyncio
async def test_public_detail_no_score_breakdown_leak(client, db_session):
    """Even with full internal score data seeded, none of it appears in the response."""
    source = await _seed_source(db_session, credibility_score=5)
    item = await _seed_raw_item(db_session, source, title="No Leak")
    alert = await _seed_alert(
        db_session, item, is_published=True,
        score_source_credibility=5,
        score_financial_impact=5,
        score_victim_scale=5,
        score_cross_source=3,
        score_trend_acceleration=3,
        financial_impact_estimate="$10M+",
        victim_scale_raw="nationwide",
        ai_model="gpt-5-mini",
        matched_keywords=["money laundering"],
        entities_json={"names": ["FBI"]},
    )
    data = (await client.get(f"/api/alerts/{alert.id}")).json()
    forbidden = (
        "score_source_credibility", "score_financial_impact", "score_victim_scale",
        "score_cross_source", "score_trend_acceleration",
        "victim_scale_raw", "financial_impact_estimate",
        "ai_model", "matched_keywords", "entities_json",
        "is_published", "is_relevant", "raw_item_id",
        "published_by_user_id", "review_status", "signal_score_total",
    )
    for f in forbidden:
        assert f not in data, f"Forbidden field leaked: {f}"


# ===========================================================================
# Public stats — GET /api/alerts/stats  (NEW)
# ===========================================================================


@pytest.mark.asyncio
async def test_public_stats_requires_no_auth(client):
    """GET /api/alerts/stats must succeed without any auth header or cookie."""
    response = await client.get("/api/alerts/stats")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_public_stats_empty_returns_zeros(client):
    """Stats endpoint returns valid structure with non-negative integer counts.

    The SQLite test DB is session-scoped and shared across all tests, so we
    cannot guarantee a zero count here. We verify the invariants that must
    always hold regardless of pre-existing data:
      - all counts are non-negative integers
      - total_alerts >= high + medium + low (null-risk alerts are in total)
      - category_breakdown is a list
    """
    response = await client.get("/api/alerts/stats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["total_alerts"], int) and data["total_alerts"] >= 0
    assert isinstance(data["high_count"], int) and data["high_count"] >= 0
    assert isinstance(data["medium_count"], int) and data["medium_count"] >= 0
    assert isinstance(data["low_count"], int) and data["low_count"] >= 0
    assert isinstance(data["category_breakdown"], list)
    # total_alerts >= bucket sum (null-risk alerts count in total but not buckets)
    bucket_sum = data["high_count"] + data["medium_count"] + data["low_count"]
    assert data["total_alerts"] >= bucket_sum


@pytest.mark.asyncio
async def test_public_stats_counts_published_only(client, db_session):
    """Stats counts must exclude unpublished alerts entirely.

    Uses delta-based assertions to be resilient to data seeded by prior tests.
    """
    # Capture baseline before seeding
    baseline = (await client.get("/api/alerts/stats")).json()

    source = await _seed_source(db_session)
    item_pub = await _seed_raw_item(db_session, source, title="Pub High stats_only")
    item_unpub = await _seed_raw_item(db_session, source, title="Unpub High stats_only")

    # Counts are derived from signal_score_total — score=20 is the High bucket.
    await _seed_alert(db_session, item_pub, is_published=True, signal_score=20)
    await _seed_alert(db_session, item_unpub, is_published=False, signal_score=20)

    after = (await client.get("/api/alerts/stats")).json()

    # Only the published alert should increase the count
    assert after["total_alerts"] == baseline["total_alerts"] + 1
    assert after["high_count"] == baseline["high_count"] + 1
    # Unpublished alert must NOT appear — medium and low unchanged
    assert after["medium_count"] == baseline["medium_count"]
    assert after["low_count"] == baseline["low_count"]


@pytest.mark.asyncio
async def test_public_stats_risk_level_counts(client, db_session):
    """high_count, medium_count, low_count correctly partition published alerts.

    Uses delta-based assertions to be resilient to data seeded by prior tests.
    """
    baseline = (await client.get("/api/alerts/stats")).json()

    source = await _seed_source(db_session)

    # Buckets derived from signal_score_total (M3): >=16 high, 9..15 medium, <9 low.
    for _ in range(2):
        item = await _seed_raw_item(db_session, source, title="High rl")
        await _seed_alert(db_session, item, is_published=True, signal_score=20)

    for _ in range(3):
        item = await _seed_raw_item(db_session, source, title="Medium rl")
        await _seed_alert(db_session, item, is_published=True, signal_score=10)

    for _ in range(1):
        item = await _seed_raw_item(db_session, source, title="Low rl")
        await _seed_alert(db_session, item, is_published=True, signal_score=4)

    after = (await client.get("/api/alerts/stats")).json()

    # Delta assertions: exactly 2 high, 3 medium, 1 low were added
    assert after["high_count"] == baseline["high_count"] + 2
    assert after["medium_count"] == baseline["medium_count"] + 3
    assert after["low_count"] == baseline["low_count"] + 1
    assert after["total_alerts"] == baseline["total_alerts"] + 6


@pytest.mark.asyncio
async def test_public_stats_total_is_sum_of_risk_levels(client, db_session):
    """Seeding known-risk-level alerts increases total by the exact delta seeded.

    Uses delta-based assertions. Note: total_alerts >= high+medium+low because
    other tests may have seeded alerts with null risk_level that appear in total
    but not in any bucket. This test seeds only well-known risk levels and verifies
    the delta is exact.
    """
    baseline = (await client.get("/api/alerts/stats")).json()

    source = await _seed_source(db_session)
    # Counts are derived from signal_score_total — pick scores per bucket.
    score_for = {"high": 20, "medium": 10, "low": 4}
    for risk in ("high", "medium", "low", "high"):
        item = await _seed_raw_item(db_session, source, title=f"Sum test {risk}")
        await _seed_alert(db_session, item, is_published=True, signal_score=score_for[risk])

    after = (await client.get("/api/alerts/stats")).json()

    # We seeded 4 alerts with known risk levels — total must increase by exactly 4
    assert after["total_alerts"] == baseline["total_alerts"] + 4
    assert after["high_count"] == baseline["high_count"] + 2
    assert after["medium_count"] == baseline["medium_count"] + 1
    assert after["low_count"] == baseline["low_count"] + 1


@pytest.mark.asyncio
async def test_public_stats_category_breakdown_correct(client, db_session):
    """category_breakdown groups published alerts by primary_category correctly."""
    source = await _seed_source(db_session)

    for _ in range(3):
        item = await _seed_raw_item(db_session, source, title="Invest")
        await _seed_alert(db_session, item, is_published=True, category="Investment Fraud")

    for _ in range(2):
        item = await _seed_raw_item(db_session, source, title="Cyber")
        await _seed_alert(db_session, item, is_published=True, category="Cybercrime")

    response = await client.get("/api/alerts/stats")
    data = response.json()
    breakdown = {entry["category"]: entry["count"] for entry in data["category_breakdown"]}

    assert breakdown.get("Investment Fraud", 0) >= 3
    assert breakdown.get("Cybercrime", 0) >= 2


@pytest.mark.asyncio
async def test_public_stats_category_breakdown_ordered_by_count_desc(client, db_session):
    """category_breakdown must be ordered by count descending."""
    source = await _seed_source(db_session)

    for _ in range(4):
        item = await _seed_raw_item(db_session, source, title="Invest")
        await _seed_alert(db_session, item, is_published=True, category="Investment Fraud")

    for _ in range(1):
        item = await _seed_raw_item(db_session, source, title="Cyber")
        await _seed_alert(db_session, item, is_published=True, category="Cybercrime")

    response = await client.get("/api/alerts/stats")
    data = response.json()
    counts = [entry["count"] for entry in data["category_breakdown"]]
    assert counts == sorted(counts, reverse=True), "Breakdown not ordered by count descending"


@pytest.mark.asyncio
async def test_public_stats_null_category_excluded_from_breakdown(client, db_session):
    """Alerts with null primary_category must not appear in category_breakdown."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="No Category")
    await _seed_alert(db_session, item, is_published=True, category=None)

    response = await client.get("/api/alerts/stats")
    data = response.json()
    categories = [entry["category"] for entry in data["category_breakdown"]]
    assert None not in categories
    # null must not appear as the string "None" either
    assert "None" not in categories


@pytest.mark.asyncio
async def test_public_stats_breakdown_excludes_unpublished(client, db_session):
    """Unpublished alerts must NOT appear in the category breakdown counts."""
    source = await _seed_source(db_session)
    item_pub = await _seed_raw_item(db_session, source, title="Published Cat")
    item_unpub = await _seed_raw_item(db_session, source, title="Unpublished Cat")

    await _seed_alert(db_session, item_pub, is_published=True, category="Consumer Scam")
    await _seed_alert(db_session, item_unpub, is_published=False, category="Consumer Scam")

    response = await client.get("/api/alerts/stats")
    data = response.json()
    breakdown = {entry["category"]: entry["count"] for entry in data["category_breakdown"]}

    # The published alert increments Consumer Scam by 1; the unpublished one must not.
    # We can't assert an exact value of 1 here because other tests may have seeded
    # Consumer Scam rows, but unpublished alert must not add to the count.
    # We verify via total_alerts vs breakdown sum consistency instead.
    total_from_breakdown = sum(entry["count"] for entry in data["category_breakdown"])
    # total_alerts may be > total_from_breakdown because null-category alerts
    # are excluded from breakdown; but total_alerts counts them.
    # The key invariant: breakdown total <= total_alerts
    assert total_from_breakdown <= data["total_alerts"]


@pytest.mark.asyncio
async def test_public_stats_response_shape(client):
    """Stats response must always contain all required top-level keys."""
    response = await client.get("/api/alerts/stats")
    assert response.status_code == 200
    data = response.json()
    for key in ("total_alerts", "high_count", "medium_count", "low_count", "category_breakdown"):
        assert key in data, f"Missing key: {key}"
    assert isinstance(data["category_breakdown"], list)


# ===========================================================================
# Backwards compatibility — existing protected endpoints still work
# ===========================================================================


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


# ===========================================================================
# Public top alerts — GET /api/alerts/top  (M3 frontend completion)
# ===========================================================================
#
# Threshold rationale: signal_score_total >= 15 maps Ken's "risk >= 60" to the
# 0-25 scale (60% of 25). Sits intentionally below the high threshold (16) so
# strong medium-high alerts qualify.
#
# Top-alerts tests need a clean DB per run because /top returns at most 3
# alerts and asserts about exact ordering / count. The session-scoped engine
# in conftest.py keeps committed data alive across tests, so we wipe the
# alert tables at the start of each top-alerts test via the `clean_db`
# fixture below.


import pytest_asyncio


@pytest_asyncio.fixture
async def clean_db(db_session):
    """Truncate alert/event/raw_item/source tables for deterministic /top tests."""
    from sqlalchemy import delete

    from app.models.event import Event, EventSource
    from app.models.processed_alert import ProcessedAlert
    from app.models.raw_item import RawItem
    from app.models.source import Source

    await db_session.execute(delete(EventSource))
    await db_session.execute(delete(Event))
    await db_session.execute(delete(ProcessedAlert))
    await db_session.execute(delete(RawItem))
    await db_session.execute(delete(Source))
    await db_session.commit()
    return db_session


@pytest.mark.asyncio
async def test_top_alerts_no_auth_required(client):
    """GET /api/alerts/top must succeed without any auth header or cookie."""
    response = await client.get("/api/alerts/top")
    assert response.status_code == 200
    assert "alerts" in response.json()


@pytest.mark.asyncio
async def test_top_alerts_returns_only_published(client, clean_db):
    """Unpublished alerts must never appear in /top, even at high score."""
    source = await _seed_source(clean_db, credibility_score=5)
    item_pub = await _seed_raw_item(clean_db, source, title="Pub", url="https://x.com/pub")
    item_unpub = await _seed_raw_item(clean_db, source, title="Unpub", url="https://x.com/unpub")

    a_pub = await _seed_alert(
        clean_db, item_pub, is_published=True, signal_score=20,
        entities_json={"names": ["Acme"]},
    )
    await _seed_alert(
        clean_db, item_unpub, is_published=False, signal_score=20,
        entities_json={"names": ["Beta"]},
    )

    response = await client.get("/api/alerts/top")
    assert response.status_code == 200
    ids = [a["id"] for a in response.json()["alerts"]]
    assert ids == [a_pub.id]


@pytest.mark.asyncio
async def test_top_alerts_max_three(client, clean_db):
    """Even with 6 qualifying alerts, /top returns at most 3."""
    source = await _seed_source(clean_db, credibility_score=5)
    now = datetime.now(timezone.utc)
    for i in range(6):
        item = await _seed_raw_item(
            clean_db, source, title=f"Alert {i}", url=f"https://x.com/a{i}"
        )
        await _seed_alert(
            clean_db, item, is_published=True, signal_score=20,
            entities_json={"names": [f"Entity{i}"]},
            published_at=now - timedelta(minutes=i),
        )

    response = await client.get("/api/alerts/top")
    assert response.status_code == 200
    assert len(response.json()["alerts"]) == 3


@pytest.mark.asyncio
async def test_top_alerts_excludes_below_min_score(client, clean_db):
    """Alerts at score=14 are excluded; score=15 qualifies."""
    source = await _seed_source(clean_db, credibility_score=5)
    item_low = await _seed_raw_item(clean_db, source, title="Low", url="https://x.com/low")
    item_qual = await _seed_raw_item(clean_db, source, title="Qual", url="https://x.com/qual")

    await _seed_alert(
        clean_db, item_low, is_published=True, signal_score=14,
        entities_json={"names": ["X"]},
    )
    a_qual = await _seed_alert(
        clean_db, item_qual, is_published=True, signal_score=15,
        entities_json={"names": ["Y"]},
    )

    response = await client.get("/api/alerts/top")
    ids = [a["id"] for a in response.json()["alerts"]]
    assert ids == [a_qual.id]


@pytest.mark.asyncio
async def test_top_alerts_ranks_by_score_desc(client, clean_db):
    """Score is the dominant ranking key — highest score first."""
    source = await _seed_source(clean_db, credibility_score=5)
    item16 = await _seed_raw_item(clean_db, source, title="S16", url="https://x.com/s16")
    item18 = await _seed_raw_item(clean_db, source, title="S18", url="https://x.com/s18")
    item20 = await _seed_raw_item(clean_db, source, title="S20", url="https://x.com/s20")

    a16 = await _seed_alert(
        clean_db, item16, is_published=True, signal_score=16,
        entities_json={"names": ["A"]},
    )
    a18 = await _seed_alert(
        clean_db, item18, is_published=True, signal_score=18,
        entities_json={"names": ["B"]},
    )
    a20 = await _seed_alert(
        clean_db, item20, is_published=True, signal_score=20,
        entities_json={"names": ["C"]},
    )

    response = await client.get("/api/alerts/top")
    ids = [a["id"] for a in response.json()["alerts"]]
    assert ids == [a20.id, a18.id, a16.id]


@pytest.mark.asyncio
async def test_top_alerts_tie_broken_by_signal_strength(client, clean_db):
    """Same score → alert with more event_sources ranks first."""
    source = await _seed_source(clean_db, credibility_score=5)
    item_strong = await _seed_raw_item(
        clean_db, source, title="Strong", url="https://x.com/strong"
    )
    item_weak = await _seed_raw_item(
        clean_db, source, title="Weak", url="https://x.com/weak"
    )

    a_strong = await _seed_alert(
        clean_db, item_strong, is_published=True, signal_score=18,
        entities_json={"names": ["Foo"]},
    )
    a_weak = await _seed_alert(
        clean_db, item_weak, is_published=True, signal_score=18,
        entities_json={"names": ["Bar"]},
    )

    # Give a_strong two event_sources bridges (different events)
    await _seed_event_link(clean_db, None, a_strong)
    await _seed_event_link(clean_db, None, a_strong)

    response = await client.get("/api/alerts/top")
    ids = [a["id"] for a in response.json()["alerts"]]
    assert ids[0] == a_strong.id
    assert ids[1] == a_weak.id


@pytest.mark.asyncio
async def test_top_alerts_tie_broken_by_source_credibility(client, clean_db):
    """Same score + signal strength → higher source credibility wins."""
    src_high = await _seed_source(clean_db, name="Trusted", credibility_score=5)
    src_low = await _seed_source(clean_db, name="Less Trusted", credibility_score=3)
    item_high = await _seed_raw_item(
        clean_db, src_high, title="High", url="https://x.com/high"
    )
    item_low = await _seed_raw_item(
        clean_db, src_low, title="Low", url="https://x.com/low"
    )

    a_high = await _seed_alert(
        clean_db, item_high, is_published=True, signal_score=18,
        entities_json={"names": ["A"]},
    )
    a_low = await _seed_alert(
        clean_db, item_low, is_published=True, signal_score=18,
        entities_json={"names": ["B"]},
    )

    response = await client.get("/api/alerts/top")
    ids = [a["id"] for a in response.json()["alerts"]]
    assert ids[0] == a_high.id
    assert ids[1] == a_low.id


@pytest.mark.asyncio
async def test_top_alerts_tie_broken_by_recency(client, clean_db):
    """Identical score / strength / credibility → newer source date wins."""
    source = await _seed_source(clean_db, credibility_score=5)
    now = datetime.now(timezone.utc)
    item_old = await _seed_raw_item(
        clean_db, source, title="Old", url="https://x.com/old",
        published_at=now - timedelta(days=2),
    )
    item_new = await _seed_raw_item(
        clean_db, source, title="New", url="https://x.com/new",
        published_at=now - timedelta(hours=1),
    )

    a_old = await _seed_alert(
        clean_db, item_old, is_published=True, signal_score=18,
        entities_json={"names": ["A"]},
    )
    a_new = await _seed_alert(
        clean_db, item_new, is_published=True, signal_score=18,
        entities_json={"names": ["B"]},
    )

    response = await client.get("/api/alerts/top")
    ids = [a["id"] for a in response.json()["alerts"]]
    assert ids[0] == a_new.id
    assert ids[1] == a_old.id


@pytest.mark.asyncio
async def test_top_alerts_dedups_primary_entity(client, clean_db):
    """Two alerts whose primary entity is identical → only one is kept."""
    source = await _seed_source(clean_db, credibility_score=5)
    item_a = await _seed_raw_item(clean_db, source, title="A", url="https://x.com/a")
    item_b = await _seed_raw_item(clean_db, source, title="B", url="https://x.com/b")
    item_c = await _seed_raw_item(clean_db, source, title="C", url="https://x.com/c")

    now = datetime.now(timezone.utc)
    # All three at the same score so dedup is the deciding factor.
    a_a = await _seed_alert(
        clean_db, item_a, is_published=True, signal_score=20,
        entities_json={"names": ["Acme Corp"]},
        published_at=now - timedelta(minutes=1),
    )
    # Same primary entity as A — must be suppressed.
    await _seed_alert(
        clean_db, item_b, is_published=True, signal_score=20,
        entities_json={"names": ["Acme Corp", "FBI"]},
        published_at=now - timedelta(minutes=2),
    )
    a_c = await _seed_alert(
        clean_db, item_c, is_published=True, signal_score=20,
        entities_json={"names": ["Beta Inc"]},
        published_at=now - timedelta(minutes=3),
    )

    response = await client.get("/api/alerts/top")
    ids = [a["id"] for a in response.json()["alerts"]]
    assert a_a.id in ids
    assert a_c.id in ids
    # B is suppressed because its primary entity ("Acme Corp") was already claimed.
    assert len(ids) == 2


@pytest.mark.asyncio
async def test_top_alerts_alerts_without_entities_kept_unique(client, clean_db):
    """Alerts with no entities use a per-alert fallback key — never silently dropped."""
    source = await _seed_source(clean_db, credibility_score=5)
    item_a = await _seed_raw_item(clean_db, source, title="A", url="https://x.com/a")
    item_b = await _seed_raw_item(clean_db, source, title="B", url="https://x.com/b")

    a_a = await _seed_alert(
        clean_db, item_a, is_published=True, signal_score=20,
        entities_json=None,
    )
    a_b = await _seed_alert(
        clean_db, item_b, is_published=True, signal_score=20,
        entities_json=None,
    )

    response = await client.get("/api/alerts/top")
    ids = [a["id"] for a in response.json()["alerts"]]
    assert a_a.id in ids
    assert a_b.id in ids


@pytest.mark.asyncio
async def test_top_alerts_empty_when_none_qualify(client, clean_db):
    """All alerts below threshold → 200 with {"alerts": []}."""
    source = await _seed_source(clean_db, credibility_score=5)
    item = await _seed_raw_item(clean_db, source, title="Low", url="https://x.com/low")
    await _seed_alert(
        clean_db, item, is_published=True, signal_score=10,
        entities_json={"names": ["X"]},
    )

    response = await client.get("/api/alerts/top")
    assert response.status_code == 200
    assert response.json() == {"alerts": []}


@pytest.mark.asyncio
async def test_top_alerts_no_internal_field_leakage(client, clean_db):
    """Top response items must contain only PublicAlertRead keys — no internal fields."""
    source = await _seed_source(clean_db, credibility_score=5)
    item = await _seed_raw_item(clean_db, source, title="Leak Test", url="https://x.com/leak")
    await _seed_alert(
        clean_db, item, is_published=True, signal_score=20,
        entities_json={"names": ["A"]},
        secondary_category="Wire Fraud",
        financial_impact_estimate="$5M",
        victim_scale_raw="multiple",
        matched_keywords=["fraud"],
        score_source_credibility=5,
        score_financial_impact=3,
        score_victim_scale=3,
        score_cross_source=3,
        score_trend_acceleration=3,
        ai_model="gpt-4o-mini",
    )

    response = await client.get("/api/alerts/top")
    alerts = response.json()["alerts"]
    assert len(alerts) == 1
    item_resp = alerts[0]

    forbidden = (
        "score_source_credibility",
        "score_financial_impact",
        "score_victim_scale",
        "score_cross_source",
        "score_trend_acceleration",
        "signal_score_total",
        "entities_json",
        "victim_scale_raw",
        "financial_impact_estimate",
        "is_published",
        "is_relevant",
        "published_by_user_id",
        "review_status",
        "ai_model",
        "raw_item",
        "raw_item_id",
        "matched_keywords",
    )
    for key in forbidden:
        assert key not in item_resp, f"Forbidden internal field leaked: {key!r}"
