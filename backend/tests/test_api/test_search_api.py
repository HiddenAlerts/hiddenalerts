"""Tests for the public search API — GET /api/search/alerts.

Mirrors test_public_alerts.py style: SQLite in-memory DB, async client,
_seed_* helpers. No auth required for any test.

Test isolation note:
  The session-scoped SQLite engine (see tests/conftest.py) does NOT truncate
  between tests — committed rows persist for the whole session. To keep
  count-based assertions exact, every test embeds a unique `tok` (hex uuid)
  into its seeded data and into its query, so the ILIKE candidate match is
  scoped to that test's rows alone.

Coverage:
  - Endpoint behaviour (200, 422 on missing/empty q, empty envelope on no
    matches, no auth required)
  - Matching (title, summary, source name, parsed entity, partial substring,
    case-insensitive, multi-word phrase, unpublished excluded)
  - Grouping (entity mode, multiple entity groups, mixed entity + keyword
    fallback, sources dedup, earliest/latest from source_published_at,
    group_limit cap)
  - Ranking (signal_score DESC, recency tiebreaker — group + top-level)
  - min_score on 0–100 scale (default 0, threshold boundaries)
  - Caps and validation (limit/group_limit clamping above max, 422 below 1)
  - Frontend safety (no internal/admin keys leak)
  - Regression on existing public endpoints
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source


# ---------------------------------------------------------------------------
# Per-test unique token
# ---------------------------------------------------------------------------


@pytest.fixture
def tok() -> str:
    """Per-test unique substring used in seed data + query so ILIKE matches
    only this test's rows. 12 hex chars → essentially zero collision risk
    across the test session."""
    return "qx" + uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_source(
    db_session,
    name: str = "Test Source",
    credibility_score: int = 3,
) -> Source:
    source = Source(
        name=name,
        base_url=f"https://example.com/{uuid.uuid4().hex[:8]}",
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
    url: str | None = None,
    published_at: datetime | None = None,
) -> RawItem:
    if url is None:
        # Unique URL per item — url_hash has a UNIQUE constraint.
        url = f"https://example.com/article/{uuid.uuid4().hex}"
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
    is_published: bool = True,
    summary: str = "Test summary",
    category: str | None = "Cybercrime",
    secondary_category: str | None = None,
    signal_score: int = 12,
    entities_json: dict | None = None,
    published_at: datetime | None = None,
    is_relevant: bool = True,
) -> ProcessedAlert:
    alert = ProcessedAlert(
        raw_item_id=raw_item.id,
        risk_level="medium",
        primary_category=category,
        secondary_category=secondary_category,
        signal_score_total=signal_score,
        summary=summary,
        is_relevant=is_relevant,
        is_published=is_published,
        entities_json=entities_json,
        published_at=published_at
        or (datetime.now(timezone.utc) if is_published else None),
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert


# ---------------------------------------------------------------------------
# Endpoint behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_requires_no_auth(client):
    """GET /api/search/alerts works without any auth header or cookie."""
    response = await client.get("/api/search/alerts?q=anything")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_q_required(client):
    """Missing q parameter is rejected with 422."""
    response = await client.get("/api/search/alerts")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_q_empty_rejected(client):
    """Empty q is rejected with 422."""
    response = await client.get("/api/search/alerts?q=")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_q_whitespace_rejected(client):
    """Whitespace-only q is rejected with 422."""
    response = await client.get("/api/search/alerts?q=%20%20%20")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_unknown_query_returns_empty_shape(client, tok):
    """An unknown query returns the canonical empty-result envelope."""
    response = await client.get(f"/api/search/alerts?q={tok}")
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == tok
    assert body["normalized_query"] == tok
    assert body["total_alerts"] == 0
    assert body["group_count"] == 0
    assert body["groups"] == []
    assert body["alerts"] == []


@pytest.mark.asyncio
async def test_search_basic_response_envelope(client, db_session, tok):
    """A successful match returns the full top-level envelope."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title=f"SEC charges {tok}")
    await _seed_alert(db_session, item, summary="Crypto fraud allegations")

    response = await client.get(f"/api/search/alerts?q={tok}")
    assert response.status_code == 200
    body = response.json()
    for key in ("query", "normalized_query", "total_alerts", "group_count",
                "groups", "alerts"):
        assert key in body
    assert body["total_alerts"] == 1
    assert len(body["alerts"]) == 1


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_matches_title(client, db_session, tok):
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title=f"SEC charges {tok}")
    await _seed_alert(db_session, item, summary="Plain summary",
                      entities_json=None)

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["total_alerts"] == 1
    assert body["alerts"][0]["title"] == f"SEC charges {tok}"


