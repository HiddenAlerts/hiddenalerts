"""DOJ collection via the official RSS feed, and the summary-fallback contract.

All responses come from sanitized fixtures through an injected transport. No
network, no collector entry points, no AI.
"""
import asyncio
from datetime import datetime

import httpx
import pytest
from sqlalchemy import delete, select

from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source
from app.pipeline import collector
from app.sources import base as source_base
from app.sources.base import (
    RawItemStub,
    _safe_url,
    clean_summary_text,
    summary_fallback_allowed,
)
from app.sources.doj_press import (
    MIN_SUMMARY_CHARS,
    MIN_SUMMARY_WORDS,
    OFFICIAL_FEED_URL,
    DOJPressAdapter,
    is_usable_summary,
)
from app.sources.host_limiter import HostRateLimiter
from app.sources.http_errors import (
    ChallengeDetected,
    ContentTypeMismatch,
    EmptyContent,
    PermanentFetchError,
    RateLimitedError,
    RedirectLoop,
    TooManyRedirects,
    TransientFetchError,
    UnsafeRequestTarget,
    UnsupportedDocument,
)
from app.sources.registry import ADAPTER_REGISTRY
from app.sources.response_policy import AcceptPolicy
from app.sources.rss_adapter import RSSAdapter
from tests.test_adapters.doj_fixtures import (
    BOILERPLATE_SUMMARY,
    EMPTY_FEED,
    FEED_CHALLENGE_HTML,
    FEED_WITH_MALFORMED,
    FULL_FEED,
    GOOD_SUMMARY,
    HTML_SUMMARY,
    LINK_ONLY_SUMMARY,
    OPA_ARTICLE_HTML,
    OPA_ARTICLE_HTML_2,
    OPA_URL,
    OPA_URL_2,
    SHORT_VALID_SUMMARY,
    TITLE_ECHO_SUMMARY,
    TITLE_ECHO_TITLE,
    USAO_INTERSTITIAL_HTML,
    USAO_URL,
    USAO_URL_2,
    USAO_URL_3,
    WEAK_SUMMARY,
)

_REAL_ASYNC_CLIENT = httpx.AsyncClient
_REAL_SLEEP = asyncio.sleep


class _Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds
        await _REAL_SLEEP(0)


def _limiter():
    clock = _Clock()
    return HostRateLimiter(monotonic=clock.monotonic, sleep=clock.sleep)


class _DOJSource:
    id = 8
    name = "DOJ Press Releases"
    base_url = "https://www.justice.gov/news"
    rss_url = None
    adapter_class = "doj_press.DOJPressAdapter"


def _adapter(rss_url=None):
    src = _DOJSource()
    src.rss_url = rss_url
    return DOJPressAdapter(src)


