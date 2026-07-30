"""Shared collector ingestion, deduplication and run-log telemetry.

All collection here runs against a stub adapter — no live source is ever
contacted. The historical starvation defect these tests pin is described on
``test_item_older_than_last_successful_run_is_not_starved``.
"""
import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source
from app.pipeline import collector
from app.pipeline.normalizer import compute_url_hash
from app.services import collection_guard
from app.sources.base import RawItemStub, clean_summary_text
from app.sources.http_errors import TransientFetchError, UnsafeRequestTarget


class StubAdapter:
    """Adapter double: returns canned stubs and canned article bodies."""

    def __init__(self, source, stubs, bodies=None, fetch_error=None):
        self.source = source
        self._stubs = stubs
        self._bodies = bodies or {}
        self._fetch_error = fetch_error
        self.fetched_urls: list[str] = []

    async def fetch_item_stubs(self):
        return list(self._stubs)

    async def fetch_full_article(self, url: str):
        self.fetched_urls.append(url)
        if self._fetch_error is not None:
            raise self._fetch_error
        return self._bodies.get(url, f"Body for {url}"), f"<p>{url}</p>"

    def summary_fallback(self, stub, error):
        # Same contract as BaseSourceAdapter: any non-empty summary will do.
        return clean_summary_text(stub.summary) or None


class _CommitFailingSession:
    """Session proxy whose commit always fails, recording the rollback."""

    def __init__(self, session):
        self._session = session
        self.rolled_back = False

    def __getattr__(self, name):
        return getattr(self._session, name)

    async def commit(self):
        raise RuntimeError("connection lost during commit")

    async def rollback(self):
        self.rolled_back = True
        await self._session.rollback()


def _stub(url, *, title="Title", published_at=None, summary="Feed summary"):
    return RawItemStub(
        source_name="Stub Source",
        item_url=url,
        title=title,
        published_at=published_at,
        summary=summary,
    )


@pytest.fixture(autouse=True)
def clear_guard():
    collection_guard._active_source_runs.clear()
    yield
    collection_guard._active_source_runs.clear()


@pytest.fixture(autouse=True)
def test_session_factory(monkeypatch, db_session):
    """Point the collector's own session factory at the test session.

    ``collect_source`` and ``run_all_sources`` open their own sessions, which
    would otherwise hit the real engine instead of the in-memory test database.
    """

    @asynccontextmanager
    async def _factory():
        yield db_session

    monkeypatch.setattr(collector, "AsyncSessionLocal", _factory)


@pytest.fixture
async def source(db_session):
    src = Source(
        name=f"Stub Source {uuid.uuid4().hex[:6]}",
        base_url="https://example.test",
        source_type="rss",
        rss_url="https://example.test/feed.xml",
        adapter_class="krebs.KrebsAdapter",
        is_active=True,
    )
    db_session.add(src)
    await db_session.commit()
    await db_session.refresh(src)
    return src


def _use_adapter(monkeypatch, adapter):
    monkeypatch.setattr(collector, "get_adapter", lambda source: adapter)
    return adapter


async def _run(db_session, source, adapter, monkeypatch):
    _use_adapter(monkeypatch, adapter)
    return await collector.run_source(source, db_session)


async def _stored_urls(db_session, source):
    rows = await db_session.execute(
        select(RawItem.item_url).where(RawItem.source_id == source.id)
    )
    return sorted(rows.scalars().all())


async def _seed_successful_run(db_session, source, *, started_at):
    run = RunLog(
        source_id=source.id,
        run_started_at=started_at,
        run_finished_at=started_at,
        status="success",
        items_fetched=0,
        items_new=0,
        items_duplicate=0,
    )
    db_session.add(run)
    await db_session.commit()
    return run


