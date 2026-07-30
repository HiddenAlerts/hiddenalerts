"""IC3 and FinCEN listing discovery and publication dates.

All responses come from sanitized fixtures through an injected transport. No
network, no collector entry points, no AI.
"""
import asyncio
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import delete, select

from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source
from app.pipeline import collector
from app.sources import base as source_base
from app.sources.fincen_press import FinCENPressAdapter
from app.sources.host_limiter import HostRateLimiter
from app.sources.ic3_alerts import (
    LISTING_YEAR_DEPTH,
    IC3AlertsAdapter,
    listing_years,
    psa_url_date,
)
from app.sources.response_policy import AcceptPolicy
from tests.test_adapters.ic3_fincen_fixtures import (
    FINCEN_ABSOLUTE_URL,
    FINCEN_ADJACENT_LISTING,
    FINCEN_ARTICLE_PAGE,
    FINCEN_EMPTY_LISTING,
    FINCEN_FULL_LISTING,
    FINCEN_LISTING_URL,
    FINCEN_NO_DATE_URL,
    FINCEN_TZ_URL,
    FINCEN_VISIBLE_URL,
    IC3_ADJACENT_LISTING,
    IC3_ARTICLE_PAGE,
    IC3_EDGE_LISTING,
    IC3_EMPTY_LISTING,
    IC3_FULL_LISTING,
    IC3_LEAP_LISTING,
    IC3_ROOT,
    PSA_BAD_SLUG_URL,
    PSA_SUFFIXED_URL,
    PSA_TZ_URL,
    PSA_URL_DATE_URL,
    PSA_VISIBLE_URL,
    PSA_YEAR_MISMATCH_URL,
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


def _ic3(base_url=IC3_ROOT):
    src = _Src()
    src.id, src.name, src.base_url = 4, "IC3 Press Releases", base_url
    return IC3AlertsAdapter(src)


def _fincen(base_url=FINCEN_LISTING_URL):
    src = _Src()
    src.id, src.name, src.base_url = 3, "FinCEN Press Releases", base_url
    return FinCENPressAdapter(src)


def _year_routes(body, *, years=(2026, 2025, 2024), root=IC3_ROOT):
    """The current year serves ``body``; the older year pages are empty."""
    routes = {f"{root}/{years[0]}": (body, "text/html", 200)}
    for year in years[1:]:
        routes[f"{root}/{year}"] = (IC3_EMPTY_LISTING, "text/html", 200)
    return routes


@pytest.fixture(autouse=True)
def _frozen_year(monkeypatch):
    """Pin the crawl to 2026 so fixtures do not age out."""
    import app.sources.ic3_alerts as ic3

    monkeypatch.setattr(
        ic3, "listing_years", lambda now=None: [2026, 2025, 2024]
    )


# ===========================================================================
# IC3 — discovery
# ===========================================================================


@pytest.mark.asyncio
async def test_ic3_parses_the_current_card_listing(monkeypatch):
    _routes(monkeypatch, _year_routes(IC3_FULL_LISTING))
    stubs = await _ic3().fetch_item_stubs()

    assert [s.item_url for s in stubs] == [
        PSA_TZ_URL, PSA_VISIBLE_URL, PSA_URL_DATE_URL, PSA_SUFFIXED_URL
    ]
    assert stubs[0].title == "Scammers Impersonate the IC3 to Contact Fraud Victims"
    assert stubs[0].source_name == "IC3 Press Releases"


def test_ic3_parser_needs_no_table_or_row_ancestor():
    assert "<table" not in IC3_FULL_LISTING and "<tr" not in IC3_FULL_LISTING

    import inspect

    from app.sources import ic3_alerts

    src = inspect.getsource(ic3_alerts)
    assert '"tr"' not in src and "'tr'" not in src
    assert "find_parent" not in src


@pytest.mark.asyncio
async def test_each_ic3_card_keeps_its_own_date(monkeypatch):
    """Adjacent cards must not borrow each other's dates."""
    _routes(monkeypatch, _year_routes(IC3_ADJACENT_LISTING))
    stubs = await _ic3().fetch_item_stubs()

    assert [s.published_at for s in stubs] == [
        datetime(2026, 7, 20, 14, 0), datetime(2026, 6, 26, 0, 0)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("excluded", ["/PSA/Archive", "/PSA/RSS"])
async def test_ic3_excludes_the_psa_landing_pages(monkeypatch, excluded):
    _routes(monkeypatch, _year_routes(IC3_FULL_LISTING))
    stubs = await _ic3().fetch_item_stubs()

    assert not any(url.endswith(excluded) for url in (s.item_url for s in stubs))


@pytest.mark.asyncio
async def test_ic3_excludes_navigation_pagination_and_offsite_links(monkeypatch):
    _routes(monkeypatch, _year_routes(IC3_FULL_LISTING))
    urls = [s.item_url for s in await _ic3().fetch_item_stubs()]

    for rejected in ("?page=", "/Media/", "/Privacy", "fbi.gov", f"{IC3_ROOT}/2025"):
        assert not any(rejected in url for url in urls), rejected


@pytest.mark.asyncio
async def test_ic3_requires_a_title(monkeypatch):
    listing = IC3_FULL_LISTING.replace(
        "Scammers Impersonate the IC3 to Contact Fraud Victims", ""
    )
    _routes(monkeypatch, _year_routes(listing))
    urls = [s.item_url for s in await _ic3().fetch_item_stubs()]

    assert PSA_TZ_URL not in urls
    assert PSA_VISIBLE_URL in urls
    assert all(s.title for s in await _ic3().fetch_item_stubs())


@pytest.mark.asyncio
async def test_ic3_resolves_relative_and_absolute_links(monkeypatch):
    _routes(monkeypatch, _year_routes(IC3_FULL_LISTING))
    urls = [s.item_url for s in await _ic3().fetch_item_stubs()]

    assert PSA_TZ_URL in urls          # href was relative
    assert PSA_SUFFIXED_URL in urls    # href was absolute
    assert all(url.startswith(f"{IC3_ROOT}/") for url in urls)


@pytest.mark.asyncio
async def test_ic3_honors_source_base_url(monkeypatch):
    root = "https://ic3.mirror.test/PSA"
    seen = _routes(monkeypatch, _year_routes(IC3_FULL_LISTING, root=root))
    stubs = await _ic3(base_url=f"{root}/").fetch_item_stubs()

    assert seen[0] == f"{root}/2026"
    assert not any("www.ic3.gov" in url for url in seen)
    assert all(s.item_url.startswith(f"{root}/") for s in stubs)


@pytest.mark.parametrize("base_url", ["", "   ", None, "not-a-url", "ftp://ic3.gov/PSA"])
def test_ic3_rejects_unusable_base_url(base_url):
    with pytest.raises(ValueError, match="base_url"):
        _ic3(base_url=base_url).listing_root


@pytest.mark.asyncio
async def test_ic3_empty_but_valid_listing_returns_no_stubs(monkeypatch):
    _routes(monkeypatch, _year_routes(IC3_EMPTY_LISTING))
    assert await _ic3().fetch_item_stubs() == []


@pytest.mark.asyncio
async def test_ic3_listing_uses_the_html_listing_policy(monkeypatch):
    captured = []
    adapter = _ic3()

    async def _fetch(url, *, accept=AcceptPolicy.ANY_TEXT, **kw):
        captured.append((url, accept))
        return source_base.FetchResult(
            url=url, final_url=url, status=200, content_type="text/html",
            text=IC3_EMPTY_LISTING,
        )

    monkeypatch.setattr(adapter, "fetch", _fetch)
    await adapter.fetch_item_stubs()

    assert captured
    assert all(accept is AcceptPolicy.HTML_LISTING for _, accept in captured)


@pytest.mark.asyncio
async def test_ic3_never_enables_the_browser(monkeypatch):
    _routes(monkeypatch, {
        **_year_routes(IC3_FULL_LISTING),
        PSA_TZ_URL: (IC3_ARTICLE_PAGE, "text/html", 200),
    })
    launched = _no_browser(monkeypatch)

    await _ic3().fetch_item_stubs()
    await _ic3().fetch_full_article(PSA_TZ_URL)
    assert launched == []


def test_ic3_declares_no_browser_opt_in():
    import inspect

    from app.sources import ic3_alerts

    assert "allow_browser" not in inspect.getsource(ic3_alerts)


@pytest.mark.asyncio
async def test_ic3_survives_a_failing_year_page(monkeypatch):
    """One unreachable year must not lose the years that answered."""
    routes = _year_routes(IC3_FULL_LISTING)
    routes[f"{IC3_ROOT}/2025"] = ("", "text/html", 500)
    _routes(monkeypatch, routes)

    assert len(await _ic3().fetch_item_stubs()) == 4


# ===========================================================================
# IC3 — dates
# ===========================================================================


@pytest.mark.asyncio
async def test_ic3_time_datetime_wins_over_the_url_slug(monkeypatch):
    _routes(monkeypatch, _year_routes(IC3_FULL_LISTING))
    stubs = {s.item_url: s.published_at for s in await _ic3().fetch_item_stubs()}

    # 2026-07-20T10:00-04:00 → 14:00 UTC. The slug alone would give midnight.
    assert stubs[PSA_TZ_URL] == datetime(2026, 7, 20, 14, 0)


@pytest.mark.asyncio
async def test_ic3_timezone_offsets_convert_to_naive_utc(monkeypatch):
    _routes(monkeypatch, _year_routes(IC3_FULL_LISTING))
    stubs = {s.item_url: s.published_at for s in await _ic3().fetch_item_stubs()}

    assert stubs[PSA_TZ_URL] == datetime(2026, 7, 20, 14, 0)
    assert stubs[PSA_TZ_URL].tzinfo is None
    assert stubs[PSA_SUFFIXED_URL] == datetime(2026, 5, 15, 13, 30)


@pytest.mark.asyncio
async def test_ic3_uses_visible_text_when_datetime_is_absent(monkeypatch):
    _routes(monkeypatch, _year_routes(IC3_FULL_LISTING))
    stubs = {s.item_url: s.published_at for s in await _ic3().fetch_item_stubs()}

    assert stubs[PSA_VISIBLE_URL] == datetime(2026, 6, 26, 0, 0)


@pytest.mark.asyncio
async def test_ic3_falls_back_to_the_url_slug_date(monkeypatch):
    _routes(monkeypatch, _year_routes(IC3_FULL_LISTING))
    stubs = {s.item_url: s.published_at for s in await _ic3().fetch_item_stubs()}

    assert stubs[PSA_URL_DATE_URL] == datetime(2026, 6, 18, 0, 0)


@pytest.mark.asyncio
async def test_ic3_impossible_slug_and_year_mismatch_yield_no_date(monkeypatch):
    _routes(monkeypatch, _year_routes(IC3_EDGE_LISTING))
    stubs = {s.item_url: s.published_at for s in await _ic3().fetch_item_stubs()}

    assert stubs[PSA_BAD_SLUG_URL] is None
    assert stubs[PSA_YEAR_MISMATCH_URL] is None


@pytest.mark.asyncio
async def test_ic3_keeps_undated_items(monkeypatch):
    _routes(monkeypatch, _year_routes(IC3_EDGE_LISTING))
    stubs = await _ic3().fetch_item_stubs()

    assert len(stubs) == 2
    assert all(s.published_at is None and s.title for s in stubs)


@pytest.mark.asyncio
async def test_ic3_accepts_a_valid_leap_day(monkeypatch):
    """A 29 February slug survives the calendar check on a leap year."""
    import app.sources.ic3_alerts as ic3

    monkeypatch.setattr(ic3, "listing_years", lambda now=None: [2024, 2023, 2022])
    _routes(monkeypatch, _year_routes(IC3_LEAP_LISTING, years=(2024, 2023, 2022)))
    stubs = await _ic3().fetch_item_stubs()

    assert len(stubs) == 1
    assert stubs[0].published_at == datetime(2024, 2, 29)


@pytest.mark.parametrize("path_year,slug,expected", [
    ("2026", "260720", datetime(2026, 7, 20)),
    ("2026", "260515", datetime(2026, 5, 15)),
    ("2024", "240229", datetime(2024, 2, 29)),   # leap day
    ("2026", "260229", None),                     # not a leap year
    ("2026", "269932", None),                     # impossible month/day
    ("2026", "261301", None),                     # month 13
    ("2026", "260732", None),                     # day 32
    ("2026", "240301", None),                     # slug year vs path year
    ("2025", "260301", None),                     # slug year vs path year
    ("2026", "260000", None),                     # month/day zero
])
def test_psa_url_date_validates_the_calendar(path_year, slug, expected):
    assert psa_url_date(path_year, slug) == expected


def test_ic3_does_not_infer_dates_from_unrelated_digits():
    import inspect

    from app.sources import ic3_alerts

    # The only slug rule is the anchored PSA pattern; there is no loose \d{6}
    # scan that could pick up a document number.
    assert inspect.getsource(ic3_alerts).count(r"\d{6}") == 1


# ===========================================================================
# IC3 — dynamic listing years
# ===========================================================================


def test_listing_years_uses_the_current_utc_year(monkeypatch):
    assert listing_years(datetime(2026, 7, 30, tzinfo=timezone.utc)) == [2026, 2025, 2024]


@pytest.mark.parametrize("moment,expected", [
    (datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc), [2025, 2024, 2023]),
    (datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc), [2026, 2025, 2024]),
    # 2025-12-31 21:00 in New York is 2026-01-01 02:00 UTC — UTC decides.
    (datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc), [2026, 2025, 2024]),
])
def test_listing_years_crosses_the_year_boundary(moment, expected):
    assert listing_years(moment) == expected