def _routes(monkeypatch, mapping, *, default=None):
    """Serve fixtures by URL through the httpx tier. Records what was requested."""
    seen: list[str] = []

    def handler(request):
        url = str(request.url)
        seen.append(url)
        body, ctype, status = mapping.get(url, default or ("", "text/html", 404))
        return httpx.Response(status, headers={"content-type": ctype}, text=body)

    transport = httpx.MockTransport(handler)

    def _factory(**kw):
        kw.pop("transport", None)
        return _REAL_ASYNC_CLIENT(**kw, transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    monkeypatch.setattr(source_base, "host_limiter", _limiter())
    return seen


def _no_browser(monkeypatch):
    launched: list[str] = []

    async def _browser(*a, **k):
        launched.append("playwright")
        return 200, "", "text/html", ""

    monkeypatch.setattr(source_base, "_playwright_get", _browser)
    return launched


FEED_RESPONSE = (FULL_FEED, "application/rss+xml; charset=utf-8", 200)

# Production shape: /opa/ pages serve the article, /usao-* pages serve the
# interstitial. FULL_FEED lists two of the former and three of the latter.
FULL_ROUTES = {
    OFFICIAL_FEED_URL: FEED_RESPONSE,
    OPA_URL: (OPA_ARTICLE_HTML, "text/html", 200),
    OPA_URL_2: (OPA_ARTICLE_HTML_2, "text/html", 200),
    USAO_URL: (USAO_INTERSTITIAL_HTML, "text/html", 200),
    USAO_URL_2: (USAO_INTERSTITIAL_HTML, "text/html", 200),
    USAO_URL_3: (USAO_INTERSTITIAL_HTML, "text/html", 200),
}


# ---------------------------------------------------------------------------
# Adapter and feed
# ---------------------------------------------------------------------------


def test_doj_adapter_is_an_rss_adapter():
    assert issubclass(DOJPressAdapter, RSSAdapter)
    assert ADAPTER_REGISTRY["doj_press.DOJPressAdapter"] is DOJPressAdapter


def test_doj_no_longer_scrapes_the_challenged_listing():
    import inspect

    from app.sources import doj_press

    src = inspect.getsource(doj_press)
    assert "parse_listing_page" not in src
    assert "justice.gov/news" not in src.replace(OFFICIAL_FEED_URL, "")


def test_official_feed_is_used_when_no_rss_url_is_configured():
    assert _adapter().rss_url == OFFICIAL_FEED_URL
    assert OFFICIAL_FEED_URL == "https://www.justice.gov/news/rss?type=press_release"


def test_configured_rss_url_takes_precedence():
    assert _adapter("https://custom.test/doj.xml").rss_url == "https://custom.test/doj.xml"


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_feed_resolution_is_deterministic(configured):
    adapter = _adapter(configured)
    assert adapter.rss_url == OFFICIAL_FEED_URL
    assert adapter.rss_url == adapter.rss_url  # no per-call state


def test_only_one_default_feed_url_exists():
    import inspect

    from app.sources import doj_press

    assert inspect.getsource(doj_press).count("justice.gov/news/rss") == 1


@pytest.mark.asyncio
async def test_feed_is_requested_with_the_feed_policy(monkeypatch):
    captured = {}
    adapter = _adapter()

    async def _fetch(url, *, accept=AcceptPolicy.ANY_TEXT, **kw):
        captured["url"] = url
        captured["accept"] = accept
        return source_base.FetchResult(url=url, final_url=url, status=200,
                                       content_type="application/rss+xml",
                                       text=FULL_FEED)

    monkeypatch.setattr(adapter, "fetch", _fetch)
    await adapter.fetch_item_stubs()
    assert captured["url"] == OFFICIAL_FEED_URL
    assert captured["accept"] is AcceptPolicy.FEED


@pytest.mark.asyncio
async def test_feed_entries_parse_into_stubs(monkeypatch):
    _routes(monkeypatch, {OFFICIAL_FEED_URL: FEED_RESPONSE})
    stubs = await _adapter().fetch_item_stubs()

    assert len(stubs) == 5
    first = stubs[0]
    assert first.item_url == OPA_URL
    assert first.title == "Massachusetts Man Convicted of Violating Sanctions"
    assert first.summary == GOOD_SUMMARY
    assert first.source_name == "DOJ Press Releases"

    # The whole feed is represented, in document order.
    assert [s.item_url for s in stubs] == [
        OPA_URL, USAO_URL, USAO_URL_2, USAO_URL_3, OPA_URL_2
    ]


@pytest.mark.asyncio
async def test_publication_dates_parse_and_normalize_to_utc(monkeypatch):
    _routes(monkeypatch, {OFFICIAL_FEED_URL: FEED_RESPONSE})
    stubs = await _adapter().fetch_item_stubs()

    assert stubs[0].published_at == datetime(2026, 7, 28, 12, 0)
    # -0400 offset converted to naive UTC, matching the column convention.
    assert stubs[1].published_at == datetime(2026, 7, 27, 20, 30)
    assert all(s.published_at.tzinfo is None for s in stubs if s.published_at)


@pytest.mark.asyncio
async def test_entries_without_a_link_or_title_are_skipped(monkeypatch):
    _routes(monkeypatch, {OFFICIAL_FEED_URL: (FEED_WITH_MALFORMED,
                                              "application/rss+xml", 200)})
    stubs = await _adapter().fetch_item_stubs()

    assert len(stubs) == 1
    assert stubs[0].item_url == OPA_URL


@pytest.mark.asyncio
async def test_structurally_empty_feed_is_valid_and_yields_no_stubs(monkeypatch):
    _routes(monkeypatch, {OFFICIAL_FEED_URL: (EMPTY_FEED, "application/rss+xml", 200)})
    assert await _adapter().fetch_item_stubs() == []


@pytest.mark.asyncio
async def test_interstitial_served_for_the_feed_raises_challenge(monkeypatch):
    _routes(monkeypatch, {OFFICIAL_FEED_URL: (FEED_CHALLENGE_HTML, "text/html", 200)})
    launched = _no_browser(monkeypatch)

    with pytest.raises(ChallengeDetected):
        await _adapter().fetch_item_stubs()
    assert launched == []


@pytest.mark.asyncio
async def test_adapter_never_enables_browser_mode(monkeypatch):
    _routes(monkeypatch, {OFFICIAL_FEED_URL: FEED_RESPONSE,
                          OPA_URL: (OPA_ARTICLE_HTML, "text/html", 200)})
    launched = _no_browser(monkeypatch)

    await _adapter().fetch_item_stubs()
    await _adapter().fetch_full_article(OPA_URL)
    assert launched == []


def test_adapter_declares_no_browser_opt_in():
    import inspect

    from app.sources import doj_press

    assert "allow_browser" not in inspect.getsource(doj_press)


# ---------------------------------------------------------------------------
# Summary quality
# ---------------------------------------------------------------------------


def test_good_summary_is_accepted():
    assert is_usable_summary(GOOD_SUMMARY, "Massachusetts Man Convicted")


def test_meaningful_short_release_is_accepted():
    """Short but complete — the audit's shortest DOJ summaries are ~68 chars."""
    assert len(clean_summary_text(SHORT_VALID_SUMMARY)) >= MIN_SUMMARY_CHARS
    assert is_usable_summary(SHORT_VALID_SUMMARY, "Gretna Man Indicted")


@pytest.mark.parametrize("summary", ["", "   \n\t ", None])
def test_empty_and_whitespace_summaries_are_rejected(summary):
    assert not is_usable_summary(summary or "", "Some Title")


def test_title_echo_summary_is_rejected():
    assert not is_usable_summary(TITLE_ECHO_SUMMARY, TITLE_ECHO_TITLE)


def test_weak_short_summary_is_rejected():
    assert not is_usable_summary(WEAK_SUMMARY, "Defendant Sentenced")


def test_boilerplate_summary_is_rejected():
    assert not is_usable_summary(BOILERPLATE_SUMMARY, "Some Title")


def test_link_only_summary_is_rejected():
    assert not is_usable_summary(LINK_ONLY_SUMMARY, "Some Title")


def test_sentence_structure_is_required():
    words = " ".join(["evidence"] * (MIN_SUMMARY_WORDS + 10))
    assert len(words) > MIN_SUMMARY_CHARS
    assert not is_usable_summary(words, "Title")


def test_word_count_is_required_not_just_length():
    padded = "aaaaaaaaaaaaaaaaaaaa " * 8 + "."
    assert len(padded) > MIN_SUMMARY_CHARS
    assert not is_usable_summary(padded, "Title")


def test_summary_cleaning_removes_markup_and_scripts():
    cleaned = clean_summary_text(HTML_SUMMARY)
    assert "<" not in cleaned and "track()" not in cleaned
    assert "Skip to content" not in cleaned
    assert cleaned.startswith("A federal grand jury")
    assert is_usable_summary(HTML_SUMMARY, "Three Charged in Investor Fraud Scheme")


def test_validator_is_pure_and_deterministic():
    assert is_usable_summary(GOOD_SUMMARY, "T") == is_usable_summary(GOOD_SUMMARY, "T")


# ---------------------------------------------------------------------------
# Typed-error fallback matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("error", [
    ChallengeDetected("c"), EmptyContent("e"), RateLimitedError("r", status=429),
    TransientFetchError("t", status=503), UnsupportedDocument("u"),
    PermanentFetchError("p", status=403), PermanentFetchError("p", status=404),
])
def test_expected_unavailability_permits_fallback(error):
    assert summary_fallback_allowed(error) is True


