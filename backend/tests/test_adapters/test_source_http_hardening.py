"""Final hardening of the shared source HTTP boundary.

Tier-escalation limits, browser navigation without an HTTP response, Host and
cross-origin header handling, initial-target validation, log-safe URLs,
HTML-fragment classification, retry error preservation and status-aware denial
pages.

Local fixtures and mocked transports only. No network, no real sleeps.
"""
import asyncio

import httpx
import pytest
import requests as _requests

from app.sources import base as source_base
from app.sources.base import (
    BaseSourceAdapter,
    _follow,
    _safe_url,
    _sync_requests_get,
    assert_safe_target,
    safe_redirect_headers,
)
from app.sources.host_limiter import HostRateLimiter
from app.sources.http_errors import (
    ChallengeDetected,
    ContentTypeMismatch,
    EmptyContent,
    PermanentFetchError,
    RateLimitedError,
    TransientFetchError,
    UnsafeRequestTarget,
)
from app.sources.response_policy import AcceptPolicy, BodyKind, classify_challenge, sniff_body_kind
from tests.test_adapters.fixtures import (
    ACCESS_DENIED_403,
    ARTICLE_ABOUT_ACCESS_DENIAL,
    ARTICLE_HTML,
    DOJ_INTERSTITIAL,
    GENERIC_XML,
    GENERIC_XML_NO_PROLOGUE,
    HTML_ARTICLE_FRAGMENT,
    HTML_DIV_FRAGMENT,
    ORDINARY_HTML_LISTING,
    PLAIN_FORBIDDEN_403,
    RSS_FEED,
)

_REAL_ASYNC_CLIENT = httpx.AsyncClient
_REAL_SLEEP = asyncio.sleep


class _Clock:
    def __init__(self):
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self):
        return self.now

    async def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds
        await _REAL_SLEEP(0)


def _limiter(**kw):
    clock = _Clock()
    return HostRateLimiter(monotonic=clock.monotonic, sleep=clock.sleep, **kw)


class _Adapter(BaseSourceAdapter):
    async def fetch_item_stubs(self):  # pragma: no cover
        return []

    async def fetch_items(self):  # pragma: no cover
        return []


class _Source:
    id = 9
    name = "Hardening Source"


def _adapter():
    return _Adapter(_Source())