def test_listing_years_preserves_the_existing_lookback_depth():
    assert LISTING_YEAR_DEPTH == 3
    assert len(listing_years(datetime(2026, 7, 30, tzinfo=timezone.utc))) == 3
    assert len(listing_years()) == 3


def test_no_hardcoded_calendar_years_remain():
    """No literal 2024/2025/2026 survives in executable IC3 code."""
    import ast
    import inspect

    from app.sources import ic3_alerts

    tree = ast.parse(inspect.getsource(ic3_alerts))
    literals = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, int)
        and 2020 <= node.value <= 2099
    ]
    assert literals == [], f"literal year(s) in IC3 production code: {literals}"


def test_listing_years_defaults_to_now(monkeypatch):
    years = listing_years()
    assert years == [datetime.now(timezone.utc).year - n for n in range(3)]


@pytest.mark.parametrize("module_name", ["ic3_alerts", "fincen_press"])
def test_no_publication_date_filter_is_introduced(module_name):
    """A date may be recorded, never used to decide whether to keep an item."""
    import ast
    import importlib
    import inspect

    module = importlib.import_module(f"app.sources.{module_name}")
    source = inspect.getsource(module)
    for token in ("last_successful", "watermark", "run_started_at"):
        assert token not in source, token

    def _mentions_date(node):
        return any(
            (isinstance(n, ast.Name) and n.id == "published_at")
            or (isinstance(n, ast.Attribute) and n.attr == "published_at")
            for n in ast.walk(node)
        )

    # `is None` / `is not None` drive the date-precedence chain and the dated
    # counter. Anything else — an ordering or a value equality — would mean a
    # date had started deciding which items get collected.
    filtering = [
        ast.dump(node)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Compare)
        and _mentions_date(node)
        and not all(
            isinstance(op, (ast.Is, ast.IsNot))
            and isinstance(comparator, ast.Constant)
            and comparator.value is None
            for op, comparator in zip(node.ops, node.comparators)
        )
    ]
    assert filtering == [], "published_at is compared as a filter"


