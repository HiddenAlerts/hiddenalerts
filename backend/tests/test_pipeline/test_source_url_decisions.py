"""Durable source-specific URL decisions, and the collector behaviour they drive.

An excluded URL creates no RawItem, so without a recorded decision it stays
"unseen" and is requested again on every run. These tests pin that it is
remembered, that the memory is per-source, and that remembering never looks like
collecting.

Mocked adapters only. No network, no AI.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source
from app.models.source_url_decision import (
    EXTERNAL_DESTINATION_EXCLUDED,
    SourceURLDecision,
)
from app.pipeline import collector
from app.pipeline.normalizer import compute_url_hash
from app.services.source_url_decisions import (
    get_suppressing_decisions,
    normalize_destination_host,
    record_external_exclusion,
)
from app.sources.base import RawItemStub, clean_summary_text
from app.sources.http_errors import ChallengeDetected, DestinationExcluded

FBI_URL = "https://www.fbi.gov/news/press-releases/joint-doj-announcement"
FBI_URL_2 = "https://www.fbi.gov/news/press-releases/second-joint-announcement"
FBI_OWN_URL = "https://www.fbi.gov/news/press-releases/director-statement"
DOJ_HOST = "www.justice.gov"


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class _AdapterDouble:
    def should_fetch_article(self, stub):
        return True

    def summary_fallback(self, stub, error):
        return clean_summary_text(stub.summary) or None


class ExcludingAdapter(_AdapterDouble):
    """Raises DestinationExcluded for the URLs it was told to exclude."""

    def __init__(self, stubs, excluded, destination=DOJ_HOST, bodies=None):
        self._stubs = stubs
        self._excluded = set(excluded)
        self._destination = destination
        self._bodies = bodies or {}
        self.fetched: list[str] = []
        self.fallbacks: list[str] = []
        self.detail_checks: list[str] = []

    async def fetch_item_stubs(self):
        return list(self._stubs)

    async def fetch_full_article(self, url):
        self.fetched.append(url)
        if url in self._excluded:
            raise DestinationExcluded(
                "refusing redirect", url=url, destination=self._destination
            )
        return self._bodies.get(url, f"Article body for {url}"), f"<p>{url}</p>"

    def should_fetch_article(self, stub):
        self.detail_checks.append(stub.item_url)
        return True

    def summary_fallback(self, stub, error):
        self.fallbacks.append(stub.item_url)
        return "a summary that must never be used for an excluded item"


def _stub(url, *, title="Title", published_at=None, summary="Feed summary"):
    return RawItemStub(source_name="S", item_url=url, title=title,
                       published_at=published_at, summary=summary)


@pytest.fixture
async def make_source(db_session):
    created: list[int] = []

    async def _make(name, adapter_class="fbi_national.FBINationalAdapter"):
        src = Source(
            name=name, base_url="https://www.fbi.gov/news", source_type="rss",
            adapter_class=adapter_class, is_active=True,
        )
        db_session.add(src)
        await db_session.commit()
        await db_session.refresh(src)
        created.append(src.id)
        return src

    yield _make

    await db_session.rollback()
    for source_id in created:
        await db_session.execute(
            delete(SourceURLDecision).where(SourceURLDecision.source_id == source_id)
        )
        await db_session.execute(delete(RawItem).where(RawItem.source_id == source_id))
        await db_session.execute(delete(RunLog).where(RunLog.source_id == source_id))
        await db_session.execute(delete(Source).where(Source.id == source_id))
    await db_session.commit()


async def _decisions(db_session, source):
    rows = await db_session.execute(
        select(SourceURLDecision).where(SourceURLDecision.source_id == source.id)
    )
    return rows.scalars().all()


async def _run(db_session, source, adapter, monkeypatch):
    monkeypatch.setattr(collector, "get_adapter", lambda s: adapter)
    return await collector.run_source(source, db_session)


# ===========================================================================
# Persistence and isolation
# ===========================================================================


@pytest.mark.asyncio
async def test_first_exclusion_inserts_exactly_one_row(db_session, make_source):
    source = await make_source("FBI National")
    await record_external_exclusion(
        db_session, source_id=source.id, url_hash=compute_url_hash(FBI_URL),
        item_url=FBI_URL, destination_host=DOJ_HOST, reason_code="DestinationExcluded",
    )
    await db_session.commit()

    rows = await _decisions(db_session, source)
    assert len(rows) == 1
    row = rows[0]
    assert row.decision == EXTERNAL_DESTINATION_EXCLUDED
    assert row.destination_host == DOJ_HOST
    assert row.occurrence_count == 1
    assert row.first_seen_at == row.last_seen_at


@pytest.mark.asyncio
async def test_repeat_exclusion_updates_rather_than_duplicates(db_session, make_source):
    source = await make_source("FBI National")
    first_moment = datetime(2026, 7, 1, 12, 0)
    later = first_moment + timedelta(days=3)
    url_hash = compute_url_hash(FBI_URL)

    await record_external_exclusion(
        db_session, source_id=source.id, url_hash=url_hash, item_url=FBI_URL,
        destination_host=DOJ_HOST, now=first_moment,
    )
    await db_session.commit()
    await record_external_exclusion(
        db_session, source_id=source.id, url_hash=url_hash, item_url=FBI_URL,
        destination_host=DOJ_HOST, now=later,
    )
    await db_session.commit()

    rows = await _decisions(db_session, source)
    assert len(rows) == 1
    assert rows[0].first_seen_at == first_moment, "first_seen_at is never rewritten"
    assert rows[0].last_seen_at == later
    assert rows[0].occurrence_count == 2


@pytest.mark.asyncio
async def test_repeated_calls_stay_idempotent(db_session, make_source):
    source = await make_source("FBI National")
    url_hash = compute_url_hash(FBI_URL)
    for _ in range(5):
        await record_external_exclusion(
            db_session, source_id=source.id, url_hash=url_hash, item_url=FBI_URL,
            destination_host=DOJ_HOST,
        )
    await db_session.commit()

    rows = await _decisions(db_session, source)
    assert len(rows) == 1
    assert rows[0].occurrence_count == 5


@pytest.mark.asyncio
async def test_losing_the_unique_race_becomes_an_update(db_session, make_source):
    """A concurrent writer wins the insert; we must fold into an update."""
    source = await make_source("FBI National")
    url_hash = compute_url_hash(FBI_URL)

    # Simulate the other writer having already committed the row.
    db_session.add(SourceURLDecision(
        source_id=source.id, url_hash=url_hash, item_url=FBI_URL,
        decision=EXTERNAL_DESTINATION_EXCLUDED, destination_host=DOJ_HOST,
        first_seen_at=datetime(2026, 6, 1), last_seen_at=datetime(2026, 6, 1),
        occurrence_count=1,
    ))
    await db_session.commit()

    result = await record_external_exclusion(
        db_session, source_id=source.id, url_hash=url_hash, item_url=FBI_URL,
        destination_host=DOJ_HOST, now=datetime(2026, 7, 2),
    )
    await db_session.commit()

    assert result.occurrence_count == 2
    assert result.first_seen_at == datetime(2026, 6, 1)
    assert len(await _decisions(db_session, source)) == 1


@pytest.mark.asyncio
async def test_the_same_url_holds_independent_decisions_per_source(
    db_session, make_source
):
    fbi = await make_source("FBI National")
    doj = await make_source("DOJ Press Releases", "doj_press.DOJPressAdapter")
    url_hash = compute_url_hash(FBI_URL)

    await record_external_exclusion(
        db_session, source_id=fbi.id, url_hash=url_hash, item_url=FBI_URL,
        destination_host=DOJ_HOST,
    )
    await db_session.commit()

    assert len(await _decisions(db_session, fbi)) == 1
    assert await _decisions(db_session, doj) == []

    # And DOJ may record its own, different verdict for the same hash.
    await record_external_exclusion(
        db_session, source_id=doj.id, url_hash=url_hash, item_url=FBI_URL,
        destination_host="example.test",
    )
    await db_session.commit()
    assert len(await _decisions(db_session, doj)) == 1


@pytest.mark.asyncio
async def test_batch_lookup_is_source_scoped(db_session, make_source):
    fbi = await make_source("FBI National")
    doj = await make_source("DOJ Press Releases", "doj_press.DOJPressAdapter")
    hashes = {compute_url_hash(u) for u in (FBI_URL, FBI_URL_2)}

    for url in (FBI_URL, FBI_URL_2):
        await record_external_exclusion(
            db_session, source_id=fbi.id, url_hash=compute_url_hash(url),
            item_url=url, destination_host=DOJ_HOST,
        )
    await db_session.commit()

    assert set(await get_suppressing_decisions(db_session, fbi.id, hashes)) == hashes
    assert await get_suppressing_decisions(db_session, doj.id, hashes) == {}
    assert await get_suppressing_decisions(db_session, fbi.id, set()) == {}


@pytest.mark.asyncio
async def test_batch_lookup_ignores_hashes_it_was_not_asked_about(
    db_session, make_source
):
    source = await make_source("FBI National")
    await record_external_exclusion(
        db_session, source_id=source.id, url_hash=compute_url_hash(FBI_URL),
        item_url=FBI_URL, destination_host=DOJ_HOST,
    )
    await db_session.commit()

    other = {compute_url_hash(FBI_URL_2)}
    assert await get_suppressing_decisions(db_session, source.id, other) == {}


@pytest.mark.parametrize("raw,expected", [
    ("WWW.Justice.GOV", "www.justice.gov"),
    ("www.justice.gov.", "www.justice.gov"),
    ("  www.justice.gov  ", "www.justice.gov"),
    ("", None), ("   ", None), (None, None),
])
def test_destination_host_is_normalized(raw, expected):
    assert normalize_destination_host(raw) == expected


@pytest.mark.asyncio
async def test_stored_url_carries_no_query_or_fragment(db_session, make_source):
    """The collector redacts before calling; the row must reflect that."""
    source = await make_source("FBI National")
    tracked = "https://www.fbi.gov/news/press-releases/x?token=SECRET#frag"

    from app.sources.base import _safe_url

    await record_external_exclusion(
        db_session, source_id=source.id, url_hash=compute_url_hash(tracked),
        item_url=_safe_url(tracked), destination_host=DOJ_HOST,
    )
    await db_session.commit()

    stored = (await _decisions(db_session, source))[0].item_url
    assert "SECRET" not in stored
    assert "?" not in stored and "#" not in stored
    assert stored.endswith("/news/press-releases/x")


@pytest.mark.asyncio
async def test_deleting_a_source_removes_its_decisions(db_session, make_source):
    source = await make_source("FBI National")
    await record_external_exclusion(
        db_session, source_id=source.id, url_hash=compute_url_hash(FBI_URL),
        item_url=FBI_URL, destination_host=DOJ_HOST,
    )
    await db_session.commit()
    source_id = source.id

    loaded = await db_session.get(Source, source_id)
    await db_session.delete(loaded)
    await db_session.commit()

    remaining = await db_session.execute(
        select(func.count()).select_from(SourceURLDecision)
        .where(SourceURLDecision.source_id == source_id)
    )
    assert remaining.scalar_one() == 0


# ===========================================================================
# Collector — new exclusions
# ===========================================================================


@pytest.mark.asyncio
async def test_new_exclusion_persists_a_decision_and_counts_external(
    db_session, make_source, monkeypatch
):
    source = await make_source("FBI National")
    adapter = ExcludingAdapter([_stub(FBI_URL), _stub(FBI_OWN_URL)], {FBI_URL})

    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.status == "success"
    assert run.items_skipped_external == 1
    assert run.items_skipped_invalid == 0, "external is never also invalid"
    assert run.items_new == 1

    rows = await _decisions(db_session, source)
    assert len(rows) == 1
    assert rows[0].url_hash == compute_url_hash(FBI_URL)
    assert rows[0].destination_host == DOJ_HOST
    assert rows[0].reason_code == "DestinationExcluded"


@pytest.mark.asyncio
async def test_new_exclusion_never_calls_summary_fallback(
    db_session, make_source, monkeypatch
):
    source = await make_source("FBI National")
    adapter = ExcludingAdapter([_stub(FBI_URL)], {FBI_URL})

    await _run(db_session, source, adapter, monkeypatch)
    assert adapter.fallbacks == []


@pytest.mark.asyncio
async def test_later_stubs_still_process_after_an_exclusion(
    db_session, make_source, monkeypatch
):
    source = await make_source("FBI National")
    adapter = ExcludingAdapter(
        [_stub(FBI_URL), _stub(FBI_URL_2), _stub(FBI_OWN_URL)], {FBI_URL, FBI_URL_2}
    )

    run = await _run(db_session, source, adapter, monkeypatch)
    stored = await db_session.execute(
        select(RawItem.item_url).where(RawItem.source_id == source.id)
    )

    assert run.items_skipped_external == 2
    assert list(stored.scalars().all()) == [FBI_OWN_URL]


@pytest.mark.asyncio
async def test_exclusion_stores_no_raw_item(db_session, make_source, monkeypatch):
    source = await make_source("FBI National")
    adapter = ExcludingAdapter([_stub(FBI_URL)], {FBI_URL})

    await _run(db_session, source, adapter, monkeypatch)
    count = await db_session.execute(
        select(func.count()).select_from(RawItem).where(RawItem.source_id == source.id)
    )
    assert count.scalar_one() == 0


# ===========================================================================
# Collector — previously persisted exclusions
# ===========================================================================


@pytest.mark.asyncio
async def test_a_remembered_exclusion_costs_no_article_request(
    db_session, make_source, monkeypatch
):
    """The whole point: the second run must not ask for the URL again."""
    source = await make_source("FBI National")

    first = ExcludingAdapter([_stub(FBI_URL)], {FBI_URL})
    await _run(db_session, source, first, monkeypatch)
    assert first.fetched == [FBI_URL]

    second = ExcludingAdapter([_stub(FBI_URL)], {FBI_URL})
    run = await _run(db_session, source, second, monkeypatch)

    assert second.fetched == [], "no article request"
    assert second.detail_checks == [], "should_fetch_article not consulted"
    assert second.fallbacks == [], "no summary fallback"
    assert run.items_skipped_external == 1
    assert run.items_skipped_invalid == 0
    assert run.items_new == 0


@pytest.mark.asyncio
async def test_a_remembered_exclusion_computes_no_content_hash(
    db_session, make_source, monkeypatch
):
    source = await make_source("FBI National")
    await _run(db_session, source, ExcludingAdapter([_stub(FBI_URL)], {FBI_URL}),
               monkeypatch)

    hashed: list[str] = []
    real = collector.compute_content_hash
    monkeypatch.setattr(collector, "compute_content_hash",
                        lambda text: hashed.append(text) or real(text))

    await _run(db_session, source, ExcludingAdapter([_stub(FBI_URL)], {FBI_URL}),
               monkeypatch)
    assert hashed == []


@pytest.mark.asyncio
async def test_seeing_a_remembered_exclusion_again_advances_the_counters(
    db_session, make_source, monkeypatch
):
    source = await make_source("FBI National")
    await _run(db_session, source, ExcludingAdapter([_stub(FBI_URL)], {FBI_URL}),
               monkeypatch)
    await _run(db_session, source, ExcludingAdapter([_stub(FBI_URL)], {FBI_URL}),
               monkeypatch)

    rows = await _decisions(db_session, source)
    assert len(rows) == 1
    assert rows[0].occurrence_count == 2
    assert rows[0].last_seen_at >= rows[0].first_seen_at


@pytest.mark.asyncio
async def test_a_decision_for_one_source_does_not_suppress_another(
    db_session, make_source, monkeypatch
):
    """DOJ still collects the article FBI refused."""
    fbi = await make_source("FBI National")
    doj = await make_source("DOJ Press Releases", "doj_press.DOJPressAdapter")

    await _run(db_session, fbi, ExcludingAdapter([_stub(FBI_URL)], {FBI_URL}), monkeypatch)
    assert len(await _decisions(db_session, fbi)) == 1

    doj_adapter = ExcludingAdapter([_stub(FBI_URL)], set())  # DOJ excludes nothing
    run = await _run(db_session, doj, doj_adapter, monkeypatch)

    assert doj_adapter.fetched == [FBI_URL], "DOJ still requested it"
    assert run.items_new == 1
    assert run.items_skipped_external == 0


@pytest.mark.asyncio
async def test_no_ai_is_invoked_for_exclusions(db_session, make_source, monkeypatch):
    from app.pipeline import ai_processor

    called: list[str] = []
    monkeypatch.setattr(ai_processor, "analyze_article",
                        lambda *a, **k: called.append("ai"), raising=False)
    source = await make_source("FBI National")

    await _run(db_session, source, ExcludingAdapter([_stub(FBI_URL)], {FBI_URL}),
               monkeypatch)
    await _run(db_session, source, ExcludingAdapter([_stub(FBI_URL)], {FBI_URL}),
               monkeypatch)
    assert called == []


# ===========================================================================
# Counter identity and transactions
# ===========================================================================


def _identity_holds(run: RunLog) -> bool:
    return run.items_fetched == (
        run.items_new + run.items_skipped_url + run.items_skipped_content
        + run.items_skipped_invalid + run.items_skipped_external
    )


@pytest.mark.asyncio
async def test_counter_identity_covers_every_outcome(
    db_session, make_source, monkeypatch
):
    """Stored, excluded, duplicate-in-batch, invalid and content-duplicate."""
    source = await make_source("FBI National")
    shared = "Identical article text for the duplicate check"

    adapter = ExcludingAdapter(
        [
            _stub(FBI_OWN_URL),                       # stored
            _stub(FBI_URL),                           # newly excluded
            _stub(FBI_URL),                           # same-batch duplicate
            _stub("https://www.fbi.gov/news/press-releases/a"),   # stored
            _stub("https://www.fbi.gov/news/press-releases/b"),   # content duplicate
            _stub("https://www.fbi.gov/news/press-releases/c", summary=""),  # invalid
        ],
        {FBI_URL},
        bodies={
            "https://www.fbi.gov/news/press-releases/a": shared,
            "https://www.fbi.gov/news/press-releases/b": shared,
            "https://www.fbi.gov/news/press-releases/c": "   ",
        },
    )

    run = await _run(db_session, source, adapter, monkeypatch)

    assert run.status == "success"
    assert run.items_fetched == 6
    assert run.items_skipped_url == 1        # the repeated FBI_URL
    assert run.items_skipped_external == 1
    assert run.items_skipped_content == 1
    assert run.items_skipped_invalid == 1
    assert run.items_new == 2
    assert _identity_holds(run)


@pytest.mark.asyncio
async def test_identity_holds_on_a_second_run_with_remembered_exclusions(
    db_session, make_source, monkeypatch
):
    source = await make_source("FBI National")
    stubs = [_stub(FBI_URL), _stub(FBI_URL_2), _stub(FBI_OWN_URL)]

    await _run(db_session, source, ExcludingAdapter(stubs, {FBI_URL, FBI_URL_2}),
               monkeypatch)
    run = await _run(db_session, source, ExcludingAdapter(stubs, {FBI_URL, FBI_URL_2}),
                     monkeypatch)

    assert run.items_fetched == 3
    assert run.items_skipped_external == 2
    assert run.items_skipped_url == 1, "FBI_OWN_URL is now a stored RawItem"
    assert run.items_new == 0
    assert _identity_holds(run)


@pytest.mark.asyncio
async def test_a_persistence_failure_fails_the_run(db_session, make_source, monkeypatch):
    """A run must never claim an exclusion was remembered when it was not."""
    source = await make_source("FBI National")

    async def _boom(*a, **k):
        raise RuntimeError("decision store unavailable")

    monkeypatch.setattr(collector, "record_external_exclusion", _boom)
    run = await _run(db_session, source,
                     ExcludingAdapter([_stub(FBI_URL)], {FBI_URL}), monkeypatch)

    assert run.status == "failed"
    assert "decision store unavailable" in (run.error_message or "")
    assert run.items_skipped_external == 0


@pytest.mark.asyncio
async def test_decision_and_run_log_share_one_transaction(engine, db_session, make_source):
    """A rollback must not leave a decision without the run that counted it."""
    source = await make_source("FBI National")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        adapter = ExcludingAdapter([_stub(FBI_URL)], {FBI_URL})

        import app.pipeline.collector as mod
        original = mod.get_adapter
        mod.get_adapter = lambda s: adapter
        try:
            src = await session.get(Source, source.id)
            run = await mod.run_source(src, session)
            assert run.items_skipped_external == 1
        finally:
            mod.get_adapter = original

    # Committed together: the decision exists and the run counts it.
    async with factory() as verify:
        decisions = (await verify.execute(
            select(SourceURLDecision).where(SourceURLDecision.source_id == source.id)
        )).scalars().all()
        runs = (await verify.execute(
            select(RunLog).where(RunLog.source_id == source.id)
        )).scalars().all()

    assert len(decisions) == 1
    assert sum(r.items_skipped_external for r in runs) == len(decisions)


@pytest.mark.asyncio
async def test_the_collector_stays_source_agnostic():
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(collector))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef))
        and node.body and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    literals = [
        node.value.lower() for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docstrings
    ]
    for token in ("fbi", "justice.gov", "doj"):
        assert not [t for t in literals if token in t], token


@pytest.mark.asyncio
async def test_a_non_terminal_failure_is_still_invalid_not_external(
    db_session, make_source, monkeypatch
):
    """Only DestinationExcluded feeds the external counter."""
    source = await make_source("FBI National")

    class _Challenged(_AdapterDouble):
        async def fetch_item_stubs(self):
            return [_stub(FBI_URL)]

        async def fetch_full_article(self, url):
            raise ChallengeDetected("interstitial")

        def summary_fallback(self, stub, error):
            return None

    run = await _run(db_session, source, _Challenged(), monkeypatch)

    assert run.items_skipped_invalid == 1
    assert run.items_skipped_external == 0
    assert await _decisions(db_session, source) == []