def _patch_httpx(monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def _factory(**kw):
        kw.pop("transport", None)
        return _REAL_ASYNC_CLIENT(**kw, transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


def _forbidden_tier1(monkeypatch, body=PLAIN_FORBIDDEN_403):
    def handler(request):
        return httpx.Response(403, headers={"content-type": "text/html"}, text=body)

    _patch_httpx(monkeypatch, handler)


def _no_browser(monkeypatch):
    launched: list[str] = []

    async def _browser(*a, **k):
        launched.append("playwright")
        return 200, "https://x.test/a", "text/html", ARTICLE_HTML

    monkeypatch.setattr(source_base, "_playwright_get", _browser)
    return launched


# ---------------------------------------------------------------------------
# 1. Tier 2 / browser escalation is restricted to an ordinary 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier2_requests_timeout_reaches_neither_tier2b_nor_playwright(monkeypatch):
    _forbidden_tier1(monkeypatch)
    launched = _no_browser(monkeypatch)
    attempts: list[str] = []

    def _timeout(*a, **k):
        attempts.append("requests")
        raise _requests.exceptions.ConnectTimeout("timed out")

    monkeypatch.setattr(source_base._requests.Session, "get",
                        lambda self, url, **kw: _timeout())

    with pytest.raises(TransientFetchError):
        await _adapter().fetch("https://x.test/a", limiter=_limiter())

    assert attempts == ["requests"], "tier 2b must not be attempted"
    assert launched == []


@pytest.mark.asyncio
async def test_tier2_503_does_not_launch_playwright(monkeypatch):
    _forbidden_tier1(monkeypatch)
    launched = _no_browser(monkeypatch)
    monkeypatch.setattr(source_base, "_sync_requests_get",
                        lambda *a, **k: (503, {"content-type": "text/html"}, "busy", b"busy"))

    with pytest.raises(TransientFetchError) as exc:
        await _adapter().fetch("https://x.test/a", limiter=_limiter())
    assert exc.value.status == 503
    assert launched == []


@pytest.mark.asyncio
async def test_unexpected_tier2_runtime_error_does_not_become_browser_success(monkeypatch):
    _forbidden_tier1(monkeypatch)
    launched = _no_browser(monkeypatch)

    def _boom(*a, **k):
        raise RuntimeError("unexpected parser explosion")

    monkeypatch.setattr(source_base, "_sync_requests_get", _boom)

    with pytest.raises(TransientFetchError) as exc:
        await _adapter().fetch("https://x.test/a", limiter=_limiter())
    assert isinstance(exc.value.__cause__, RuntimeError)
    assert launched == []


@pytest.mark.asyncio
async def test_tier2_rate_limit_is_not_escalated(monkeypatch):
    _forbidden_tier1(monkeypatch)
    launched = _no_browser(monkeypatch)
    monkeypatch.setattr(
        source_base, "_sync_requests_get",
        lambda *a, **k: (429, {"content-type": "text/html", "retry-after": "3"}, "slow", b"slow"),
    )

    with pytest.raises(RateLimitedError) as exc:
        await _adapter().fetch("https://x.test/a", limiter=_limiter())
    assert exc.value.retry_after == 3.0
    assert launched == []


@pytest.mark.asyncio
async def test_ordinary_403_in_tier2a_still_proceeds_to_tier2b(monkeypatch):
    _forbidden_tier1(monkeypatch)
    seen: list[str] = []

    def _requests_get(url, headers, timeout):
        seen.append(headers.get("Accept", "minimal"))
        if len(seen) == 1:
            return 403, {"content-type": "text/html"}, PLAIN_FORBIDDEN_403, b"x"
        return 200, {"content-type": "text/html"}, ARTICLE_HTML, ARTICLE_HTML.encode()

    monkeypatch.setattr(source_base, "_sync_requests_get", _requests_get)
    result = await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                                    limiter=_limiter())
    assert result.status == 200
    assert len(seen) == 2, "tier 2b must be reached after an ordinary 2a 403"


@pytest.mark.asyncio
async def test_two_ordinary_403s_still_reach_playwright(monkeypatch):
    _forbidden_tier1(monkeypatch)
    launched: list[str] = []

    monkeypatch.setattr(
        source_base, "_sync_requests_get",
        lambda *a, **k: (403, {"content-type": "text/html"}, PLAIN_FORBIDDEN_403, b"x"),
    )

    async def _browser(*a, **k):
        launched.append("playwright")
        return 200, "https://x.test/a", "text/html", ARTICLE_HTML

    monkeypatch.setattr(source_base, "_playwright_get", _browser)

    result = await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                                    allow_browser=True, limiter=_limiter())
    assert launched == ["playwright"]
    assert result.status == 200


def test_requests_transport_errors_are_typed_at_the_boundary(monkeypatch):
    class _Sess:
        headers: dict = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            raise _requests.exceptions.ReadTimeout("slow")

    monkeypatch.setattr(source_base._requests, "Session", _Sess)
    with pytest.raises(TransientFetchError):
        _sync_requests_get("https://x.test/a", {}, 1.0)


# ---------------------------------------------------------------------------
# 2. Browser navigation with no HTTP response
# ---------------------------------------------------------------------------


def _browser_returns(monkeypatch, result):
    _forbidden_tier1(monkeypatch)
    monkeypatch.setattr(
        source_base, "_sync_requests_get",
        lambda *a, **k: (403, {"content-type": "text/html"}, PLAIN_FORBIDDEN_403, b"x"),
    )

    async def _browser(*a, **k):
        return result

    monkeypatch.setattr(source_base, "_playwright_get", _browser)


@pytest.mark.asyncio
async def test_browser_status_none_with_html_is_rejected(monkeypatch):
    _browser_returns(monkeypatch, (None, "https://x.test/final", "text/html", ARTICLE_HTML))
    with pytest.raises(TransientFetchError) as exc:
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               allow_browser=True, limiter=_limiter())
    assert "no HTTP response" in str(exc.value)
    assert "x.test/final" in exc.value.url


@pytest.mark.asyncio
async def test_browser_status_none_with_empty_html_is_rejected(monkeypatch):
    _browser_returns(monkeypatch, (None, "https://x.test/final", "text/html", ""))
    with pytest.raises(TransientFetchError):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               allow_browser=True, limiter=_limiter())


