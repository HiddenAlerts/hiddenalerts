"""Read-only source recovery preview tool.

Every adapter here is a double and every database is the in-memory test database.
No network, no collector, no AI.
"""
import ast
import inspect
import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import delete, select

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source
from app.pipeline.normalizer import compute_content_hash, compute_url_hash
from app.sources.base import RawItemStub
from app.sources.http_errors import (
    ChallengeDetected,
    DestinationExcluded,
    PermanentFetchError,
)
from app.tools import source_recovery_preview as tool
from app.tools.source_recovery_preview import (
    ARTICLE_READY,
    CONFIGURATION_BLOCKED,
    CONTENT_DUPLICATE,
    CONTENT_READY,
    EMPTY_UPSTREAM,
    EXIT_BAD_INPUT,
    EXIT_OK,
    EXIT_READ_ONLY_VIOLATION,
    EXIT_SOURCE_FAILED,
    EXTERNAL_DESTINATION_EXCLUDED,
    INVALID_CONTENT,
    LISTING_READY,
    NOT_CHECKED_DUE_TO_LIMIT,
    PARTIALLY_CHECKED,
    SOURCE_FAILED,
    SUMMARY_READY,
    UNAVAILABLE,
    EffectiveSource,
    PreviewConfigError,
    load_overlay,
)

# This module owns preview.test. The test engine is session-scoped, so an item
# URL shared with another module would arrive here already "known".
FEED_URL = "https://preview.test/feed.xml"


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class StubAdapter:
    """Adapter double honouring the same hooks ``run_source`` uses."""

    def __init__(self, source, stubs=None, bodies=None, errors=None,
                 fetch_detail=True, summaries=None, stub_error=None):
        self.source = source
        self._stubs = stubs if stubs is not None else []
        self._bodies = bodies or {}
        self._errors = errors or {}
        self._fetch_detail = fetch_detail
        self._summaries = summaries or {}
        self._stub_error = stub_error
        self.fetched: list[str] = []
        self.fallbacks: list[tuple[str, object]] = []

    async def fetch_item_stubs(self):
        if self._stub_error is not None:
            raise self._stub_error
        return list(self._stubs)

    async def fetch_full_article(self, url):
        self.fetched.append(url)
        if url in self._errors:
            raise self._errors[url]
        return self._bodies.get(url, f"Body for {url}"), f"<p>{url}</p>"

    def should_fetch_article(self, stub):
        return self._fetch_detail

    def summary_fallback(self, stub, error):
        self.fallbacks.append((stub.item_url, error))
        return self._summaries.get(stub.item_url)


def _stub(url, *, title="Title", published_at=None, summary="Feed summary"):
    return RawItemStub(source_name="Preview Source", item_url=url, title=title,
                       published_at=published_at, summary=summary)


def _use_adapter(monkeypatch, adapter):
    monkeypatch.setattr(tool, "get_adapter", lambda source: adapter)
    return adapter


@pytest.fixture
async def source(db_session):
    src = Source(
        name="Preview Source", base_url="https://preview.test/news",
        source_type="rss", rss_url=FEED_URL,
        adapter_class="krebs.KrebsAdapter", is_active=True,
    )
    db_session.add(src)
    await db_session.commit()
    await db_session.refresh(src)
    source_id = src.id  # the tool rolls back, which detaches src
    yield src
    await db_session.rollback()
    await db_session.execute(delete(RawItem).where(RawItem.source_id == source_id))
    await db_session.execute(delete(RunLog).where(RunLog.source_id == source_id))
    await db_session.execute(delete(Source).where(Source.id == source_id))
    await db_session.commit()


