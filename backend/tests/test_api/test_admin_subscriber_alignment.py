"""Admin/Subscriber canonical risk-band alignment (see app/services/alert_query.py).

Proves the central guarantee of the alignment directly between the two real
product APIs — there is no third mirror endpoint:

    GET /api/v1/alerts?risk_band=...&is_published=true   (Admin, Published view)
    GET /api/v1/subscriber/alerts?risk_band=...           (Subscriber)

Both read the exact same `processed_alerts.risk_band` column through the same
shared primitives in `app/services/alert_query.py` — neither recomputes a band
from `signal_score_total`. Also proves the shared canonical date filters
(`published_from`/`published_to` against `ProcessedAlert.published_at`,
`source_published_from`/`source_published_to` against the article's own date)
behave identically on both APIs, that omitting them still returns full
historical inventory, and that pagination selects identical rows in identical
order.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_api.test_alerts_api import _create_admin_user, _make_token
from tests.test_api.test_public_alerts import _seed_alert, _seed_raw_item, _seed_source
from tests.test_api.test_subscriber_api import _claims, _patch_validator
from tests.test_api.test_subscriber_content import _seed_profile_with_subscription

_AUTH = {"Authorization": "Bearer ignored"}


async def _admin_headers(db_session: AsyncSession) -> dict:
    user = await _create_admin_user(db_session)
    token = _make_token(user)
    return {"Cookie": f"access_token={token}"}


async def _subscriber_sub_id(db_session: AsyncSession) -> str:
    sub_id = f"align-{uuid.uuid4()}"
    await _seed_profile_with_subscription(db_session, sub_id=sub_id, status="active")
    return sub_id


async def _admin_get(client, db_session, query: str) -> list[dict]:
    headers = await _admin_headers(db_session)
    resp = await client.get(f"/api/v1/alerts?is_published=true&{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _subscriber_get(client, db_session, query: str) -> list[dict]:
    sub_id = await _subscriber_sub_id(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(f"/api/v1/subscriber/alerts?{query}", headers=_AUTH)
    assert resp.status_code == 200, resp.text
    return resp.json()["alerts"]


async def _seed_band_alert(
    db_session: AsyncSession,
    *,
    category: str,
    score: int,
    is_published: bool = True,
    risk_band: str | None | object = "__unset__",
    source_date: datetime | None = None,
    our_date: datetime | None = None,
):
    """Seed a ProcessedAlert with independently controllable score, band,
    source article date, and HiddenAlerts publish date — the four things this
    alignment must keep consistent between Admin and Subscriber.
    """
    source = await _seed_source(db_session, name=f"AlignSrc {uuid.uuid4()}")
    raw = await _seed_raw_item(
        db_session, source, url=f"https://x/{uuid.uuid4()}", published_at=source_date
    )
    kwargs = dict(
        category=category,
        signal_score=score,
        is_published=is_published,
        published_at=our_date,
    )
    if risk_band != "__unset__":
        kwargs["risk_band"] = risk_band
    return await _seed_alert(db_session, raw, **kwargs)


@pytest.mark.asyncio
class TestBandParity:
    """A/B/C/D — Critical, High, Medium, Below 60 parity between the two APIs."""

    @pytest.mark.parametrize("band,score", [
        ("critical", 21), ("high", 19), ("medium", 16), ("below_60", 8),
    ])
    async def test_band_parity(
        self, client: AsyncClient, db_session: AsyncSession, band, score
    ):
        cat = f"Parity-{band}-{uuid.uuid4().hex[:8]}"
        wanted = await _seed_band_alert(db_session, category=cat, score=score)
        # A published row in a different band under the same category must
        # never leak into either result set.
        other_score = 8 if score != 8 else 21
        await _seed_band_alert(db_session, category=cat, score=other_score)
        # The exact bug this alignment fixes: real score, no stored band —
        # invisible to BOTH APIs now, neither may invent one.
        await _seed_band_alert(db_session, category=cat, score=score, risk_band=None)
        # A Draft (unpublished) alert in the wanted band must never appear on
        # either the Admin-Published or the Subscriber view.
        await _seed_band_alert(
            db_session, category=cat, score=score, is_published=False
        )

        admin_alerts = await _admin_get(client, db_session, f"category={cat}&risk_band={band}")
        sub_alerts = await _subscriber_get(client, db_session, f"category={cat}&risk_band={band}")

        admin_ids = [a["id"] for a in admin_alerts]
        sub_ids = [a["id"] for a in sub_alerts]
        assert admin_ids == [wanted.id]
        assert sub_ids == [wanted.id]
        assert admin_ids == sub_ids

    async def test_stored_band_wins_over_a_disagreeing_score(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """E — score implies Critical, stored risk_band=high. Both APIs must
        classify/filter it as High, not Critical."""
        cat = f"StoredWins-{uuid.uuid4().hex[:8]}"
        alert = await _seed_band_alert(db_session, category=cat, score=22, risk_band="high")

        admin_high = await _admin_get(client, db_session, f"category={cat}&risk_band=high")
        admin_critical = await _admin_get(client, db_session, f"category={cat}&risk_band=critical")
        sub_high = await _subscriber_get(client, db_session, f"category={cat}&risk_band=high")
        sub_critical = await _subscriber_get(client, db_session, f"category={cat}&risk_band=critical")

        assert [a["id"] for a in admin_high] == [alert.id]
        assert [a["id"] for a in sub_high] == [alert.id]
        assert admin_critical == [] and sub_critical == []

    async def test_null_band_is_invisible_to_both_apis_despite_a_qualifying_score(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """F — score implies Critical, risk_band is NULL. Neither API may
        invent Critical during list filtering (the pre-normalization shape)."""
        cat = f"NullBand-{uuid.uuid4().hex[:8]}"
        await _seed_band_alert(db_session, category=cat, score=23, risk_band=None)

        admin_critical = await _admin_get(client, db_session, f"category={cat}&risk_band=critical")
        sub_critical = await _subscriber_get(client, db_session, f"category={cat}&risk_band=critical")
        assert admin_critical == []
        assert sub_critical == []


@pytest.mark.asyncio
class TestOrderingParity:
    async def test_published_at_desc_nulls_last_then_processed_at_desc(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """G/H — an old source article published by HiddenAlerts recently must
        sort ahead of a newer article published earlier; source_published_at
        never decides ordering on either API (the production id-327 shape from
        the freshness audit)."""
        cat = f"AlignOrder-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        older_article_recent_publish = await _seed_band_alert(
            db_session, category=cat, score=19,
            source_date=datetime(2025, 2, 4, tzinfo=timezone.utc),
            our_date=now,
        )
        newer_article_earlier_publish = await _seed_band_alert(
            db_session, category=cat, score=19,
            source_date=now,
            our_date=now - timedelta(hours=1),
        )

        admin_alerts = await _admin_get(client, db_session, f"category={cat}&risk_band=high")
        sub_alerts = await _subscriber_get(client, db_session, f"category={cat}&risk_band=high")

        expected = [older_article_recent_publish.id, newer_article_earlier_publish.id]
        assert [a["id"] for a in admin_alerts] == expected
        assert [a["id"] for a in sub_alerts] == expected


@pytest.mark.asyncio
class TestDateFilterParity:
    async def test_published_from_to_filter_our_timestamp_on_both_apis(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """I — published_from/published_to give identical IDs on both APIs."""
        cat = f"AlignPubDate-{uuid.uuid4().hex[:8]}"
        old = await _seed_band_alert(
            db_session, category=cat, score=19,
            our_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        recent = await _seed_band_alert(
            db_session, category=cat, score=19,
            our_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        cutoff = "2026-06-01T00:00:00Z"

        admin_alerts = await _admin_get(
            client, db_session, f"category={cat}&risk_band=high&published_from={cutoff}"
        )
        sub_alerts = await _subscriber_get(
            client, db_session, f"category={cat}&risk_band=high&published_from={cutoff}"
        )

        admin_ids = {a["id"] for a in admin_alerts}
        sub_ids = {a["id"] for a in sub_alerts}
        assert admin_ids == {recent.id}
        assert sub_ids == {recent.id}
        assert old.id not in admin_ids and old.id not in sub_ids

    async def test_source_published_from_to_filters_the_article_date_on_both_apis(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """J — source_published_from/source_published_to give identical IDs on
        both APIs, and filter the article date, not our own timestamp."""
        cat = f"AlignSrcDate-{uuid.uuid4().hex[:8]}"
        old_article = await _seed_band_alert(
            db_session, category=cat, score=19,
            source_date=datetime(2025, 2, 4, tzinfo=timezone.utc),
            our_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        recent_article = await _seed_band_alert(
            db_session, category=cat, score=19,
            source_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
            our_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        cutoff = "2026-06-01T00:00:00Z"

        admin_alerts = await _admin_get(
            client, db_session, f"category={cat}&risk_band=high&source_published_from={cutoff}"
        )
        sub_alerts = await _subscriber_get(
            client, db_session, f"category={cat}&risk_band=high&source_published_from={cutoff}"
        )

        admin_ids = {a["id"] for a in admin_alerts}
        sub_ids = {a["id"] for a in sub_alerts}
        assert admin_ids == {recent_article.id}
        assert sub_ids == {recent_article.id}
        assert old_article.id not in admin_ids and old_article.id not in sub_ids

    async def test_published_to_filters_our_timestamp_on_both_apis(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """The upper-bound counterpart to published_from — not implied by it.
        published_to must exclude a HiddenAlerts-recent alert and keep only
        the one published before the cutoff, on both APIs."""
        cat = f"AlignPubDateTo-{uuid.uuid4().hex[:8]}"
        older = await _seed_band_alert(
            db_session, category=cat, score=19,
            our_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        newer = await _seed_band_alert(
            db_session, category=cat, score=19,
            our_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        cutoff = "2026-06-01T00:00:00Z"

        admin_alerts = await _admin_get(
            client, db_session, f"category={cat}&risk_band=high&published_to={cutoff}"
        )
        sub_alerts = await _subscriber_get(
            client, db_session, f"category={cat}&risk_band=high&published_to={cutoff}"
        )

        admin_ids = {a["id"] for a in admin_alerts}
        sub_ids = {a["id"] for a in sub_alerts}
        assert admin_ids == {older.id}
        assert sub_ids == {older.id}
        assert newer.id not in admin_ids and newer.id not in sub_ids

    async def test_source_published_to_filters_the_article_date_on_both_apis(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """The upper-bound counterpart to source_published_from — operates on
        the article date, never HiddenAlerts' own timestamp, on both APIs."""
        cat = f"AlignSrcDateTo-{uuid.uuid4().hex[:8]}"
        old_article = await _seed_band_alert(
            db_session, category=cat, score=19,
            source_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            our_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        recent_article = await _seed_band_alert(
            db_session, category=cat, score=19,
            source_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
            our_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        cutoff = "2026-06-01T00:00:00Z"

        admin_alerts = await _admin_get(
            client, db_session, f"category={cat}&risk_band=high&source_published_to={cutoff}"
        )
        sub_alerts = await _subscriber_get(
            client, db_session, f"category={cat}&risk_band=high&source_published_to={cutoff}"
        )

        admin_ids = {a["id"] for a in admin_alerts}
        sub_ids = {a["id"] for a in sub_alerts}
        assert admin_ids == {old_article.id}
        assert sub_ids == {old_article.id}
        assert recent_article.id not in admin_ids and recent_article.id not in sub_ids

    async def test_no_date_filter_returns_full_historical_inventory(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """K — no default freshness window: a 2025 alert appears on both APIs
        exactly like a brand-new one when no date params are supplied."""
        cat = f"AlignNoWindow-{uuid.uuid4().hex[:8]}"
        ancient = await _seed_band_alert(
            db_session, category=cat, score=19,
            source_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            our_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        admin_alerts = await _admin_get(client, db_session, f"category={cat}&risk_band=high")
        sub_alerts = await _subscriber_get(client, db_session, f"category={cat}&risk_band=high")

        assert ancient.id in {a["id"] for a in admin_alerts}
        assert ancient.id in {a["id"] for a in sub_alerts}


@pytest.mark.asyncio
class TestSourceFilterParity:
    async def test_source_name_filter_selects_identical_ids_on_both_apis(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """L — source=<partial name>, case-insensitive partial match (the
        existing contract on both routes), selects identical Published IDs
        and order on Admin and Subscriber."""
        cat = f"AlignSource-{uuid.uuid4().hex[:8]}"
        unique = uuid.uuid4().hex[:10]
        source_name = f"DistinctiveWire{unique}"
        source = await _seed_source(db_session, name=source_name)
        raw_match = await _seed_raw_item(db_session, source, url=f"https://x/{uuid.uuid4()}")
        matching = await _seed_alert(
            db_session, raw_match, category=cat, is_published=True, signal_score=19
        )
        other = await _seed_band_alert(db_session, category=cat, score=19)

        # Partial, mixed-case fragment of the source name.
        fragment = f"distinctivewire{unique}"[3:-3]

        admin_alerts = await _admin_get(
            client, db_session, f"category={cat}&risk_band=high&source={fragment}"
        )
        sub_alerts = await _subscriber_get(
            client, db_session, f"category={cat}&risk_band=high&source={fragment}"
        )

        admin_ids = [a["id"] for a in admin_alerts]
        sub_ids = [a["id"] for a in sub_alerts]
        assert admin_ids == [matching.id]
        assert sub_ids == [matching.id]
        assert other.id not in admin_ids and other.id not in sub_ids


@pytest.mark.asyncio
class TestPaginationParity:
    async def test_identical_page_ids_and_order_across_multiple_pages(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """L — limit=3&offset=3 (page two of a five-row set) must select the
        exact same three IDs, in the exact same order, on both APIs."""
        cat = f"AlignPage-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        seeded = []
        for i in range(5):
            alert = await _seed_band_alert(
                db_session, category=cat, score=19,
                our_date=now - timedelta(hours=i),
            )
            seeded.append(alert)

        admin_page = await _admin_get(
            client, db_session, f"category={cat}&risk_band=high&limit=3&offset=3"
        )
        sub_page = await _subscriber_get(
            client, db_session, f"category={cat}&risk_band=high&limit=3&offset=3"
        )

        admin_ids = [a["id"] for a in admin_page]
        sub_ids = [a["id"] for a in sub_page]
        assert len(admin_ids) == 2, "5 rows, offset 3, limit 3 -> 2 remaining"
        assert admin_ids == sub_ids

        admin_first_page = await _admin_get(
            client, db_session, f"category={cat}&risk_band=high&limit=3&offset=0"
        )
        sub_first_page = await _subscriber_get(
            client, db_session, f"category={cat}&risk_band=high&limit=3&offset=0"
        )
        assert [a["id"] for a in admin_first_page] == [a["id"] for a in sub_first_page]
        # No overlap between the two pages.
        assert set(a["id"] for a in admin_first_page).isdisjoint(admin_ids)


@pytest.mark.asyncio
class TestInvalidRiskBand:
    async def test_admin_rejects_an_invalid_risk_band_with_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        headers = await _admin_headers(db_session)
        resp = await client.get("/api/v1/alerts?risk_band=extreme", headers=headers)
        assert resp.status_code == 422

    async def test_subscriber_rejects_an_invalid_risk_band_with_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        sub_id = await _subscriber_sub_id(db_session)
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get("/api/v1/subscriber/alerts?risk_band=extreme", headers=_AUTH)
        assert resp.status_code == 422

    async def test_subscriber_no_longer_accepts_risk_level_as_a_band_filter(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """risk_level was removed as the Subscriber V1 band parameter — FastAPI
        silently ignores an unrecognized query param, so ?risk_level=critical
        now returns the full unfiltered set rather than 422ing or filtering.
        This test pins that as the documented, understood behavior: Hasnain's
        frontend must send risk_band, not risk_level, or filtering silently
        does nothing.
        """
        cat = f"NoRiskLevel-{uuid.uuid4().hex[:8]}"
        critical = await _seed_band_alert(db_session, category=cat, score=22)
        medium = await _seed_band_alert(db_session, category=cat, score=16)

        sub_alerts = await _subscriber_get(
            client, db_session, f"category={cat}&risk_level=critical"
        )
        ids = {a["id"] for a in sub_alerts}
        assert ids == {critical.id, medium.id}, (
            "risk_level is an unrecognized param now — both rows come back unfiltered"
        )


@pytest.mark.asyncio
class TestNoQueryTimeRecomputationRemains:
    async def test_subscriber_stats_also_reads_the_stored_column(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """subscriber_alert_stats (Critical/High/Medium/Low counts) must move in
        lockstep with the list filter — both read risk_band, neither recomputes
        from signal_score_total. A mismatched-band row must not be counted as
        its score would suggest.
        """
        sub_id = await _subscriber_sub_id(db_session)
        with _patch_validator(_claims(sub=sub_id)):
            before = (
                await client.get("/api/v1/subscriber/alerts/stats", headers=_AUTH)
            ).json()

        cat = f"AlignStats-{uuid.uuid4().hex[:8]}"
        # Score says "critical" (>=20); stored column says "high". The count
        # must move under high_count, never critical_count.
        await _seed_band_alert(db_session, category=cat, score=21, risk_band="high")

        with _patch_validator(_claims(sub=sub_id)):
            after = (
                await client.get("/api/v1/subscriber/alerts/stats", headers=_AUTH)
            ).json()

        assert after["high_count"] == before["high_count"] + 1
        assert after["critical_count"] == before["critical_count"]
