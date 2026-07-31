"""FTC listing repair, SEC summary-only policy, and Krebs RSS alignment.

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
from app.sources.base import RawItemStub
from app.sources.ftc_feeds import FTCFeedsAdapter
from app.sources.host_limiter import HostRateLimiter
from app.sources.http_errors import (
    ChallengeDetected,
    ContentTypeMismatch,
    PermanentFetchError,
    RateLimitedError,
    RedirectLoop,
    TooManyRedirects,
    TransientFetchError,
    UnsafeRequestTarget,
)
from app.sources.krebs import OFFICIAL_FEED_URL as KREBS_OFFICIAL_FEED
from app.sources.krebs import KrebsAdapter
from app.sources.registry import ADAPTER_REGISTRY
from app.sources.response_policy import AcceptPolicy
from app.sources.rss_adapter import RSSAdapter
from app.sources.sec_press import (
    MIN_SUMMARY_CHARS,
    MIN_SUMMARY_WORDS,
)
from app.sources.sec_press import OFFICIAL_FEED_URL as SEC_OFFICIAL_FEED
from app.sources.sec_press import SECPressAdapter, is_usable_summary
from tests.test_adapters.fixtures import DOJ_INTERSTITIAL as CHALLENGE_INTERSTITIAL
from tests.test_adapters.ftc_sec_krebs_fixtures import (
    FTC_ARTICLE_PAGE,
    FTC_EMPTY_LISTING,
    FTC_FULL_LISTING,
    FTC_LISTING_URL,
    FTC_MALFORMED_LISTING,
    KREBS_ARTICLE_PAGE,
    KREBS_EMPTY_FEED,
    KREBS_FEED_URL,
    KREBS_FEED_WITH_MALFORMED,
    KREBS_FULL_FEED,
    KREBS_HTML_LISTING,
    KREBS_POST_1,
    KREBS_POST_2,
    KREBS_SUMMARY_1,
    PR_ABSOLUTE_URL,
    PR_NO_DATE_URL,
    PR_TZ_URL,
    PR_VISIBLE_URL,
    SEC_BOILERPLATE_SUMMARY,
    SEC_EMPTY_FEED,
    SEC_FEED_URL,
    SEC_FULL_FEED,
    SEC_GOOD_SUMMARY,
    SEC_HTML_SUMMARY,
    SEC_LINK_ONLY_SUMMARY,
    SEC_PR_1,
    SEC_PR_2,
    SEC_PR_3,
    SEC_PR_4,
    SEC_PR_5,
    SEC_SHORT_VALID_SUMMARY,
    SEC_TITLE_ECHO_SUMMARY,
    SEC_TITLE_ECHO_TITLE,
    SEC_WEAK_SUMMARY,
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


def _routes(monkeypatch, mapping, *, default=("", "text/html", 404)):
    """Serve fixtures by URL through the httpx tier. Records what was requested."""
    seen: list[str] = []

    def handler(request):
        url = str(request.url)
        seen.append(url)
        body, ctype, status = mapping.get(url, default)
        return httpx.Response(status, headers={"content-type": ctype}, text=body)

    transport = httpx.MockTransport(handler)

    def _factory(**kw):
        kw.pop("transport", None)
        return _REAL_ASYNC_CLIENT(**kw, transport=transport)

    clock = _Clock()
    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    monkeypatch.setattr(
        source_base, "host_limiter",
        HostRateLimiter(monotonic=clock.monotonic, sleep=clock.sleep),
    )
    return seen


def _no_browser(monkeypatch):
    launched: list[str] = []

    async def _browser(*a, **k):
        launched.append("playwright")
        return 200, "", "text/html", ""

    monkeypatch.setattr(source_base, "_playwright_get", _browser)
    return launched


class _Src:
    id = 0
    name = ""
    base_url = ""
    rss_url = None


def _ftc(base_url=FTC_LISTING_URL):
    src = _Src()
    src.id, src.name, src.base_url = 2, "FTC Press Releases", base_url
    return FTCFeedsAdapter(src)


def _sec(rss_url=None):
    src = _Src()
    src.id, src.name = 1, "SEC Press Releases"
    src.base_url, src.rss_url = "https://www.sec.gov/newsroom/press-releases", rss_url
    return SECPressAdapter(src)


def _krebs(rss_url=None):
    src = _Src()
    src.id, src.name = 9, "KrebsOnSecurity"
    src.base_url, src.rss_url = "https://krebsonsecurity.com", rss_url
    return KrebsAdapter(src)


def _stub(url="https://example.test/a", title="T", summary=""):
    return RawItemStub(source_name="S", item_url=url, title=title,
                       published_at=None, summary=summary)


# ===========================================================================
# Source-agnostic detail policy
# ===========================================================================


def test_every_adapter_fetches_details_by_default():
    """Only SEC opts out; the rest keep their existing behaviour."""
    declining = [
        name for name, cls in ADAPTER_REGISTRY.items()
        if not cls.should_fetch_article(cls.__new__(cls), _stub())
    ]
    assert declining == ["sec_press.SECPressAdapter"]


def test_sec_declines_the_detail_fetch():
    assert _sec().should_fetch_article(_stub()) is False


def test_collector_holds_no_source_specific_identifiers():
    import inspect

    src = inspect.getsource(collector).lower()
    for token in ("sec", "ftc", "krebs", "sec.gov", "should_fetch_article(stub) and"):
        if token == "sec":
            # `sec` appears inside unrelated words; check it is never a source ref.
            assert "sec_press" not in src and "sec.gov" not in src
            continue
        assert token not in src, token


def test_default_summary_fallback_accepts_a_none_error():
    from app.sources.bleeping import BleepingAdapter

    adapter = BleepingAdapter(_Src())
    assert adapter.summary_fallback(_stub(summary="Some text."), None) == "Some text."
    assert adapter.summary_fallback(_stub(summary="  "), None) is None


# ===========================================================================
# SEC — summary quality rules
# ===========================================================================


def test_sec_good_summary_is_accepted():
    assert is_usable_summary(SEC_GOOD_SUMMARY, "SEC Charges Investment Adviser")


def test_sec_shorter_factual_summary_is_accepted():
    from app.sources.base import clean_summary_text

    assert len(clean_summary_text(SEC_SHORT_VALID_SUMMARY)) >= MIN_SUMMARY_CHARS
    assert is_usable_summary(SEC_SHORT_VALID_SUMMARY, "SEC Charges Two in Offering Fraud")


@pytest.mark.parametrize("summary", ["", "   \n\t ", None])
def test_sec_empty_summaries_are_rejected(summary):
    assert not is_usable_summary(summary or "", "Some Title")


def test_sec_title_echo_is_rejected():
    assert not is_usable_summary(SEC_TITLE_ECHO_SUMMARY, SEC_TITLE_ECHO_TITLE)


def test_sec_weak_summary_is_rejected():
    assert not is_usable_summary(SEC_WEAK_SUMMARY, "SEC Announces Enforcement Action")


def test_sec_boilerplate_summary_is_rejected():
    assert not is_usable_summary(SEC_BOILERPLATE_SUMMARY, "Some Title")


def test_sec_link_only_summary_is_rejected():
    assert not is_usable_summary(SEC_LINK_ONLY_SUMMARY, "Some Title")


def test_sec_requires_sentence_structure():
    words = " ".join(["enforcement"] * (MIN_SUMMARY_WORDS + 10))
    assert len(words) > MIN_SUMMARY_CHARS
    assert not is_usable_summary(words, "Title")


def test_sec_requires_words_not_just_length():
    padded = "aaaaaaaaaaaaaaaaaaaa " * 10 + "."
    assert len(padded) > MIN_SUMMARY_CHARS
    assert not is_usable_summary(padded, "Title")


def test_sec_summary_cleaning_removes_markup_safely():
    from app.sources.base import clean_summary_text

    cleaned = clean_summary_text(SEC_HTML_SUMMARY)
    assert "<" not in cleaned and "ga(" not in cleaned
    assert "Skip to main content" not in cleaned
    assert cleaned.startswith("The Securities and Exchange Commission")
    assert is_usable_summary(SEC_HTML_SUMMARY, "SEC Obtains Final Judgment")


def test_sec_thresholds_sit_below_the_audited_floor():
    """The audit measured a 212-character minimum across 25 real entries."""
    assert MIN_SUMMARY_CHARS < 212


def test_sec_rules_do_not_leak_into_doj_or_generic_rss():
    from app.sources import doj_press, rss_adapter, sec_press

    assert doj_press.MIN_SUMMARY_CHARS == 120
    assert sec_press.MIN_SUMMARY_CHARS == 140
    assert doj_press.is_usable_summary is not sec_press.is_usable_summary
    assert not hasattr(rss_adapter.RSSAdapter, "is_usable_summary")


# ===========================================================================
# SEC — feed and collection
# ===========================================================================


def test_sec_is_an_rss_adapter():
    assert issubclass(SECPressAdapter, RSSAdapter)
    assert _sec().rss_url == SEC_OFFICIAL_FEED


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_sec_blank_feed_config_uses_the_official_feed(configured):
    assert _sec(configured).rss_url == SEC_OFFICIAL_FEED


def test_sec_configured_feed_wins():
    assert _sec("https://custom.test/sec.xml").rss_url == "https://custom.test/sec.xml"


@pytest.mark.asyncio
async def test_sec_feed_entries_parse_fully(monkeypatch):
    _routes(monkeypatch, {SEC_FEED_URL: (SEC_FULL_FEED, "application/rss+xml", 200)})
    stubs = await _sec().fetch_item_stubs()

    assert [s.item_url for s in stubs] == [
        SEC_PR_1, SEC_PR_2, SEC_PR_3, SEC_PR_4, SEC_PR_5
    ]
    assert stubs[0].title == "SEC Charges Investment Adviser Over Custody Misstatements"
    assert stubs[0].summary == SEC_GOOD_SUMMARY
    # -0400 stored as naive UTC; +0000 unchanged.
    assert stubs[0].published_at == datetime(2026, 7, 22, 18, 0)
    assert stubs[1].published_at == datetime(2026, 7, 21, 9, 30)
    assert all(s.published_at.tzinfo is None for s in stubs)


@pytest.mark.asyncio
async def test_sec_uses_the_feed_policy(monkeypatch):
    captured = {}
    adapter = _sec()

    async def _fetch(url, *, accept=AcceptPolicy.ANY_TEXT, **kw):
        captured["url"], captured["accept"] = url, accept
        return source_base.FetchResult(
            url=url, final_url=url, status=200, content_type="application/rss+xml",
            text=SEC_EMPTY_FEED,
        )

    monkeypatch.setattr(adapter, "fetch", _fetch)
    await adapter.fetch_item_stubs()
    assert captured == {"url": SEC_OFFICIAL_FEED, "accept": AcceptPolicy.FEED}


# ===========================================================================
# FTC — discovery
# ===========================================================================


@pytest.mark.asyncio
async def test_ftc_emits_only_true_press_releases(monkeypatch):
    _routes(monkeypatch, {FTC_LISTING_URL: (FTC_FULL_LISTING, "text/html", 200)})
    stubs = await _ftc().fetch_item_stubs()

    # PR_TZ_URL appears twice: the thumbnail link and the heading link.
    assert [s.item_url for s in stubs] == [
        PR_TZ_URL, PR_TZ_URL, PR_VISIBLE_URL, PR_NO_DATE_URL, PR_ABSOLUTE_URL
    ]
    assert stubs[1].title == "FTC Returns Money to Consumers Harmed by a Tech Support Scam"


@pytest.mark.asyncio
async def test_ftc_excludes_the_listing_page_itself(monkeypatch):
    _routes(monkeypatch, {FTC_LISTING_URL: (FTC_FULL_LISTING, "text/html", 200)})
    urls = [s.item_url for s in await _ftc().fetch_item_stubs()]

    assert FTC_LISTING_URL not in urls
    assert f"{FTC_LISTING_URL}/" not in urls


@pytest.mark.asyncio
async def test_ftc_excludes_topic_navigation_and_pagination(monkeypatch):
    _routes(monkeypatch, {FTC_LISTING_URL: (FTC_FULL_LISTING, "text/html", 200)})
    urls = [s.item_url for s in await _ftc().fetch_item_stubs()]

    for rejected in ("/news-events/topics/", "?page=", "?items_per_page=",
                     "/about-ftc/", "consumer.gov"):
        assert not any(rejected in url for url in urls), rejected


@pytest.mark.asyncio
async def test_ftc_excludes_non_press_release_content(monkeypatch):
    """The exact shapes production actually stored: events, blogs, section pages."""
    _routes(monkeypatch, {FTC_LISTING_URL: (FTC_FULL_LISTING, "text/html", 200)})
    urls = [s.item_url for s in await _ftc().fetch_item_stubs()]

    for rejected in ("/news-events/events/", "/enforcement/competition-matters/",
                     "/microeconomics", "/policy/advocacy-research"):
        assert not any(rejected in url for url in urls), rejected
    assert all("/news-events/news/press-releases/" in url for url in urls)


@pytest.mark.asyncio
async def test_ftc_repeated_anchors_reach_collector_deduplication(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("FTC Press Releases", FTC_LISTING_URL,
                                 "ftc_feeds.FTCFeedsAdapter")
    _routes(monkeypatch, {
        FTC_LISTING_URL: (FTC_FULL_LISTING, "text/html", 200),
        PR_TZ_URL: (FTC_ARTICLE_PAGE, "text/html", 200),
        PR_VISIBLE_URL: (FTC_ARTICLE_PAGE.replace("sending payments", "alleges"), "text/html", 200),
        PR_NO_DATE_URL: (FTC_ARTICLE_PAGE.replace("sending payments", "finalizes"), "text/html", 200),
        PR_ABSOLUTE_URL: (FTC_ARTICLE_PAGE.replace("sending payments", "reports"), "text/html", 200),
    })
    _no_browser(monkeypatch)

    assert len(await _ftc().fetch_item_stubs()) == 5, "adapter does not deduplicate"

    run = await collector.run_source(source, db_session)
    assert run.items_new == 4
    assert run.items_skipped_url == 1


@pytest.mark.asyncio
async def test_ftc_uses_item_local_dates(monkeypatch):
    _routes(monkeypatch, {FTC_LISTING_URL: (FTC_FULL_LISTING, "text/html", 200)})
    dates = {s.item_url: s.published_at for s in await _ftc().fetch_item_stubs()}

    assert dates[PR_TZ_URL] == datetime(2026, 7, 22, 17, 0)      # -04:00 → UTC
    assert dates[PR_VISIBLE_URL] == datetime(2026, 7, 8, 0, 0)   # visible text
    assert dates[PR_NO_DATE_URL] is None                          # kept undated
    assert dates[PR_ABSOLUTE_URL] == datetime(2026, 6, 30, 13, 15)


@pytest.mark.asyncio
async def test_repeated_anchors_to_one_release_keep_that_release_date(monkeypatch):
    """A card links its release twice; both stubs must still carry its date.

    Bounding an item's scope on *every* accepted anchor would stop inside the
    card, between the thumbnail link and the heading link, and lose the date
    sitting beside them.
    """
    _routes(monkeypatch, {FTC_LISTING_URL: (FTC_FULL_LISTING, "text/html", 200)})
    stubs = [s for s in await _ftc().fetch_item_stubs() if s.item_url == PR_TZ_URL]

    assert len(stubs) == 2
    assert {s.published_at for s in stubs} == {datetime(2026, 7, 22, 17, 0)}


@pytest.mark.asyncio
async def test_ftc_undated_item_is_still_valid(monkeypatch):
    _routes(monkeypatch, {FTC_LISTING_URL: (FTC_FULL_LISTING, "text/html", 200)})
    stubs = {s.item_url: s for s in await _ftc().fetch_item_stubs()}

    assert stubs[PR_NO_DATE_URL].published_at is None
    assert stubs[PR_NO_DATE_URL].title


@pytest.mark.asyncio
async def test_ftc_honors_source_base_url(monkeypatch):
    configured = "https://ftc.mirror.test/news-events/news/press-releases"
    seen = _routes(monkeypatch, {configured: (FTC_FULL_LISTING, "text/html", 200)})
    stubs = await _ftc(base_url=configured).fetch_item_stubs()

    assert seen == [configured]
    assert not any("www.ftc.gov" in url for url in seen)
    assert stubs


@pytest.mark.asyncio
async def test_ftc_resolves_relative_links_against_the_final_url(monkeypatch):
    configured = "https://ftc.mirror.test/news-events/news/press-releases"
    final = "https://ftc.mirror.test/news-events/news/press-releases/"
    adapter = _ftc(base_url=configured)

    async def _fetch(url, *, accept=AcceptPolicy.ANY_TEXT, **kw):
        return source_base.FetchResult(
            url=url, final_url=final, status=200, content_type="text/html",
            text=FTC_FULL_LISTING,
        )

    monkeypatch.setattr(adapter, "fetch", _fetch)
    urls = [s.item_url for s in await adapter.fetch_item_stubs()]

    assert urls[0] == (
        "https://ftc.mirror.test/news-events/news/press-releases/2026/07/"
        "ftc-returns-money-scam-victims"
    )
    # The absolute www.ftc.gov row is now off-host and correctly dropped.
    assert all("ftc.mirror.test" in url for url in urls)


@pytest.mark.parametrize("base_url", [
    "", "   ", None, "news-events/news/press-releases", "ftp://ftc.gov/x",
    "http://127.0.0.1/news-events/news/press-releases",
    "http://user:pw@www.ftc.gov/news-events/news/press-releases",
])
def test_ftc_rejects_unusable_listing_config(base_url):
    with pytest.raises(ValueError, match="base_url"):
        _ftc(base_url=base_url).listing_url


@pytest.mark.asyncio
async def test_ftc_malformed_anchor_does_not_stop_parsing(monkeypatch, caplog):
    _routes(monkeypatch, {FTC_LISTING_URL: (FTC_MALFORMED_LISTING, "text/html", 200)})

    with caplog.at_level("DEBUG", logger="app.sources.ftc_feeds"):
        stubs = await _ftc().fetch_item_stubs()

    assert [s.item_url for s in stubs] == [PR_TZ_URL, PR_TZ_URL]
    assert not any("[::1" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_ftc_empty_but_valid_listing_returns_no_stubs(monkeypatch):
    _routes(monkeypatch, {FTC_LISTING_URL: (FTC_EMPTY_LISTING, "text/html", 200)})
    assert await _ftc().fetch_item_stubs() == []


@pytest.mark.asyncio
async def test_ftc_uses_the_html_listing_policy(monkeypatch):
    captured = []
    adapter = _ftc()

    async def _fetch(url, *, accept=AcceptPolicy.ANY_TEXT, **kw):
        captured.append((url, accept))
        return source_base.FetchResult(
            url=url, final_url=url, status=200, content_type="text/html",
            text=FTC_EMPTY_LISTING,
        )

    monkeypatch.setattr(adapter, "fetch", _fetch)
    await adapter.fetch_item_stubs()
    assert captured == [(FTC_LISTING_URL, AcceptPolicy.HTML_LISTING)]


@pytest.mark.asyncio
async def test_ftc_never_enables_the_browser(monkeypatch):
    _routes(monkeypatch, {
        FTC_LISTING_URL: (FTC_FULL_LISTING, "text/html", 200),
        PR_TZ_URL: (FTC_ARTICLE_PAGE, "text/html", 200),
    })
    launched = _no_browser(monkeypatch)

    await _ftc().fetch_item_stubs()
    await _ftc().fetch_full_article(PR_TZ_URL)
    assert launched == []


def test_ftc_keeps_no_hardcoded_listing_url():
    import inspect

    from app.sources import ftc_feeds

    code = "\n".join(
        line for line in inspect.getsource(ftc_feeds).splitlines()
        if not line.strip().startswith(("#", '"', "'"))
    )
    assert "ftc.gov" not in code
    assert "allow_browser" not in code
    # The broad page-wide link fallback is gone.
    assert "if not results" not in code


# ===========================================================================
# Krebs
# ===========================================================================


def test_krebs_is_an_rss_adapter():
    assert issubclass(KrebsAdapter, RSSAdapter)
    assert ADAPTER_REGISTRY["krebs.KrebsAdapter"] is KrebsAdapter


def test_krebs_html_fallback_is_gone():
    import inspect

    from app.sources import krebs

    src = inspect.getsource(krebs)
    for token in ("HTMLScraperAdapter", "parse_listing_page", "_KrebsRSSAdapter",
                  "BeautifulSoup", "entry-title", "allow_browser"):
        assert token not in src, token


def test_krebs_configured_feed_wins():
    assert _krebs("https://custom.test/krebs.xml").rss_url == "https://custom.test/krebs.xml"


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_krebs_blank_config_uses_one_official_default(configured):
    import inspect

    from app.sources import krebs

    assert _krebs(configured).rss_url == KREBS_OFFICIAL_FEED
    assert KREBS_OFFICIAL_FEED == KREBS_FEED_URL
    assert inspect.getsource(krebs).count("krebsonsecurity.com") == 1


@pytest.mark.asyncio
async def test_krebs_discovery_uses_the_feed(monkeypatch):
    seen = _routes(monkeypatch, {
        KREBS_FEED_URL: (KREBS_FULL_FEED, "application/rss+xml", 200),
        "https://krebsonsecurity.com": (KREBS_HTML_LISTING, "text/html", 200),
    })
    stubs = await _krebs().fetch_item_stubs()

    assert seen == [KREBS_FEED_URL]
    assert [s.item_url for s in stubs] == [KREBS_POST_1, KREBS_POST_2]


@pytest.mark.asyncio
async def test_krebs_entries_retain_dates_and_summaries(monkeypatch):
    _routes(monkeypatch, {KREBS_FEED_URL: (KREBS_FULL_FEED, "application/rss+xml", 200)})
    stubs = await _krebs().fetch_item_stubs()

    assert stubs[0].title == "Inside a Phishing-as-a-Service Operation"
    assert stubs[0].summary == KREBS_SUMMARY_1
    assert stubs[0].published_at == datetime(2026, 7, 21, 18, 5)
    assert stubs[1].published_at == datetime(2026, 7, 13, 16, 30)  # -0400 → UTC
    assert all(s.published_at is not None for s in stubs)


@pytest.mark.asyncio
async def test_krebs_relative_entry_links_resolve(monkeypatch):
    _routes(monkeypatch, {KREBS_FEED_URL: (KREBS_FULL_FEED, "application/rss+xml", 200)})
    stubs = await _krebs().fetch_item_stubs()

    assert stubs[1].item_url == KREBS_POST_2


@pytest.mark.asyncio
async def test_krebs_skips_entries_missing_a_link_or_title(monkeypatch):
    _routes(monkeypatch, {
        KREBS_FEED_URL: (KREBS_FEED_WITH_MALFORMED, "application/rss+xml", 200)
    })
    stubs = await _krebs().fetch_item_stubs()

    assert [s.item_url for s in stubs] == [KREBS_POST_1]


@pytest.mark.asyncio
async def test_krebs_empty_but_valid_feed_returns_no_stubs(monkeypatch):
    _routes(monkeypatch, {KREBS_FEED_URL: (KREBS_EMPTY_FEED, "application/rss+xml", 200)})
    assert await _krebs().fetch_item_stubs() == []


@pytest.mark.asyncio
async def test_krebs_challenge_for_the_feed_fails_explicitly(monkeypatch):
    """No silent degradation to the HTML listing — the run fails visibly."""
    _routes(monkeypatch, {
        KREBS_FEED_URL: (CHALLENGE_INTERSTITIAL, "text/html", 200),
        "https://krebsonsecurity.com": (KREBS_HTML_LISTING, "text/html", 200),
    })
    launched = _no_browser(monkeypatch)

    with pytest.raises(ChallengeDetected):
        await _krebs().fetch_item_stubs()
    assert launched == []


@pytest.mark.asyncio
async def test_krebs_never_enables_the_browser(monkeypatch):
    _routes(monkeypatch, {
        KREBS_FEED_URL: (KREBS_FULL_FEED, "application/rss+xml", 200),
        KREBS_POST_1: (KREBS_ARTICLE_PAGE, "text/html", 200),
    })
    launched = _no_browser(monkeypatch)

    await _krebs().fetch_item_stubs()
    await _krebs().fetch_full_article(KREBS_POST_1)
    assert launched == []


def test_krebs_registry_mapping_is_unchanged():
    from app.sources.registry import get_adapter

    src = _Src()
    src.adapter_class = "krebs.KrebsAdapter"
    assert isinstance(get_adapter(src), KrebsAdapter)


# ===========================================================================
# Collector integration
# ===========================================================================


@pytest.fixture
async def stored_source(db_session):
    """Factory for a source row whose items are removed afterwards."""
    created: list[Source] = []

    async def _make(name, base_url, adapter_class, rss_url=None):
        src = Source(
            name=name, base_url=base_url, source_type="html",
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
        select(RawItem.item_url, RawItem.raw_text, RawItem.raw_html).where(
            RawItem.source_id == source.id
        )
    )
    return {url: (text, html) for url, text, html in result.all()}


@pytest.mark.asyncio
async def test_sec_collection_never_requests_a_detail_page(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("SEC Press Releases",
                                 "https://www.sec.gov/newsroom/press-releases",
                                 "sec_press.SECPressAdapter", SEC_FEED_URL)
    seen = _routes(monkeypatch, {SEC_FEED_URL: (SEC_FULL_FEED, "application/rss+xml", 200)},
                   default=("blocked", "text/html", 403))
    launched = _no_browser(monkeypatch)

    run = await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    assert seen == [SEC_FEED_URL], "only the feed was requested"
    assert launched == []
    assert run.status == "success"
    # Good, short-but-valid and HTML summaries stored; empty and weak skipped.
    assert set(stored) == {SEC_PR_1, SEC_PR_2, SEC_PR_5}
    assert run.items_new == 3
    assert run.items_skipped_invalid == 2
    assert run.items_fetched == (
        run.items_new + run.items_skipped_url + run.items_skipped_content
        + run.items_skipped_invalid
    )


@pytest.mark.asyncio
async def test_sec_stored_items_carry_summary_text_and_no_html(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("SEC Press Releases",
                                 "https://www.sec.gov/newsroom/press-releases",
                                 "sec_press.SECPressAdapter", SEC_FEED_URL)
    _routes(monkeypatch, {SEC_FEED_URL: (SEC_FULL_FEED, "application/rss+xml", 200)})

    await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    text, html = stored[SEC_PR_1]
    assert text == SEC_GOOD_SUMMARY
    assert html == ""
    # Markup is cleaned, not stored raw.
    assert "<" not in stored[SEC_PR_5][0]


@pytest.mark.asyncio
async def test_sec_invalid_summaries_stay_unstored_and_retriable(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("SEC Press Releases",
                                 "https://www.sec.gov/newsroom/press-releases",
                                 "sec_press.SECPressAdapter", SEC_FEED_URL)
    _routes(monkeypatch, {SEC_FEED_URL: (SEC_FULL_FEED, "application/rss+xml", 200)})

    await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    assert SEC_PR_3 not in stored   # empty summary
    assert SEC_PR_4 not in stored   # weak summary
    # Nothing was fabricated from the title.
    assert not any("SEC Announces Enforcement Action" in text for text, _ in stored.values())


@pytest.mark.asyncio
async def test_summary_only_mode_does_not_call_fetch_full_article(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("SEC Press Releases",
                                 "https://www.sec.gov/newsroom/press-releases",
                                 "sec_press.SECPressAdapter", SEC_FEED_URL)
    calls: list[str] = []

    async def _boom(self, url):
        calls.append(url)
        raise AssertionError("fetch_full_article must not be called")

    monkeypatch.setattr(SECPressAdapter, "fetch_full_article", _boom)
    _routes(monkeypatch, {SEC_FEED_URL: (SEC_FULL_FEED, "application/rss+xml", 200)})

    run = await collector.run_source(source, db_session)
    assert calls == []
    assert run.status == "success"


@pytest.mark.asyncio
async def test_unexpected_summary_policy_error_fails_the_run(
    monkeypatch, db_session, stored_source
):
    """A bug in the policy hook must surface, not degrade to no content."""
    source = await stored_source("SEC Press Releases",
                                 "https://www.sec.gov/newsroom/press-releases",
                                 "sec_press.SECPressAdapter", SEC_FEED_URL)

    def _boom(self, stub, error):
        raise RuntimeError("summary policy bug")

    monkeypatch.setattr(SECPressAdapter, "summary_fallback", _boom)
    _routes(monkeypatch, {SEC_FEED_URL: (SEC_FULL_FEED, "application/rss+xml", 200)})

    run = await collector.run_source(source, db_session)
    assert run.status == "failed"
    assert "summary policy bug" in (run.error_message or "")
    assert await _rows(db_session, source) == {}


@pytest.mark.asyncio
async def test_unexpected_detail_policy_error_fails_the_run(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("SEC Press Releases",
                                 "https://www.sec.gov/newsroom/press-releases",
                                 "sec_press.SECPressAdapter", SEC_FEED_URL)

    def _boom(self, stub):
        raise RuntimeError("detail policy bug")

    monkeypatch.setattr(SECPressAdapter, "should_fetch_article", _boom)
    _routes(monkeypatch, {SEC_FEED_URL: (SEC_FULL_FEED, "application/rss+xml", 200)})

    run = await collector.run_source(source, db_session)
    assert run.status == "failed"
    assert "detail policy bug" in (run.error_message or "")


@pytest.mark.asyncio
async def test_doj_article_first_behaviour_is_unchanged(
    monkeypatch, db_session, stored_source
):
    """DOJ still requests the article and only falls back when it fails."""
    from tests.test_adapters.doj_fixtures import (
        FULL_FEED,
        OPA_ARTICLE_HTML,
        OPA_URL,
        USAO_INTERSTITIAL_HTML,
        USAO_URL,
    )

    source = await stored_source("DOJ Press Releases", "https://www.justice.gov/news",
                                 "doj_press.DOJPressAdapter")
    feed_url = "https://www.justice.gov/news/rss?type=press_release"
    seen = _routes(monkeypatch, {
        feed_url: (FULL_FEED, "application/rss+xml", 200),
        OPA_URL: (OPA_ARTICLE_HTML, "text/html", 200),
    }, default=(USAO_INTERSTITIAL_HTML, "text/html", 200))
    _no_browser(monkeypatch)

    await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    assert len(seen) > 1, "DOJ still requests article pages"
    assert "fourteen-day trial" in stored[OPA_URL][0]
    assert stored[USAO_URL][0].startswith("A Gretna man was indicted")
    assert stored[OPA_URL][1] != "", "article HTML is retained for DOJ"


@pytest.mark.asyncio
async def test_krebs_collection_stores_article_text(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("KrebsOnSecurity", "https://krebsonsecurity.com",
                                 "krebs.KrebsAdapter", KREBS_FEED_URL)
    _routes(monkeypatch, {
        KREBS_FEED_URL: (KREBS_FULL_FEED, "application/rss+xml", 200),
        KREBS_POST_1: (KREBS_ARTICLE_PAGE, "text/html", 200),
        KREBS_POST_2: (KREBS_ARTICLE_PAGE.replace("operation", "campaign"), "text/html", 200),
    })
    _no_browser(monkeypatch)

    run = await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    assert run.status == "success"
    assert run.items_new == 2
    assert "advertised itself openly" in stored[KREBS_POST_1][0]
    assert stored[KREBS_POST_1][1] != ""


@pytest.mark.asyncio
async def test_no_ai_processing_is_invoked(monkeypatch, db_session, stored_source):
    from app.pipeline import ai_processor

    called: list[str] = []
    monkeypatch.setattr(ai_processor, "analyze_article",
                        lambda *a, **k: called.append("ai"), raising=False)
    source = await stored_source("SEC Press Releases",
                                 "https://www.sec.gov/newsroom/press-releases",
                                 "sec_press.SECPressAdapter", SEC_FEED_URL)
    _routes(monkeypatch, {SEC_FEED_URL: (SEC_FULL_FEED, "application/rss+xml", 200)})

    await collector.run_source(source, db_session)
    assert called == []


# ===========================================================================
# Regression
# ===========================================================================


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


def test_untouched_sources_keep_their_adapters():
    """BleepingComputer keeps every default; the FBI feeds keep the RSS path.

    The FBI adapters' ``summary_fallback`` is deliberately overridden by the
    canonical-source policy (Slice 3B.2E) — asserted in that slice's tests. What
    matters here is that this slice's detail-fetch hook left them alone.
    """
    from app.sources.bleeping import BleepingAdapter
    from app.sources.fbi_blog import FBIBlogAdapter
    from app.sources.fbi_national import FBINationalAdapter
    from app.sources.fbi_news import FBINewsAdapter

    for cls in (FBINationalAdapter, FBIBlogAdapter, FBINewsAdapter, BleepingAdapter):
        assert issubclass(cls, RSSAdapter)
        assert cls.should_fetch_article is source_base.BaseSourceAdapter.should_fetch_article

    assert BleepingAdapter.summary_fallback is source_base.BaseSourceAdapter.summary_fallback


def test_no_api_surface_was_touched():
    from app.main import app

    schema = str(app.openapi()).lower()
    for token in ("ftc", "krebs", "should_fetch_article", "pressreleases.rss"):
        assert token not in schema, token


# ===========================================================================
# Krebs feed reliability (Slice 3B.2G)
# ===========================================================================

VALID_RSS = KREBS_FULL_FEED
VALID_ATOM = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom">'
    "<title>Krebs on Security</title>"
    f'<link href="{KREBS_POST_1}"/><updated>2026-07-21T18:05:00Z</updated>'
    "<entry><title>Inside a Phishing-as-a-Service Operation</title>"
    f'<link href="{KREBS_POST_1}"/>'
    "<updated>2026-07-21T18:05:00Z</updated>"
    "<summary>A phishing-as-a-service operation sold ready-made login pages.</summary>"
    "</entry></feed>"
)
VALID_EMPTY_RSS = KREBS_EMPTY_FEED
ORDINARY_HTML = (
    "<!DOCTYPE html><html><head><title>Krebs on Security</title></head><body>"
    "<h1>Krebs on Security</h1><p>In-depth security news and investigation.</p>"
    "<article><h2>Inside a Phishing-as-a-Service Operation</h2></article>"
    "</body></html>"
)
NON_FEED_XML = (
    '<?xml version="1.0"?><catalog><book id="1"><title>Not a feed</title></book></catalog>'
)
JSON_BODY = '{"items": [{"title": "Not a feed", "link": "https://krebsonsecurity.com/x"}]}'

HTML_CT = "text/html; charset=UTF-8"
RSS_CT = "application/rss+xml; charset=UTF-8"


def _sequence(monkeypatch, adapter, responses):
    """Serve one canned (body, content_type) per fetch call, recording attempts."""
    seen: list[str] = []
    queue = list(responses)

    async def _fetch(url, *, accept=AcceptPolicy.ANY_TEXT, **kw):
        seen.append(url)
        body, ctype = queue.pop(0)
        return source_base.FetchResult(
            url=url, final_url=url, status=200, content_type=ctype, text=body,
        )

    monkeypatch.setattr(adapter, "fetch", _fetch)
    return seen


# --- Documents the strict parser must accept or reject --------------------


@pytest.mark.parametrize("body", [VALID_RSS, VALID_ATOM, VALID_EMPTY_RSS])
def test_feed_documents_are_recognized(body):
    from app.sources.rss_adapter import parse_feed_document

    assert parse_feed_document(body) is not None


@pytest.mark.parametrize("body", [
    ORDINARY_HTML, NON_FEED_XML, JSON_BODY, "", "   ", "just some text",
    "<!DOCTYPE html><html><body><pre>&lt;rss version='2.0'&gt;</pre></body></html>",
])
def test_non_feed_documents_are_rejected(body):
    from app.sources.rss_adapter import parse_feed_document

    assert parse_feed_document(body) is None


def test_zero_entries_alone_proves_nothing():
    """A valid empty feed parses; an HTML page with no entries does not."""
    from app.sources.rss_adapter import parse_feed_document

    empty = parse_feed_document(VALID_EMPTY_RSS)
    assert empty is not None and len(empty.entries) == 0
    assert parse_feed_document(ORDINARY_HTML) is None


def test_feed_root_must_be_top_level():
    from app.sources.rss_adapter import has_feed_root

    assert has_feed_root('<?xml version="1.0"?>\n<!-- c -->\n<rss version="2.0"></rss>')
    assert has_feed_root('﻿<feed xmlns="http://www.w3.org/2005/Atom"></feed>')
    assert has_feed_root('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>')
    assert not has_feed_root("<html><body><rss version='2.0'></rss></body></html>")


# --- Krebs attempt policy -------------------------------------------------


@pytest.mark.asyncio
async def test_krebs_normal_rss_content_type_succeeds(monkeypatch):
    adapter = _krebs()
    seen = _sequence(monkeypatch, adapter, [(VALID_RSS, RSS_CT)])

    stubs = await adapter.fetch_item_stubs()
    assert [s.item_url for s in stubs] == [KREBS_POST_1, KREBS_POST_2]
    assert len(seen) == 1, "a healthy feed costs exactly one request"


@pytest.mark.asyncio
async def test_krebs_valid_rss_declared_text_html_succeeds(monkeypatch):
    """The live defect: a valid feed mislabeled as text/html."""
    adapter = _krebs()
    seen = _sequence(monkeypatch, adapter, [(VALID_RSS, HTML_CT)])

    stubs = await adapter.fetch_item_stubs()
    assert [s.item_url for s in stubs] == [KREBS_POST_1, KREBS_POST_2]
    assert stubs[0].summary == KREBS_SUMMARY_1
    assert stubs[0].published_at == datetime(2026, 7, 21, 18, 5)
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_krebs_valid_atom_declared_text_html_succeeds(monkeypatch):
    adapter = _krebs()
    _sequence(monkeypatch, adapter, [(VALID_ATOM, HTML_CT)])

    stubs = await adapter.fetch_item_stubs()
    assert [s.item_url for s in stubs] == [KREBS_POST_1]
    assert stubs[0].published_at == datetime(2026, 7, 21, 18, 5)


@pytest.mark.asyncio
async def test_krebs_valid_empty_feed_declared_text_html_returns_zero_stubs(monkeypatch):
    adapter = _krebs()
    seen = _sequence(monkeypatch, adapter, [(VALID_EMPTY_RSS, HTML_CT)])

    assert await adapter.fetch_item_stubs() == []
    assert len(seen) == 1, "a valid empty feed is an answer, not a reason to retry"


@pytest.mark.asyncio
async def test_ordinary_html_never_becomes_an_empty_feed(monkeypatch):
    """The rule that matters: silence must never be manufactured from a web page."""
    adapter = _krebs()
    seen = _sequence(monkeypatch, adapter, [(ORDINARY_HTML, HTML_CT)] * 3)

    with pytest.raises(ContentTypeMismatch):
        await adapter.fetch_item_stubs()
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_two_bad_documents_then_rss_succeeds_on_the_third(monkeypatch):
    adapter = _krebs()
    seen = _sequence(monkeypatch, adapter, [
        (ORDINARY_HTML, HTML_CT), (ORDINARY_HTML, HTML_CT), (VALID_RSS, RSS_CT),
    ])

    stubs = await adapter.fetch_item_stubs()
    assert [s.item_url for s in stubs] == [KREBS_POST_1, KREBS_POST_2]
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_three_bad_documents_fail_visibly(monkeypatch):
    adapter = _krebs()
    seen = _sequence(monkeypatch, adapter, [(ORDINARY_HTML, HTML_CT)] * 3)

    with pytest.raises(ContentTypeMismatch, match="3 attempts"):
        await adapter.fetch_item_stubs()
    assert len(seen) == 3, "bounded at exactly MAX_FEED_ATTEMPTS"


@pytest.mark.asyncio
@pytest.mark.parametrize("body,ctype", [
    (NON_FEED_XML, "application/xml"), (JSON_BODY, "application/json"),
    ("plain words", "text/plain"),
])
async def test_other_non_feed_bodies_also_fail(monkeypatch, body, ctype):
    adapter = _krebs()
    _sequence(monkeypatch, adapter, [(body, ctype)] * 3)

    with pytest.raises(ContentTypeMismatch):
        await adapter.fetch_item_stubs()


# --- Errors this logic must never retry or swallow ------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [
    ChallengeDetected("interstitial"),
    UnsafeRequestTarget("private address"),
    RedirectLoop("loop"),
    TooManyRedirects("too many"),
    PermanentFetchError("HTTP 403", status=403),
    RateLimitedError("rate limited", status=429),
    TransientFetchError("upstream busy", status=503),
    RuntimeError("adapter bug"),
], ids=["challenge", "unsafe", "loop", "redirects", "403", "429", "503", "bug"])
async def test_typed_failures_are_not_converted_into_feed_retries(monkeypatch, error):
    adapter = _krebs()
    attempts: list[str] = []

    async def _fetch(url, **kw):
        attempts.append(url)
        raise error

    monkeypatch.setattr(adapter, "fetch", _fetch)

    with pytest.raises(type(error)):
        await adapter.fetch_item_stubs()
    assert len(attempts) == 1, "the failure propagated on the first attempt"


@pytest.mark.asyncio
async def test_krebs_never_enables_the_browser_or_scrapes_html(monkeypatch):
    import inspect

    from app.sources import krebs

    src = inspect.getsource(krebs)
    for token in ("allow_browser", "HTMLScraperAdapter", "parse_listing_page",
                  "BeautifulSoup", "_KrebsRSSAdapter", "entry-title"):
        assert token not in src, token
    assert not hasattr(KrebsAdapter, "parse_listing_page")


@pytest.mark.asyncio
async def test_krebs_retries_still_pass_through_the_host_limiter(monkeypatch):
    """Each attempt is a real fetch, so each acquires the shared limiter."""
    acquired: list[str] = []
    routes = {KREBS_FEED_URL: (ORDINARY_HTML, "text/html", 200)}
    _routes(monkeypatch, routes)

    limiter = source_base.host_limiter
    real_acquire = limiter.acquire

    async def _acquire(host):
        acquired.append(host)
        return await real_acquire(host)

    monkeypatch.setattr(limiter, "acquire", _acquire)

    with pytest.raises(ContentTypeMismatch):
        await _krebs().fetch_item_stubs()
    assert acquired == ["krebsonsecurity.com"] * 3


def test_krebs_adds_no_sleep_of_its_own():
    """Pacing is the limiter's job; the adapter must not stall a run itself.

    Checked on call nodes, not prose — the docstring says the word.
    """
    import ast
    import inspect

    from app.sources import krebs

    sleeps = [
        node for node in ast.walk(ast.parse(inspect.getsource(krebs)))
        if isinstance(node, ast.Call)
        and (getattr(node.func, "id", "") == "sleep"
             or getattr(node.func, "attr", "") == "sleep")
    ]
    assert sleeps == []


@pytest.mark.asyncio
async def test_krebs_malformed_entries_are_still_skipped(monkeypatch):
    adapter = _krebs()
    _sequence(monkeypatch, adapter, [(KREBS_FEED_WITH_MALFORMED, HTML_CT)])

    stubs = await adapter.fetch_item_stubs()
    assert [s.item_url for s in stubs] == [KREBS_POST_1]


@pytest.mark.asyncio
async def test_krebs_configured_rss_url_still_takes_precedence(monkeypatch):
    adapter = _krebs("https://custom.test/krebs.xml")
    seen = _sequence(monkeypatch, adapter, [(VALID_RSS, RSS_CT)])

    await adapter.fetch_item_stubs()
    assert seen == ["https://custom.test/krebs.xml"]


def test_krebs_attempt_bound_is_three():
    from app.sources.krebs import MAX_FEED_ATTEMPTS

    assert MAX_FEED_ATTEMPTS == 3


# --- Every other RSS source keeps the plain single-fetch FEED behaviour ---


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_key", [
    "sec_press.SECPressAdapter", "fbi_national.FBINationalAdapter",
    "fbi_blog.FBIBlogAdapter", "fbi_news.FBINewsAdapter",
    "bleeping.BleepingAdapter", "doj_press.DOJPressAdapter",
])
async def test_other_rss_sources_use_one_feed_policy_fetch(monkeypatch, adapter_key):
    cls = ADAPTER_REGISTRY[adapter_key]
    src = _Src()
    src.id, src.name, src.rss_url = 99, "S", "https://example.test/feed.xml"
    src.base_url = "https://example.test"
    adapter = cls(src)

    calls: list[tuple] = []

    async def _fetch(url, *, accept=AcceptPolicy.ANY_TEXT, **kw):
        calls.append((url, accept))
        return source_base.FetchResult(
            url=url, final_url=url, status=200, content_type=RSS_CT, text=VALID_RSS,
        )

    monkeypatch.setattr(adapter, "fetch", _fetch)
    await adapter.fetch_item_stubs()

    assert len(calls) == 1
    assert calls[0][1] is AcceptPolicy.FEED


@pytest.mark.asyncio
async def test_generic_rss_rejects_a_non_feed_body(monkeypatch):
    """The strict parser applies to every RSS source, not only Krebs."""
    from app.sources.bleeping import BleepingAdapter

    src = _Src()
    src.name, src.rss_url = "B", "https://example.test/feed.xml"
    adapter = BleepingAdapter(src)

    async def _fetch(url, *, accept=AcceptPolicy.ANY_TEXT, **kw):
        return source_base.FetchResult(
            url=url, final_url=url, status=200, content_type="application/xml",
            text=NON_FEED_XML,
        )

    monkeypatch.setattr(adapter, "fetch", _fetch)
    with pytest.raises(ContentTypeMismatch, match="recognizable"):
        await adapter.fetch_item_stubs()