@pytest.fixture
def session_factory(db_session):
    """A factory the CLI can use that yields the test session."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory():
        yield db_session

    return _factory


async def _seed_item(db_session, source, url, text="Existing body"):
    item = RawItem(
        source_id=source.id, item_url=url, title="Existing", published_at=None,
        raw_text=text, raw_html="", content_hash=compute_content_hash(text),
        url_hash=compute_url_hash(url), is_duplicate=False,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(item)
    await db_session.commit()
    return item


async def _run(session, source=None, **kwargs):
    """Preview one source by id.

    The test engine is session-scoped and other modules leave active sources
    behind, so a preview must name its source rather than sweep every enabled
    row. Pass ``source=None`` with explicit kwargs to exercise selection itself.
    """
    defaults = dict(
        source_ids=[source.id] if source is not None else [],
        all_enabled=source is None, excluded=set(), overlay=None,
        overlay_sha256=None, mode="listing", max_unseen=25,
    )
    defaults.update(kwargs)
    return await tool.run_preview(session, **defaults)


# ===========================================================================
# Safety — read-only by construction
# ===========================================================================


def _tool_tree():
    return ast.parse(inspect.getsource(tool))


def test_tool_never_instantiates_raw_item_or_run_log():
    called = [
        node.func.id
        for node in ast.walk(_tool_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "RawItem" not in called
    assert "RunLog" not in called
    assert "ProcessedAlert" not in called


def test_tool_never_writes_through_the_session():
    forbidden = {"add", "add_all", "delete", "flush", "commit", "merge", "bulk_save_objects"}
    offenders = [
        node.func.attr
        for node in ast.walk(_tool_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden
    ]
    assert offenders == [], offenders


def test_tool_imports_no_collector_or_ai_entry_point():
    """Docstrings may name the collector; executable code must never reach it."""
    forbidden = {"run_source", "collect_source", "collect_reserved_source",
                 "run_all_sources", "analyze_article"}
    forbidden_modules = {"app.pipeline.collector", "app.pipeline.ai_processor",
                         "app.services.scheduler", "anthropic"}
    tree = _tool_tree()

    imported_names, imported_modules = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")
            imported_names.update(alias.name for alias in node.names)

    assert imported_modules & forbidden_modules == set()
    assert imported_names & forbidden == set()

    called = {
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } | {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called & forbidden == set(), called & forbidden


def test_tool_offers_no_write_option():
    parser = tool.build_parser()
    options = {opt for action in parser._actions for opt in action.option_strings}
    for forbidden in ("--apply", "--write", "--recover", "--process", "--publish",
                      "--commit", "--execute"):
        assert forbidden not in options
    assert options == {
        "-h", "--help", "--source-id", "--all-enabled", "--exclude-source-id",
        "--overlay", "--mode", "--max-unseen-per-source",
        "--output-json", "--output-markdown",
    }


class _FakeSession:
    """Minimal session double: just a bind dialect and a recording execute."""

    def __init__(self, dialect_name):
        self.executed: list[str] = []
        self.bind = type("Bind", (), {"dialect": type("D", (), {"name": dialect_name})()})()

    async def execute(self, statement, *a, **k):
        self.executed.append(str(statement))
        return None


@pytest.mark.asyncio
async def test_postgres_gets_a_read_only_transaction():
    session = _FakeSession("postgresql")

    assert await tool.begin_read_only(session) is True
    assert session.executed == ["SET TRANSACTION READ ONLY"]


@pytest.mark.asyncio
async def test_non_postgres_dialects_issue_no_statement():
    session = _FakeSession("sqlite")

    assert await tool.begin_read_only(session) is False
    assert session.executed == []


@pytest.mark.asyncio
async def test_sqlite_skips_the_statement_but_still_counts(db_session):
    assert await tool.begin_read_only(db_session) is False


@pytest.mark.asyncio
async def test_before_and_after_counts_are_captured_and_match(
    monkeypatch, db_session, source
):
    _use_adapter(monkeypatch, StubAdapter(source, [_stub("https://preview.test/a")]))
    report = await _run(db_session, source)

    assert set(report["database_counts_before"]) == {
        "sources", "raw_items", "run_logs", "processed_alerts"
    }
    assert report["database_counts_before"] == report["database_counts_after"]
    assert report["database_counts_match"] is True
    assert report["read_only"] is True


@pytest.mark.asyncio
async def test_nothing_is_written_by_a_full_preview(monkeypatch, db_session, source):
    before = {
        "raw_items": (await db_session.execute(select(RawItem))).scalars().all(),
        "run_logs": (await db_session.execute(select(RunLog))).scalars().all(),
        "alerts": (await db_session.execute(select(ProcessedAlert))).scalars().all(),
    }
    adapter = _use_adapter(monkeypatch, StubAdapter(
        source, [_stub("https://preview.test/a"), _stub("https://preview.test/b")],
    ))
    await _run(db_session, source, mode="content")

    after = {
        "raw_items": (await db_session.execute(select(RawItem))).scalars().all(),
        "run_logs": (await db_session.execute(select(RunLog))).scalars().all(),
        "alerts": (await db_session.execute(select(ProcessedAlert))).scalars().all(),
    }
    assert [len(v) for v in before.values()] == [len(v) for v in after.values()]
    assert adapter.fetched  # it really did the work


@pytest.mark.asyncio
async def test_count_mismatch_returns_exit_code_four(
    monkeypatch, db_session, source, session_factory
):
    counts = iter([
        {"sources": 1, "raw_items": 0, "run_logs": 0, "processed_alerts": 0},
        {"sources": 1, "raw_items": 1, "run_logs": 0, "processed_alerts": 0},
    ])

    async def _counts(session):
        return next(counts)

    monkeypatch.setattr(tool, "table_counts", _counts)
    _use_adapter(monkeypatch, StubAdapter(source, []))

    code = await tool.main(["--source-id", str(source.id)],
                           session_factory=session_factory)
    assert code == EXIT_READ_ONLY_VIOLATION


@pytest.mark.asyncio
async def test_the_orm_source_is_never_mutated(monkeypatch, db_session, source):
    original = (source.base_url, source.rss_url, source.source_type)
    _use_adapter(monkeypatch, StubAdapter(source, []))

    await _run(db_session, source, overlay={source.id: {
        "expect": {"base_url": source.base_url},
        "override": {"base_url": "https://proposed.test/listing"},
    }})

    assert (source.base_url, source.rss_url, source.source_type) == original
    await db_session.refresh(source)
    assert source.base_url == original[0]


# ===========================================================================
# Overlay
# ===========================================================================


def _overlay_file(tmp_path: Path, document) -> Path:
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(document))
    return path


def test_valid_overlay_parses_with_a_digest(tmp_path):
    path = _overlay_file(tmp_path, {"sources": [
        {"id": 2, "expect": {"base_url": "old"}, "override": {"base_url": "new"}}
    ]})
    entries, digest = load_overlay(path)

    assert entries == {2: {"expect": {"base_url": "old"}, "override": {"base_url": "new"}}}
    assert len(digest) == 64


@pytest.mark.parametrize("document,fragment", [
    ({"sources": [{"id": 2, "override": {"base_url": "x"}},
                  {"id": 2, "override": {"base_url": "y"}}]}, "more than once"),
    ({"sources": [{"override": {"base_url": "x"}}]}, "integer id"),
    ({"sources": [{"id": 2, "override": {"adapter_class": "x.Y"}}]}, "may not be overridden"),
    ({"sources": [{"id": 2, "override": {"id": 3}}]}, "may not be overridden"),
    ({"sources": [{"id": 2, "override": {"is_active": False}}]}, "may not be overridden"),
    ({"sources": [{"id": 2, "override": {}}]}, "overrides nothing"),
    ({"sources": [{"id": 2, "expect": "x", "override": {"base_url": "y"}}]}, "must be objects"),
    ({"sources": {}}, "sources"),
    ([], "sources"),
])
def test_malformed_overlays_are_rejected(tmp_path, document, fragment):
    with pytest.raises(PreviewConfigError, match=fragment):
        load_overlay(_overlay_file(tmp_path, document))


def test_unreadable_and_non_json_overlays_are_rejected(tmp_path):
    with pytest.raises(PreviewConfigError, match="cannot read"):
        load_overlay(tmp_path / "missing.json")

    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(PreviewConfigError, match="not valid JSON"):
        load_overlay(broken)


@pytest.mark.asyncio
async def test_overlay_builds_a_detached_effective_source(monkeypatch, db_session, source):
    seen: list[object] = []

    def _capture(effective):
        seen.append(effective)
        return StubAdapter(effective, [])

    monkeypatch.setattr(tool, "get_adapter", _capture)

    report = await _run(db_session, source, overlay={source.id: {
        "expect": {"base_url": source.base_url, "adapter_class": source.adapter_class},
        "override": {"base_url": "https://proposed.test/listing", "source_type": "html"},
    }})

    effective = seen[0]
    assert isinstance(effective, EffectiveSource)
    assert not isinstance(effective, Source)
    assert effective.base_url == "https://proposed.test/listing"
    assert effective.source_type == "html"
    assert effective.adapter_class == source.adapter_class

    entry = report["sources"][0]
    assert entry["current_config"]["base_url"] == source.base_url
    assert entry["effective_config"]["base_url"] == "https://proposed.test/listing"
    assert entry["config_changed"] is True
    assert set(entry["config_differences"]) == {"base_url", "source_type"}
    assert report["configuration_differences"][str(source.id)]


@pytest.mark.asyncio
async def test_expectation_mismatch_blocks_the_source(monkeypatch, db_session, source):
    _use_adapter(monkeypatch, StubAdapter(source, []))
    report = await _run(db_session, source, overlay={source.id: {
        "expect": {"base_url": "https://something-else.test/"},
        "override": {"base_url": "https://proposed.test/"},
    }})

    entry = report["sources"][0]
    assert entry["status"] == CONFIGURATION_BLOCKED
    assert entry["error_class"] == "ExpectationMismatch"
    assert "base_url" in entry["error_message"]
    assert report["totals"]["configuration_blocked"] == 1


@pytest.mark.asyncio
async def test_overlay_for_an_unselected_source_is_rejected(
    monkeypatch, db_session, source
):
    _use_adapter(monkeypatch, StubAdapter(source, []))
    with pytest.raises(PreviewConfigError, match="not in this run"):
        await _run(db_session, source,
                   overlay={99999: {"expect": {}, "override": {"base_url": "x"}}})


@pytest.mark.asyncio
async def test_unknown_explicit_source_id_is_rejected(db_session):
    with pytest.raises(PreviewConfigError, match="unknown source id"):
        await _run(db_session, source_ids=[987654], all_enabled=False)


@pytest.mark.asyncio
async def test_exclusions_remove_a_source(monkeypatch, db_session, source):
    _use_adapter(monkeypatch, StubAdapter(source, []))

    included = await _run(db_session, source)
    assert [s["source_id"] for s in included["sources"]] == [source.id]

    excluded = await _run(
        db_session, source_ids=[source.id], all_enabled=False, excluded={source.id}
    )
    assert excluded["sources"] == []
    assert excluded["totals"]["sources_previewed"] == 0


@pytest.mark.asyncio
async def test_unknown_adapter_class_is_configuration_blocked(db_session, source):
    """No monkeypatch: the real registry rejects the class."""
    source.adapter_class = "nope.MissingAdapter"
    report = await _run(db_session, source)
    source.adapter_class = "krebs.KrebsAdapter"

    entry = [s for s in report["sources"] if s["source_id"] == source.id][0]
    assert entry["status"] == CONFIGURATION_BLOCKED
    assert entry["error_class"] == "ValueError"


# ===========================================================================
# Listing mode
# ===========================================================================


@pytest.mark.asyncio
async def test_known_and_unseen_urls_are_counted(monkeypatch, db_session, source):
    known = "https://preview.test/known"
    await _seed_item(db_session, source, known)
    _use_adapter(monkeypatch, StubAdapter(source, [
        _stub(known), _stub("https://preview.test/new-1"), _stub("https://preview.test/new-2"),
    ]))

    entry = (await _run(db_session, source))["sources"][0]
    assert entry["stubs_fetched"] == 3
    assert entry["known_urls"] == 1
    assert entry["prospective_unseen"] == 2
    assert entry["unique_urls"] == 3
    assert entry["status"] == LISTING_READY


@pytest.mark.asyncio
async def test_same_batch_duplicates_are_counted(monkeypatch, db_session, source):
    url = "https://preview.test/repeat"
    _use_adapter(monkeypatch, StubAdapter(source, [
        _stub(url), _stub(url), _stub(url + "?utm_source=x"), _stub("https://preview.test/other"),
    ]))

    entry = (await _run(db_session, source))["sources"][0]
    # The tracking-param variant normalizes to the same hash — three of one URL.
    assert entry["batch_duplicates"] == 2
    assert entry["unique_urls"] == 2
    assert entry["prospective_unseen"] == 2


@pytest.mark.asyncio
async def test_blank_urls_are_invalid(monkeypatch, db_session, source):
    _use_adapter(monkeypatch, StubAdapter(source, [
        _stub(""), _stub("   "), _stub("https://preview.test/real"),
    ]))

    entry = (await _run(db_session, source))["sources"][0]
    assert entry["invalid_urls"] == 2
    assert entry["prospective_unseen"] == 1


@pytest.mark.asyncio
async def test_missing_titles_and_dates_are_reported(monkeypatch, db_session, source):
    _use_adapter(monkeypatch, StubAdapter(source, [
        _stub("https://preview.test/1", title="", published_at=datetime(2026, 7, 1)),
        _stub("https://preview.test/2", title="Has title", published_at=None),
        _stub("https://preview.test/3", title="Has title", published_at=datetime(2026, 7, 20)),
    ]))

    entry = (await _run(db_session, source))["sources"][0]
    assert entry["missing_titles"] == 1
    assert entry["missing_dates"] == 1
    assert entry["oldest_prospective"] == "2026-07-01T00:00:00"
    assert entry["newest_prospective"] == "2026-07-20T00:00:00"


@pytest.mark.asyncio
async def test_valid_empty_feed_is_empty_upstream_not_failed(
    monkeypatch, db_session, source
):
    _use_adapter(monkeypatch, StubAdapter(source, []))
    report = await _run(db_session, source)
    entry = report["sources"][0]

    assert entry["status"] == EMPTY_UPSTREAM
    assert entry["empty_upstream"] is True
    assert entry["error_class"] is None
    assert report["totals"]["healthy_empty_sources"] == 1
    assert report["totals"]["failed_sources"] == 0


@pytest.mark.parametrize("error", [
    ChallengeDetected("interstitial"),
    PermanentFetchError("HTTP 404", status=404),
    ValueError("selector produced nothing"),
])
@pytest.mark.asyncio
async def test_typed_and_untyped_discovery_failures_are_source_failed(
    monkeypatch, db_session, source, error
):
    _use_adapter(monkeypatch, StubAdapter(source, stub_error=error))
    report = await _run(db_session, source)
    entry = report["sources"][0]

    assert entry["status"] == SOURCE_FAILED
    assert entry["error_class"] == type(error).__name__
    assert report["totals"]["failed_sources"] == 1


@pytest.mark.asyncio
async def test_url_hashes_match_the_collector(monkeypatch, db_session, source):
    url = "https://preview.test/hash-me?utm_source=news#frag"
    _use_adapter(monkeypatch, StubAdapter(source, [_stub(url)]))

    entry = (await _run(db_session, source, mode="content"))["sources"][0]
    assert entry["items"][0]["url_hash"] == compute_url_hash(url)


# ===========================================================================
# Content mode
# ===========================================================================


@pytest.mark.asyncio
async def test_full_article_success_is_article_ready(monkeypatch, db_session, source):
    url = "https://preview.test/article"
    _use_adapter(monkeypatch, StubAdapter(source, [_stub(url)],
                                          bodies={url: "Real article body"}))

    entry = (await _run(db_session, source, mode="content"))["sources"][0]
    assert entry["outcome_counts"][ARTICLE_READY] == 1
    assert entry["predicted_storable"] == 1
    assert entry["items"][0]["content_origin"] == "article"
    assert entry["status"] == CONTENT_READY


@pytest.mark.asyncio
async def test_declined_detail_with_a_good_summary_is_summary_ready(
    monkeypatch, db_session, source
):
    """The SEC shape: no detail request at all."""
    url = "https://preview.test/sec-item"
    adapter = _use_adapter(monkeypatch, StubAdapter(
        source, [_stub(url)], fetch_detail=False, summaries={url: "A full sentence."},
    ))

    entry = (await _run(db_session, source, mode="content"))["sources"][0]
    assert adapter.fetched == []
    assert entry["outcome_counts"][SUMMARY_READY] == 1
    assert entry["predicted_storable"] == 1
    assert adapter.fallbacks == [(url, None)]


@pytest.mark.asyncio
async def test_typed_failure_with_a_fallback_is_summary_ready(
    monkeypatch, db_session, source
):
    """The DOJ shape: article blocked, summary substituted."""
    url = "https://preview.test/doj-item"
    adapter = _use_adapter(monkeypatch, StubAdapter(
        source, [_stub(url)],
        errors={url: ChallengeDetected("interstitial")},
        summaries={url: "A substantial summary sentence."},
    ))

    entry = (await _run(db_session, source, mode="content"))["sources"][0]
    assert entry["outcome_counts"][SUMMARY_READY] == 1
    assert entry["items"][0]["content_origin"] == "summary"
    assert entry["items"][0]["error_class"] == "ChallengeDetected"
    assert [e for _, e in adapter.fallbacks] != [None]


@pytest.mark.asyncio
async def test_destination_excluded_is_counted_separately(
    monkeypatch, db_session, source
):
    """The FBI shape: DOJ is canonical, so this item belongs to another source."""
    url = "https://www.fbi.gov/news/press-releases/joint"
    adapter = _use_adapter(monkeypatch, StubAdapter(
        source, [_stub(url)],
        errors={url: DestinationExcluded("refusing redirect",
                                         url=url, destination="www.justice.gov")},
        summaries={url: "This summary must never be used."},
    ))

    report = await _run(db_session, source, mode="content")
    entry = report["sources"][0]

    assert entry["outcome_counts"][EXTERNAL_DESTINATION_EXCLUDED] == 1
    assert entry["predicted_storable"] == 0
    assert entry["items"][0]["destination"] == "www.justice.gov"
    assert report["totals"]["external_destination_excluded"] == 1
    # Counted apart from every other skip reason.
    assert report["totals"]["invalid_content"] == 0
    assert report["totals"]["unavailable"] == 0


@pytest.mark.asyncio
async def test_destination_excluded_never_calls_summary_fallback(
    monkeypatch, db_session, source
):
    url = "https://www.fbi.gov/news/press-releases/joint"
    adapter = _use_adapter(monkeypatch, StubAdapter(
        source, [_stub(url)],
        errors={url: DestinationExcluded("x", url=url, destination="www.justice.gov")},
        summaries={url: "Never used."},
    ))

    await _run(db_session, source, mode="content")
    assert adapter.fallbacks == []


@pytest.mark.asyncio
async def test_unusable_summary_is_not_predicted_storable(
    monkeypatch, db_session, source
):
    url = "https://preview.test/thin"
    _use_adapter(monkeypatch, StubAdapter(
        source, [_stub(url)], errors={url: ChallengeDetected("x")}, summaries={url: None},
    ))

    entry = (await _run(db_session, source, mode="content"))["sources"][0]
    assert entry["outcome_counts"][UNAVAILABLE] == 1
    assert entry["predicted_storable"] == 0


@pytest.mark.asyncio
async def test_empty_article_body_is_invalid_content(monkeypatch, db_session, source):
    url = "https://preview.test/blank"
    _use_adapter(monkeypatch, StubAdapter(source, [_stub(url)], bodies={url: "   "},
                                          fetch_detail=True))

    entry = (await _run(db_session, source, mode="content"))["sources"][0]
    assert entry["outcome_counts"][INVALID_CONTENT] == 1
    assert entry["predicted_storable"] == 0
    assert entry["items"][0]["content_origin"] is None


@pytest.mark.asyncio
async def test_existing_content_hash_is_a_content_duplicate(
    monkeypatch, db_session, source
):
    body = "This exact text already exists in storage"
    await _seed_item(db_session, source, "https://preview.test/original", text=body)
    _use_adapter(monkeypatch, StubAdapter(
        source, [_stub("https://preview.test/republished")],
        bodies={"https://preview.test/republished": body},
    ))

    entry = (await _run(db_session, source, mode="content"))["sources"][0]
    assert entry["outcome_counts"][CONTENT_DUPLICATE] == 1
    assert entry["predicted_storable"] == 0


@pytest.mark.asyncio
async def test_the_per_source_limit_produces_unchecked_items(
    monkeypatch, db_session, source
):
    stubs = [_stub(f"https://preview.test/i{n}") for n in range(5)]
    adapter = _use_adapter(monkeypatch, StubAdapter(source, stubs))

    report = await _run(db_session, source, mode="content", max_unseen=2)
    entry = report["sources"][0]

    assert entry["checked_unseen"] == 2
    assert entry["unchecked_unseen"] == 3
    assert entry["outcome_counts"][NOT_CHECKED_DUE_TO_LIMIT] == 3
    assert len(adapter.fetched) == 2
    assert entry["status"] == PARTIALLY_CHECKED
    assert report["totals"]["unchecked_unseen"] == 3
    assert any("unchecked" in w for w in report["warnings"])


@pytest.mark.asyncio
async def test_partially_checked_is_never_content_ready(
    monkeypatch, db_session, source
):
    stubs = [_stub(f"https://preview.test/i{n}") for n in range(3)]
    _use_adapter(monkeypatch, StubAdapter(source, stubs))

    entry = (await _run(db_session, source, mode="content", max_unseen=1))["sources"][0]
    assert entry["status"] != CONTENT_READY
    assert entry["status"] == PARTIALLY_CHECKED


@pytest.mark.asyncio
async def test_unexpected_error_fails_the_source_not_the_item(
    monkeypatch, db_session, source
):
    url = "https://preview.test/bug"
    _use_adapter(monkeypatch, StubAdapter(
        source, [_stub(url), _stub("https://preview.test/later")],
        errors={url: RuntimeError("adapter bug")},
    ))

    report = await _run(db_session, source, mode="content")
    entry = report["sources"][0]

    assert entry["status"] == SOURCE_FAILED
    assert entry["error_class"] == "RuntimeError"
    assert entry["outcome_counts"][INVALID_CONTENT] == 0
    assert report["totals"]["failed_sources"] == 1


@pytest.mark.asyncio
async def test_listing_mode_checks_no_content(monkeypatch, db_session, source):
    adapter = _use_adapter(monkeypatch, StubAdapter(
        source, [_stub("https://preview.test/a")],
    ))
    entry = (await _run(db_session, source, mode="listing"))["sources"][0]

    assert adapter.fetched == []
    assert entry["items"] == []
    assert entry["checked_unseen"] == 0


@pytest.mark.asyncio
async def test_no_ai_module_is_imported_or_invoked(monkeypatch, db_session, source):
    import app.pipeline.ai_processor as ai_processor

    called: list[str] = []
    monkeypatch.setattr(ai_processor, "analyze_article",
                        lambda *a, **k: called.append("ai"), raising=False)
    _use_adapter(monkeypatch, StubAdapter(source, [_stub("https://preview.test/a")]))

    await _run(db_session, source, mode="content")
    assert called == []
    assert "ai_processor" not in inspect.getsource(tool)


# ===========================================================================
# Output, totals and CLI
# ===========================================================================


@pytest.mark.asyncio
async def test_json_and_markdown_totals_agree(
    monkeypatch, db_session, source, session_factory, tmp_path
):
    url = "https://www.fbi.gov/news/press-releases/joint"
    _use_adapter(monkeypatch, StubAdapter(
        source,
        [_stub("https://preview.test/ok"), _stub(url)],
        errors={url: DestinationExcluded("x", url=url, destination="www.justice.gov")},
    ))
    json_path, md_path = tmp_path / "p.json", tmp_path / "p.md"

    code = await tool.main(
        ["--source-id", str(source.id), "--mode", "content",
         "--output-json", str(json_path), "--output-markdown", str(md_path)],
        session_factory=session_factory,
    )
    assert code == EXIT_OK

    report = json.loads(json_path.read_text())
    markdown = md_path.read_text()

    for key, value in report["totals"].items():
        assert f"| {key.replace('_', ' ')} | {value} |" in markdown
    assert report["totals"]["predicted_storable"] == 1
    assert report["totals"]["external_destination_excluded"] == 1
    assert "# Source recovery preview" in markdown


@pytest.mark.asyncio
async def test_output_carries_no_bodies_or_query_strings(
    monkeypatch, db_session, source, session_factory, tmp_path
):
    secret_url = "https://preview.test/tracked?token=SUPERSECRET123"
    body = "SENSITIVE ARTICLE BODY THAT MUST NOT BE EXPORTED"
    _use_adapter(monkeypatch, StubAdapter(
        source, [_stub(secret_url)], bodies={secret_url: body},
    ))
    json_path, md_path = tmp_path / "p.json", tmp_path / "p.md"

    await tool.main(
        ["--source-id", str(source.id), "--mode", "content",
         "--output-json", str(json_path), "--output-markdown", str(md_path)],
        session_factory=session_factory,
    )
    written = json_path.read_text() + md_path.read_text()

    assert "SUPERSECRET123" not in written
    assert "token=" not in written
    assert body not in written
    assert "SENSITIVE" not in written
    # The URL is still identifiable, just redacted.
    assert "https://preview.test/tracked" in written


@pytest.mark.asyncio
async def test_report_carries_provenance_and_settings(
    monkeypatch, db_session, source, tmp_path
):
    _use_adapter(monkeypatch, StubAdapter(source, []))
    report = await _run(db_session, source, mode="content", max_unseen=7,
                        overlay_sha256="abc123")

    assert report["mode"] == "content"
    assert report["max_unseen_per_source"] == 7
    assert report["overlay_sha256"] == "abc123"
    assert report["generated_at"]
    assert "branch" in report and "commit" in report
    assert "database_revision" in report


@pytest.mark.asyncio
async def test_source_selection_is_required(session_factory, capsys):
    assert await tool.main([], session_factory=session_factory) == EXIT_BAD_INPUT
    assert "--source-id or --all-enabled" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_conflicting_and_repeated_selection_is_rejected(session_factory):
    assert await tool.main(
        ["--all-enabled", "--source-id", "1"], session_factory=session_factory
    ) == EXIT_BAD_INPUT
    assert await tool.main(
        ["--source-id", "1", "--source-id", "1"], session_factory=session_factory
    ) == EXIT_BAD_INPUT
    assert await tool.main(
        ["--source-id", "1", "--max-unseen-per-source", "-1"],
        session_factory=session_factory,
    ) == EXIT_BAD_INPUT


@pytest.mark.asyncio
async def test_bad_overlay_returns_exit_code_two(session_factory, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"sources": [{"id": 1, "override": {"adapter_class": "x.Y"}}]}')

    code = await tool.main(
        ["--all-enabled", "--overlay", str(bad)], session_factory=session_factory
    )
    assert code == EXIT_BAD_INPUT


@pytest.mark.asyncio
async def test_missing_overlay_file_returns_exit_code_two(session_factory, tmp_path):
    code = await tool.main(
        ["--all-enabled", "--overlay", str(tmp_path / "nope.json")],
        session_factory=session_factory,
    )
    assert code == EXIT_BAD_INPUT


@pytest.mark.asyncio
async def test_failed_source_returns_exit_code_three(
    monkeypatch, db_session, source, session_factory, tmp_path
):
    _use_adapter(monkeypatch, StubAdapter(source, stub_error=ChallengeDetected("blocked")))

    code = await tool.main(
        ["--source-id", str(source.id), "--output-json", str(tmp_path / "p.json")],
        session_factory=session_factory,
    )
    assert code == EXIT_SOURCE_FAILED


@pytest.mark.asyncio
async def test_clean_run_returns_exit_code_zero(
    monkeypatch, db_session, source, session_factory, tmp_path
):
    _use_adapter(monkeypatch, StubAdapter(source, [_stub("https://preview.test/a")]))

    code = await tool.main(
        ["--source-id", str(source.id), "--output-json", str(tmp_path / "p.json")],
        session_factory=session_factory,
    )
    assert code == EXIT_OK


@pytest.mark.asyncio
async def test_report_is_deterministic(monkeypatch, db_session, source):
    stubs = [_stub("https://preview.test/b"), _stub("https://preview.test/a")]
    _use_adapter(monkeypatch, StubAdapter(source, stubs))

    first = await _run(db_session, source, mode="content")
    _use_adapter(monkeypatch, StubAdapter(source, stubs))
    second = await _run(db_session, source, mode="content")

    for report in (first, second):
        for volatile in ("generated_at", "branch", "commit"):
            report.pop(volatile)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# ===========================================================================
# Persisted terminal decisions (Slice 3B.2H)
# ===========================================================================


async def _record_decision(db_session, source, url, destination="www.justice.gov"):
    from app.models.source_url_decision import (
        EXTERNAL_DESTINATION_EXCLUDED,
        SourceURLDecision,
    )

    decision = SourceURLDecision(
        source_id=source.id, url_hash=compute_url_hash(url), item_url=url,
        decision=EXTERNAL_DESTINATION_EXCLUDED, destination_host=destination,
        first_seen_at=datetime(2026, 7, 1), last_seen_at=datetime(2026, 7, 1),
        occurrence_count=1,
    )
    db_session.add(decision)
    await db_session.commit()
    return decision


@pytest.fixture
async def clean_decisions(db_session):
    from app.models.source_url_decision import SourceURLDecision

    yield
    await db_session.rollback()
    await db_session.execute(delete(SourceURLDecision))
    await db_session.commit()


@pytest.mark.asyncio
async def test_persisted_decisions_leave_prospective_unseen(
    monkeypatch, db_session, source, clean_decisions
):
    excluded = "https://preview.test/excluded"
    await _record_decision(db_session, source, excluded)
    _use_adapter(monkeypatch, StubAdapter(
        source, [_stub(excluded), _stub("https://preview.test/fresh")],
    ))

    entry = (await _run(db_session, source))["sources"][0]

    assert entry["stubs_fetched"] == 2
    assert entry["previously_excluded_external"] == 1
    assert entry["prospective_unseen"] == 1, "the decided URL is not backlog"
    assert entry["known_urls"] == 0, "it is not a stored RawItem either"


@pytest.mark.asyncio
async def test_preview_makes_no_article_request_for_a_decided_url(
    monkeypatch, db_session, source, clean_decisions
):
    excluded = "https://preview.test/excluded"
    await _record_decision(db_session, source, excluded)
    adapter = _use_adapter(monkeypatch, StubAdapter(source, [_stub(excluded)]))

    entry = (await _run(db_session, source, mode="content"))["sources"][0]

    assert adapter.fetched == []
    assert entry["prospective_unseen"] == 0
    assert entry["checked_unseen"] == 0
    assert entry["predicted_storable"] == 0


@pytest.mark.asyncio
async def test_decision_lookup_is_source_scoped_in_the_preview(
    monkeypatch, db_session, source, clean_decisions
):
    """A decision recorded for one source must not hide the URL from another."""
    other = Source(
        name="Other Preview Source", base_url="https://preview.test/news",
        source_type="rss", rss_url=FEED_URL,
        adapter_class="krebs.KrebsAdapter", is_active=True,
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    shared = "https://preview.test/shared-article"
    await _record_decision(db_session, source, shared)
    _use_adapter(monkeypatch, StubAdapter(other, [_stub(shared)]))

    entry = (await _run(db_session, other))["sources"][0]
    assert entry["previously_excluded_external"] == 0
    assert entry["prospective_unseen"] == 1

    await db_session.execute(delete(Source).where(Source.id == other.id))
    await db_session.commit()


@pytest.mark.asyncio
async def test_the_preview_never_mutates_a_decision(
    monkeypatch, db_session, source, clean_decisions
):
    """Read-only means occurrence_count and last_seen_at do not move."""
    from app.models.source_url_decision import SourceURLDecision

    excluded = "https://preview.test/excluded"
    await _record_decision(db_session, source, excluded)
    _use_adapter(monkeypatch, StubAdapter(source, [_stub(excluded)]))

    await _run(db_session, source, mode="content")

    row = (await db_session.execute(
        select(SourceURLDecision).where(SourceURLDecision.source_id == source.id)
    )).scalar_one()
    assert row.occurrence_count == 1
    assert row.last_seen_at == datetime(2026, 7, 1)


@pytest.mark.asyncio
async def test_totals_and_markdown_include_previously_excluded(
    monkeypatch, db_session, source, session_factory, tmp_path, clean_decisions
):
    excluded = "https://preview.test/excluded"
    await _record_decision(db_session, source, excluded)
    _use_adapter(monkeypatch, StubAdapter(
        source, [_stub(excluded), _stub("https://preview.test/fresh")],
    ))
    json_path, md_path = tmp_path / "p.json", tmp_path / "p.md"

    code = await tool.main(
        ["--source-id", str(source.id),
         "--output-json", str(json_path), "--output-markdown", str(md_path)],
        session_factory=session_factory,
    )
    assert code == EXIT_OK

    report = json.loads(json_path.read_text())
    markdown = md_path.read_text()

    assert report["totals"]["previously_excluded_external"] == 1
    for key, value in report["totals"].items():
        assert f"| {key.replace('_', ' ')} | {value} |" in markdown
    assert "Prev. external" in markdown


def test_preview_still_offers_no_write_option():
    parser = tool.build_parser()
    options = {opt for action in parser._actions for opt in action.option_strings}
    assert options == {
        "-h", "--help", "--source-id", "--all-enabled", "--exclude-source-id",
        "--overlay", "--mode", "--max-unseen-per-source",
        "--output-json", "--output-markdown",
    }


def test_preview_decision_lookup_is_the_shared_helper():
    """One definition of "suppressing" for the collector and the preview."""
    import inspect

    from app.services import source_url_decisions

    assert tool.get_suppressing_decisions is source_url_decisions.get_suppressing_decisions
    # The read-only tool must not reach for the mutating helpers.
    source = inspect.getsource(tool)
    assert "record_external_exclusion" not in source
    assert "touch_seen_decisions" not in source
