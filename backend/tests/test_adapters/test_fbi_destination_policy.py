"""FBI canonical-source policy: FBI-hosted article content only.

Ken's approved decision — DOJ is canonical for justice.gov content, and FBI
sources exclude any item whose final destination is DOJ or another external site.

All responses come from sanitized fixtures through an injected transport. No
network, no production collector entry points, no AI.
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
    BaseSourceAdapter,
    RawItemStub,
    host_in_domains,
    summary_fallback_allowed,
)
from app.sources.fbi_blog import FBIBlogAdapter
from app.sources.fbi_national import FBINationalAdapter
from app.sources.fbi_news import FBINewsAdapter
from app.sources.fbi_policy import FBI_DOMAINS, FBIHostedContentMixin
from app.sources.host_limiter import HostRateLimiter
from app.sources.http_errors import DestinationExcluded, SourceFetchError
from app.sources.registry import ADAPTER_REGISTRY
from app.sources.response_policy import AcceptPolicy
from tests.test_adapters.fbi_fixtures import (
    DECEPTIVE_DASH_URL,
    DECEPTIVE_PREFIX_URL,
    DECEPTIVE_SUFFIX_URL,
    DOJ_ARTICLE,
    DOJ_OPA_TARGET,
    DOJ_TARGET,
    DOJ_USAO_TARGET,
    EXTERNAL_FEED_LINK,
    FBI_ARTICLE,
    FBI_ARTICLE_2,
    FBI_ARTICLE_MOVED,
    FBI_ARTICLE_SUBDOMAIN,
    FBI_BLOG_EMPTY_FEED,
    FBI_BLOG_FEED,
    FBI_BLOG_FUTURE_EXTERNAL_FEED,
    FBI_BLOG_FUTURE_FEED,
    FBI_DIRECT_URL,
    FBI_DIRECT_URL_2,
    FBI_MULTIHOP_MIDDLE,
    FBI_MULTIHOP_URL,
    FBI_NATIONAL_FEED,
    FBI_NATIONAL_FEED_BODY,
    FBI_NEWS_FEED,
    FBI_NEWS_FEED_BODY,
    FBI_REDIRECT_FEED_BODY,
    FBI_SAME_HOST_REDIRECT,
    FBI_SAME_HOST_TARGET,
    FBI_SECRET_QUERY_URL,
    FBI_SUBDOMAIN_REDIRECT,
    FBI_SUBDOMAIN_TARGET,
    FBI_TO_DECEPTIVE_URL,
    FBI_TO_DOJ_OPA_URL,
    FBI_TO_DOJ_URL,
    FBI_TO_DOJ_USAO_URL,
    FBI_TO_IC3_URL,
    FBI_TO_TREASURY_URL,
    IC3_TARGET,
    TREASURY_TARGET,
    WEAK_FBI_SUMMARY,
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


class _Recorder:
    """Everything the boundary reached for, at every level."""

    def __init__(self):
        self.requested: list[str] = []      # httpx tier
        self.limited: list[str] = []        # host limiter acquisitions
        self.fingerprints: list[str] = []   # requests tier (tier 2a/2b)
        self.browser: list[str] = []        # Playwright tier


def _routes(monkeypatch, mapping, *, default=("", "text/html", 404)):
    """Serve fixtures by URL, following the mapping's redirect entries.

    A mapping value of ``("redirect", location)`` produces a 302 to ``location``.
    """
    rec = _Recorder()

    def handler(request):
        url = str(request.url)
        rec.requested.append(url)
        entry = mapping.get(url, default)
        if entry[0] == "redirect":
            return httpx.Response(302, headers={"location": entry[1]})
        body, ctype, status = entry
        return httpx.Response(status, headers={"content-type": ctype}, text=body)

    transport = httpx.MockTransport(handler)

    def _factory(**kw):
        kw.pop("transport", None)
        return _REAL_ASYNC_CLIENT(**kw, transport=transport)

    clock = _Clock()
    limiter = HostRateLimiter(monotonic=clock.monotonic, sleep=clock.sleep)
    real_acquire = limiter.acquire

    async def _acquire(host):
        rec.limited.append(host)
        return await real_acquire(host)

    limiter.acquire = _acquire

    def _sync_get(url, headers, timeout):
        rec.fingerprints.append(url)
        raise AssertionError(f"tier 2 must not run for {url}")

    async def _browser(url, *a, **k):
        rec.browser.append(url)
        raise AssertionError(f"browser must not run for {url}")

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    monkeypatch.setattr(source_base, "host_limiter", limiter)
    monkeypatch.setattr(source_base, "_sync_requests_get", _sync_get)
    monkeypatch.setattr(source_base, "_playwright_get", _browser)
    return rec


class _Src:
    id = 0
    name = ""
    base_url = ""
    rss_url = None


def _adapter(cls, source_id, name, rss_url):
    src = _Src()
    src.id, src.name, src.rss_url = source_id, name, rss_url
    src.base_url = "https://www.fbi.gov/news"
    return cls(src)


def _national(rss_url=FBI_NATIONAL_FEED):
    return _adapter(FBINationalAdapter, 5, "FBI National Press Releases", rss_url)


def _news(rss_url=FBI_NEWS_FEED):
    return _adapter(FBINewsAdapter, 7, "FBI in the News RSS", rss_url)


def _blog(rss_url=FBI_BLOG_FEED):
    return _adapter(FBIBlogAdapter, 6, "FBI News Blog RSS", rss_url)


FBI_ADAPTERS = (FBINationalAdapter, FBIBlogAdapter, FBINewsAdapter)


def _stub(url, title="T", summary=WEAK_FBI_SUMMARY):
    return RawItemStub(source_name="FBI", item_url=url, title=title,
                       published_at=None, summary=summary)


# ===========================================================================
# Generic destination policy
# ===========================================================================


def test_adapters_are_unrestricted_by_default():
    assert BaseSourceAdapter.allowed_article_domains is None

    restricted = {
        name for name, cls in ADAPTER_REGISTRY.items()
        if cls.allowed_article_domains is not None
    }
    assert restricted == {
        "fbi_national.FBINationalAdapter",
        "fbi_blog.FBIBlogAdapter",
        "fbi_news.FBINewsAdapter",
    }


@pytest.mark.parametrize("host", [
    "fbi.gov", "www.fbi.gov", "newsroom.fbi.gov", "a.b.fbi.gov",
    "FBI.GOV", "WWW.FBI.GOV", "fbi.gov.", "www.fbi.gov.",
])
def test_fbi_hosts_are_accepted(host):
    assert host_in_domains(host, FBI_DOMAINS) is True


@pytest.mark.parametrize("host", [
    "evilfbi.gov", "fbi.gov.example.com", "fbi-gov.example", "notfbi.gov",
    "justice.gov", "ic3.gov", "home.treasury.gov", "fbi.gov.evil.com",
    "xfbi.gov", "", "   ", "gov",
])
def test_non_fbi_hosts_are_rejected(host):
    assert host_in_domains(host, FBI_DOMAINS) is False


@pytest.mark.parametrize("url,allowed", [
    ("https://www.fbi.gov:443/news/x", True),
    ("https://www.fbi.gov:8443/news/x", True),
    ("https://evilfbi.gov:443/news/x", False),
])
def test_ports_do_not_change_the_domain_decision(url, allowed):
    from app.sources.base import assert_allowed_destination

    if allowed:
        assert_allowed_destination(url, FBI_DOMAINS, hop="target")
    else:
        with pytest.raises(DestinationExcluded):
            assert_allowed_destination(url, FBI_DOMAINS, hop="target")


def test_none_means_unrestricted():
    from app.sources.base import assert_allowed_destination

    # Would be rejected under a policy; None must let everything through.
    assert_allowed_destination(DOJ_TARGET, None, hop="target")


def test_destination_excluded_is_never_summary_eligible():
    assert summary_fallback_allowed(DestinationExcluded("x", destination="justice.gov")) is False


def test_destination_excluded_is_a_source_fetch_error_not_unsafe_target():
    from app.sources.http_errors import UnsafeRequestTarget

    exc = DestinationExcluded("x", destination="justice.gov")
    assert isinstance(exc, SourceFetchError)
    assert not isinstance(exc, UnsafeRequestTarget)


def test_destination_excluded_carries_no_secrets():
    exc = DestinationExcluded(
        "refusing redirect", url=FBI_SECRET_QUERY_URL, destination="Justice.GOV.",
    )
    assert "SUPERSECRET123" not in str(exc)
    assert "SUPERSECRET123" not in exc.url
    assert "?" not in exc.url
    assert exc.destination == "justice.gov"


# ===========================================================================
# Redirect enforcement
# ===========================================================================


async def _fetch_article(adapter, url, rec_routes):
    return await adapter.fetch_full_article(url)


@pytest.mark.parametrize("start,target,host", [
    (FBI_TO_DOJ_URL, DOJ_TARGET, "www.justice.gov"),
    (FBI_TO_DOJ_OPA_URL, DOJ_OPA_TARGET, "www.justice.gov"),
    (FBI_TO_DOJ_USAO_URL, DOJ_USAO_TARGET, "www.justice.gov"),
    (FBI_TO_IC3_URL, IC3_TARGET, "www.ic3.gov"),
    (FBI_TO_TREASURY_URL, TREASURY_TARGET, "home.treasury.gov"),
    (FBI_TO_DECEPTIVE_URL, DECEPTIVE_SUFFIX_URL, "fbi.gov.example.com"),
    (FBI_TO_DECEPTIVE_URL, DECEPTIVE_PREFIX_URL, "evilfbi.gov"),
    (FBI_TO_DECEPTIVE_URL, DECEPTIVE_DASH_URL, "fbi-gov.example"),
])
@pytest.mark.asyncio
async def test_redirect_off_fbi_is_refused_before_the_request(
    monkeypatch, start, target, host
):
    rec = _routes(monkeypatch, {
        start: ("redirect", target),
        target: (DOJ_ARTICLE, "text/html", 200),
    })

    with pytest.raises(DestinationExcluded) as excinfo:
        await _national().fetch_full_article(start)

    assert excinfo.value.destination == host
    # The destination was never contacted, at any level.
    assert target not in rec.requested
    assert host not in rec.limited
    assert rec.fingerprints == []
    assert rec.browser == []


@pytest.mark.asyncio
async def test_the_justice_gov_request_is_never_sent(monkeypatch):
    """The single most important assertion in this slice."""
    rec = _routes(monkeypatch, {
        FBI_TO_DOJ_URL: ("redirect", DOJ_TARGET),
        DOJ_TARGET: (DOJ_ARTICLE, "text/html", 200),
    })

    with pytest.raises(DestinationExcluded):
        await _national().fetch_full_article(FBI_TO_DOJ_URL)

    assert rec.requested == [FBI_TO_DOJ_URL]
    assert not any("justice.gov" in url for url in rec.requested)
    assert not any("justice.gov" in host for host in rec.limited)


@pytest.mark.asyncio
async def test_same_host_redirect_succeeds(monkeypatch):
    _routes(monkeypatch, {
        FBI_SAME_HOST_REDIRECT: ("redirect", FBI_SAME_HOST_TARGET),
        FBI_SAME_HOST_TARGET: (FBI_ARTICLE_MOVED, "text/html", 200),
    })
    text, html = await _national().fetch_full_article(FBI_SAME_HOST_REDIRECT)

    assert "canonical trailing-slash" in text
    assert html


@pytest.mark.asyncio
async def test_redirect_to_an_fbi_subdomain_succeeds(monkeypatch):
    rec = _routes(monkeypatch, {
        FBI_SUBDOMAIN_REDIRECT: ("redirect", FBI_SUBDOMAIN_TARGET),
        FBI_SUBDOMAIN_TARGET: (FBI_ARTICLE_SUBDOMAIN, "text/html", 200),
    })
    text, _ = await _national().fetch_full_article(FBI_SUBDOMAIN_REDIRECT)

    assert "newsroom service" in text
    assert "newsroom.fbi.gov" in rec.limited


@pytest.mark.asyncio
async def test_multi_hop_chain_stops_at_the_first_external_destination(monkeypatch):
    rec = _routes(monkeypatch, {
        FBI_MULTIHOP_URL: ("redirect", FBI_MULTIHOP_MIDDLE),
        FBI_MULTIHOP_MIDDLE: ("redirect", DOJ_TARGET),
        DOJ_TARGET: (DOJ_ARTICLE, "text/html", 200),
    })

    with pytest.raises(DestinationExcluded) as excinfo:
        await _national().fetch_full_article(FBI_MULTIHOP_URL)

    assert excinfo.value.destination == "www.justice.gov"
    assert rec.requested == [FBI_MULTIHOP_URL, FBI_MULTIHOP_MIDDLE]
    assert DOJ_TARGET not in rec.requested


@pytest.mark.asyncio
async def test_a_direct_external_feed_link_is_refused_before_any_request(monkeypatch):
    """No redirect involved — the target itself is off-domain."""
    rec = _routes(monkeypatch, {EXTERNAL_FEED_LINK: ("x" * 800, "text/html", 200)})

    with pytest.raises(DestinationExcluded) as excinfo:
        await _news().fetch_full_article(EXTERNAL_FEED_LINK)

    assert excinfo.value.destination == "www.reuters.com"
    assert rec.requested == []
    assert rec.limited == []


@pytest.mark.asyncio
async def test_excluded_destination_does_not_escalate_a_tier(monkeypatch):
    """Not another fingerprint, not a browser — the answer is already final."""
    rec = _routes(monkeypatch, {
        FBI_TO_DOJ_URL: ("redirect", DOJ_TARGET),
        DOJ_TARGET: (DOJ_ARTICLE, "text/html", 200),
    })

    with pytest.raises(DestinationExcluded):
        await _national().fetch(
            FBI_TO_DOJ_URL, accept=AcceptPolicy.ARTICLE, allow_browser=True,
            allowed_domains=FBI_DOMAINS,
        )

    assert rec.fingerprints == []
    assert rec.browser == []


@pytest.mark.asyncio
async def test_excluded_destination_is_not_retried(monkeypatch):
    rec = _routes(monkeypatch, {
        FBI_TO_DOJ_URL: ("redirect", DOJ_TARGET),
        DOJ_TARGET: (DOJ_ARTICLE, "text/html", 200),
    })

    with pytest.raises(DestinationExcluded):
        await _national().fetch_full_article(FBI_TO_DOJ_URL)

    assert rec.requested.count(FBI_TO_DOJ_URL) == 1


@pytest.mark.asyncio
async def test_unrestricted_adapters_still_follow_cross_host_redirects(monkeypatch):
    """DOJ and every other source keep their existing behaviour."""
    from app.sources.doj_press import DOJPressAdapter

    src = _Src()
    src.id, src.name, src.rss_url = 8, "DOJ Press Releases", None
    adapter = DOJPressAdapter(src)

    start = "https://www.justice.gov/opa/pr/redirecting-release"
    target = "https://www.justice.gov/opa/pr/final-release"
    rec = _routes(monkeypatch, {
        start: ("redirect", target),
        target: (FBI_ARTICLE, "text/html", 200),
    })
    text, _ = await adapter.fetch_full_article(start)

    assert "sixty months" in text
    assert rec.requested == [start, target]


@pytest.mark.asyncio
async def test_feed_discovery_is_not_destination_restricted(monkeypatch):
    """The policy governs article requests only; the feed is read normally."""
    _routes(monkeypatch, {
        FBI_NATIONAL_FEED: (FBI_NATIONAL_FEED_BODY, "application/rss+xml", 200)
    })
    stubs = await _national().fetch_item_stubs()

    # The external link is still discovered — it is refused at article fetch.
    assert EXTERNAL_FEED_LINK in [s.item_url for s in stubs]
    assert len(stubs) == 5


@pytest.mark.asyncio
async def test_feed_on_a_non_fbi_host_still_works(monkeypatch):
    """A relocated feed is discovery, not article content, so it is allowed."""
    mirror = "https://feeds.example.test/fbi-national.xml"
    _routes(monkeypatch, {mirror: (FBI_NATIONAL_FEED_BODY, "application/rss+xml", 200)})

    assert len(await _national(rss_url=mirror).fetch_item_stubs()) == 5


# ===========================================================================
# FBI summary policy
# ===========================================================================


@pytest.mark.parametrize("cls", FBI_ADAPTERS)
def test_fbi_adapters_never_use_a_feed_summary(cls):
    adapter = cls(_Src())
    for error in (
        DestinationExcluded("x", destination="justice.gov"),
        SourceFetchError("boom"),
        None,
    ):
        assert adapter.summary_fallback(_stub(FBI_DIRECT_URL), error) is None


@pytest.mark.parametrize("cls", FBI_ADAPTERS)
def test_fbi_adapters_carry_the_shared_policy(cls):
    assert issubclass(cls, FBIHostedContentMixin)
    assert cls.allowed_article_domains == ("fbi.gov",)
    assert cls.summary_fallback is FBIHostedContentMixin.summary_fallback


@pytest.mark.parametrize("cls", FBI_ADAPTERS)
def test_fbi_adapters_still_require_article_detail(cls):
    assert cls.should_fetch_article(cls(_Src()), _stub(FBI_DIRECT_URL)) is True


@pytest.mark.parametrize("cls", FBI_ADAPTERS)
def test_fbi_adapters_never_enable_the_browser(cls):
    import inspect

    import app.sources.fbi_policy as policy

    module = inspect.getmodule(cls)
    assert "allow_browser" not in inspect.getsource(module)
    assert "allow_browser" not in inspect.getsource(policy)


def test_no_fbi_specific_text_threshold_exists():
    import inspect

    import app.sources.fbi_policy as policy

    src = inspect.getsource(policy)
    for token in ("MIN_SUMMARY", "is_usable_summary", "len("):
        assert token not in src, token


# ===========================================================================
# Collector integration
# ===========================================================================


@pytest.fixture
async def stored_source(db_session):
    created: list[Source] = []

    async def _make(name, adapter_class, rss_url, source_id=None):
        src = Source(
            name=name, base_url="https://www.fbi.gov/news", source_type="rss",
            adapter_class=adapter_class, rss_url=rss_url, is_active=True,
        )
        db_session.add(src)
        await db_session.commit()
        await db_session.refresh(src)
        created.append(src)
        return src

    yield _make

    for src in created:
        await db_session.execute(delete(RawItem).where(RawItem.source_id == src.id))
        await db_session.execute(delete(RunLog).where(RunLog.source_id == src.id))
        await db_session.execute(delete(Source).where(Source.id == src.id))
    await db_session.commit()


async def _rows(db_session, source):
    result = await db_session.execute(
        select(RawItem.item_url, RawItem.raw_text).where(RawItem.source_id == source.id)
    )
    return dict(result.all())


def _national_routes():
    return {
        FBI_NATIONAL_FEED: (FBI_NATIONAL_FEED_BODY, "application/rss+xml", 200),
        FBI_DIRECT_URL: (FBI_ARTICLE, "text/html", 200),
        FBI_TO_DOJ_URL: ("redirect", DOJ_TARGET),
        FBI_TO_DOJ_OPA_URL: ("redirect", DOJ_OPA_TARGET),
        FBI_TO_DOJ_USAO_URL: ("redirect", DOJ_USAO_TARGET),
        DOJ_TARGET: (DOJ_ARTICLE, "text/html", 200),
        DOJ_OPA_TARGET: (DOJ_ARTICLE, "text/html", 200),
        DOJ_USAO_TARGET: (DOJ_ARTICLE, "text/html", 200),
        EXTERNAL_FEED_LINK: (DOJ_ARTICLE, "text/html", 200),
    }


@pytest.mark.asyncio
async def test_exclusions_do_not_fail_the_run_and_valid_items_survive(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("FBI National Press Releases",
                                 "fbi_national.FBINationalAdapter", FBI_NATIONAL_FEED)
    rec = _routes(monkeypatch, _national_routes())

    run = await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    assert run.status == "success"
    assert run.items_fetched == 5
    assert run.items_new == 1
    assert run.items_skipped_invalid == 4
    assert run.items_fetched == (
        run.items_new + run.items_skipped_url + run.items_skipped_content
        + run.items_skipped_invalid
    )

    # Only the FBI-hosted article is stored, and DOJ content never arrived.
    assert set(stored) == {FBI_DIRECT_URL}
    assert "sixty months" in stored[FBI_DIRECT_URL]
    assert not any("MUST NOT BE COLLECTED" in text for text in stored.values())
    assert not any("justice.gov" in url for url in rec.requested)
    assert rec.browser == []


@pytest.mark.asyncio
async def test_exclusion_stores_no_item_and_computes_no_content_hash(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("FBI National Press Releases",
                                 "fbi_national.FBINationalAdapter", FBI_NATIONAL_FEED)
    hashed: list[str] = []
    real_hash = collector.compute_content_hash
    monkeypatch.setattr(
        collector, "compute_content_hash",
        lambda text: hashed.append(text) or real_hash(text),
    )
    _routes(monkeypatch, _national_routes())

    await collector.run_source(source, db_session)

    # One hash, for the one stored article — none for the four excluded items.
    assert len(hashed) == 1
    assert "sixty months" in hashed[0]


@pytest.mark.asyncio
async def test_exclusion_never_calls_summary_fallback(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("FBI National Press Releases",
                                 "fbi_national.FBINationalAdapter", FBI_NATIONAL_FEED)
    calls: list[object] = []

    def _record(self, stub, error):
        calls.append(error)
        return None

    monkeypatch.setattr(FBIHostedContentMixin, "summary_fallback", _record)
    _routes(monkeypatch, _national_routes())

    await collector.run_source(source, db_session)
    assert calls == []


@pytest.mark.asyncio
async def test_later_valid_items_still_process_after_an_exclusion(
    monkeypatch, db_session, stored_source
):
    """The excluded items come first in the feed; the last one must still land."""
    from tests.test_adapters.fbi_fixtures import feed

    body = feed(
        '<item><title>DOJ One</title>'
        f"<link>{FBI_TO_DOJ_URL}</link></item>",
        '<item><title>DOJ Two</title>'
        f"<link>{FBI_TO_DOJ_OPA_URL}</link></item>",
        '<item><title>Real FBI Release</title>'
        f"<link>{FBI_DIRECT_URL_2}</link></item>",
    )
    source = await stored_source("FBI National Press Releases",
                                 "fbi_national.FBINationalAdapter", FBI_NATIONAL_FEED)
    _routes(monkeypatch, {
        FBI_NATIONAL_FEED: (body, "application/rss+xml", 200),
        FBI_TO_DOJ_URL: ("redirect", DOJ_TARGET),
        FBI_TO_DOJ_OPA_URL: ("redirect", DOJ_OPA_TARGET),
        DOJ_TARGET: (DOJ_ARTICLE, "text/html", 200),
        DOJ_OPA_TARGET: (DOJ_ARTICLE, "text/html", 200),
        FBI_DIRECT_URL_2: (FBI_ARTICLE_2, "text/html", 200),
    })

    run = await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    assert run.status == "success"
    assert set(stored) == {FBI_DIRECT_URL_2}
    assert run.items_skipped_invalid == 2


@pytest.mark.asyncio
async def test_exclusion_logging_is_structured_and_leaks_nothing(
    monkeypatch, db_session, stored_source, caplog
):
    from tests.test_adapters.fbi_fixtures import feed

    body = feed(
        "<item><title>Tracked Release</title>"
        f"<link>{FBI_SECRET_QUERY_URL}</link></item>"
    )
    source = await stored_source("FBI National Press Releases",
                                 "fbi_national.FBINationalAdapter", FBI_NATIONAL_FEED)
    _routes(monkeypatch, {
        FBI_NATIONAL_FEED: (body, "application/rss+xml", 200),
        FBI_SECRET_QUERY_URL: ("redirect", DOJ_TARGET),
        DOJ_TARGET: (DOJ_ARTICLE, "text/html", 200),
    })

    with caplog.at_level("DEBUG"):
        run = await collector.run_source(source, db_session)

    messages = [r.getMessage() for r in caplog.records]
    excluded = [
        r.getMessage() for r in caplog.records
        if r.name == "app.pipeline.collector"
        and "outside this source's domains" in r.getMessage()
    ]
    assert len(excluded) == 1, messages
    line = excluded[0]
    assert f"Source {source.id} 'FBI National Press Releases'" in line
    assert "www.justice.gov" in line
    assert "fbi.gov/news/press-releases/tracked-release" in line

    # No application log record carries the query token. (httpx's own request
    # logger echoes the URL it was given; that is third-party and outside this
    # boundary — every line we emit goes through _safe_url.)
    ours = [r.getMessage() for r in caplog.records if r.name.startswith("app.")]
    assert ours
    assert not any("SUPERSECRET123" in m for m in ours), ours
    assert run.items_skipped_invalid == 1


@pytest.mark.asyncio
async def test_exclusion_exception_carries_no_query_token(monkeypatch):
    _routes(monkeypatch, {
        FBI_SECRET_QUERY_URL: ("redirect", DOJ_TARGET),
        DOJ_TARGET: (DOJ_ARTICLE, "text/html", 200),
    })

    with pytest.raises(DestinationExcluded) as excinfo:
        await _national().fetch_full_article(FBI_SECRET_QUERY_URL)

    exc = excinfo.value
    assert "SUPERSECRET123" not in str(exc)
    assert "SUPERSECRET123" not in exc.url
    assert "SUPERSECRET123" not in repr(exc)
    assert exc.destination == "www.justice.gov"


@pytest.mark.asyncio
async def test_no_ai_processing_is_invoked(monkeypatch, db_session, stored_source):
    from app.pipeline import ai_processor

    called: list[str] = []
    monkeypatch.setattr(ai_processor, "analyze_article",
                        lambda *a, **k: called.append("ai"), raising=False)
    source = await stored_source("FBI National Press Releases",
                                 "fbi_national.FBINationalAdapter", FBI_NATIONAL_FEED)
    _routes(monkeypatch, _national_routes())

    await collector.run_source(source, db_session)
    assert called == []


@pytest.mark.asyncio
async def test_article_failure_does_not_fall_back_to_the_feed_summary(
    monkeypatch, db_session, stored_source
):
    """A 403 on an FBI-hosted article leaves the item unstored and retriable."""
    from tests.test_adapters.fbi_fixtures import feed

    body = feed(f"<item><title>Blocked</title><link>{FBI_DIRECT_URL}</link>"
                f"<description>{WEAK_FBI_SUMMARY}</description></item>")
    source = await stored_source("FBI in the News RSS",
                                 "fbi_news.FBINewsAdapter", FBI_NEWS_FEED)
    _routes(monkeypatch, {
        FBI_NEWS_FEED: (body, "application/rss+xml", 200),
        FBI_DIRECT_URL: ("denied", "text/html", 403),
    })

    run = await collector.run_source(source, db_session)

    assert run.status == "success"
    assert run.items_new == 0
    assert run.items_skipped_invalid == 1
    assert await _rows(db_session, source) == {}


@pytest.mark.asyncio
async def test_fbi_in_the_news_keeps_only_its_fbi_hosted_item(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("FBI in the News RSS",
                                 "fbi_news.FBINewsAdapter", FBI_NEWS_FEED)
    rec = _routes(monkeypatch, {
        FBI_NEWS_FEED: (FBI_NEWS_FEED_BODY, "application/rss+xml", 200),
        FBI_DIRECT_URL_2: (FBI_ARTICLE_2, "text/html", 200),
        FBI_TO_DOJ_USAO_URL: ("redirect", DOJ_USAO_TARGET),
        FBI_TO_IC3_URL: ("redirect", IC3_TARGET),
        DOJ_USAO_TARGET: (DOJ_ARTICLE, "text/html", 200),
        IC3_TARGET: ("%PDF-1.4 fake", "application/pdf", 200),
        EXTERNAL_FEED_LINK: (DOJ_ARTICLE, "text/html", 200),
    })

    run = await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    assert set(stored) == {FBI_DIRECT_URL_2}
    assert run.items_skipped_invalid == 3
    assert not any("ic3.gov" in url for url in rec.requested)
    assert not any("justice.gov" in url for url in rec.requested)


# ===========================================================================
# FBI News Blog
# ===========================================================================


@pytest.mark.asyncio
async def test_blog_valid_empty_feed_returns_zero_stubs(monkeypatch):
    _routes(monkeypatch, {FBI_BLOG_FEED: (FBI_BLOG_EMPTY_FEED, "application/rss+xml", 200)})
    assert await _blog().fetch_item_stubs() == []


@pytest.mark.asyncio
async def test_blog_empty_feed_is_a_successful_run(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("FBI News Blog RSS", "fbi_blog.FBIBlogAdapter",
                                 FBI_BLOG_FEED)
    _routes(monkeypatch, {FBI_BLOG_FEED: (FBI_BLOG_EMPTY_FEED, "application/rss+xml", 200)})

    run = await collector.run_source(source, db_session)

    assert run.status == "success"
    assert run.items_fetched == 0
    assert run.error_message is None


def test_blog_remains_registered_and_enabled_in_code():
    import inspect

    from app.sources import fbi_blog

    assert ADAPTER_REGISTRY["fbi_blog.FBIBlogAdapter"] is FBIBlogAdapter

    # Nothing in the source tree disables or special-cases source id 6.
    for module in (fbi_blog, collector, source_base):
        src = inspect.getsource(module)
        assert "is_active = False" not in src
        assert "is_active=False" not in src


@pytest.mark.asyncio
async def test_blog_collects_a_future_fbi_hosted_item(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("FBI News Blog RSS", "fbi_blog.FBIBlogAdapter",
                                 FBI_BLOG_FEED)
    _routes(monkeypatch, {
        FBI_BLOG_FEED: (FBI_BLOG_FUTURE_FEED, "application/rss+xml", 200),
        FBI_DIRECT_URL: (FBI_ARTICLE, "text/html", 200),
    })

    run = await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    assert run.items_new == 1
    assert "sixty months" in stored[FBI_DIRECT_URL]


@pytest.mark.asyncio
async def test_blog_excludes_a_future_external_item(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("FBI News Blog RSS", "fbi_blog.FBIBlogAdapter",
                                 FBI_BLOG_FEED)
    rec = _routes(monkeypatch, {
        FBI_BLOG_FEED: (FBI_BLOG_FUTURE_EXTERNAL_FEED, "application/rss+xml", 200),
        FBI_TO_TREASURY_URL: ("redirect", TREASURY_TARGET),
        TREASURY_TARGET: (DOJ_ARTICLE, "text/html", 200),
    })

    run = await collector.run_source(source, db_session)

    assert run.status == "success"
    assert run.items_new == 0
    assert run.items_skipped_invalid == 1
    assert await _rows(db_session, source) == {}
    assert not any("treasury.gov" in url for url in rec.requested)


@pytest.mark.asyncio
async def test_mixed_redirect_feed_keeps_only_fbi_destinations(monkeypatch):
    _routes(monkeypatch, {
        FBI_NATIONAL_FEED: (FBI_REDIRECT_FEED_BODY, "application/rss+xml", 200),
    })
    stubs = await _national().fetch_item_stubs()

    assert [s.item_url for s in stubs] == [
        FBI_SAME_HOST_REDIRECT, FBI_SUBDOMAIN_REDIRECT, FBI_TO_TREASURY_URL
    ]


# ===========================================================================
# Regression
# ===========================================================================


def test_doj_remains_canonical_and_unchanged():
    from app.sources.doj_press import DOJPressAdapter, is_usable_summary

    assert DOJPressAdapter.allowed_article_domains is None
    assert DOJPressAdapter.summary_fallback is not FBIHostedContentMixin.summary_fallback
    assert is_usable_summary(
        "A federal jury convicted a Massachusetts man of conspiring to export "
        "controlled components in violation of federal sanctions. The defendant "
        "faces twenty years at sentencing later this year.",
        "Massachusetts Man Convicted",
    )


def test_other_sources_keep_their_behaviour():
    from app.sources.bleeping import BleepingAdapter
    from app.sources.fincen_press import FinCENPressAdapter
    from app.sources.ftc_feeds import FTCFeedsAdapter
    from app.sources.ic3_alerts import IC3AlertsAdapter
    from app.sources.krebs import KrebsAdapter
    from app.sources.rss_adapter import RSSAdapter
    from app.sources.sec_press import SECPressAdapter

    for cls in (SECPressAdapter, FTCFeedsAdapter, FinCENPressAdapter,
                IC3AlertsAdapter, KrebsAdapter, BleepingAdapter):
        assert cls.allowed_article_domains is None, cls.__name__

    assert SECPressAdapter.should_fetch_article(SECPressAdapter(_Src()), _stub("x")) is False
    assert issubclass(KrebsAdapter, RSSAdapter)


def test_registry_shape_is_unchanged():
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


def test_no_source_identifiers_in_shared_http_or_collector():
    """No host, source name or id is baked into the shared layers.

    Docstrings and comments *do* name fbi.gov and justice.gov — that is where the
    policy is explained. What must not exist is executable code that behaves
    differently for them, so this inspects string literals and comparisons, not
    prose.
    """
    import ast
    import inspect

    for module in (source_base, collector):
        tree = ast.parse(inspect.getsource(module))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        literals = [
            node.value.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docstrings
        ]
        for token in ("fbi", "justice.gov", "ic3", "treasury"):
            offenders = [text for text in literals if token in text]
            assert offenders == [], f"{module.__name__}: {token} in {offenders}"

        # No branch keys off a specific source row.
        source_refs = [
            ast.dump(node) for node in ast.walk(tree)
            if isinstance(node, ast.Compare)
            and any(
                isinstance(n, ast.Attribute) and n.attr in ("id", "name")
                and isinstance(n.value, ast.Name) and n.value.id == "source"
                for n in ast.walk(node)
            )
        ]
        assert source_refs == [], f"{module.__name__} branches on the source row"


def test_no_api_surface_was_touched():
    from app.main import app

    schema = str(app.openapi()).lower()
    for token in ("fbi", "destinationexcluded", "allowed_article_domains"):
        assert token not in schema, token


def test_feed_urls_and_registry_keys_are_unchanged():
    assert _national().rss_url == FBI_NATIONAL_FEED
    assert _news().rss_url == FBI_NEWS_FEED
    assert _blog().rss_url == FBI_BLOG_FEED

    blank = _Src()
    assert FBINationalAdapter(blank).rss_url == FBI_NATIONAL_FEED
    assert FBINewsAdapter(blank).rss_url == FBI_NEWS_FEED
    assert FBIBlogAdapter(blank).rss_url == FBI_BLOG_FEED


def test_run_log_has_no_new_column():
    """The exclusion count rides in items_skipped_invalid; no migration 0013."""
    columns = {c.name for c in RunLog.__table__.columns}
    assert "external_destination_excluded" not in columns
    assert "items_skipped_invalid" in columns


@pytest.mark.asyncio
async def test_dates_and_titles_survive_the_policy(monkeypatch):
    _routes(monkeypatch, {
        FBI_NATIONAL_FEED: (FBI_NATIONAL_FEED_BODY, "application/rss+xml", 200)
    })
    stubs = await _national().fetch_item_stubs()

    assert stubs[0].title == "Man Sentenced for Wire Fraud"
    assert stubs[0].published_at == datetime(2026, 7, 21, 17, 0)
    assert all(s.title and s.published_at for s in stubs)