@pytest.mark.asyncio
async def test_browser_hosts_include_initial_and_final(monkeypatch):
    _browser_returns(monkeypatch, (200, "https://www.justice.gov/opa/pr/x", "text/html", ARTICLE_HTML))
    result = await _adapter().fetch("https://www.fbi.gov/a", accept=AcceptPolicy.ARTICLE,
                                    allow_browser=True, limiter=_limiter())
    assert result.hosts == ("www.fbi.gov", "www.justice.gov")


@pytest.mark.asyncio
async def test_browser_hosts_collapse_when_no_host_change(monkeypatch):
    _browser_returns(monkeypatch, (200, "https://x.test/a", "text/html", ARTICLE_HTML))
    result = await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                                    allow_browser=True, limiter=_limiter())
    assert result.hosts == ("x.test",)


# ---------------------------------------------------------------------------
# 3. Host header and cross-origin handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("header", ["Host", "host", "HOST"])
def test_host_header_is_stripped_case_insensitively(header):
    out = safe_redirect_headers({header: "x.test", "User-Agent": "ua"}, cross_origin=True)
    assert not any(k.lower() == "host" for k in out)
    assert out["User-Agent"] == "ua"


async def _capture_redirect(from_url, to_url, headers):
    captured: list[dict] = []

    async def _send(target, hdrs):
        captured.append(dict(hdrs))
        if target == from_url:
            return 302, {"location": to_url}, "", b""
        return 200, {"content-type": "text/html"}, ARTICLE_HTML, ARTICLE_HTML.encode()

    await _follow(from_url, policy=AcceptPolicy.ARTICLE, headers=headers, timeout=5.0,
                  send=_send, limiter=_limiter(), source_label="s")
    return captured


@pytest.mark.asyncio
async def test_host_stripped_on_hostname_change():
    captured = await _capture_redirect(
        "https://a.test/x", "https://b.test/y",
        {**source_base._BROWSER_HEADERS, "Host": "a.test", "Cookie": "s=1"},
    )
    assert "Host" in captured[0]
    assert "Host" not in captured[1] and "Cookie" not in captured[1]


@pytest.mark.asyncio
async def test_host_stripped_on_https_to_http_downgrade():
    captured = await _capture_redirect(
        "https://a.test/x", "http://a.test/y",
        {**source_base._BROWSER_HEADERS, "Host": "a.test", "Authorization": "Bearer s"},
    )
    assert "Host" not in captured[1] and "Authorization" not in captured[1]


@pytest.mark.asyncio
async def test_host_stripped_on_port_change():
    captured = await _capture_redirect(
        "https://a.test/x", "https://a.test:8443/y",
        {**source_base._BROWSER_HEADERS, "Host": "a.test", "X-Api-Key": "k"},
    )
    assert "Host" not in captured[1] and "X-Api-Key" not in captured[1]


@pytest.mark.asyncio
async def test_public_headers_survive_every_origin_change():
    captured = await _capture_redirect(
        "https://a.test/x", "http://b.test:8080/y",
        {**source_base._BROWSER_HEADERS, "Host": "a.test"},
    )
    for key in ("User-Agent", "Accept", "Accept-Language"):
        assert captured[1][key] == source_base._BROWSER_HEADERS[key]


# ---------------------------------------------------------------------------
# 4. Initial request target validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://169.254.169.254/latest/meta-data",
    "http://localhost/",
    "https://user:pass@example.com/",
    "file:///etc/passwd",
    "https://x.test:99999/",
    "http://10.1.2.3/",
    "http://[::1]/",
    "ftp://x.test/a",
    "https://service.internal/a",
])
@pytest.mark.asyncio
async def test_unsafe_initial_target_never_issues_a_request(url, monkeypatch):
    issued: list[str] = []

    def handler(request):  # pragma: no cover - must never run
        issued.append(request.url)
        return httpx.Response(200, text="x")

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(source_base, "_sync_requests_get",
                        lambda *a, **k: issued.append("requests") or (200, {}, "", b""))

    with pytest.raises(UnsafeRequestTarget):
        await _adapter().fetch(url, limiter=_limiter())
    assert issued == []


@pytest.mark.parametrize("url", [
    "https://www.justice.gov/news/rss?type=press_release",
    "https://www.fbi.gov/feeds/national-press-releases/rss.xml",
    "https://krebsonsecurity.com/feed/",
    "https://x.test:8443/a",
])
def test_public_source_urls_are_accepted(url):
    assert_safe_target(url)