@pytest.mark.parametrize("error", [
    UnsafeRequestTarget("u"), RedirectLoop("l"), TooManyRedirects("m"),
    ContentTypeMismatch("c"), PermanentFetchError("p", status=400),
    RuntimeError("boom"), ValueError("bad"),
])
def test_terminal_and_unexpected_errors_forbid_fallback(error):
    assert summary_fallback_allowed(error) is False


def test_unsupported_redirect_scheme_forbids_fallback():
    from app.sources.http_errors import UnsupportedRedirectScheme

    assert summary_fallback_allowed(UnsupportedRedirectScheme("s")) is False


def test_default_adapter_fallback_preserves_existing_behaviour():
    """Non-DOJ adapters keep using any non-empty summary."""
    from app.sources.bleeping import BleepingAdapter

    class _S:
        id = 10
        name = "BleepingComputer"
        rss_url = "https://x.test/feed"

    stub = RawItemStub(source_name="B", item_url="https://x.test/a", title="T",
                       published_at=None, summary=WEAK_SUMMARY)
    assert BleepingAdapter(_S()).summary_fallback(stub, EmptyContent("e")) == WEAK_SUMMARY


def test_default_adapter_fallback_returns_none_for_empty_summary():
    from app.sources.bleeping import BleepingAdapter

    class _S:
        id = 10
        name = "B"
        rss_url = "https://x.test/feed"

    stub = RawItemStub(source_name="B", item_url="https://x.test/a", title="T",
                       published_at=None, summary="   ")
    assert BleepingAdapter(_S()).summary_fallback(stub, EmptyContent("e")) is None