# ===========================================================================
# FinCEN — discovery
# ===========================================================================


@pytest.mark.asyncio
async def test_fincen_parses_every_press_release_row(monkeypatch):
    _routes(monkeypatch, {FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200)})
    stubs = await _fincen().fetch_item_stubs()

    assert [s.item_url for s in stubs] == [
        FINCEN_TZ_URL, FINCEN_VISIBLE_URL, FINCEN_NO_DATE_URL, FINCEN_ABSOLUTE_URL
    ]
    assert stubs[0].title == "FinCEN Proposes Rule to Pay Whistleblowers"
    assert stubs[0].source_name == "FinCEN Press Releases"


@pytest.mark.asyncio
async def test_fincen_does_not_emit_wrapper_or_navigation_links(monkeypatch):
    _routes(monkeypatch, {FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200)})
    urls = [s.item_url for s in await _fincen().fetch_item_stubs()]

    for rejected in ("/news/press-releases", "/news-room/topic/", "?page=",
                     "/contact", "treasury.gov", "/resources/advisories/"):
        assert not any(rejected in url for url in urls), rejected


@pytest.mark.asyncio
async def test_fincen_unrelated_first_anchor_does_not_hide_the_article(monkeypatch):
    """Each row leads with a topic link; the release link must still win."""
    _routes(monkeypatch, {FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200)})
    stubs = await _fincen().fetch_item_stubs()

    assert FINCEN_TZ_URL in [s.item_url for s in stubs]
    assert "Enforcement" not in [s.title for s in stubs]