def test_assert_safe_target_message_has_no_credentials():
    with pytest.raises(UnsafeRequestTarget) as exc:
        assert_safe_target("https://user:hunter2@example.com/a?token=SECRET")
    text = str(exc.value) + str(exc.value.url)
    assert "hunter2" not in text and "SECRET" not in text


# ---------------------------------------------------------------------------
# 5. Log-safe URLs
# ---------------------------------------------------------------------------


def test_safe_url_removes_credentials_query_and_fragment():
    out = _safe_url("https://user:hunter2@x.test/path?token=SECRET&a=1#frag")
    assert out == "https://x.test/path"
    for leaked in ("hunter2", "SECRET", "user", "?", "#"):
        assert leaked not in out


def test_safe_url_keeps_non_default_port():
    assert _safe_url("https://x.test:8443/a?q=1") == "https://x.test:8443/a"


def test_safe_url_drops_default_ports():
    assert _safe_url("https://x.test:443/a") == "https://x.test/a"
    assert _safe_url("http://x.test:80/a") == "http://x.test/a"


def test_safe_url_handles_invalid_port_without_raising():
    assert _safe_url("https://x.test:99999/a") == "https://x.test/a"


@pytest.mark.asyncio
async def test_credentials_never_appear_in_logs(caplog, monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text=DOJ_INTERSTITIAL)

    _patch_httpx(monkeypatch, handler)
    with caplog.at_level("DEBUG", logger="app.sources.base"):
        with pytest.raises(ChallengeDetected):
            await _adapter().fetch("https://x.test/a?token=SUPERSECRET",
                                   accept=AcceptPolicy.ARTICLE, limiter=_limiter())
    ours = [r.getMessage() for r in caplog.records if r.name == "app.sources.base"]
    assert ours, "the boundary must log something for a challenge"
    assert not any("SUPERSECRET" in m for m in ours)


# ---------------------------------------------------------------------------
# 6. HTML fragment classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body,ctype,expected", [
    (HTML_ARTICLE_FRAGMENT, "text/html", BodyKind.HTML),
    (HTML_DIV_FRAGMENT, "text/html", BodyKind.HTML),
    (HTML_ARTICLE_FRAGMENT, "", BodyKind.HTML),
    (HTML_DIV_FRAGMENT, "", BodyKind.HTML),
    (GENERIC_XML, "application/xml", BodyKind.XML),
    (GENERIC_XML_NO_PROLOGUE, "application/xml", BodyKind.XML),
    (RSS_FEED, "application/rss+xml", BodyKind.XML),
    (RSS_FEED, "text/html", BodyKind.XML),
    (DOJ_INTERSTITIAL, "application/xml", BodyKind.HTML),
])
def test_fragment_and_declared_type_classification(body, ctype, expected):
    assert sniff_body_kind(body, b"", ctype) is expected


@pytest.mark.asyncio
async def test_html_article_fragment_is_accepted_under_article():
    async def _send(target, headers):
        return 200, {"content-type": "text/html"}, HTML_ARTICLE_FRAGMENT, b""

    result = await _follow("https://x.test/a", policy=AcceptPolicy.ARTICLE,
                           headers={}, timeout=5.0, send=_send,
                           limiter=_limiter(), source_label="s")
    assert "Sentenced" in result.text


@pytest.mark.asyncio
async def test_generic_xml_stays_xml_under_feed():
    async def _send(target, headers):
        return 200, {"content-type": "application/xml"}, GENERIC_XML, b""

    result = await _follow("https://x.test/f", policy=AcceptPolicy.FEED,
                           headers={}, timeout=5.0, send=_send,
                           limiter=_limiter(), source_label="s")
    assert "<catalog>" in result.text


@pytest.mark.asyncio
async def test_html_fragment_is_still_rejected_under_feed():
    async def _send(target, headers):
        return 200, {"content-type": "text/html"}, HTML_DIV_FRAGMENT, b""

    with pytest.raises(ContentTypeMismatch):
        await _follow("https://x.test/f", policy=AcceptPolicy.FEED, headers={},
                      timeout=5.0, send=_send, limiter=_limiter(), source_label="s")