@pytest.mark.parametrize("summary,expected", [
    (GOOD_SUMMARY, True), (SHORT_VALID_SUMMARY, True),
    (WEAK_SUMMARY, False), ("", False), (BOILERPLATE_SUMMARY, False),
])
def test_doj_fallback_judges_each_item(summary, expected):
    stub = RawItemStub(source_name="DOJ", item_url=USAO_URL, title="A Title",
                       published_at=None, summary=summary)
    result = _adapter().summary_fallback(stub, ChallengeDetected("c"))
    assert (result is not None) is expected


# ---------------------------------------------------------------------------
# Collector integration
# ---------------------------------------------------------------------------


@pytest.fixture
async def doj_source(db_session):
    """A DOJ source whose rows are removed afterwards.

    The test engine is session-scoped and ``run_source`` commits, so without the
    teardown a second collection would find its own URLs already stored and skip
    every item.
    """
    src = Source(
        name="DOJ Press Releases",
        base_url="https://www.justice.gov/news",
        source_type="rss",
        rss_url=None,
        adapter_class="doj_press.DOJPressAdapter",
        is_active=True,
    )
    db_session.add(src)
    await db_session.commit()
    await db_session.refresh(src)
    yield src
    await db_session.execute(delete(RawItem).where(RawItem.source_id == src.id))
    await db_session.execute(delete(RunLog).where(RunLog.source_id == src.id))
    await db_session.execute(delete(Source).where(Source.id == src.id))
    await db_session.commit()


async def _stored(db_session, source):
    rows = await db_session.execute(
        select(RawItem.item_url, RawItem.raw_text).where(RawItem.source_id == source.id)
    )
    return {url: text for url, text in rows.all()}


@pytest.mark.asyncio
async def test_collection_uses_article_then_validated_summary(
    monkeypatch, db_session, doj_source
):
    _routes(monkeypatch, FULL_ROUTES)
    launched = _no_browser(monkeypatch)

    run = await collector.run_source(doj_source, db_session)
    stored = await _stored(db_session, doj_source)

    # /opa/ article wins over its summary.
    assert "fourteen-day trial" in stored[OPA_URL]
    assert "superseding indictment" in stored[OPA_URL_2]
    # /usao-* challenge + good summary → validated fallback.
    assert stored[USAO_URL].startswith("A Gretna man was indicted")
    # /usao-* challenge + empty or weak summary → not stored at all.
    assert USAO_URL_2 not in stored
    assert USAO_URL_3 not in stored

    assert run.status == "success"
    assert run.items_new == 3
    assert run.items_skipped_invalid == 2
    assert run.items_fetched == (
        run.items_new + run.items_skipped_url + run.items_skipped_content
        + run.items_skipped_invalid
    )
    assert launched == []