@pytest.mark.asyncio
async def test_each_fincen_row_keeps_its_own_date(monkeypatch):
    _routes(monkeypatch, {FINCEN_LISTING_URL: (FINCEN_ADJACENT_LISTING, "text/html", 200)})
    stubs = await _fincen().fetch_item_stubs()

    assert [s.published_at for s in stubs] == [
        datetime(2026, 7, 15, 18, 0), datetime(2026, 6, 30, 13, 0)
    ]


@pytest.mark.asyncio
async def test_fincen_resolves_relative_links_against_the_listing_url(monkeypatch):
    """Relative hrefs resolve against the URL actually fetched, redirects included."""
    configured = "https://fincen.mirror.test/news/press-releases"
    final = "https://fincen.mirror.test/news/press-releases/"
    adapter = _fincen(base_url=configured)

    async def _fetch(url, *, accept=AcceptPolicy.ANY_TEXT, **kw):
        return source_base.FetchResult(
            url=url, final_url=final, status=200, content_type="text/html",
            text=FINCEN_FULL_LISTING,
        )

    monkeypatch.setattr(adapter, "fetch", _fetch)
    urls = [s.item_url for s in await adapter.fetch_item_stubs()]

    assert urls[0] == (
        "https://fincen.mirror.test/news/news-releases/"
        "fincen-proposes-rule-pay-whistleblowers"
    )
    # The absolute www.fincen.gov row is now off-host and correctly dropped.
    assert all("fincen.mirror.test" in url for url in urls)


