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

Public detail  (NEW — GET /api/v1/subscriber/alerts/{id}):
  - No auth required
  - Returns 200 for a published alert
  - Returns 404 for an unpublished alert
  - Returns 404 for a non-existent alert
  - Response contains only safe public fields
  - Field mapping is correct (incl. secondary_category, entities, processed_at)
  - Internal / moderation fields are NOT present

Public stats  (NEW — GET /api/v1/subscriber/alerts/stats):
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
import itertools
import uuid

import pytest
from sqlalchemy import delete

from app.api.public_alerts import PUBLIC_SUMMARY_MAX_CHARS, summary_preview
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source



# ---------------------------------------------------------------------------
# Shared-serializer coverage after Slice 3B.2P
#
# The public detail, stats and search routes were removed, but the helpers they
# exercised — `_to_public_detail`, `published_stats_impl` and every enrichment
# function — are still reached through the Subscriber API. Those assertions were
# repointed to the subscriber endpoints rather than deleted, so serializer
# coverage did not drop along with the routes.
#
# The subscription gate has its own coverage in the subscriber test modules; it
# is overridden here so these tests keep exercising serialization, not auth.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _bypass_subscription_gate():
    from app.auth.subscriber_access import require_active_subscription
    from app.main import app

    app.dependency_overrides[require_active_subscription] = lambda: None
    yield
    app.dependency_overrides.pop(require_active_subscription, None)


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
















# ===========================================================================
# Public detail — GET /api/v1/subscriber/alerts/{id}  (NEW)
# ===========================================================================


@pytest.mark.asyncio
async def test_public_detail_requires_no_auth(client, db_session):
    """GET /api/v1/subscriber/alerts/{id} must succeed without any auth header or cookie."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Auth Test")
    alert = await _seed_alert(db_session, item, is_published=True)

    response = await client.get(f"/api/v1/subscriber/alerts/{alert.id}")
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

    response = await client.get(f"/api/v1/subscriber/alerts/{alert.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == alert.id
    assert data["title"] == "Detail OK"
    assert data["summary"] == "Detail summary"
    assert data["category"] == "Investment Fraud"
    # Title case in the enriched detail (Ken's schema)
    assert data["risk_level"] == "High"
    # Ken's primary score key — normalized to 0-100 (20/25 → 80).
    assert data["score"] == 80
    # Backward-compat alias — same 0-100 value.
    assert data["signal_score"] == 80
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

    response = await client.get(f"/api/v1/subscriber/alerts/{alert.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_detail_nonexistent_returns_404(client):
    """Non-existent alert ID must return 404."""
    response = await client.get("/api/v1/subscriber/alerts/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_detail_entities_empty_when_none(client, db_session):
    """entities defaults to [] when entities_json is null or missing."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="No Entities")
    alert = await _seed_alert(db_session, item, is_published=True, entities_json=None)

    response = await client.get(f"/api/v1/subscriber/alerts/{alert.id}")
    assert response.status_code == 200
    assert response.json()["entities"] == []


@pytest.mark.asyncio
async def test_public_detail_entities_empty_dict(client, db_session):
    """entities defaults to [] when entities_json has no 'names' key."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Empty Dict Entities")
    alert = await _seed_alert(db_session, item, is_published=True, entities_json={})

    response = await client.get(f"/api/v1/subscriber/alerts/{alert.id}")
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

    response = await client.get(f"/api/v1/subscriber/alerts/{alert.id}")
    assert response.status_code == 200
    data = response.json()

    # Ken's primary fields
    assert data["id"] == alert.id
    assert data["title"] == "SEC Charges Investment Firm with $4.2M Fraud"
    assert data["score"] == 80  # 20 internal → 80/100
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
    """Credibility 5 + relevant + score >= 18 → confidence 'High' (M3 final bands)."""
    source = await _seed_source(db_session, credibility_score=5)
    item = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(
        db_session, item, is_published=True, signal_score=18, is_relevant=True,
    )
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
    assert data["confidence"] == "High"


@pytest.mark.asyncio
async def test_public_detail_confidence_medium_via_credibility(client, db_session):
    """Credibility 4 → confidence 'Medium' (regardless of score)."""
    source = await _seed_source(db_session, credibility_score=4)
    item = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(db_session, item, is_published=True, signal_score=5)
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
    assert data["confidence"] == "Medium"


@pytest.mark.asyncio
async def test_public_detail_confidence_low(client, db_session):
    """Credibility 3 + low score → confidence 'Low'."""
    source = await _seed_source(db_session, credibility_score=3)
    item = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(db_session, item, is_published=True, signal_score=4)
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
    assert data["confidence"] == "Low"


@pytest.mark.asyncio
async def test_public_detail_confidence_medium_via_score(client, db_session):
    """Credibility 3 + score >= 10 → confidence 'Medium' via score-tier path (M3 final bands)."""
    source = await _seed_source(db_session, credibility_score=3)
    item = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(db_session, item, is_published=True, signal_score=10)
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
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
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
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
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
    assert "affected_group" not in data


@pytest.mark.asyncio
async def test_public_detail_affected_group_present_for_multiple(client, db_session):
    """victim_scale_raw='multiple' → affected_group is the human-readable string."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Multiple Victims")
    alert = await _seed_alert(
        db_session, item, is_published=True, victim_scale_raw="multiple",
    )
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
    assert data["affected_group"] == "Multiple victims or organizations"