@pytest.mark.asyncio
async def test_no_empty_raw_item_is_ever_stored(monkeypatch, db_session, doj_source):
    _routes(monkeypatch, FULL_ROUTES)
    _no_browser(monkeypatch)

    await collector.run_source(doj_source, db_session)
    stored = await _stored(db_session, doj_source)
    assert stored
    assert all(text and text.strip() for text in stored.values())


@pytest.mark.asyncio
async def test_empty_content_error_uses_the_validated_summary(
    monkeypatch, db_session, doj_source
):
    """A page that renders to nothing is expected unavailability, not a defect."""
    async def _empty(url):
        raise EmptyContent("article has no extractable text", url=url)

    monkeypatch.setattr(DOJPressAdapter, "fetch_full_article",
                        lambda self, url: _empty(url))
    _routes(monkeypatch, {OFFICIAL_FEED_URL: FEED_RESPONSE})

    await collector.run_source(doj_source, db_session)
    stored = await _stored(db_session, doj_source)
    assert stored[USAO_URL].startswith("A Gretna man was indicted")


@pytest.mark.asyncio
async def test_transient_failure_uses_the_validated_summary(
    monkeypatch, db_session, doj_source
):
    async def _transient(url):
        raise TransientFetchError("upstream busy", url=url, status=503)

    monkeypatch.setattr(DOJPressAdapter, "fetch_full_article",
                        lambda self, url: _transient(url))
    _routes(monkeypatch, {OFFICIAL_FEED_URL: FEED_RESPONSE})

    run = await collector.run_source(doj_source, db_session)
    stored = await _stored(db_session, doj_source)
    assert OPA_URL in stored
    assert run.items_new >= 1


@pytest.mark.parametrize("error_factory", [
    lambda url: UnsafeRequestTarget("unsafe", url=url),
    lambda url: RedirectLoop("loop", url=url),
    lambda url: TooManyRedirects("too many", url=url),
], ids=["unsafe-target", "redirect-loop", "too-many-redirects"])
@pytest.mark.asyncio
async def test_terminal_errors_never_use_the_summary(
    monkeypatch, db_session, doj_source, error_factory
):
    async def _fail(url):
        raise error_factory(url)

    monkeypatch.setattr(DOJPressAdapter, "fetch_full_article",
                        lambda self, url: _fail(url))
    _routes(monkeypatch, {OFFICIAL_FEED_URL: FEED_RESPONSE})

    run = await collector.run_source(doj_source, db_session)
    assert await _stored(db_session, doj_source) == {}
    assert run.items_new == 0
    assert run.items_skipped_invalid == 5


@pytest.mark.asyncio
async def test_unexpected_runtime_error_is_not_converted_to_a_fallback(
    monkeypatch, db_session, doj_source
):
    """A programming error must surface, not be papered over with a summary."""
    async def _boom(url):
        raise RuntimeError("programming error")

    monkeypatch.setattr(DOJPressAdapter, "fetch_full_article",
                        lambda self, url: _boom(url))
    _routes(monkeypatch, {OFFICIAL_FEED_URL: FEED_RESPONSE})

    run = await collector.run_source(doj_source, db_session)
    assert run.status == "failed"
    assert "programming error" in (run.error_message or "")
    assert await _stored(db_session, doj_source) == {}