@pytest.mark.asyncio
async def test_fincen_honors_source_base_url(monkeypatch):
    configured = "https://www.fincen.gov/news/press-releases?page=0"
    seen = _routes(monkeypatch, {configured: (FINCEN_FULL_LISTING, "text/html", 200)})

    stubs = await _fincen(base_url=configured).fetch_item_stubs()
    assert seen == [configured]
    assert stubs


@pytest.mark.parametrize("base_url", ["", "   ", None, "news/press-releases", "file:///etc"])
def test_fincen_rejects_unusable_base_url(base_url):
    with pytest.raises(ValueError, match="base_url"):
        _fincen(base_url=base_url).listing_url


@pytest.mark.asyncio
async def test_fincen_requires_a_title(monkeypatch):
    listing = FINCEN_FULL_LISTING.replace("FinCEN Proposes Rule to Pay Whistleblowers", "")
    _routes(monkeypatch, {FINCEN_LISTING_URL: (listing, "text/html", 200)})
    urls = [s.item_url for s in await _fincen().fetch_item_stubs()]

    assert FINCEN_TZ_URL not in urls
    assert FINCEN_VISIBLE_URL in urls


@pytest.mark.asyncio
async def test_fincen_empty_but_valid_listing_returns_no_stubs(monkeypatch):
    _routes(monkeypatch, {FINCEN_LISTING_URL: (FINCEN_EMPTY_LISTING, "text/html", 200)})
    assert await _fincen().fetch_item_stubs() == []


@pytest.mark.asyncio
async def test_fincen_listing_uses_the_html_listing_policy(monkeypatch):
    captured = []
    adapter = _fincen()

    async def _fetch(url, *, accept=AcceptPolicy.ANY_TEXT, **kw):
        captured.append((url, accept))
        return source_base.FetchResult(
            url=url, final_url=url, status=200, content_type="text/html",
            text=FINCEN_EMPTY_LISTING,
        )

    monkeypatch.setattr(adapter, "fetch", _fetch)
    await adapter.fetch_item_stubs()

    assert captured == [(FINCEN_LISTING_URL, AcceptPolicy.HTML_LISTING)]


@pytest.mark.asyncio
async def test_fincen_never_enables_the_browser(monkeypatch):
    _routes(monkeypatch, {
        FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200),
        FINCEN_TZ_URL: (FINCEN_ARTICLE_PAGE, "text/html", 200),
    })
    launched = _no_browser(monkeypatch)

    await _fincen().fetch_item_stubs()
    await _fincen().fetch_full_article(FINCEN_TZ_URL)
    assert launched == []


def test_fincen_declares_no_browser_opt_in():
    import inspect

    from app.sources import fincen_press

    assert "allow_browser" not in inspect.getsource(fincen_press)


def test_fincen_keeps_no_hardcoded_listing_host():
    import inspect

    from app.sources import fincen_press

    code = "\n".join(
        line for line in inspect.getsource(fincen_press).splitlines()
        if not line.strip().startswith(("#", '"', "'"))
    )
    assert "fincen.gov" not in code


