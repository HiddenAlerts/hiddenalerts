"""Regression coverage for the source_published_from/source_published_to
production hotfix (see app/services/alert_query.py::_as_naive_utc).

The production defect: GET /api/v1/alerts and GET /api/v1/subscriber/alerts
returned HTTP 500 with source_published_from/source_published_to set, because
asyncpg's naive datetime codec crashed on the timezone-aware value FastAPI
parses from an ISO 8601 query parameter, binding against RawItem.published_at
(a column the ORM model under-declares as naive). SQLite (this suite's driver)
does not reproduce that asyncpg-specific crash — these tests prove the filter
still selects the *correct* rows once bounds are normalized, including with a
non-UTC offset, and that the join composition stays correct when combined with
Admin's other raw_items-joining filters. They cannot, on their own, prove the
production crash is fixed; that is confirmed by the real PostgreSQL E2E check
after deployment (see scripts/e2e/production_smoke.py).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from tests.test_api.test_alerts_api import _create_admin_user, _make_token
from tests.test_api.test_public_alerts import _seed_alert, _seed_raw_item, _seed_source
from tests.test_api.test_subscriber_api import _claims, _patch_validator
from tests.test_api.test_subscriber_content import _seed_profile_with_subscription

_AUTH = {"Authorization": "Bearer ignored"}

#: Every Source this module creates uses this prefix, so the autouse cleanup
#: fixture can find and remove exactly the rows this module added — without
#: it, seeded alerts leak into the shared session-scoped test DB and can push
#: an unrelated test's default-page-size assertion (e.g.
#: test_alerts_api.py::test_is_published_filter_admin) or its empty-db
#: assertion (test_list_alerts_empty_db) over the edge.
_SOURCE_NAME_PREFIX = "SrcDate-"


@pytest.fixture(autouse=True)
async def _cleanup_seeded_rows(db_session: AsyncSession):
    yield
    await db_session.rollback()
    source_ids = (
        await db_session.execute(
            select(Source.id).where(Source.name.startswith(_SOURCE_NAME_PREFIX))
        )
    ).scalars().all()
    if not source_ids:
        return
    raw_ids = (
        await db_session.execute(select(RawItem.id).where(RawItem.source_id.in_(source_ids)))
    ).scalars().all()
    if raw_ids:
        await db_session.execute(delete(ProcessedAlert).where(ProcessedAlert.raw_item_id.in_(raw_ids)))
        await db_session.execute(delete(RawItem).where(RawItem.id.in_(raw_ids)))
    await db_session.execute(delete(Source).where(Source.id.in_(source_ids)))
    await db_session.commit()


async def _admin_headers(db_session: AsyncSession) -> dict:
    user = await _create_admin_user(db_session)
    token = _make_token(user)
    return {"Cookie": f"access_token={token}"}


async def _admin_get(client, db_session, query: str) -> list[dict]:
    headers = await _admin_headers(db_session)
    resp = await client.get(f"/api/v1/alerts?{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _subscriber_get(client, db_session, query: str) -> list[dict]:
    sub_id = f"srcdate-{uuid.uuid4()}"
    await _seed_profile_with_subscription(db_session, sub_id=sub_id, status="active")
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(f"/api/v1/subscriber/alerts?{query}", headers=_AUTH)
    assert resp.status_code == 200, resp.text
    return resp.json()["alerts"]


async def _seed(
    db_session: AsyncSession,
    *,
    category: str,
    score: int = 19,
    source_name: str | None = None,
    source_credibility: int = 4,
    source_date: datetime | None = None,
    title: str | None = None,
    matched_keywords: list | None = None,
    is_published: bool = True,
):
    suffix = uuid.uuid4().hex[:8]
    source = await _seed_source(
        db_session, name=source_name or f"{_SOURCE_NAME_PREFIX}{suffix}",
        credibility_score=source_credibility,
    )
    raw = await _seed_raw_item(
        db_session, source, title=title or f"Article {suffix}",
        url=f"https://x/{suffix}", published_at=source_date,
    )
    alert = await _seed_alert(
        db_session, raw, is_published=is_published, category=category,
        signal_score=score, published_at=datetime.now(timezone.utc) if is_published else None,
        matched_keywords=matched_keywords,
    )
    return source, raw, alert


# ---------------------------------------------------------------------------
# Admin — boundary and range semantics (§7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAdminSourceDateFilters:
    async def test_source_published_from_only(self, client: AsyncClient, db_session: AsyncSession):
        cat = f"SrcFrom-{uuid.uuid4().hex[:8]}"
        _, _, old = await _seed(db_session, category=cat, source_date=datetime(2025, 1, 1, tzinfo=timezone.utc))
        _, _, new = await _seed(db_session, category=cat, source_date=datetime(2026, 8, 1, tzinfo=timezone.utc))

        alerts = await _admin_get(client, db_session, f"category={cat}&source_published_from=2026-01-01T00:00:00Z")
        ids = {a["id"] for a in alerts}
        assert ids == {new.id}
        assert old.id not in ids

    async def test_source_published_to_only(self, client: AsyncClient, db_session: AsyncSession):
        cat = f"SrcTo-{uuid.uuid4().hex[:8]}"
        _, _, old = await _seed(db_session, category=cat, source_date=datetime(2025, 1, 1, tzinfo=timezone.utc))
        _, _, new = await _seed(db_session, category=cat, source_date=datetime(2026, 8, 1, tzinfo=timezone.utc))

        alerts = await _admin_get(client, db_session, f"category={cat}&source_published_to=2026-01-01T00:00:00Z")
        ids = {a["id"] for a in alerts}
        assert ids == {old.id}
        assert new.id not in ids

    async def test_source_published_from_and_to_combined_range(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"SrcRange-{uuid.uuid4().hex[:8]}"
        _, _, before = await _seed(db_session, category=cat, source_date=datetime(2026, 1, 1, tzinfo=timezone.utc))
        _, _, within = await _seed(db_session, category=cat, source_date=datetime(2026, 6, 1, tzinfo=timezone.utc))
        _, _, after = await _seed(db_session, category=cat, source_date=datetime(2026, 12, 1, tzinfo=timezone.utc))

        alerts = await _admin_get(
            client, db_session,
            f"category={cat}&source_published_from=2026-03-01T00:00:00Z&source_published_to=2026-09-01T00:00:00Z",
        )
        ids = {a["id"] for a in alerts}
        assert ids == {within.id}
        assert before.id not in ids and after.id not in ids

    async def test_source_published_from_exact_boundary_is_included(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"SrcFromBound-{uuid.uuid4().hex[:8]}"
        boundary = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        _, _, on_boundary = await _seed(db_session, category=cat, source_date=boundary)

        alerts = await _admin_get(client, db_session, f"category={cat}&source_published_from=2026-06-01T00:00:00Z")
        assert {a["id"] for a in alerts} == {on_boundary.id}

    async def test_source_published_to_exact_boundary_is_included(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"SrcToBound-{uuid.uuid4().hex[:8]}"
        boundary = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        _, _, on_boundary = await _seed(db_session, category=cat, source_date=boundary)

        alerts = await _admin_get(client, db_session, f"category={cat}&source_published_to=2026-06-01T00:00:00Z")
        assert {a["id"] for a in alerts} == {on_boundary.id}

    async def test_source_published_one_second_outside_boundary_is_excluded(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"SrcOutside-{uuid.uuid4().hex[:8]}"
        just_after = datetime(2026, 6, 1, 0, 0, 1, tzinfo=timezone.utc)
        _, _, alert = await _seed(db_session, category=cat, source_date=just_after)

        alerts = await _admin_get(client, db_session, f"category={cat}&source_published_to=2026-06-01T00:00:00Z")
        assert alert.id not in {a["id"] for a in alerts}

    async def test_source_published_from_accepts_non_utc_offset_equivalent_to_z(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """2026-06-01T02:00:00+02:00 is the same instant as 2026-06-01T00:00:00Z
        — the regression this hotfix exists for. Both must select the same row."""
        cat = f"SrcOffset-{uuid.uuid4().hex[:8]}"
        boundary = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        _, _, matching = await _seed(db_session, category=cat, source_date=boundary)

        via_z = await _admin_get(client, db_session, f"category={cat}&source_published_from=2026-06-01T00:00:00Z")
        via_offset = await _admin_get(
            client, db_session, f"category={cat}&source_published_from=2026-06-01T02:00:00%2B02:00"
        )
        assert {a["id"] for a in via_z} == {matching.id}
        assert {a["id"] for a in via_offset} == {matching.id}
        assert {a["id"] for a in via_z} == {a["id"] for a in via_offset}

    async def test_source_published_negative_offset_boundary(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """2026-05-31T19:00:00-05:00 is the same instant as 2026-06-01T00:00:00Z."""
        cat = f"SrcNegOffset-{uuid.uuid4().hex[:8]}"
        boundary = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        _, _, matching = await _seed(db_session, category=cat, source_date=boundary)

        alerts = await _admin_get(
            client, db_session, f"category={cat}&source_published_from=2026-05-31T19:00:00-05:00"
        )
        assert {a["id"] for a in alerts} == {matching.id}

    async def test_published_from_still_filters_processed_alert_timestamp_independently(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """published_from (ProcessedAlert.published_at) must be unaffected by
        this fix — it never went through _as_naive_utc and never needed to."""
        cat = f"OurDateStillWorks-{uuid.uuid4().hex[:8]}"
        source = await _seed_source(db_session, name=f"{_SOURCE_NAME_PREFIX}{uuid.uuid4().hex[:6]}")
        raw_old = await _seed_raw_item(db_session, source, url=f"https://x/{uuid.uuid4().hex[:6]}")
        raw_new = await _seed_raw_item(db_session, source, url=f"https://x/{uuid.uuid4().hex[:6]}")
        old = await _seed_alert(
            db_session, raw_old, is_published=True, category=cat, signal_score=19,
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        new = await _seed_alert(
            db_session, raw_new, is_published=True, category=cat, signal_score=19,
            published_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        alerts = await _admin_get(client, db_session, f"category={cat}&published_from=2026-01-01T00:00:00Z")
        ids = {a["id"] for a in alerts}
        assert ids == {new.id}
        assert old.id not in ids


# ---------------------------------------------------------------------------
# Subscriber — mirrored coverage (§8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubscriberSourceDateFilters:
    async def test_source_published_from(self, client: AsyncClient, db_session: AsyncSession):
        cat = f"SubSrcFrom-{uuid.uuid4().hex[:8]}"
        _, _, old = await _seed(db_session, category=cat, source_date=datetime(2025, 1, 1, tzinfo=timezone.utc))
        _, _, new = await _seed(db_session, category=cat, source_date=datetime(2026, 8, 1, tzinfo=timezone.utc))

        alerts = await _subscriber_get(client, db_session, f"category={cat}&source_published_from=2026-01-01T00:00:00Z")
        ids = {a["id"] for a in alerts}
        assert ids == {new.id}
        assert old.id not in ids

    async def test_source_published_to(self, client: AsyncClient, db_session: AsyncSession):
        cat = f"SubSrcTo-{uuid.uuid4().hex[:8]}"
        _, _, old = await _seed(db_session, category=cat, source_date=datetime(2025, 1, 1, tzinfo=timezone.utc))
        _, _, new = await _seed(db_session, category=cat, source_date=datetime(2026, 8, 1, tzinfo=timezone.utc))

        alerts = await _subscriber_get(client, db_session, f"category={cat}&source_published_to=2026-01-01T00:00:00Z")
        ids = {a["id"] for a in alerts}
        assert ids == {old.id}
        assert new.id not in ids

    async def test_source_published_combined_range(self, client: AsyncClient, db_session: AsyncSession):
        cat = f"SubSrcRange-{uuid.uuid4().hex[:8]}"
        _, _, before = await _seed(db_session, category=cat, source_date=datetime(2026, 1, 1, tzinfo=timezone.utc))
        _, _, within = await _seed(db_session, category=cat, source_date=datetime(2026, 6, 1, tzinfo=timezone.utc))
        _, _, after = await _seed(db_session, category=cat, source_date=datetime(2026, 12, 1, tzinfo=timezone.utc))

        alerts = await _subscriber_get(
            client, db_session,
            f"category={cat}&source_published_from=2026-03-01T00:00:00Z&source_published_to=2026-09-01T00:00:00Z",
        )
        ids = {a["id"] for a in alerts}
        assert ids == {within.id}
        assert before.id not in ids and after.id not in ids

    async def test_source_published_from_accepts_utc_z(self, client: AsyncClient, db_session: AsyncSession):
        cat = f"SubSrcZ-{uuid.uuid4().hex[:8]}"
        _, _, matching = await _seed(db_session, category=cat, source_date=datetime(2026, 6, 1, tzinfo=timezone.utc))
        alerts = await _subscriber_get(client, db_session, f"category={cat}&source_published_from=2026-06-01T00:00:00Z")
        assert {a["id"] for a in alerts} == {matching.id}

    async def test_source_published_from_non_utc_offset_equivalent_to_z(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"SubSrcOffset-{uuid.uuid4().hex[:8]}"
        _, _, matching = await _seed(db_session, category=cat, source_date=datetime(2026, 6, 1, tzinfo=timezone.utc))

        via_z = await _subscriber_get(client, db_session, f"category={cat}&source_published_from=2026-06-01T00:00:00Z")
        via_offset = await _subscriber_get(
            client, db_session, f"category={cat}&source_published_from=2026-06-01T02:00:00%2B02:00"
        )
        assert {a["id"] for a in via_z} == {matching.id}
        assert {a["id"] for a in via_z} == {a["id"] for a in via_offset}

    async def test_subscription_enforcement_unchanged(self, client: AsyncClient, db_session: AsyncSession):
        """This fix must not touch auth/subscription enforcement — an
        unauthenticated request to the same endpoint still 401s."""
        resp = await client.get(
            "/api/v1/subscriber/alerts?source_published_from=2026-06-01T00:00:00Z"
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Shared-primitive drift protection (§9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSharedSourceDateFilterDriftProtection:
    async def test_admin_and_subscriber_agree_on_a_non_utc_offset_boundary(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Both surfaces route through the same apply_source_published_at_filters
        primitive — a non-UTC offset must select the identical row on both."""
        cat = f"DriftOffset-{uuid.uuid4().hex[:8]}"
        _, _, matching = await _seed(db_session, category=cat, source_date=datetime(2026, 6, 1, tzinfo=timezone.utc))

        admin_alerts = await _admin_get(
            client, db_session, f"is_published=true&category={cat}&source_published_from=2026-06-01T02:00:00%2B02:00"
        )
        sub_alerts = await _subscriber_get(
            client, db_session, f"category={cat}&source_published_from=2026-06-01T02:00:00%2B02:00"
        )
        assert {a["id"] for a in admin_alerts} == {matching.id}
        assert {a["id"] for a in sub_alerts} == {matching.id}