@pytest.mark.asyncio
async def test_fallback_logging_names_the_source_and_a_safe_url(
    monkeypatch, db_session, doj_source, caplog
):
    _routes(monkeypatch, FULL_ROUTES)
    _no_browser(monkeypatch)

    with caplog.at_level("INFO", logger="app.pipeline.collector"):
        await collector.run_source(doj_source, db_session)

    messages = [r.getMessage() for r in caplog.records
                if r.name == "app.pipeline.collector"]

    fallback_lines = [m for m in messages if "feed summary" in m]
    assert len(fallback_lines) == 1, messages
    line = fallback_lines[0]
    assert f"Source {doj_source.id} 'DOJ Press Releases'" in line
    assert "ChallengeDetected" in line
    assert _safe_url(USAO_URL) in line

    # Items with no usable summary are recorded as such, not silently dropped.
    no_content = [m for m in messages if "no content" in m]
    assert len(no_content) == 2, messages

    # Nothing logged carries article text or feed prose.
    assert not any("Gretna man was indicted" in m for m in messages)


def test_collector_holds_no_doj_specific_logic():
    import inspect

    src = inspect.getsource(collector)
    for token in ("doj", "justice.gov", "usao", "opa/pr"):
        assert token not in src.lower()


@pytest.mark.asyncio
async def test_no_ai_processing_is_invoked(monkeypatch, db_session, doj_source):
    from app.pipeline import ai_processor

    called: list[str] = []
    monkeypatch.setattr(ai_processor, "analyze_article",
                        lambda *a, **k: called.append("ai"), raising=False)
    _routes(monkeypatch, FULL_ROUTES)
    _no_browser(monkeypatch)

    await collector.run_source(doj_source, db_session)
    assert called == []


@pytest.mark.asyncio
async def test_items_remain_attributed_to_doj(monkeypatch, db_session, doj_source):
    _routes(monkeypatch, FULL_ROUTES)
    _no_browser(monkeypatch)

    await collector.run_source(doj_source, db_session)
    rows = await db_session.execute(select(RawItem).where(RawItem.source_id == doj_source.id))
    items = rows.scalars().all()
    assert items
    assert all(item.source_id == doj_source.id for item in items)
    assert all("justice.gov" in item.item_url for item in items)


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------


def test_registry_shape_is_unchanged():
    """DOJ changed adapter behaviour, not the adapter surface."""
    assert set(ADAPTER_REGISTRY) == {
        "sec_press.SECPressAdapter",
        "ftc_feeds.FTCFeedsAdapter",
        "fincen_press.FinCENPressAdapter",
        "ic3_alerts.IC3AlertsAdapter",
        "fbi_national.FBINationalAdapter",
        "fbi_blog.FBIBlogAdapter",
        "fbi_news.FBINewsAdapter",
        "doj_press.DOJPressAdapter",
        "krebs.KrebsAdapter",
        "bleeping.BleepingAdapter",
    }


def test_other_adapters_keep_reading_the_configured_feed_column():
    """Only DOJ overrides rss_url; every other RSS adapter uses source.rss_url."""
    class _S:
        name = "S"
        rss_url = "https://example.test/feed.xml"

    others = [cls for cls in ADAPTER_REGISTRY.values()
              if issubclass(cls, RSSAdapter) and cls is not DOJPressAdapter]
    assert others
    for cls in others:
        assert cls(_S()).rss_url == "https://example.test/feed.xml", cls.__name__


@pytest.mark.asyncio
async def test_generic_rss_parsing_is_unchanged_for_other_sources(monkeypatch):
    """A non-DOJ RSS source parses the same feed identically."""
    from app.sources.bleeping import BleepingAdapter

    class _S:
        id = 10
        name = "BleepingComputer"
        rss_url = "https://example.test/feed.xml"

    _routes(monkeypatch, {"https://example.test/feed.xml": FEED_RESPONSE})
    stubs = await BleepingAdapter(_S()).fetch_item_stubs()

    assert [s.item_url for s in stubs] == [
        OPA_URL, USAO_URL, USAO_URL_2, USAO_URL_3, OPA_URL_2
    ]
    assert stubs[0].source_name == "BleepingComputer"


def test_no_api_surface_was_touched():
    """This slice is collection-only — no route or schema change."""
    from app.main import app

    schema = app.openapi()
    assert "doj" not in str(schema).lower()
    assert not [p for p in schema["paths"] if "summary-fallback" in p]