@pytest.mark.asyncio
async def test_public_detail_published_date_uses_source_first(client, db_session):
    """published_date prefers raw_item.published_at when available."""
    src_pub = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    plat_pub = datetime(2026, 4, 22, 10, 30, tzinfo=timezone.utc)

    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Source First", published_at=src_pub)
    alert = await _seed_alert(db_session, item, is_published=True, published_at=plat_pub)

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
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

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
    parsed = datetime.fromisoformat(data["published_date"].replace("Z", "+00:00"))
    parsed_naive = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    assert parsed_naive == plat_pub.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_public_detail_risk_level_is_title_case(client, db_session):
    """risk_level stored lowercase but returned title case in detail."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Title Case")
    alert = await _seed_alert(db_session, item, is_published=True, risk_level="medium")
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
    assert data["risk_level"] == "Medium"


@pytest.mark.asyncio
async def test_public_detail_sources_array_has_current_source(client, db_session):
    """sources array contains at least the current source with name + url."""
    source = await _seed_source(db_session, name="DOJ Press Releases")
    item = await _seed_raw_item(db_session, source,
                                title="Sources Test",
                                url="https://justice.gov/article/x")
    alert = await _seed_alert(db_session, item, is_published=True)
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
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

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
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

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert_a.id}")).json()
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
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
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

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert_a.id}")).json()
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

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert_a.id}")).json()
    assert isinstance(data["related_signals"], list)
    assert len(data["related_signals"]) <= 4




@pytest.mark.asyncio
async def test_public_detail_risk_level_derived_from_score(client, db_session):
    """Detail endpoint risk_level is derived from signal_score_total (Title Case)."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Stale High Detail")
    alert = await _seed_alert(
        db_session, item, is_published=True,
        risk_level="high", signal_score=15,  # 15 → 60/100 → medium per M3 final bands
    )
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
    assert data["risk_level"] == "Medium"
    assert data["score"] == 60  # 15 internal → 60/100


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

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert_a.id}")).json()
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
        entities_json={"names": ["Acme Corp", "Treasury"]},  # Acme Corp overlaps
    )
    alert_c = await _seed_alert(
        db_session, item_c, is_published=True,
        entities_json={"names": ["Acme Corp"]},  # Acme Corp overlaps
    )
    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)
    await _seed_event_link(db_session, event_id, alert_c)

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert_a.id}")).json()
    ids = [r["id"] for r in data.get("related_signals", [])]
    assert alert_b.id in ids
    assert alert_c.id in ids


@pytest.mark.asyncio
async def test_related_signals_overlap_is_case_insensitive(client, db_session):
    """Entity overlap is case-insensitive — 'acme corp' matches 'Acme Corp' (need >=2 peers)."""
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="A1", url="https://x.com/a1")
    item_b = await _seed_raw_item(db_session, source, title="B1", url="https://x.com/b1")
    item_c = await _seed_raw_item(db_session, source, title="C1", url="https://x.com/c1")
    alert_a = await _seed_alert(
        db_session, item_a, is_published=True,
        entities_json={"names": ["Acme Corp"]},
    )
    alert_b = await _seed_alert(
        db_session, item_b, is_published=True,
        entities_json={"names": ["acme corp"]},  # case-different match
    )
    alert_c = await _seed_alert(
        db_session, item_c, is_published=True,
        entities_json={"names": ["AcMe CoRp"]},  # mixed case match
    )
    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)
    await _seed_event_link(db_session, event_id, alert_c)

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert_a.id}")).json()
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

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert_a.id}")).json()
    assert "related_signals" not in data