# ---------------------------------------------------------------------------
# 7. Retry exhaustion preserves the typed failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repeated_503_surfaces_as_transient_with_status(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503, headers={"content-type": "text/html"}, text="busy")

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(asyncio, "sleep", _Clock().sleep)

    with pytest.raises(TransientFetchError) as exc:
        await _adapter().fetch("https://x.test/a", retries=3, limiter=_limiter())
    assert exc.value.status == 503
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_repeated_429_surfaces_rate_limited_with_retry_after(monkeypatch):
    def handler(request):
        return httpx.Response(429, headers={"content-type": "text/html", "retry-after": "4"},
                              text="slow down")

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(asyncio, "sleep", _Clock().sleep)

    with pytest.raises(RateLimitedError) as exc:
        await _adapter().fetch("https://x.test/a", retries=2, limiter=_limiter())
    assert exc.value.status == 429
    assert exc.value.retry_after == 4.0


@pytest.mark.asyncio
async def test_timeout_exhaustion_becomes_actionable_transient_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectTimeout("timed out")

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(asyncio, "sleep", _Clock().sleep)

    with pytest.raises(TransientFetchError) as exc:
        await _adapter().fetch("https://x.test/a", retries=2, limiter=_limiter())
    assert "ConnectTimeout" in str(exc.value)
    assert isinstance(exc.value.__cause__, httpx.ConnectTimeout)


# ---------------------------------------------------------------------------
# 8. Status-aware denial pages
# ---------------------------------------------------------------------------


def test_short_403_access_denied_is_conclusive():
    verdict = classify_challenge(ACCESS_DENIED_403, content_type="text/html", status=403)
    assert verdict
    assert "access_denied" in verdict.signals


def test_same_denial_page_at_status_200_is_not_a_challenge():
    assert not classify_challenge(ACCESS_DENIED_403, content_type="text/html", status=200)


def test_article_discussing_access_denial_stays_usable():
    assert not classify_challenge(ARTICLE_ABOUT_ACCESS_DENIAL, content_type="text/html",
                                  status=200)
    assert not classify_challenge(ARTICLE_ABOUT_ACCESS_DENIAL, content_type="text/html",
                                  status=403)


def test_plain_forbidden_403_is_not_a_challenge():
    assert not classify_challenge(PLAIN_FORBIDDEN_403, content_type="text/html", status=403)


@pytest.mark.asyncio
async def test_short_403_denial_does_not_amplify_requests(monkeypatch):
    tiers: list[str] = []

    def handler(request):
        tiers.append("httpx")
        return httpx.Response(403, headers={"content-type": "text/html"}, text=ACCESS_DENIED_403)

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(source_base, "_sync_requests_get",
                        lambda *a, **k: tiers.append("requests") or (200, {}, "", b""))

    async def _browser(*a, **k):
        tiers.append("playwright")
        return 200, "", "text/html", ARTICLE_HTML

    monkeypatch.setattr(source_base, "_playwright_get", _browser)

    with pytest.raises(ChallengeDetected):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               limiter=_limiter())
    assert tiers == ["httpx"]


@pytest.mark.asyncio
async def test_plain_403_still_uses_the_existing_tier_behaviour(monkeypatch):
    tiers: list[str] = []

    def handler(request):
        tiers.append("httpx")
        return httpx.Response(403, headers={"content-type": "text/html"}, text=PLAIN_FORBIDDEN_403)

    _patch_httpx(monkeypatch, handler)

    def _requests_get(url, headers, timeout):
        tiers.append("requests")
        return 200, {"content-type": "text/html"}, ARTICLE_HTML, ARTICLE_HTML.encode()

    monkeypatch.setattr(source_base, "_sync_requests_get", _requests_get)

    result = await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                                    limiter=_limiter())
    assert tiers == ["httpx", "requests"]
    assert result.status == 200


# ---------------------------------------------------------------------------
# 9. Documentation
# ---------------------------------------------------------------------------


def test_fetch_item_stubs_doc_no_longer_mentions_date_prefiltering():
    doc = BaseSourceAdapter.fetch_item_stubs.__doc__ or ""
    assert "date pre-filtering" not in doc
    assert "never gate ingestion" in doc


def test_fetch_result_hosts_doc_describes_distinct_hosts():
    import inspect
    src = inspect.getsource(source_base.FetchResult)
    assert "not one entry per hop" in src


def test_browser_hop_limitation_is_documented():
    import inspect
    assert "interception" in inspect.getsource(source_base._playwright_get)
    assert "not observable" in inspect.getsource(source_base.BaseSourceAdapter._browser_fetch)


def test_dns_rebinding_limitation_remains_documented():
    import inspect
    src = inspect.getsource(source_base._unsafe_target_reason)
    assert "DNS-rebinding protection is NOT implemented" in src