# ===========================================================================
# FinCEN — dates
# ===========================================================================


@pytest.mark.asyncio
async def test_fincen_prefers_time_datetime(monkeypatch):
    _routes(monkeypatch, {FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200)})
    dates = {s.item_url: s.published_at for s in await _fincen().fetch_item_stubs()}

    assert dates[FINCEN_TZ_URL] == datetime(2026, 7, 15, 18, 0)


@pytest.mark.asyncio
async def test_fincen_falls_back_to_visible_date_text(monkeypatch):
    _routes(monkeypatch, {FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200)})
    dates = {s.item_url: s.published_at for s in await _fincen().fetch_item_stubs()}

    assert dates[FINCEN_VISIBLE_URL] == datetime(2026, 7, 9, 0, 0)


@pytest.mark.asyncio
async def test_fincen_keeps_an_undated_item_with_none(monkeypatch):
    _routes(monkeypatch, {FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200)})
    stubs = {s.item_url: s for s in await _fincen().fetch_item_stubs()}

    assert stubs[FINCEN_NO_DATE_URL].published_at is None
    assert stubs[FINCEN_NO_DATE_URL].title


@pytest.mark.asyncio
async def test_fincen_timezone_conversion_matches_the_column_convention(monkeypatch):
    _routes(monkeypatch, {FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200)})
    dates = [s.published_at for s in await _fincen().fetch_item_stubs()]

    # -04:00 offsets stored as naive UTC, never as the local wall time.
    assert dates[0] == datetime(2026, 7, 15, 18, 0)
    assert all(d is None or d.tzinfo is None for d in dates)


@pytest.mark.asyncio
async def test_fincen_never_uses_collection_time_as_publication_time(monkeypatch):
    _routes(monkeypatch, {FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200)})
    before = datetime.utcnow()
    dates = [s.published_at for s in await _fincen().fetch_item_stubs()]

    assert None in dates
    assert all(d is None or d < before for d in dates)


def test_neither_adapter_reads_the_clock_for_publication_dates():
    import inspect

    from app.sources import fincen_press, ic3_alerts

    assert "utcnow" not in inspect.getsource(fincen_press)
    assert "utcnow" not in inspect.getsource(ic3_alerts)
    # IC3 reads the clock only to pick which year pages to crawl.
    assert inspect.getsource(ic3_alerts).count("datetime.now") == 1


# ===========================================================================
# Collector integration and regression
# ===========================================================================


@pytest.fixture
async def stored_source(db_session):
    """Factory for a source row whose items are removed afterwards."""
    created: list[Source] = []

    async def _make(name, base_url, adapter_class):
        src = Source(
            name=name, base_url=base_url, source_type="html",
            adapter_class=adapter_class, is_active=True,
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
        select(RawItem.item_url, RawItem.published_at).where(
            RawItem.source_id == source.id
        )
    )
    return dict(result.all())


@pytest.mark.asyncio
async def test_collector_stores_repaired_ic3_dates(monkeypatch, db_session, stored_source):
    source = await stored_source("IC3 Press Releases", IC3_ROOT,
                                 "ic3_alerts.IC3AlertsAdapter")
    _routes(monkeypatch, {
        **_year_routes(IC3_FULL_LISTING),
        PSA_TZ_URL: (IC3_ARTICLE_PAGE, "text/html", 200),
        PSA_VISIBLE_URL: (IC3_ARTICLE_PAGE.replace("criminals are", "callers are"),
                          "text/html", 200),
        PSA_URL_DATE_URL: (IC3_ARTICLE_PAGE.replace("criminals are", "senders are"),
                           "text/html", 200),
        PSA_SUFFIXED_URL: (IC3_ARTICLE_PAGE.replace("criminals are", "actors are"),
                           "text/html", 200),
    })
    _no_browser(monkeypatch)

    run = await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    assert run.status == "success"
    assert run.items_new == 4
    assert stored[PSA_TZ_URL] == datetime(2026, 7, 20, 14, 0)
    assert stored[PSA_VISIBLE_URL] == datetime(2026, 6, 26, 0, 0)
    assert stored[PSA_URL_DATE_URL] == datetime(2026, 6, 18, 0, 0)
    assert all(value is not None for value in stored.values())