@pytest.mark.asyncio
async def test_search_matches_summary(client, db_session, tok):
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Ordinary title")
    await _seed_alert(
        db_session, item,
        summary=f"Discusses {tok} exchange compliance.",
        entities_json=None,
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["total_alerts"] == 1


@pytest.mark.asyncio
async def test_search_matches_source_name(client, db_session, tok):
    source = await _seed_source(db_session, name=f"{tok} Insider Newsletter")
    item = await _seed_raw_item(db_session, source, title="Anything")
    await _seed_alert(db_session, item, summary="Plain summary",
                      entities_json=None)

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["total_alerts"] == 1


@pytest.mark.asyncio
async def test_search_matches_entity_only(client, db_session, tok):
    """Entity-only match: entity in entities_json, NOT in title/summary/source."""
    source = await _seed_source(db_session, name="Generic Wire")
    item = await _seed_raw_item(
        db_session, source, title="Title without keyword",
    )
    await _seed_alert(
        db_session, item,
        summary="Summary without the keyword.",
        entities_json={"names": [f"{tok} Holdings", "Unrelated Person"]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["total_alerts"] == 1
    assert body["alerts"][0]["matched_entity"] == f"{tok} holdings"


@pytest.mark.asyncio
async def test_search_partial_substring(client, db_session, tok):
    """Searching for a substring of the title still matches."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(
        db_session, source, title=f"Binance{tok}LongName under fire",
    )
    await _seed_alert(db_session, item, summary="x")

    body = (await client.get(f"/api/search/alerts?q={tok}Long")).json()
    assert body["total_alerts"] == 1


@pytest.mark.asyncio
async def test_search_case_insensitive(client, db_session, tok):
    """Title in mixed-case is matched by a query of differing case."""
    upper = tok.upper()
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title=f"Probe of {upper}")
    await _seed_alert(db_session, item, summary="x")

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["total_alerts"] == 1


@pytest.mark.asyncio
async def test_search_multi_word_phrase(client, db_session, tok):
    """Multi-word query is a literal phrase: must appear contiguous."""
    source = await _seed_source(db_session)
    item_match = await _seed_raw_item(db_session, source, title="A")
    await _seed_alert(
        db_session, item_match,
        summary=f"Major {tok} crypto fraud case opens this week.",
    )
    # Both words present but not adjacent — must NOT match.
    item_split = await _seed_raw_item(db_session, source, title="B")
    await _seed_alert(
        db_session, item_split,
        summary=(
            f"Crypto exchange {tok} tightens controls; separately, fraud "
            "unit grows."
        ),
    )

    body = (await client.get(
        f"/api/search/alerts?q={tok}%20crypto%20fraud"
    )).json()
    assert body["total_alerts"] == 1
    assert "Major " in body["alerts"][0]["summary"]


@pytest.mark.asyncio
async def test_search_excludes_unpublished(client, db_session, tok):
    """Unpublished alerts that match the query are never returned."""
    source = await _seed_source(db_session)
    item_pub = await _seed_raw_item(db_session, source, title=f"{tok} one")
    item_unpub = await _seed_raw_item(db_session, source, title=f"{tok} two")
    await _seed_alert(db_session, item_pub, is_published=True)
    await _seed_alert(db_session, item_unpub, is_published=False)

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["total_alerts"] == 1
    assert body["alerts"][0]["title"] == f"{tok} one"


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_group_type_entity(client, db_session, tok):
    source = await _seed_source(db_session, name="SEC Press Releases")
    item = await _seed_raw_item(db_session, source, title="Plain title")
    await _seed_alert(
        db_session, item,
        summary="x",
        entities_json={"names": [tok]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["group_count"] == 1
    g = body["groups"][0]
    assert g["group_type"] == "entity"
    assert g["entity"] == tok
    assert g["alertCount"] == 1
    assert g["sourceCount"] == 1
    assert g["sources"] == ["SEC Press Releases"]


@pytest.mark.asyncio
async def test_search_multiple_entity_groups(client, db_session, tok):
    """Each distinct matched entity becomes its own group."""
    source = await _seed_source(db_session)
    item_a = await _seed_raw_item(db_session, source, title="A")
    item_b = await _seed_raw_item(db_session, source, title="B")
    await _seed_alert(
        db_session, item_a,
        summary="x",
        entities_json={"names": [f"{tok} Holdings"]},
    )
    await _seed_alert(
        db_session, item_b,
        summary="x",
        entities_json={"names": [f"{tok}.US"]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["group_count"] == 2
    entities = sorted(g["entity"] for g in body["groups"])
    assert entities == sorted([f"{tok} holdings", f"{tok}.us"])


@pytest.mark.asyncio
async def test_search_alert_in_multiple_groups_total_dedups(client, db_session, tok):
    """Alert with two matched entities → 2 groups, total_alerts dedups to 1."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title="Joint case")
    await _seed_alert(
        db_session, item,
        summary="x",
        entities_json={"names": [f"{tok} Holdings", f"{tok}.US"]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["total_alerts"] == 1
    assert body["group_count"] == 2
    assert sum(g["alertCount"] for g in body["groups"]) == 2  # > total_alerts


@pytest.mark.asyncio
async def test_search_keyword_fallback_when_no_entity_match(client, db_session, tok):
    """When no matching alert has a parsed entity match, only the keyword group is returned."""
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title=f"{tok} advisory")
    await _seed_alert(
        db_session, item,
        summary=f"Discusses {tok} practices.",
        entities_json={"names": ["Acme Corp"]},  # no entity matches tok
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["group_count"] == 1
    g = body["groups"][0]
    assert g["group_type"] == "keyword"
    assert g["entity"] == tok


@pytest.mark.asyncio
async def test_search_mixed_entity_and_keyword_fallback(client, db_session, tok):
    """Entity-matched alerts AND non-entity-matched alerts both appear.

    Mixed-mode: entity-matched alerts populate entity groups while alerts
    matching only on title/summary/source go into the keyword fallback group.
    Total counts include all unique matches.
    """
    source = await _seed_source(db_session)

    # Entity match: parsed entities contain the token.
    item_ent = await _seed_raw_item(db_session, source, title="Plain title 1")
    await _seed_alert(
        db_session, item_ent,
        summary="Plain summary 1",
        entities_json={"names": [f"{tok} Holdings"]},
    )

    # Title-only match: parsed entity does NOT contain the token.
    item_title = await _seed_raw_item(
        db_session, source, title=f"{tok} scandal hits market",
    )
    await _seed_alert(
        db_session, item_title,
        summary="Generic summary",
        entities_json={"names": ["Acme Corp"]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()

    assert body["total_alerts"] == 2
    assert len(body["alerts"]) == 2
    titles = {a["title"] for a in body["alerts"]}
    assert titles == {"Plain title 1", f"{tok} scandal hits market"}

    assert body["group_count"] == 2
    by_type = {g["group_type"]: g for g in body["groups"]}
    assert "entity" in by_type and "keyword" in by_type

    assert by_type["entity"]["entity"] == f"{tok} holdings"
    assert by_type["entity"]["alertCount"] == 1
    assert by_type["entity"]["alerts"][0]["title"] == "Plain title 1"

    assert by_type["keyword"]["entity"] == tok
    assert by_type["keyword"]["alertCount"] == 1
    assert by_type["keyword"]["alerts"][0]["title"] == f"{tok} scandal hits market"


@pytest.mark.asyncio
async def test_search_mixed_entity_groups_appear_before_keyword(client, db_session, tok):
    """Entity-first ordering: entity groups precede the keyword fallback group."""
    source = await _seed_source(db_session)

    item_ent = await _seed_raw_item(db_session, source, title="Plain")
    await _seed_alert(
        db_session, item_ent,
        summary="x",
        entities_json={"names": [f"{tok} Holdings"]},
    )
    item_title = await _seed_raw_item(
        db_session, source, title=f"{tok} latest news",
    )
    await _seed_alert(
        db_session, item_title,
        summary="x",
        entities_json={"names": ["Acme"]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["group_count"] == 2
    types_in_order = [g["group_type"] for g in body["groups"]]
    assert types_in_order == ["entity", "keyword"]


@pytest.mark.asyncio
async def test_search_group_sources_unique(client, db_session, tok):
    src_a = await _seed_source(db_session, name=f"SEC-{tok}")
    src_b = await _seed_source(db_session, name=f"DOJ-{tok}")
    a1 = await _seed_raw_item(db_session, src_a, title="A1")
    a2 = await _seed_raw_item(db_session, src_a, title="A2")
    b1 = await _seed_raw_item(db_session, src_b, title="B1")
    for it in (a1, a2, b1):
        await _seed_alert(
            db_session, it, summary="x",
            entities_json={"names": [tok]},
        )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    # Exactly one entity group (entity == tok) plus the source-name match
    # produces a keyword fallback (source name contains tok via SQL ILIKE).
    by_type = {g["group_type"]: g for g in body["groups"]}
    g_ent = by_type["entity"]
    assert g_ent["alertCount"] == 3
    assert g_ent["sourceCount"] == 2
    assert sorted(g_ent["sources"]) == sorted([f"DOJ-{tok}", f"SEC-{tok}"])


@pytest.mark.asyncio
async def test_search_earliest_latest_from_source_published_at(client, db_session, tok):
    """earliest/latest prefer raw_item.published_at over alert.published_at."""
    source = await _seed_source(db_session)
    earliest = datetime(2025, 11, 12, 10, 0, tzinfo=timezone.utc)
    latest = datetime(2026, 4, 28, 15, 30, tzinfo=timezone.utc)
    middle = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)

    for ts in (earliest, middle, latest):
        item = await _seed_raw_item(
            db_session, source, title=f"Item {ts.isoformat()}",
            published_at=ts,
        )
        await _seed_alert(
            db_session, item, summary="x",
            entities_json={"names": [tok]},
        )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    g_ent = next(g for g in body["groups"] if g["group_type"] == "entity")
    assert g_ent["earliest"].startswith("2025-11-12")
    assert g_ent["latest"].startswith("2026-04-28")


@pytest.mark.asyncio
async def test_search_group_limit_caps_alerts_per_group(client, db_session, tok):
    source = await _seed_source(db_session)
    for i in range(5):
        item = await _seed_raw_item(db_session, source, title=f"Item {i}")
        await _seed_alert(
            db_session, item, summary="x",
            entities_json={"names": [tok]},
        )

    body = (await client.get(
        f"/api/search/alerts?q={tok}&group_limit=3"
    )).json()
    g = next(g for g in body["groups"] if g["group_type"] == "entity")
    assert g["alertCount"] == 5  # un-capped count
    assert len(g["alerts"]) == 3  # capped display


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_ranks_by_signal_score_desc(client, db_session, tok):
    source = await _seed_source(db_session)
    item_low = await _seed_raw_item(db_session, source, title="Low score")
    item_high = await _seed_raw_item(db_session, source, title="High score")
    await _seed_alert(
        db_session, item_low, summary="x", signal_score=8,
        entities_json={"names": [tok]},
    )
    await _seed_alert(
        db_session, item_high, summary="x", signal_score=20,
        entities_json={"names": [tok]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    titles = [a["title"] for a in body["alerts"]]
    assert titles[0] == "High score"
    assert titles[1] == "Low score"


@pytest.mark.asyncio
async def test_search_recency_breaks_score_ties(client, db_session, tok):
    source = await _seed_source(db_session)
    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 4, 1, tzinfo=timezone.utc)
    item_older = await _seed_raw_item(
        db_session, source, title="Older", published_at=older,
    )
    item_newer = await _seed_raw_item(
        db_session, source, title="Newer", published_at=newer,
    )
    await _seed_alert(
        db_session, item_older, summary="x", signal_score=15,
        entities_json={"names": [tok]},
    )
    await _seed_alert(
        db_session, item_newer, summary="x", signal_score=15,
        entities_json={"names": [tok]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert [a["title"] for a in body["alerts"]] == ["Newer", "Older"]


@pytest.mark.asyncio
async def test_search_group_alerts_ranked(client, db_session, tok):
    source = await _seed_source(db_session)
    item_low = await _seed_raw_item(db_session, source, title="Low")
    item_high = await _seed_raw_item(db_session, source, title="High")
    await _seed_alert(
        db_session, item_low, summary="x", signal_score=8,
        entities_json={"names": [tok]},
    )
    await _seed_alert(
        db_session, item_high, summary="x", signal_score=22,
        entities_json={"names": [tok]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    g = next(g for g in body["groups"] if g["group_type"] == "entity")
    assert [a["title"] for a in g["alerts"]] == ["High", "Low"]


# ---------------------------------------------------------------------------
# min_score filter (0–100 scale)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_default_min_score_includes_low_and_medium(client, db_session, tok):
    """Default min_score=0 returns low- and medium-bucket alerts too."""
    source = await _seed_source(db_session)
    item_low = await _seed_raw_item(db_session, source, title="Low Risk Match")
    item_med = await _seed_raw_item(db_session, source, title="Medium Risk Match")
    item_hi = await _seed_raw_item(db_session, source, title="High Risk Match")
    # internal 6 -> 24 (low); 12 -> 48 (medium); 20 -> 80 (high)
    await _seed_alert(
        db_session, item_low, summary="x", signal_score=6,
        entities_json={"names": [tok]},
    )
    await _seed_alert(
        db_session, item_med, summary="x", signal_score=12,
        entities_json={"names": [tok]},
    )
    await _seed_alert(
        db_session, item_hi, summary="x", signal_score=20,
        entities_json={"names": [tok]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    assert body["total_alerts"] == 3
    titles = {a["title"] for a in body["alerts"]}
    assert titles == {"Low Risk Match", "Medium Risk Match", "High Risk Match"}


@pytest.mark.asyncio
async def test_search_min_score_60_filters(client, db_session, tok):
    """min_score=60 excludes alerts whose normalized score < 60 (internal < 15)."""
    source = await _seed_source(db_session)
    item_below = await _seed_raw_item(db_session, source, title="Below")
    item_at = await _seed_raw_item(db_session, source, title="AtBoundary")
    # internal 14 -> 56 (below 60). internal 15 -> 60 (at).
    await _seed_alert(
        db_session, item_below, summary="x", signal_score=14,
        entities_json={"names": [tok]},
    )
    await _seed_alert(
        db_session, item_at, summary="x", signal_score=15,
        entities_json={"names": [tok]},
    )

    body = (await client.get(
        f"/api/search/alerts?q={tok}&min_score=60"
    )).json()
    titles = {a["title"] for a in body["alerts"]}
    assert titles == {"AtBoundary"}


@pytest.mark.asyncio
async def test_search_min_score_70_boundary(client, db_session, tok):
    """internal 17 -> 68 (excluded); internal 18 -> 72 (included)."""
    source = await _seed_source(db_session)
    item_17 = await _seed_raw_item(db_session, source, title="i17")
    item_18 = await _seed_raw_item(db_session, source, title="i18")
    await _seed_alert(
        db_session, item_17, summary="x", signal_score=17,
        entities_json={"names": [tok]},
    )
    await _seed_alert(
        db_session, item_18, summary="x", signal_score=18,
        entities_json={"names": [tok]},
    )

    body = (await client.get(
        f"/api/search/alerts?q={tok}&min_score=70"
    )).json()
    titles = {a["title"] for a in body["alerts"]}
    assert titles == {"i18"}


# ---------------------------------------------------------------------------
# Caps and validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_limit_above_max_clamped(client, db_session, tok):
    """limit=200 returns 200 OK (clamped, not rejected)."""
    source = await _seed_source(db_session)
    for i in range(5):
        item = await _seed_raw_item(db_session, source, title=f"Item {i}")
        await _seed_alert(
            db_session, item, summary="x",
            entities_json={"names": [tok]},
        )

    response = await client.get(f"/api/search/alerts?q={tok}&limit=200")
    assert response.status_code == 200
    assert len(response.json()["alerts"]) == 5  # clamped (200->100); we seeded 5


@pytest.mark.asyncio
async def test_search_group_limit_above_max_clamped(client, db_session, tok):
    """group_limit=999 returns 200 OK (clamped, not rejected)."""
    source = await _seed_source(db_session)
    for i in range(3):
        item = await _seed_raw_item(db_session, source, title=f"Item {i}")
        await _seed_alert(
            db_session, item, summary="x",
            entities_json={"names": [tok]},
        )
    response = await client.get(
        f"/api/search/alerts?q={tok}&group_limit=999"
    )
    assert response.status_code == 200
    g = next(
        g for g in response.json()["groups"] if g["group_type"] == "entity"
    )
    assert len(g["alerts"]) == 3


@pytest.mark.asyncio
async def test_search_limit_zero_rejected(client):
    response = await client.get("/api/search/alerts?q=anything&limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_limit_negative_rejected(client):
    response = await client.get("/api/search/alerts?q=anything&limit=-5")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_group_limit_zero_rejected(client):
    response = await client.get(
        "/api/search/alerts?q=anything&group_limit=0"
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Frontend safety
# ---------------------------------------------------------------------------

_FORBIDDEN_KEYS = {
    "entities_json",
    "score_source_credibility",
    "score_financial_impact",
    "score_victim_scale",
    "score_cross_source",
    "score_trend_acceleration",
    "is_published",
    "is_relevant",
    "ai_model",
    "victim_scale_raw",
    "financial_impact_estimate",
    "matched_keywords",
    "raw_text",
    "raw_html",
    "review_status",
    "published_by_user_id",
    "url_hash",
    "content_hash",
}


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v)


@pytest.mark.asyncio
async def test_search_response_does_not_leak_internal_keys(client, db_session, tok):
    source = await _seed_source(db_session)
    item = await _seed_raw_item(db_session, source, title=f"{tok} one")
    await _seed_alert(
        db_session, item,
        summary="x",
        entities_json={"names": [tok]},
    )

    body = (await client.get(f"/api/search/alerts?q={tok}")).json()
    leaked = set(_walk_keys(body)) & _FORBIDDEN_KEYS
    assert leaked == set(), f"Internal keys leaked: {leaked}"


# ---------------------------------------------------------------------------
# Regression — existing public endpoints still work
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regression_public_alerts_list(client):
    response = await client.get("/api/alerts")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_regression_public_alerts_top(client):
    response = await client.get("/api/alerts/top")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_regression_public_alerts_stats(client):
    response = await client.get("/api/alerts/stats")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_regression_public_alert_detail_404(client):
    response = await client.get("/api/alerts/999999")
    assert response.status_code == 404
