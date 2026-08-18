"""Admin operational-state regression coverage (see app/api/alerts.py:_admin_list_order_by).

The canonical Published ordering (published_at DESC NULLS LAST, processed_at
DESC) is correct for is_published=true, but Admin is also the operational
interface for Draft/Review/Excluded/Hold — rows that have no published_at by
definition. Applying the Published ordering universally would bury a
brand-new Draft/Review alert behind the entire historical Published backlog,
since NULLS LAST always pushes an unpublished row to the very end.

These tests protect the four required behaviors:
  A. is_published=true       -> published_at DESC NULLS LAST, processed_at DESC
  B. is_published=false      -> processed_at DESC
  C. publish_decision=review -> processed_at DESC
  D. All Status (neither filter) -> COALESCE(published_at, processed_at) DESC

Also covers the three-timestamp distinctness contract (published_at,
source_published_at, processed_at never alias or overwrite one another).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from tests.test_api.test_alerts_api import _create_admin_user, _make_token
from tests.test_api.test_subscriber_api import _claims, _patch_validator
from tests.test_api.test_subscriber_content import _seed_profile_with_subscription

NOW = datetime.now(timezone.utc)


async def _seed(
    db_session: AsyncSession,
    *,
    category: str,
    processed_at: datetime,
    published_at: datetime | None = None,
    is_published: bool = False,
    publish_decision: str | None = None,
    risk_band: str | None = "medium",
    source_published_at: datetime | None = None,
    is_excluded: bool = False,
    is_manual_hold: bool = False,
) -> ProcessedAlert:
    suffix = uuid.uuid4().hex[:10]
    source = Source(
        name=f"OpOrderSrc {suffix}", base_url=f"https://oporder-{suffix}.test",
        source_type="rss", credibility_score=4, adapter_class="RSSAdapter",
    )
    db_session.add(source)
    await db_session.flush()

    raw = RawItem(
        source_id=source.id, item_url=f"https://oporder-{suffix}.test/a",
        title=f"OpOrder {suffix}", url_hash=f"oh-{suffix}",
        published_at=source_published_at,
    )
    db_session.add(raw)
    await db_session.flush()

    alert = ProcessedAlert(
        raw_item_id=raw.id, primary_category=category, is_relevant=True,
        signal_score_total=16, risk_band=risk_band,
        is_published=is_published, published_at=published_at,
        publish_decision=publish_decision, is_excluded=is_excluded,
        is_manual_hold=is_manual_hold, processed_at=processed_at,
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert


async def _admin_list(client, db_session, query: str) -> list[dict]:
    user = await _create_admin_user(db_session)
    token = _make_token(user)
    resp = await client.get(
        f"/api/v1/alerts?{query}", headers={"Cookie": f"access_token={token}"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
class TestOperationalStatesRemainRetrievable:
    async def test_draft_remains_retrievable(self, client: AsyncClient, db_session: AsyncSession):
        cat = f"OpDraft-{uuid.uuid4().hex[:8]}"
        draft = await _seed(db_session, category=cat, processed_at=NOW, is_published=False)
        alerts = await _admin_list(client, db_session, f"category={cat}&is_published=false")
        assert [a["id"] for a in alerts] == [draft.id]

    async def test_review_remains_retrievable(self, client: AsyncClient, db_session: AsyncSession):
        cat = f"OpReview-{uuid.uuid4().hex[:8]}"
        review = await _seed(
            db_session, category=cat, processed_at=NOW,
            is_published=False, publish_decision="review",
        )
        alerts = await _admin_list(client, db_session, f"category={cat}&publish_decision=review")
        assert [a["id"] for a in alerts] == [review.id]

    async def test_excluded_remains_retrievable(self, client: AsyncClient, db_session: AsyncSession):
        cat = f"OpExcluded-{uuid.uuid4().hex[:8]}"
        excluded = await _seed(
            db_session, category=cat, processed_at=NOW,
            is_published=False, publish_decision="exclude", is_excluded=True,
        )
        alerts = await _admin_list(client, db_session, f"category={cat}&is_excluded=true")
        assert [a["id"] for a in alerts] == [excluded.id]

    async def test_manual_hold_remains_retrievable(self, client: AsyncClient, db_session: AsyncSession):
        cat = f"OpHold-{uuid.uuid4().hex[:8]}"
        held = await _seed(
            db_session, category=cat, processed_at=NOW,
            is_published=False, publish_decision="hold", is_manual_hold=True,
        )
        alerts = await _admin_list(client, db_session, f"category={cat}&is_manual_hold=true")
        assert [a["id"] for a in alerts] == [held.id]


@pytest.mark.asyncio
class TestOperationalOrdering:
    async def test_is_published_false_sorts_by_processed_at_desc(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"OpOrderDraft-{uuid.uuid4().hex[:8]}"
        older = await _seed(db_session, category=cat, processed_at=NOW - timedelta(hours=2))
        newer = await _seed(db_session, category=cat, processed_at=NOW - timedelta(minutes=1))

        alerts = await _admin_list(client, db_session, f"category={cat}&is_published=false")
        assert [a["id"] for a in alerts] == [newer.id, older.id]

    async def test_review_queue_sorts_by_processed_at_desc(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"OpOrderReview-{uuid.uuid4().hex[:8]}"
        older = await _seed(
            db_session, category=cat, processed_at=NOW - timedelta(hours=3),
            publish_decision="review",
        )
        newer = await _seed(
            db_session, category=cat, processed_at=NOW - timedelta(minutes=5),
            publish_decision="review",
        )

        alerts = await _admin_list(client, db_session, f"category={cat}&publish_decision=review")
        assert [a["id"] for a in alerts] == [newer.id, older.id]

    async def test_published_filter_matches_canonical_ordering(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """A — is_published=true uses published_at DESC NULLS LAST, exactly the
        ordering Subscriber uses (see test_admin_subscriber_alignment.py)."""
        cat = f"OpOrderPub-{uuid.uuid4().hex[:8]}"
        older_publish = await _seed(
            db_session, category=cat, processed_at=NOW,
            is_published=True, published_at=NOW - timedelta(days=2),
        )
        newer_publish = await _seed(
            db_session, category=cat, processed_at=NOW,
            is_published=True, published_at=NOW - timedelta(hours=1),
        )

        alerts = await _admin_list(client, db_session, f"category={cat}&is_published=true")
        assert [a["id"] for a in alerts] == [newer_publish.id, older_publish.id]

    async def test_all_status_does_not_bury_a_fresh_draft_behind_published_history(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """D — the product requirement this ordering exists for: a brand-new
        Draft/Review item must not sort behind months of historical Published
        rows just because it has no published_at yet."""
        cat = f"OpOrderMixed-{uuid.uuid4().hex[:8]}"
        old_published = await _seed(
            db_session, category=cat, processed_at=NOW - timedelta(days=200),
            is_published=True, published_at=NOW - timedelta(days=200),
        )
        fresh_draft = await _seed(
            db_session, category=cat, processed_at=NOW - timedelta(minutes=1),
            is_published=False,
        )

        # No is_published / publish_decision filter — "All Status".
        alerts = await _admin_list(client, db_session, f"category={cat}")
        ids = [a["id"] for a in alerts]
        assert ids == [fresh_draft.id, old_published.id], (
            "a fresh Draft must outrank a 200-day-old Published row under "
            "COALESCE(published_at, processed_at) ordering"
        )


@pytest.mark.asyncio
class TestEqualTimestampDeterministicOrdering:
    """Every Admin ordering branch ends in ``id DESC`` (see
    ``_admin_list_order_by``) — without it, rows sharing an identical
    processed_at (or COALESCE(published_at, processed_at)) have no defined
    relative order, so equal-timestamp results could reorder or lose/duplicate
    rows across paginated offsets. These pin ``id DESC`` as the deciding
    tie-breaker for each branch that can plausibly see a timestamp tie.
    """

    async def test_draft_ties_break_on_id_desc(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"OpTieDraft-{uuid.uuid4().hex[:8]}"
        seeded = [
            await _seed(db_session, category=cat, processed_at=NOW, is_published=False)
            for _ in range(4)
        ]
        expected = sorted((a.id for a in seeded), reverse=True)

        alerts = await _admin_list(client, db_session, f"category={cat}&is_published=false")
        assert [a["id"] for a in alerts] == expected

    async def test_review_queue_ties_break_on_id_desc(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"OpTieReview-{uuid.uuid4().hex[:8]}"
        seeded = [
            await _seed(
                db_session, category=cat, processed_at=NOW,
                is_published=False, publish_decision="review",
            )
            for _ in range(4)
        ]
        expected = sorted((a.id for a in seeded), reverse=True)

        alerts = await _admin_list(client, db_session, f"category={cat}&publish_decision=review")
        assert [a["id"] for a in alerts] == expected

    async def test_all_status_mixed_ties_break_on_id_desc(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Both a Published tie and a Draft tie sharing the same COALESCE
        value must each resolve deterministically by id, independently."""
        cat = f"OpTieMixed-{uuid.uuid4().hex[:8]}"
        published = [
            await _seed(
                db_session, category=cat, processed_at=NOW,
                is_published=True, published_at=NOW,
            )
            for _ in range(3)
        ]
        drafts = [
            await _seed(
                db_session, category=cat,
                processed_at=NOW - timedelta(hours=1), is_published=False,
            )
            for _ in range(3)
        ]
        expected = sorted((a.id for a in published), reverse=True) + sorted(
            (a.id for a in drafts), reverse=True
        )

        alerts = await _admin_list(client, db_session, f"category={cat}")
        assert [a["id"] for a in alerts] == expected

    async def test_repeated_identical_calls_return_the_same_order(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"OpTieStable-{uuid.uuid4().hex[:8]}"
        seeded = [
            await _seed(db_session, category=cat, processed_at=NOW, is_published=False)
            for _ in range(5)
        ]
        expected = sorted((a.id for a in seeded), reverse=True)

        first = await _admin_list(client, db_session, f"category={cat}&is_published=false")
        second = await _admin_list(client, db_session, f"category={cat}&is_published=false")
        assert [a["id"] for a in first] == expected
        assert [a["id"] for a in second] == expected

    async def test_paginated_offsets_over_a_tie_have_no_duplicates_or_gaps(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"OpTiePage-{uuid.uuid4().hex[:8]}"
        seeded = [
            await _seed(db_session, category=cat, processed_at=NOW, is_published=False)
            for _ in range(7)
        ]
        expected = sorted((a.id for a in seeded), reverse=True)

        collected: list[int] = []
        for offset in (0, 3, 6):
            page = await _admin_list(
                client, db_session,
                f"category={cat}&is_published=false&limit=3&offset={offset}",
            )
            collected.extend(a["id"] for a in page)

        assert collected == expected
        assert len(set(collected)) == len(collected), "no duplicates across pages"


@pytest.mark.asyncio
class TestThreeTimestampsStayDistinct:
    async def test_published_source_and_processed_timestamps_never_alias(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"OpTimestamps-{uuid.uuid4().hex[:8]}"
        source_published_at = datetime(2026, 4, 6, tzinfo=timezone.utc)
        processed_at = datetime(2026, 8, 16, tzinfo=timezone.utc)
        published_at = datetime(2026, 8, 17, tzinfo=timezone.utc)

        alert = await _seed(
            db_session, category=cat, processed_at=processed_at,
            published_at=published_at, is_published=True,
            source_published_at=source_published_at,
        )

        alerts = await _admin_list(client, db_session, f"category={cat}&is_published=true")
        assert len(alerts) == 1
        body = alerts[0]
        assert body["id"] == alert.id
        assert body["published_at"].startswith("2026-08-17")
        assert body["source_published_at"].startswith("2026-04-06")
        assert body["processed_at"].startswith("2026-08-16")
        assert len({body["published_at"], body["source_published_at"], body["processed_at"]}) == 3

    async def test_subscriber_preserves_the_same_three_distinct_timestamps(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        cat = f"OpTimestampsSub-{uuid.uuid4().hex[:8]}"
        source_published_at = datetime(2026, 4, 6, tzinfo=timezone.utc)
        processed_at = datetime(2026, 8, 16, tzinfo=timezone.utc)
        published_at = datetime(2026, 8, 17, tzinfo=timezone.utc)

        alert = await _seed(
            db_session, category=cat, processed_at=processed_at,
            published_at=published_at, is_published=True,
            source_published_at=source_published_at,
        )

        sub_id = f"ts-{uuid.uuid4()}"
        await _seed_profile_with_subscription(db_session, sub_id=sub_id, status="active")
        with _patch_validator(_claims(sub=sub_id)):
            resp = await client.get(
                f"/api/v1/subscriber/alerts?category={cat}",
                headers={"Authorization": "Bearer ignored"},
            )
        assert resp.status_code == 200
        alerts = resp.json()["alerts"]
        assert len(alerts) == 1
        body = alerts[0]
        assert body["id"] == alert.id
        assert body["published_at"].startswith("2026-08-17")
        assert body["source_published_at"].startswith("2026-04-06")
        assert body["processed_at"].startswith("2026-08-16")
        assert len({body["published_at"], body["source_published_at"], body["processed_at"]}) == 3