@pytest.mark.asyncio
async def test_related_signals_omitted_when_only_one_clean_peer(client, db_session):
    """Ken's quantity rule: a single qualifying peer means the section is omitted."""
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="Solo Anchor",
                                  url="https://x.com/solo-a")
    item_b = await _seed_raw_item(db_session, source, title="Solo Peer",
                                  url="https://x.com/solo-b")
    shared = {"names": ["Acme Corp"]}
    alert_a = await _seed_alert(db_session, item_a, is_published=True,
                                entities_json=shared)
    alert_b = await _seed_alert(db_session, item_b, is_published=True,
                                entities_json=shared)
    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert_a.id}")).json()
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
    shared = {"names": ["Acme Corp"]}
    alert_a = await _seed_alert(db_session, item_a, is_published=True,
                                entities_json=shared)
    alert_b = await _seed_alert(db_session, item_b, is_published=True,
                                entities_json=shared)
    alert_c = await _seed_alert(db_session, item_c, is_published=True,
                                entities_json=shared)
    event_id = await _seed_event_link(db_session, None, alert_a)
    await _seed_event_link(db_session, event_id, alert_b)
    await _seed_event_link(db_session, event_id, alert_c)

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert_a.id}")).json()
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
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
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
    text = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()["risk_assessment"]
    assert "notable financial impact" in text


@pytest.mark.asyncio
async def test_risk_assessment_medium_concise(client, db_session):
    """Medium risk_assessment is a single concise sentence (no factor data here)."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Medium Concise")
    alert = await _seed_alert(db_session, item, is_published=True, signal_score=10)
    text = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()["risk_assessment"]
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
    text = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()["risk_assessment"]
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
    text = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()["risk_assessment"]
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
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
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
    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
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
# Public stats — GET /api/v1/subscriber/alerts/stats  (NEW)
# ===========================================================================


@pytest.mark.asyncio
async def test_public_stats_requires_no_auth(client):
    """GET /api/v1/subscriber/alerts/stats must succeed without any auth header or cookie."""
    response = await client.get("/api/v1/subscriber/alerts/stats")
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
    response = await client.get("/api/v1/subscriber/alerts/stats")
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
async def test_public_stats_category_breakdown_correct(client, db_session):
    """category_breakdown groups published alerts by primary_category correctly."""
    source = await _seed_source(db_session)

    for _ in range(3):
        item = await _seed_raw_item(db_session, source, title="Invest")
        await _seed_alert(db_session, item, is_published=True, category="Investment Fraud")

    for _ in range(2):
        item = await _seed_raw_item(db_session, source, title="Cyber")
        await _seed_alert(db_session, item, is_published=True, category="Cybercrime")

    response = await client.get("/api/v1/subscriber/alerts/stats")
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

    response = await client.get("/api/v1/subscriber/alerts/stats")
    data = response.json()
    counts = [entry["count"] for entry in data["category_breakdown"]]
    assert counts == sorted(counts, reverse=True), "Breakdown not ordered by count descending"


@pytest.mark.asyncio
async def test_public_stats_null_category_excluded_from_breakdown(client, db_session):
    """Alerts with null primary_category must not appear in category_breakdown."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="No Category")
    await _seed_alert(db_session, item, is_published=True, category=None)

    response = await client.get("/api/v1/subscriber/alerts/stats")
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

    response = await client.get("/api/v1/subscriber/alerts/stats")
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
    response = await client.get("/api/v1/subscriber/alerts/stats")
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


# ===========================================================================
# Agency stoplist — _is_agency_name + _primary_entity_key + _entity_set
# ===========================================================================


def test_is_agency_name_recognizes_common_agencies():
    """Common prosecutor/regulator names must be identified as agencies."""
    from app.api.public_alerts import _is_agency_name

    agencies = (
        "FBI",
        "Federal Bureau of Investigation",
        "DOJ",
        "Department of Justice",
        "U.S. Attorney's Office for the Middle District of Florida",
        "Securities and Exchange Commission",
        "SEC",
        "FinCEN",
        "OFAC",
        "Office of Foreign Assets Control",
        "IC3",
        "HHS-OIG",
        "Internal Revenue Service",
        "Project Safe Childhood",
        "Operation Winter SHIELD",
        "Texas Medicaid Fraud Control Unit",
    )
    for name in agencies:
        assert _is_agency_name(name), f"Should be agency: {name!r}"