@pytest.mark.asyncio
async def test_collector_stores_repaired_fincen_dates(
    monkeypatch, db_session, stored_source
):
    source = await stored_source("FinCEN Press Releases", FINCEN_LISTING_URL,
                                 "fincen_press.FinCENPressAdapter")
    _routes(monkeypatch, {
        FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200),
        FINCEN_TZ_URL: (FINCEN_ARTICLE_PAGE, "text/html", 200),
        FINCEN_VISIBLE_URL: (FINCEN_ARTICLE_PAGE.replace("proposed a", "issued a"),
                             "text/html", 200),
        FINCEN_NO_DATE_URL: (FINCEN_ARTICLE_PAGE.replace("proposed a", "published a"),
                             "text/html", 200),
        FINCEN_ABSOLUTE_URL: (FINCEN_ARTICLE_PAGE.replace("proposed a", "announced a"),
                              "text/html", 200),
    })
    _no_browser(monkeypatch)

    run = await collector.run_source(source, db_session)
    stored = await _rows(db_session, source)

    assert run.status == "success"
    assert run.items_new == 4
    assert stored[FINCEN_TZ_URL] == datetime(2026, 7, 15, 18, 0)
    assert stored[FINCEN_VISIBLE_URL] == datetime(2026, 7, 9, 0, 0)
    # A missing listing date is kept as NULL; it never blocks ingestion.
    assert stored[FINCEN_NO_DATE_URL] is None


@pytest.mark.asyncio
async def test_url_dedup_stays_with_the_collector(monkeypatch, db_session, stored_source):
    """The same PSA on two year pages is emitted twice and stored once."""
    source = await stored_source("IC3 Press Releases", IC3_ROOT,
                                 "ic3_alerts.IC3AlertsAdapter")
    routes = _year_routes(IC3_FULL_LISTING)
    routes[f"{IC3_ROOT}/2025"] = (IC3_FULL_LISTING, "text/html", 200)
    routes.update({
        PSA_TZ_URL: (IC3_ARTICLE_PAGE, "text/html", 200),
        PSA_VISIBLE_URL: (IC3_ARTICLE_PAGE.replace("criminals are", "callers are"),
                          "text/html", 200),
        PSA_URL_DATE_URL: (IC3_ARTICLE_PAGE.replace("criminals are", "senders are"),
                           "text/html", 200),
        PSA_SUFFIXED_URL: (IC3_ARTICLE_PAGE.replace("criminals are", "actors are"),
                           "text/html", 200),
    })
    _routes(monkeypatch, routes)
    _no_browser(monkeypatch)

    adapter_stubs = await _ic3().fetch_item_stubs()
    assert len(adapter_stubs) == 8, "the adapter does not deduplicate"

    run = await collector.run_source(source, db_session)
    assert run.items_new == 4
    assert run.items_skipped_url == 4
    assert len(await _rows(db_session, source)) == 4


@pytest.mark.asyncio
async def test_no_ai_processing_is_invoked(monkeypatch, db_session, stored_source):
    from app.pipeline import ai_processor

    called: list[str] = []
    monkeypatch.setattr(ai_processor, "analyze_article",
                        lambda *a, **k: called.append("ai"), raising=False)
    source = await stored_source("FinCEN Press Releases", FINCEN_LISTING_URL,
                                 "fincen_press.FinCENPressAdapter")
    _routes(monkeypatch, {
        FINCEN_LISTING_URL: (FINCEN_FULL_LISTING, "text/html", 200),
        FINCEN_TZ_URL: (FINCEN_ARTICLE_PAGE, "text/html", 200),
    })
    _no_browser(monkeypatch)

    await collector.run_source(source, db_session)
    assert called == []


def test_no_api_surface_was_touched():
    from app.main import app

    schema = str(app.openapi()).lower()
    for token in ("ic3", "fincen", "psa", "listing_years"):
        assert token not in schema, token


def test_registry_still_resolves_both_adapters():
    from app.sources.registry import ADAPTER_REGISTRY

    assert ADAPTER_REGISTRY["ic3_alerts.IC3AlertsAdapter"] is IC3AlertsAdapter
    assert ADAPTER_REGISTRY["fincen_press.FinCENPressAdapter"] is FinCENPressAdapter


def test_collector_holds_no_source_specific_logic():
    import inspect

    src = inspect.getsource(collector).lower()
    for token in ("ic3", "fincen", "psa", "news-releases"):
        assert token not in src, token