def test_both_routes_import_the_same_source_date_primitive():
    """Import-level proof there is exactly one apply_source_published_at_filters
    implementation and app.api.alerts imports the very same function object
    app.services.alert_query's own published_alerts_stmt (Subscriber) uses —
    no independent copy that could drift."""
    from app.api import alerts as admin_alerts_module
    from app.services import alert_query

    assert admin_alerts_module.apply_source_published_at_filters is (
        alert_query.apply_source_published_at_filters
    )


# ---------------------------------------------------------------------------
# Join composition — no duplicate rows from the RawItem join (§10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestJoinComposition:
    async def test_source_name_filter_plus_source_published_from(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"JoinSource-{uuid.uuid4().hex[:8]}"
        source, _, matching = await _seed(
            db_session, category=cat, source_name=f"{_SOURCE_NAME_PREFIX}{uuid.uuid4().hex[:6]}",
            source_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

        alerts = await _admin_get(
            client, db_session,
            f"category={cat}&source={source.name}&source_published_from=2026-01-01T00:00:00Z",
        )
        ids = [a["id"] for a in alerts]
        assert ids == [matching.id]
        assert len(ids) == len(set(ids)), "no duplicate rows from a doubled RawItem/Source join"

    async def test_admin_source_id_filter_plus_source_published_from(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"JoinSourceId-{uuid.uuid4().hex[:8]}"
        source, _, matching = await _seed(db_session, category=cat, source_date=datetime(2026, 6, 1, tzinfo=timezone.utc))

        alerts = await _admin_get(
            client, db_session,
            f"category={cat}&source_id={source.id}&source_published_from=2026-01-01T00:00:00Z",
        )
        ids = [a["id"] for a in alerts]
        assert ids == [matching.id]
        assert len(ids) == len(set(ids))

    async def test_admin_keyword_filter_plus_source_published_from(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"JoinKeyword-{uuid.uuid4().hex[:8]}"
        _, _, matching = await _seed(
            db_session, category=cat, title="Distinctive Krakenfraud Headline",
            source_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

        alerts = await _admin_get(
            client, db_session,
            f"category={cat}&keyword=Krakenfraud&source_published_from=2026-01-01T00:00:00Z",
        )
        ids = [a["id"] for a in alerts]
        assert ids == [matching.id]
        assert len(ids) == len(set(ids))

    async def test_source_name_and_source_published_to_combined_excludes_correctly(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Two rows sharing a source name, only one inside the date range —
        proves the join doesn't cartesian-product across both filters."""
        cat = f"JoinCombined-{uuid.uuid4().hex[:8]}"
        shared_name = f"{_SOURCE_NAME_PREFIX}{uuid.uuid4().hex[:6]}"
        _, _, in_range = await _seed(
            db_session, category=cat, source_name=shared_name,
            source_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        _, _, out_of_range = await _seed(
            db_session, category=cat, source_name=shared_name,
            source_date=datetime(2026, 12, 1, tzinfo=timezone.utc),
        )

        alerts = await _admin_get(
            client, db_session,
            f"category={cat}&source={shared_name}&source_published_to=2026-06-01T00:00:00Z",
        )
        ids = [a["id"] for a in alerts]
        assert ids == [in_range.id]
        assert out_of_range.id not in ids
        assert len(ids) == len(set(ids))