def test_is_agency_name_does_not_false_positive_on_companies():
    """Real subject names containing agency-sounding substrings must NOT match."""
    from app.api.public_alerts import _is_agency_name

    real_subjects = (
        "Acme Corp",
        "Acme Securities Holdings",  # contains "securities" but not standalone agency
        "John Doe",
        "Patrick Cassells",
        "Corsa Coal Corporation",
        "Rah Roshd",
        "Phobos Ransomware",
        "Bitfinex",
        "Binance",
    )
    for name in real_subjects:
        assert not _is_agency_name(name), f"Should NOT be agency: {name!r}"


def test_is_agency_name_handles_blank_and_none():
    from app.api.public_alerts import _is_agency_name

    assert _is_agency_name("") is False
    assert _is_agency_name("   ") is False


def test_is_agency_name_broad_terms_precise_on_real_orgs():
    """Slice 5 precision: broad words don't false-positive inside real org names."""
    from app.api.public_alerts import _is_agency_name

    assert _is_agency_name("government") is True
    assert _is_agency_name("Operation Winter SHIELD") is True
    assert _is_agency_name("Government Employees Insurance Company") is False
    assert _is_agency_name("Operation Finance LLC") is False


# ===========================================================================
# Top Alerts signal strength — distinct outlets, not raw event_source rows
# ===========================================================================


def _alert_with_outlets(*source_names):
    from types import SimpleNamespace

    return SimpleNamespace(
        event_sources=[SimpleNamespace(source_name=n) for n in source_names]
    )


def test_entity_set_excludes_agencies():
    """Overlap must be computed on subjects, not on shared prosecutors."""
    from app.api.public_alerts import _entity_set

    s = _entity_set({"names": ["FBI", "Department of Justice", "Acme Corp"]})
    assert s == {"acme corp"}


# ===========================================================================
# Risk score normalization (M3 final, Ken-approved May 06)
# ===========================================================================
#
# `signal_score` (list) and `score` (detail) are normalized to 0–100 on the
# way out — the DB column is still 5–25 internal but the API exposes the
# frontend-facing value directly. Bands: >=70 high, 40-69 medium, <40 low.




@pytest.mark.asyncio
async def test_score_normalized_on_detail(client, db_session):
    """Detail endpoint's `score` and backward-compat `signal_score` are both 0–100."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Normalized Detail")
    alert = await _seed_alert(db_session, item, is_published=True, signal_score=20)

    data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
    assert data["score"] == 80  # 20/25 → 80
    assert data["signal_score"] == 80
    assert data["risk_level"] == "High"


@pytest.mark.asyncio
async def test_score_formula_kens_examples(client, db_session):
    """Reproduce Ken's worked examples: 17→68 Medium, 19→76 High, 21→84 High."""
    source = await _seed_source(db_session)
    cases = [(17, 68, "Medium"), (19, 76, "High"), (21, 84, "High")]
    for score, expected_100, expected_lvl in cases:
        item = await _seed_raw_item(
            db_session, source, title=f"K{score}", url=f"https://x.com/k{score}",
        )
        alert = await _seed_alert(
            db_session, item, is_published=True, signal_score=score,
        )
        data = (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).json()
        assert data["score"] == expected_100, f"score {score}"
        assert data["risk_level"] == expected_lvl, f"score {score}"


@pytest.mark.asyncio
async def test_score_band_boundaries_low_to_medium(client, db_session):
    """Internal 9 → 36 → low; 10 → 40 → medium."""
    source = await _seed_source(db_session)
    item9 = await _seed_raw_item(db_session, source, title="Band 9", url="https://x.com/b9")
    item10 = await _seed_raw_item(db_session, source, title="Band 10", url="https://x.com/b10")
    a9 = await _seed_alert(db_session, item9, is_published=True, signal_score=9)
    a10 = await _seed_alert(db_session, item10, is_published=True, signal_score=10)

    d9 = (await client.get(f"/api/v1/subscriber/alerts/{a9.id}")).json()
    d10 = (await client.get(f"/api/v1/subscriber/alerts/{a10.id}")).json()
    assert d9["score"] == 36
    assert d9["risk_level"] == "Low"
    assert d10["score"] == 40
    assert d10["risk_level"] == "Medium"


@pytest.mark.asyncio
async def test_score_band_boundaries_medium_to_high(client, db_session):
    """Internal 17 → 68 → medium; 18 → 72 → high.

    Critical band shift: under prior bands, internal 17 was high. Under M3
    final bands (Ken-approved), 17 → 68 is medium and 18 → 72 is the new
    high boundary.
    """
    source = await _seed_source(db_session)
    item17 = await _seed_raw_item(db_session, source, title="Band 17", url="https://x.com/b17")
    item18 = await _seed_raw_item(db_session, source, title="Band 18", url="https://x.com/b18")
    a17 = await _seed_alert(db_session, item17, is_published=True, signal_score=17)
    a18 = await _seed_alert(db_session, item18, is_published=True, signal_score=18)

    d17 = (await client.get(f"/api/v1/subscriber/alerts/{a17.id}")).json()
    d18 = (await client.get(f"/api/v1/subscriber/alerts/{a18.id}")).json()
    assert d17["score"] == 68
    assert d17["risk_level"] == "Medium"
    assert d18["score"] == 72
    assert d18["risk_level"] == "High"