# ---------------------------------------------------------------------------
# Removed watermark gate — the historical starvation defect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_item_older_than_last_successful_run_is_not_starved(
    db_session, source, monkeypatch
):
    """Regression: the date pre-filter used to discard any feed item whose
    published_at was <= the last successful run's start time.

    Because that watermark advanced on every successful run — including runs that
    stored nothing — an item that reached the feed later than the run straddling
    its publication date was skipped forever and never re-evaluated. Government
    feeds that publish in batches lost months of items this way. Eligibility must
    now depend on the normalized URL alone.
    """
    await _seed_successful_run(db_session, source, started_at=datetime(2026, 7, 20, 12, 0))

    adapter = StubAdapter(
        source,
        [_stub("https://example.test/old", published_at=datetime(2024, 12, 1, 9, 0))],
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.status == "success"
    assert run.items_new == 1
    assert await _stored_urls(db_session, source) == ["https://example.test/old"]


@pytest.mark.asyncio
async def test_item_newer_than_last_successful_run_still_collected(
    db_session, source, monkeypatch
):
    await _seed_successful_run(db_session, source, started_at=datetime(2026, 7, 20, 12, 0))

    adapter = StubAdapter(
        source,
        [_stub("https://example.test/new", published_at=datetime(2026, 7, 25, 9, 0))],
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_new == 1


@pytest.mark.asyncio
async def test_item_without_published_at_is_collected(db_session, source, monkeypatch):
    await _seed_successful_run(db_session, source, started_at=datetime(2026, 7, 20, 12, 0))

    adapter = StubAdapter(source, [_stub("https://example.test/undated", published_at=None)])
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_new == 1


@pytest.mark.asyncio
async def test_older_item_accepted_after_a_zero_store_success(
    db_session, source, monkeypatch
):
    """A successful run that stored nothing must not block later discovery."""
    empty = await _run(db_session, source, StubAdapter(source, []), monkeypatch)
    assert empty.status == "success"
    assert empty.items_new == 0

    late = _stub("https://example.test/late", published_at=datetime(2025, 1, 5, 8, 0))
    run = await _run(db_session, source, StubAdapter(source, [late]), monkeypatch)

    assert run.items_new == 1


@pytest.mark.asyncio
async def test_published_at_is_still_stored(db_session, source, monkeypatch):
    """Removing the gate must not stop recording the source publication date."""
    published = datetime(2025, 3, 4, 10, 30)
    adapter = StubAdapter(source, [_stub("https://example.test/dated", published_at=published)])
    await _run(db_session, source, adapter, monkeypatch)

    stored = (
        await db_session.execute(
            select(RawItem.published_at).where(RawItem.source_id == source.id)
        )
    ).scalar_one()
    assert stored == published


@pytest.mark.asyncio
async def test_collector_no_longer_consults_run_history(db_session, source, monkeypatch):
    """No watermark helper remains on the module surface."""
    assert not hasattr(collector, "_get_last_successful_run_at")


# ---------------------------------------------------------------------------
# URL deduplication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_known_url_is_skipped_on_a_later_run(db_session, source, monkeypatch):
    stub = _stub("https://example.test/a")
    first = await _run(db_session, source, StubAdapter(source, [stub]), monkeypatch)
    second = await _run(db_session, source, StubAdapter(source, [stub]), monkeypatch)

    assert first.items_new == 1
    assert second.items_new == 0
    assert second.items_skipped_url == 1
    assert len(await _stored_urls(db_session, source)) == 1


@pytest.mark.asyncio
async def test_repeated_url_in_one_batch_stores_one_item(db_session, source, monkeypatch):
    adapter = StubAdapter(
        source,
        [
            _stub("https://example.test/dup", title="First"),
            _stub("https://example.test/dup", title="Second"),
            _stub("https://example.test/other"),
        ],
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_fetched == 3
    assert run.items_new == 2
    assert run.items_skipped_url == 1
    assert len(await _stored_urls(db_session, source)) == 2


@pytest.mark.asyncio
async def test_last_stub_wins_for_a_repeated_url(db_session, source, monkeypatch):
    """Matches the dict-comprehension this replaced: later metadata overwrites."""
    url = "https://example.test/revised"
    adapter = StubAdapter(
        source,
        [
            _stub(url, title="Early title", published_at=datetime(2026, 1, 1, 8, 0)),
            _stub(url, title="Corrected title", published_at=datetime(2026, 2, 2, 9, 0)),
        ],
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_new == 1
    assert run.items_skipped_url == 1

    row = (
        await db_session.execute(
            select(RawItem.title, RawItem.published_at).where(RawItem.source_id == source.id)
        )
    ).one()
    assert row.title == "Corrected title"
    assert row.published_at == datetime(2026, 2, 2, 9, 0)


@pytest.mark.asyncio
async def test_equivalent_urls_in_one_batch_are_treated_as_duplicates(
    db_session, source, monkeypatch
):
    """Normalization decides equivalence, so tracking params collapse together."""
    adapter = StubAdapter(
        source,
        [
            _stub("https://example.test/article"),
            _stub("https://example.test/article?utm_source=news"),
            _stub("https://example.test/article#section"),
        ],
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_new == 1
    assert run.items_skipped_url == 2


@pytest.mark.asyncio
async def test_url_hash_matches_the_shared_normalizer(db_session, source, monkeypatch):
    """Stored hashes stay compatible with hashes computed elsewhere."""
    url = "https://example.test/compat?utm_campaign=x"
    await _run(db_session, source, StubAdapter(source, [_stub(url)]), monkeypatch)

    stored_hash = (
        await db_session.execute(
            select(RawItem.url_hash).where(RawItem.source_id == source.id)
        )
    ).scalar_one()
    assert stored_hash == compute_url_hash(url)
    assert stored_hash == compute_url_hash("https://example.test/compat")


@pytest.mark.asyncio
async def test_only_new_urls_are_fetched(db_session, source, monkeypatch):
    stub = _stub("https://example.test/expensive")
    await _run(db_session, source, StubAdapter(source, [stub]), monkeypatch)

    second = StubAdapter(source, [stub])
    await _run(db_session, source, second, monkeypatch)

    assert second.fetched_urls == []


@pytest.mark.asyncio
async def test_stub_without_url_is_counted_invalid_not_duplicate(
    db_session, source, monkeypatch
):
    adapter = StubAdapter(
        source, [_stub("   "), _stub("https://example.test/valid")]
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_skipped_invalid == 1
    assert run.items_skipped_url == 0
    assert run.items_new == 1


# ---------------------------------------------------------------------------
# Unique-constraint race
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unique_constraint_race_is_isolated_to_the_savepoint(
    db_session, source, monkeypatch
):
    """A url_hash inserted by a racing writer must not poison the run.

    The pre-filter is forced to report the conflicting URL as unseen, so the
    insert reaches the database and trips ``uq_raw_items_url_hash`` exactly as a
    concurrent writer would. With ``session.add()`` outside the savepoint the
    flush happens before SAVEPOINT is emitted and the outer transaction dies,
    taking the later item and the run log with it.
    """
    taken_url = "https://example.test/raced"
    existing = RawItem(
        source_id=source.id,
        item_url=taken_url,
        title="Inserted by the racing writer",
        raw_text="Original body",
        content_hash="pre-existing-content-hash",
        url_hash=compute_url_hash(taken_url),
        is_duplicate=False,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(existing)
    await db_session.commit()

    async def _no_known_hashes(session, hashes):
        return set()

    monkeypatch.setattr(collector, "get_known_url_hashes", _no_known_hashes)

    adapter = StubAdapter(
        source,
        [_stub(taken_url, title="Racing loser"), _stub("https://example.test/after-race")],
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    # The conflict is counted, not fatal.
    assert run.status == "success"
    assert run.items_skipped_url == 1
    # The outer transaction survived, so the later stub was still stored.
    assert run.items_new == 1
    stored = await _stored_urls(db_session, source)
    assert "https://example.test/after-race" in stored
    # The racing writer's row is untouched.
    assert taken_url in stored
    titles = (
        await db_session.execute(
            select(RawItem.title).where(RawItem.item_url == taken_url)
        )
    ).scalars().all()
    assert titles == ["Inserted by the racing writer"]


@pytest.mark.asyncio
async def test_run_log_survives_a_unique_constraint_race(db_session, source, monkeypatch):
    """The run log must still be committed and readable after a conflict."""
    taken_url = "https://example.test/raced-runlog"
    db_session.add(
        RawItem(
            source_id=source.id,
            item_url=taken_url,
            title="Existing",
            raw_text="Body",
            content_hash="another-content-hash",
            url_hash=compute_url_hash(taken_url),
            is_duplicate=False,
            fetched_at=datetime.utcnow(),
        )
    )
    await db_session.commit()

    async def _no_known_hashes(session, hashes):
        return set()

    monkeypatch.setattr(collector, "get_known_url_hashes", _no_known_hashes)

    run = await _run(
        db_session, source, StubAdapter(source, [_stub(taken_url)]), monkeypatch
    )

    persisted = (
        await db_session.execute(select(RunLog).where(RunLog.id == run.id))
    ).scalar_one()
    assert persisted.status == "success"
    assert persisted.items_skipped_url == 1
    assert persisted.run_finished_at is not None


# ---------------------------------------------------------------------------
# Content handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_content_duplicate_is_skipped_and_counted(db_session, source, monkeypatch):
    body = "Identical article body"
    first = StubAdapter(
        source, [_stub("https://example.test/one")], bodies={"https://example.test/one": body}
    )
    await _run(db_session, source, first, monkeypatch)

    second = StubAdapter(
        source, [_stub("https://example.test/two")], bodies={"https://example.test/two": body}
    )
    run = await _run(db_session, source, second, monkeypatch)

    assert run.items_new == 0
    assert run.items_skipped_content == 1
    assert run.items_skipped_url == 0


@pytest.mark.asyncio
async def test_unusable_content_is_skipped_and_left_retriable(
    db_session, source, monkeypatch
):
    """An article with no text is not stored, so a later run can retry the URL."""
    url = "https://example.test/empty"
    adapter = StubAdapter(source, [_stub(url, summary="")], bodies={url: "   "})
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_new == 0
    assert run.items_skipped_invalid == 1
    assert run.items_skipped_content == 0
    assert await _stored_urls(db_session, source) == []

    recovered = StubAdapter(source, [_stub(url)], bodies={url: "Real body now"})
    retry = await _run(db_session, source, recovered, monkeypatch)
    assert retry.items_new == 1


@pytest.mark.asyncio
async def test_multiple_empty_articles_are_not_mistaken_for_duplicates(
    db_session, source, monkeypatch
):
    adapter = StubAdapter(
        source,
        [_stub("https://example.test/e1", summary=""), _stub("https://example.test/e2", summary="")],
        bodies={"https://example.test/e1": "", "https://example.test/e2": ""},
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_skipped_invalid == 2
    assert run.items_skipped_content == 0


@pytest.mark.asyncio
async def test_feed_summary_is_used_when_the_article_fetch_fails(
    db_session, source, monkeypatch
):
    """Expected unavailability — the adapter decides its summary will serve."""
    adapter = StubAdapter(
        source,
        [_stub("https://example.test/fallback", summary="Summary text")],
        fetch_error=TransientFetchError("upstream unreachable", status=503),
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_new == 1
    stored = (
        await db_session.execute(
            select(RawItem.raw_text).where(RawItem.source_id == source.id)
        )
    ).scalar_one()
    assert stored == "Summary text"


@pytest.mark.asyncio
async def test_terminal_fetch_error_does_not_reach_the_summary(
    db_session, source, monkeypatch
):
    """A target we refused to request must not be papered over with feed text."""
    adapter = StubAdapter(
        source,
        [_stub("https://example.test/unsafe", summary="Summary text")],
        fetch_error=UnsafeRequestTarget("private address"),
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.status == "success"
    assert run.items_new == 0
    assert run.items_skipped_invalid == 1


@pytest.mark.asyncio
async def test_unexpected_error_fails_the_run_instead_of_falling_back(
    db_session, source, monkeypatch
):
    """A bug in an adapter must surface, not degrade silently into summaries."""
    adapter = StubAdapter(
        source,
        [_stub("https://example.test/bug", summary="Summary text")],
        fetch_error=RuntimeError("adapter bug"),
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.status == "failed"
    assert "adapter bug" in (run.error_message or "")
    assert run.items_new == 0


# ---------------------------------------------------------------------------
# Run-log telemetry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_counters_account_for_every_fetched_stub(db_session, source, monkeypatch):
    body = "Shared body"
    await _run(
        db_session,
        source,
        StubAdapter(
            source, [_stub("https://example.test/seed")], bodies={"https://example.test/seed": body}
        ),
        monkeypatch,
    )

    adapter = StubAdapter(
        source,
        [
            _stub("https://example.test/seed"),          # known url
            _stub("https://example.test/fresh"),         # stored
            _stub("https://example.test/fresh"),         # batch repeat
            _stub("https://example.test/clone"),         # content duplicate
            _stub(""),                                   # invalid
        ],
        bodies={"https://example.test/clone": body},
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_fetched == 5
    assert run.items_new == 1
    assert run.items_skipped_url == 2
    assert run.items_skipped_content == 1
    assert run.items_skipped_invalid == 1
    assert run.items_fetched == (
        run.items_new
        + run.items_skipped_url
        + run.items_skipped_content
        + run.items_skipped_invalid
    )


@pytest.mark.asyncio
async def test_items_duplicate_remains_the_url_plus_content_total(
    db_session, source, monkeypatch
):
    body = "Body"
    await _run(
        db_session,
        source,
        StubAdapter(source, [_stub("https://example.test/x")], bodies={"https://example.test/x": body}),
        monkeypatch,
    )
    adapter = StubAdapter(
        source,
        [_stub("https://example.test/x"), _stub("https://example.test/y"), _stub("")],
        bodies={"https://example.test/y": body},
    )
    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.items_duplicate == run.items_skipped_url + run.items_skipped_content
    assert run.items_duplicate == 2


@pytest.mark.asyncio
async def test_zero_store_run_is_successful(db_session, source, monkeypatch):
    run = await _run(db_session, source, StubAdapter(source, []), monkeypatch)
    assert run.status == "success"
    assert run.items_fetched == 0
    assert run.items_new == 0


@pytest.mark.asyncio
async def test_failed_run_records_status_and_message(db_session, source, monkeypatch):
    class Boom:
        async def fetch_item_stubs(self):
            raise RuntimeError("feed exploded")

    monkeypatch.setattr(collector, "get_adapter", lambda s: Boom())
    run = await collector.run_source(source, db_session)

    assert run.status == "failed"
    assert "feed exploded" in run.error_message


@pytest.mark.asyncio
async def test_failed_run_keeps_partial_counters(db_session, source, monkeypatch):
    """A run that dies part-way is not expected to satisfy the complete-run identity.

    The failure is an ordinary RuntimeError, so it reaches ``run_source``'s outer
    exception handler and the run is committed as ``failed`` with partial counts.
    """

    class HalfWay:
        async def fetch_item_stubs(self):
            return [_stub("https://example.test/p1"), _stub("https://example.test/p2")]

        async def fetch_full_article(self, url):
            if url.endswith("p2"):
                raise RuntimeError("simulated mid-run failure")
            return "Body one", "<p>one</p>"

        # The adapter's own fetch failure is caught per item, so raise from the
        # content check instead by returning text the collector then chokes on.

    class FailsAfterFirstStore(HalfWay):
        async def fetch_item_stubs(self):
            return [_stub("https://example.test/p1"), _stub("https://example.test/p2")]

    monkeypatch.setattr(collector, "get_adapter", lambda s: FailsAfterFirstStore())

    async def _boom_on_second(session, content_hash):
        if getattr(_boom_on_second, "seen", False):
            raise RuntimeError("simulated mid-run failure")
        _boom_on_second.seen = True
        return False

    monkeypatch.setattr(collector, "is_content_duplicate", _boom_on_second)

    run = await collector.run_source(source, db_session)

    assert run.status == "failed"
    assert "simulated mid-run failure" in run.error_message
    assert run.run_finished_at is not None
    assert run.items_fetched == 2
    total = (
        run.items_new
        + run.items_skipped_url
        + run.items_skipped_content
        + run.items_skipped_invalid
    )
    assert total < run.items_fetched

    persisted = (
        await db_session.execute(select(RunLog).where(RunLog.id == run.id))
    ).scalar_one()
    assert persisted.status == "failed"


@pytest.mark.asyncio
async def test_cancelled_run_is_persisted_as_failed_and_releases_the_claim(
    db_session, source, monkeypatch
):
    """Cancellation must propagate, but must not leave a run stuck at 'running'."""
    in_fetch = asyncio.Event()

    class Hanging:
        async def fetch_item_stubs(self):
            return [_stub("https://example.test/slow")]

        async def fetch_full_article(self, url):
            in_fetch.set()
            await asyncio.sleep(3600)

    monkeypatch.setattr(collector, "get_adapter", lambda s: Hanging())

    task = asyncio.create_task(collector.collect_reserved_source(source.id))
    await collection_guard.claim_source_run(source.id)
    await in_fetch.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert not collection_guard.is_source_collecting(source.id)

    run = (
        await db_session.execute(
            select(RunLog).where(RunLog.source_id == source.id).order_by(RunLog.id.desc())
        )
    ).scalars().first()
    assert run is not None
    assert run.status == "failed"
    assert run.status != "running"
    assert run.run_finished_at is not None
    assert "cancelled" in run.error_message.lower()
    assert run.items_fetched == 1
    assert run.items_new == 0


@pytest.mark.asyncio
async def test_final_commit_failure_propagates_and_rolls_back(
    db_session, source, monkeypatch
):
    """A failed final commit must not be reported as a successful run.

    The in-memory counters would otherwise claim items_new > 0 for writes that
    were rolled back, which is what makes the scheduler start AI processing.
    """
    # The rollback expires every ORM object, so read the id before the run.
    source_id = source.id
    adapter = StubAdapter(source, [_stub("https://example.test/uncommitted")])
    _use_adapter(monkeypatch, adapter)

    # Wrap rather than patch the live session: only the collector's final commit
    # fails, and the real session stays usable for the assertions below.
    proxy = _CommitFailingSession(db_session)

    with pytest.raises(RuntimeError, match="connection lost during commit"):
        await collector.run_source(source, proxy)

    assert proxy.rolled_back, "the failed commit must be rolled back"

    stored = (
        await db_session.execute(
            select(func.count()).select_from(RawItem).where(RawItem.source_id == source_id)
        )
    ).scalar_one()
    assert stored == 0

    remaining = (
        await db_session.execute(
            select(func.count()).select_from(RunLog).where(RunLog.source_id == source_id)
        )
    ).scalar_one()
    assert remaining == 0


@pytest.mark.asyncio
async def test_commit_failure_releases_the_claim(db_session, source, monkeypatch):
    async def _fail(src, session):
        raise RuntimeError("connection lost during commit")

    monkeypatch.setattr(collector, "run_source", _fail)

    with pytest.raises(RuntimeError):
        await collector.collect_source(source.id)

    assert not collection_guard.is_source_collecting(source.id)


@pytest.mark.asyncio
async def test_run_all_sources_omits_a_run_whose_commit_failed(
    db_session, source, monkeypatch
):
    async def _fail(src, session):
        raise RuntimeError("connection lost during commit")

    monkeypatch.setattr(collector, "run_source", _fail)

    logs = await collector.run_all_sources()

    assert all(entry.source_id != source.id for entry in logs)
    assert not collection_guard.is_source_collecting(source.id)


def test_run_log_schema_is_additive_and_backward_compatible():
    """New counters are appended; existing field names and types are untouched."""
    from app.schemas.run_log import RunLogRead

    fields = list(RunLogRead.model_fields)
    assert fields[:8] == [
        "id",
        "source_id",
        "run_started_at",
        "run_finished_at",
        "status",
        "items_fetched",
        "items_new",
        "items_duplicate",
    ]
    assert set(fields[8:]) == {
        "items_skipped_url",
        "items_skipped_content",
        "items_skipped_invalid",
        "error_message",
    }


@pytest.mark.asyncio
async def test_run_log_schema_serializes_historical_rows_as_zero(db_session, source):
    from app.schemas.run_log import RunLogRead

    run = RunLog(source_id=source.id, run_started_at=datetime.utcnow(), status="success")
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    payload = RunLogRead.model_validate(run).model_dump()
    assert payload["items_skipped_url"] == 0
    assert payload["items_skipped_content"] == 0
    assert payload["items_skipped_invalid"] == 0


@pytest.mark.asyncio
async def test_new_counters_default_to_zero_for_existing_rows(db_session, source):
    """Rows written without the new counters read back as 0, not NULL."""
    run = RunLog(source_id=source.id, run_started_at=datetime.utcnow(), status="success")
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    assert run.items_skipped_url == 0
    assert run.items_skipped_content == 0
    assert run.items_skipped_invalid == 0


# ---------------------------------------------------------------------------
# Collection coordination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collect_source_skips_when_already_claimed(db_session, source, monkeypatch):
    adapter = StubAdapter(source, [_stub("https://example.test/guarded")])
    _use_adapter(monkeypatch, adapter)

    assert await collection_guard.claim_source_run(source.id) is True
    result = await collector.collect_source(source.id)

    assert result is None
    assert adapter.fetched_urls == []


@pytest.mark.asyncio
async def test_rejected_claim_creates_no_run_log(db_session, source, monkeypatch):
    before = (
        await db_session.execute(
            select(func.count()).select_from(RunLog).where(RunLog.source_id == source.id)
        )
    ).scalar_one()

    await collection_guard.claim_source_run(source.id)
    assert await collector.collect_source(source.id) is None

    after = (
        await db_session.execute(
            select(func.count()).select_from(RunLog).where(RunLog.source_id == source.id)
        )
    ).scalar_one()
    assert after == before


@pytest.mark.asyncio
async def test_claim_is_released_after_success(db_session, source, monkeypatch):
    _use_adapter(monkeypatch, StubAdapter(source, []))
    await collector.collect_source(source.id)
    assert not collection_guard.is_source_collecting(source.id)


@pytest.mark.asyncio
async def test_claim_is_released_after_collector_exception(db_session, source, monkeypatch):
    async def _explode(*args, **kwargs):
        raise RuntimeError("collector blew up")

    monkeypatch.setattr(collector, "run_source", _explode)

    with pytest.raises(RuntimeError):
        await collector.collect_source(source.id)

    assert not collection_guard.is_source_collecting(source.id)


@pytest.mark.asyncio
async def test_claim_is_released_after_cancellation(db_session, source, monkeypatch):
    started = asyncio.Event()

    async def _hang(*args, **kwargs):
        started.set()
        await asyncio.sleep(3600)

    monkeypatch.setattr(collector, "run_source", _hang)

    task = asyncio.create_task(collector.collect_source(source.id))
    await started.wait()
    assert collection_guard.is_source_collecting(source.id)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert not collection_guard.is_source_collecting(source.id)


@pytest.mark.asyncio
async def test_missing_source_is_handled_and_releases_the_claim(db_session):
    assert await collector.collect_source(987654) is None
    assert not collection_guard.is_source_collecting(987654)


@pytest.mark.asyncio
async def test_different_sources_are_not_blocked_by_each_other(db_session, source, monkeypatch):
    other = Source(
        name=f"Other {uuid.uuid4().hex[:6]}",
        base_url="https://other.test",
        source_type="rss",
        adapter_class="krebs.KrebsAdapter",
        is_active=True,
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    await collection_guard.claim_source_run(source.id)
    _use_adapter(monkeypatch, StubAdapter(other, []))

    result = await collector.collect_source(other.id)
    assert result is not None


@pytest.mark.asyncio
async def test_scheduler_conflict_is_skipped_without_raising(db_session, source, monkeypatch):
    """run_all_sources must log-and-continue rather than raise on a busy source."""
    await collection_guard.claim_source_run(source.id)
    _use_adapter(monkeypatch, StubAdapter(source, []))

    logs = await collector.run_all_sources()

    assert all(entry.source_id != source.id for entry in logs)


@pytest.mark.asyncio
async def test_concurrent_collect_source_runs_collection_once(
    db_session, source, monkeypatch
):
    calls: list[int] = []

    async def _slow(src, session):
        calls.append(src.id)
        await asyncio.sleep(0.05)
        return RunLog(source_id=src.id, run_started_at=datetime.utcnow(), status="success")

    monkeypatch.setattr(collector, "run_source", _slow)

    results = await asyncio.gather(
        collector.collect_source(source.id), collector.collect_source(source.id)
    )

    assert calls == [source.id]
    assert sum(1 for r in results if r is not None) == 1


@pytest.mark.asyncio
async def test_run_all_sources_only_collects_active_sources(db_session, monkeypatch):
    inactive = Source(
        name=f"Inactive {uuid.uuid4().hex[:6]}",
        base_url="https://inactive.test",
        source_type="rss",
        adapter_class="krebs.KrebsAdapter",
        is_active=False,
    )
    db_session.add(inactive)
    await db_session.commit()

    collected: list[int] = []

    async def _record(source_id):
        collected.append(source_id)
        return None

    monkeypatch.setattr(collector, "collect_source", _record)
    await collector.run_all_sources()

    assert inactive.id not in collected


@pytest.mark.asyncio
async def test_manual_trigger_goes_through_the_shared_boundary(monkeypatch):
    from app.scheduler import jobs

    seen: list[int] = []

    async def _record(source_id):
        seen.append(source_id)
        return None

    monkeypatch.setattr(collector, "collect_source", _record)
    await jobs.trigger_source_by_id(4242)

    assert seen == [4242]


# ---------------------------------------------------------------------------
# Manual trigger reservation, through the API
# ---------------------------------------------------------------------------


async def _admin_headers(db_session) -> dict:
    from app.auth import create_access_token, hash_password
    from app.models.user import User

    user = User(
        email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("pw"),
        is_active=True,
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


async def _run_log_count(db_session, source_id: int) -> int:
    return (
        await db_session.execute(
            select(func.count()).select_from(RunLog).where(RunLog.source_id == source_id)
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_concurrent_manual_triggers_yield_one_202_and_one_409(
    client, db_session, source, monkeypatch
):
    headers = await _admin_headers(db_session)
    before = await _run_log_count(db_session, source.id)

    in_collection = asyncio.Event()
    release = asyncio.Event()
    calls: list[int] = []

    async def _slow_run(src, session):
        calls.append(src.id)
        run = RunLog(
            source_id=src.id,
            run_started_at=datetime.utcnow(),
            run_finished_at=datetime.utcnow(),
            status="success",
        )
        session.add(run)
        await session.commit()
        in_collection.set()
        await release.wait()
        return run

    monkeypatch.setattr(collector, "run_source", _slow_run)

    url = f"/api/v1/sources/{source.id}/trigger"

    async def _first():
        return await client.post(url, headers=headers)

    async def _second():
        # Fire only once the first run holds the reservation, so the overlap is
        # deterministic rather than timing-dependent.
        await in_collection.wait()
        response = await client.post(url, headers=headers)
        release.set()
        return response

    first, second = await asyncio.gather(_first(), _second())

    assert sorted([first.status_code, second.status_code]) == [202, 409]
    conflict = first if first.status_code == 409 else second
    assert "already in progress" in conflict.json()["detail"]

    assert calls == [source.id]
    assert await _run_log_count(db_session, source.id) == before + 1
    assert not collection_guard.is_source_collecting(source.id)


@pytest.mark.asyncio
async def test_manual_trigger_releases_reservation_after_background_failure(
    client, db_session, source, monkeypatch
):
    headers = await _admin_headers(db_session)

    async def _explode(src, session):
        raise RuntimeError("collection blew up")

    monkeypatch.setattr(collector, "run_source", _explode)

    response = await client.post(
        f"/api/v1/sources/{source.id}/trigger", headers=headers
    )

    assert response.status_code == 202
    assert not collection_guard.is_source_collecting(source.id)


@pytest.mark.asyncio
async def test_manual_trigger_releases_reservation_when_queueing_fails(
    client, db_session, source, monkeypatch
):
    """A reservation must not leak if the background task is never registered."""
    from fastapi import BackgroundTasks

    def _refuse(self, func, *args, **kwargs):
        raise RuntimeError("cannot queue")

    monkeypatch.setattr(BackgroundTasks, "add_task", _refuse)
    headers = await _admin_headers(db_session)

    with pytest.raises(RuntimeError):
        await client.post(f"/api/v1/sources/{source.id}/trigger", headers=headers)

    assert not collection_guard.is_source_collecting(source.id)


@pytest.mark.asyncio
async def test_rejected_manual_trigger_creates_no_run_log(
    client, db_session, source, monkeypatch
):
    headers = await _admin_headers(db_session)
    before = await _run_log_count(db_session, source.id)

    await collection_guard.claim_source_run(source.id)
    response = await client.post(
        f"/api/v1/sources/{source.id}/trigger", headers=headers
    )

    assert response.status_code == 409
    assert await _run_log_count(db_session, source.id) == before


@pytest.mark.asyncio
async def test_unauthenticated_manual_trigger_reserves_nothing(client, db_session, source):
    response = await client.post(f"/api/v1/sources/{source.id}/trigger")

    assert response.status_code == 401
    assert not collection_guard.is_source_collecting(source.id)