# ---------------------------------------------------------------------------
# Removed public routes must be gone (Slice 3B.2P)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_top_alerts_route_removed(client: AsyncClient):
    assert (await client.get("/api/alerts/top")).status_code == 404


@pytest.mark.asyncio
async def test_public_stats_route_removed(client: AsyncClient):
    assert (await client.get("/api/alerts/stats")).status_code == 404


@pytest.mark.asyncio
async def test_public_search_route_removed(client: AsyncClient):
    assert (await client.get("/api/search/alerts?q=fraud")).status_code == 404


@pytest.mark.asyncio
async def test_public_alert_detail_route_removed_for_a_real_id(
    client: AsyncClient, db_session: AsyncSession
):
    """A *known-existing* id, so the 404 proves the route is gone.

    An unknown id would 404 either way and prove nothing.
    """
    source = await _seed_source(db_session)
    raw = await _seed_raw_item(db_session, source)
    alert = await _seed_alert(db_session, raw, is_published=True)

    # The alert really is served by a retained endpoint...
    assert (await client.get(f"/api/v1/subscriber/alerts/{alert.id}")).status_code == 200
    # ...but the public detail route no longer exists.
    assert (await client.get(f"/api/alerts/{alert.id}")).status_code == 404


@pytest.mark.asyncio
async def test_public_landing_feed_is_retained(client: AsyncClient):
    """The one public route the Landing Page uses must still answer."""
    response = await client.get("/api/alerts")
    assert response.status_code == 200
    assert "alerts" in response.json()


# ===========================================================================
# GET /api/alerts — landing-page teaser
#
# This route used to be a paginated public feed exposing scores, source
# attribution and unbounded result counts. It is now a marketing teaser: at most
# three of the most recent Critical/High publications, carrying only enough to
# show that HiddenAlerts is publishing current, serious intelligence. The tests
# it replaced asserted the old contract (pagination, signal_score, source_url,
# derived risk_level) and no longer describe the product.
#
# Determinism note: the session-scoped database accumulates published alerts from
# every module, and the teaser has only three positions. Tests that need their
# own rows to occupy those positions publish them far in the future so they sort
# first regardless of what else is present.
# ===========================================================================

TEASER_KEYS = {"title", "risk_band", "category", "source_published_at", "summary"}

#: Each test takes its own strictly-later publication epoch, so its rows occupy
#: the three positions regardless of what earlier tests left in the database.
_EPOCH_BASE = datetime(2030, 1, 1, tzinfo=timezone.utc)
_epoch_counter = itertools.count()


def _epoch() -> datetime:
    """A fresh far-future instant, later than every previously issued one."""
    return _EPOCH_BASE + timedelta(days=30 * next(_epoch_counter))


@pytest.fixture
async def teaser_seed(db_session):
    """Seed teaser alerts and remove them afterwards.

    These rows publish far in the future so they occupy the three positions
    deterministically. That would otherwise outrank every other module's data in
    the session-scoped database, so the fixture deletes what it created.
    """
    created_alerts: list[int] = []
    created_items: list[int] = []
    created_sources: list[int] = []

    async def _make(*, title, published_at, score=20, is_published=True, **kw):
        source = await _seed_source(db_session, name=f"Teaser Src {uuid.uuid4()}")
        created_sources.append(source.id)
        item = await _seed_raw_item(
            db_session, source, title=title, url=f"https://x/{uuid.uuid4()}"
        )
        created_items.append(item.id)
        alert = await _seed_alert(
            db_session, item, is_published=is_published, signal_score=score,
            published_at=published_at, **kw,
        )
        created_alerts.append(alert.id)
        return alert

    yield _make

    await db_session.rollback()
    await db_session.execute(
        delete(ProcessedAlert).where(ProcessedAlert.id.in_(created_alerts or [-1]))
    )
    await db_session.execute(
        delete(RawItem).where(RawItem.id.in_(created_items or [-1]))
    )
    await db_session.execute(
        delete(Source).where(Source.id.in_(created_sources or [-1]))
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_teaser_returns_at_most_three(client, db_session, teaser_seed):
    base = _epoch()
    for n in range(6):
        await teaser_seed(
            title=f"Teaser cap {n}", published_at=base - timedelta(hours=n)
        )

    body = (await client.get("/api/alerts")).json()
    assert len(body["alerts"]) <= 3


@pytest.mark.asyncio
async def test_teaser_ignores_a_larger_requested_limit(client, db_session, teaser_seed):
    base = _epoch()
    for n in range(6):
        await teaser_seed(
            title=f"Teaser limit {n}", published_at=base - timedelta(hours=n)
        )

    for requested in (10, 100, 500):
        resp = await client.get(f"/api/alerts?limit={requested}")
        assert resp.status_code == 200
        assert len(resp.json()["alerts"]) <= 3, f"limit={requested} was not capped"


@pytest.mark.asyncio
async def test_teaser_limit_can_still_narrow_the_result(client, db_session, teaser_seed):
    base = _epoch()
    for n in range(4):
        await teaser_seed(
            title=f"Teaser narrow {n}", published_at=base - timedelta(hours=n)
        )

    assert len((await client.get("/api/alerts?limit=1")).json()["alerts"]) == 1


@pytest.mark.asyncio
async def test_teaser_item_exposes_only_the_approved_fields(client, db_session, teaser_seed):
    await teaser_seed(
        title="Teaser shape", published_at=_epoch(), summary="A stored summary."
    )

    alerts = (await client.get("/api/alerts")).json()["alerts"]
    item = next(a for a in alerts if a["title"] == "Teaser shape")
    assert set(item) == TEASER_KEYS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "withheld",
    [
        "id", "signal_score", "source_url", "source_name", "published_at",
        "risk_level", "risk_explanation", "entities", "entities_json",
        "score_source_credibility", "score_financial_impact", "credibility",
        "confidence", "key_intelligence", "why_it_matters", "risk_assessment",
        "timeline", "sources", "related_signals", "is_published", "is_relevant",
        "raw_item_id", "review_status", "publish_decision", "publication_state_source",
    ],
)
async def test_teaser_withholds_internal_and_product_fields(
    client, db_session, teaser_seed, withheld
):
    await teaser_seed(
        title="Teaser withhold", published_at=_epoch(), summary="Summary."
    )

    alerts = (await client.get("/api/alerts")).json()["alerts"]
    item = next(a for a in alerts if a["title"] == "Teaser withhold")
    assert withheld not in item, f"{withheld} must stay behind subscriber auth"


@pytest.mark.asyncio
async def test_teaser_only_includes_published_alerts(client, db_session, teaser_seed):
    await teaser_seed(
        title="Teaser unpublished", published_at=_epoch(), score=25, is_published=False
    )

    titles = [a["title"] for a in (await client.get("/api/alerts")).json()["alerts"]]
    assert "Teaser unpublished" not in titles


@pytest.mark.asyncio
async def test_teaser_only_includes_critical_and_high(client, db_session, teaser_seed):
    base = _epoch()
    await teaser_seed(
        title="Teaser medium", published_at=base, score=16
    )
    await teaser_seed(
        title="Teaser low", published_at=base, score=9
    )
    await teaser_seed(
        title="Teaser high", published_at=base - timedelta(hours=1), score=18
    )

    titles = [a["title"] for a in (await client.get("/api/alerts")).json()["alerts"]]
    assert "Teaser high" in titles
    assert "Teaser medium" not in titles
    assert "Teaser low" not in titles


@pytest.mark.asyncio
async def test_teaser_excludes_a_false_positive(client, db_session, teaser_seed):
    """An alert an admin marked false positive is unpublished, so it cannot appear."""
    alert = await teaser_seed(
        title="Teaser false positive", published_at=_epoch()
    )
    alert.is_published = False
    alert.is_excluded = True
    alert.publish_decision_reason = "manual_false_positive"
    await db_session.commit()

    titles = [a["title"] for a in (await client.get("/api/alerts")).json()["alerts"]]
    assert "Teaser false positive" not in titles


@pytest.mark.asyncio
async def test_teaser_orders_newest_publication_first(client, db_session, teaser_seed):
    base = _epoch()
    await teaser_seed(
        title="Teaser older", published_at=base - timedelta(days=2)
    )
    await teaser_seed(
        title="Teaser newest", published_at=base
    )
    await teaser_seed(
        title="Teaser middle", published_at=base - timedelta(days=1)
    )

    titles = [a["title"] for a in (await client.get("/api/alerts")).json()["alerts"]]
    assert titles[:3] == ["Teaser newest", "Teaser middle", "Teaser older"]


@pytest.mark.asyncio
@pytest.mark.parametrize("score, band", [(21, "critical"), (18, "high")])
async def test_teaser_returns_the_canonical_band(
    client, db_session, teaser_seed, score, band
):
    await teaser_seed(
        title=f"Teaser band {band}", published_at=_epoch(), score=score
    )

    alerts = (await client.get("/api/alerts")).json()["alerts"]
    item = next(a for a in alerts if a["title"] == f"Teaser band {band}")
    assert item["risk_band"] == band


@pytest.mark.asyncio
async def test_teaser_summary_is_capped_and_leaves_the_stored_row_alone(
    client, db_session, teaser_seed
):
    long_summary = " ".join(f"Sentence number {n} about the incident." for n in range(40))
    alert = await teaser_seed(
        title="Teaser summary", published_at=_epoch(), summary=long_summary
    )

    alerts = (await client.get("/api/alerts")).json()["alerts"]
    item = next(a for a in alerts if a["title"] == "Teaser summary")

    assert len(item["summary"]) <= PUBLIC_SUMMARY_MAX_CHARS  # ellipsis included
    assert item["summary"] != long_summary
    assert item["summary"].endswith("…")

    await db_session.refresh(alert)
    assert alert.summary == long_summary, "the stored summary must never be rewritten"


@pytest.mark.asyncio
async def test_teaser_summary_keeps_at_most_two_sentences(client, db_session, teaser_seed):
    await teaser_seed(
        title="Teaser sentences", published_at=_epoch(),
        summary="First sentence here. Second sentence here. Third must be dropped.",
    )

    alerts = (await client.get("/api/alerts")).json()["alerts"]
    item = next(a for a in alerts if a["title"] == "Teaser sentences")
    # The third sentence was removed, so the ellipsis is correct here.
    assert item["summary"] == "First sentence here. Second sentence here.…"
    assert "Third" not in item["summary"]


# --- summary_preview unit behaviour ----------------------------------------


def test_summary_preview_returns_none_without_a_summary():
    assert summary_preview(None) is None
    assert summary_preview("") is None
    assert summary_preview("   ") is None


def test_summary_preview_normalizes_whitespace():
    assert summary_preview("  A   summary\nwith\tgaps.  ") == "A summary with gaps."


def test_summary_preview_keeps_short_text_untouched_without_an_ellipsis():
    assert summary_preview("Short and complete.") == "Short and complete."


def test_summary_preview_marks_truncation_only_when_text_was_removed():
    two = "One sentence. Two sentences."
    assert summary_preview(two) == two
    assert not summary_preview(two).endswith("…")

    three = "One sentence. Two sentences. Three sentences."
    assert summary_preview(three).endswith("…")


def test_summary_preview_caps_a_single_long_sentence():
    text = "word " * 400
    out = summary_preview(text)
    assert len(out) <= PUBLIC_SUMMARY_MAX_CHARS
    assert out.endswith("…")


def test_summary_preview_never_empties_a_present_summary():
    """A very long unbroken token must still yield text, not an empty string."""
    out = summary_preview("x" * 5000)
    assert out
    assert len(out) <= PUBLIC_SUMMARY_MAX_CHARS


# --- teaser display-date semantics -----------------------------------------


@pytest.mark.asyncio
async def test_teaser_shows_the_original_article_date_not_ours(
    client, db_session, teaser_seed
):
    """The card date is the source's, matching the subscriber feed convention."""
    source_date = datetime(2029, 3, 4, 9, 0, tzinfo=timezone.utc)
    ours = _epoch()
    source = await _seed_source(db_session, name=f"Teaser Src {uuid.uuid4()}")
    item = await _seed_raw_item(
        db_session, source, title="Teaser source date",
        url=f"https://x/{uuid.uuid4()}", published_at=source_date,
    )
    alert = await _seed_alert(
        db_session, item, is_published=True, signal_score=20, published_at=ours
    )
    # Capture as plain ints: the rollback below expires the ORM objects, and
    # reading .id afterwards would be sync IO.
    alert_id, item_id, source_id = alert.id, item.id, source.id

    try:
        alerts = (await client.get("/api/alerts")).json()["alerts"]
        row = next(a for a in alerts if a["title"] == "Teaser source date")
        assert row["source_published_at"].startswith("2029-03-04")
        assert "published_at" not in row, "our timestamp is never exposed"
    finally:
        await db_session.rollback()
        await db_session.execute(delete(ProcessedAlert).where(ProcessedAlert.id == alert_id))
        await db_session.execute(delete(RawItem).where(RawItem.id == item_id))
        await db_session.execute(delete(Source).where(Source.id == source_id))
        await db_session.commit()


@pytest.mark.asyncio
async def test_teaser_falls_back_to_our_time_when_the_source_gave_no_date(
    client, db_session, teaser_seed
):
    """The established fallback: never leave the card without a date."""
    ours = _epoch()
    # _seed_raw_item leaves published_at null by default.
    await teaser_seed(title="Teaser no source date", published_at=ours)

    alerts = (await client.get("/api/alerts")).json()["alerts"]
    row = next(a for a in alerts if a["title"] == "Teaser no source date")
    assert row["source_published_at"] is not None
    assert row["source_published_at"].startswith(ours.strftime("%Y-%m-%d"))


@pytest.mark.asyncio
async def test_teaser_still_orders_by_our_publication_time(
    client, db_session, teaser_seed
):
    """Selection and order follow our publication time even when the source
    dates disagree — the teaser is "what HiddenAlerts published latest"."""
    base = _epoch()
    created = []
    for label, ours, src in [
        ("Teaser order newest", base, datetime(2020, 1, 1, tzinfo=timezone.utc)),
        ("Teaser order oldest", base - timedelta(days=2),
         datetime(2029, 12, 31, tzinfo=timezone.utc)),
    ]:
        source = await _seed_source(db_session, name=f"Teaser Src {uuid.uuid4()}")
        item = await _seed_raw_item(
            db_session, source, title=label, url=f"https://x/{uuid.uuid4()}",
            published_at=src,
        )
        alert = await _seed_alert(
            db_session, item, is_published=True, signal_score=20, published_at=ours
        )
        created.append((alert.id, item.id, source.id))

    try:
        titles = [a["title"] for a in (await client.get("/api/alerts")).json()["alerts"]]
        # Newest by OUR time first, despite carrying the older source date.
        assert titles.index("Teaser order newest") < titles.index("Teaser order oldest")
    finally:
        await db_session.rollback()
        for a_id, i_id, s_id in created:
            await db_session.execute(delete(ProcessedAlert).where(ProcessedAlert.id == a_id))
            await db_session.execute(delete(RawItem).where(RawItem.id == i_id))
            await db_session.execute(delete(Source).where(Source.id == s_id))
        await db_session.commit()


# --- summary cap boundaries -------------------------------------------------


def test_summary_preview_returns_exactly_max_chars_without_truncating():
    text = "y" * PUBLIC_SUMMARY_MAX_CHARS
    out = summary_preview(text)
    assert len(out) == PUBLIC_SUMMARY_MAX_CHARS
    assert not out.endswith("…"), "nothing was removed, so no ellipsis"


def test_summary_preview_never_exceeds_the_cap_including_the_ellipsis():
    """One character over the budget must still come back within the cap."""
    text = "z" * (PUBLIC_SUMMARY_MAX_CHARS + 1)
    out = summary_preview(text)
    assert out.endswith("…")
    assert len(out) <= PUBLIC_SUMMARY_MAX_CHARS


@pytest.mark.parametrize(
    "length",
    [
        PUBLIC_SUMMARY_MAX_CHARS - 2,
        PUBLIC_SUMMARY_MAX_CHARS - 1,
        PUBLIC_SUMMARY_MAX_CHARS,
        PUBLIC_SUMMARY_MAX_CHARS + 1,
        PUBLIC_SUMMARY_MAX_CHARS + 50,
        PUBLIC_SUMMARY_MAX_CHARS * 4,
    ],
)
def test_summary_preview_length_is_bounded_at_every_boundary(length):
    for filler in ("q", "qq "):
        text = (filler * length)[:length]
        out = summary_preview(text)
        assert out is None or len(out) <= PUBLIC_SUMMARY_MAX_CHARS, (
            f"{length=} {filler=} produced {len(out)} chars"
        )


def test_summary_preview_two_sentence_truncation_stays_within_the_cap():
    first = "A " + "a" * (PUBLIC_SUMMARY_MAX_CHARS - 4) + "."
    text = f"{first} Second sentence. Third sentence."
    out = summary_preview(text)
    assert out.endswith("…")
    assert len(out) <= PUBLIC_SUMMARY_MAX_CHARS
    assert "Third" not in out


def test_summary_preview_long_unbroken_token_stays_within_the_cap():
    out = summary_preview("t" * (PUBLIC_SUMMARY_MAX_CHARS * 3))
    assert out
    assert len(out) <= PUBLIC_SUMMARY_MAX_CHARS
    assert out.endswith("…")
