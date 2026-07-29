"""Shared source HTTP boundary: classification, content types, limiter, redirects.

Every response comes from a local fixture through an injected send function or an
httpx MockTransport. Nothing here touches the network, and no test sleeps for real
time — the limiter is driven by a fake clock.
"""
import asyncio

import httpx
import pytest

from app.sources import base as source_base
from app.sources.base import (
    MAX_REDIRECTS,
    BaseSourceAdapter,
    FetchResult,
    _follow,
    safe_redirect_headers,
)
from app.sources.host_limiter import HostRateLimiter, normalize_host
from app.sources.http_errors import (
    ChallengeDetected,
    ContentTypeMismatch,
    PermanentFetchError,
    RedirectLoop,
    TooManyRedirects,
    TransientFetchError,
    UnsupportedDocument,
    UnsupportedRedirectScheme,
)
from app.sources.response_policy import (
    AcceptPolicy,
    classify_challenge,
    content_type_allowed,
    is_unsupported_document,
)
from tests.test_adapters.fixtures import (
    ARTICLE_HTML,
    BENIGN_META_REFRESH,
    DOJ_INTERSTITIAL,
    IC3_ARTICLE,
    ORDINARY_HTML_LISTING,
    PDF_BYTES,
    RSS_FEED,
)


_REAL_ASYNC_CLIENT = httpx.AsyncClient
_REAL_SLEEP = asyncio.sleep


def _patch_httpx(monkeypatch, handler):
    """Route the httpx tier through a MockTransport without recursing."""
    transport = httpx.MockTransport(handler)

    def _factory(**kw):
        kw.pop("transport", None)
        return _REAL_ASYNC_CLIENT(**kw, transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


class _Clock:
    """Fake monotonic clock; sleeping advances it instantly."""

    def __init__(self):
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds
        # Yield so concurrency is observable. Bound to the real asyncio.sleep at
        # import time, since a test may monkeypatch asyncio.sleep with this method.
        await _REAL_SLEEP(0)


def _limiter(clock, **kw):
    return HostRateLimiter(monotonic=clock.monotonic, sleep=clock.sleep, **kw)


class _Adapter(BaseSourceAdapter):
    async def fetch_item_stubs(self):  # pragma: no cover - unused
        return []

    async def fetch_items(self):  # pragma: no cover - unused
        return []


class _Source:
    id = 42
    name = "Fixture Source"
    base_url = "https://example.test"
    rss_url = "https://example.test/feed.xml"


def _adapter():
    return _Adapter(_Source())


def _transport(handler):
    """Build an adapter whose httpx tier is served by a MockTransport."""
    adapter = _adapter()
    calls: list[httpx.Request] = []

    async def _send(target, headers):
        req = httpx.Request("GET", target, headers=headers)
        calls.append(req)
        resp = handler(req)
        return resp.status_code, resp.headers, resp.text, resp.content

    return adapter, _send, calls


async def _fetch_via(send, url, *, accept=AcceptPolicy.ANY_TEXT, limiter=None, clock=None):
    clock = clock or _Clock()
    return await _follow(
        url, policy=accept, headers=dict(source_base._BROWSER_HEADERS), timeout=5.0,
        send=send, limiter=limiter or _limiter(clock), source_label="source 42 'Fixture Source'",
    )


def _responder(mapping):
    """send() built from {url: (status, headers, body, raw)}."""
    seen: list[str] = []

    async def _send(target, headers):
        seen.append(target)
        status, hdrs, body, raw = mapping[target]
        return status, hdrs, body, raw

    return _send, seen


def _html(body, ctype="text/html; charset=utf-8", status=200):
    return status, {"content-type": ctype}, body, body.encode()


# ---------------------------------------------------------------------------
# Challenge classification
# ---------------------------------------------------------------------------


def test_doj_interstitial_is_a_challenge():
    verdict = classify_challenge(DOJ_INTERSTITIAL, content_type="text/html")
    assert verdict
    # Structural markers (the interstitial's own endpoint/elements) are what make
    # this conclusive — the bm-verify token alone is only contextual evidence.
    assert "doj_interstitial" in verdict.signals
    assert "akamai_sec_verify" in verdict.signals


def test_doj_interstitial_matches_the_observed_size_band():
    assert 2000 <= len(DOJ_INTERSTITIAL) <= 3000


def test_ic3_page_with_recaptcha_preconnect_is_not_a_challenge():
    """An inert gstatic recaptcha hint must never disable a healthy source."""
    verdict = classify_challenge(IC3_ARTICLE, content_type="text/html")
    assert not verdict


def test_bare_recaptcha_mention_is_not_a_challenge():
    body = "<html><body>" + ("We use reCAPTCHA to protect our forms. " * 40) + "</body></html>"
    assert not classify_challenge(body, content_type="text/html")


def test_benign_meta_refresh_alone_is_not_a_challenge():
    assert not classify_challenge(BENIGN_META_REFRESH, content_type="text/html")


def test_meta_refresh_plus_second_signal_on_small_body_is_a_challenge():
    body = (
        '<html><head><meta http-equiv="refresh" content="2; url=/x"></head>'
        "<body><noscript>Please enable JavaScript to continue.</noscript></body></html>"
    )
    verdict = classify_challenge(body, content_type="text/html")
    assert verdict
    assert len(verdict.signals) >= 2


def test_corroborating_signals_do_not_fire_on_a_large_body():
    body = (
        '<html><head><meta http-equiv="refresh" content="2; url=/x"></head><body>'
        "<noscript>Please enable JavaScript.</noscript>"
        + ("Genuine article content continues at length. " * 500)
        + "</body></html>"
    )
    assert not classify_challenge(body, content_type="text/html")


def test_xml_body_is_never_classified_as_a_challenge():
    assert not classify_challenge("<rss><item>access denied</item></rss>",
                                  content_type="application/rss+xml")


def test_empty_body_is_not_a_challenge():
    assert not classify_challenge("", content_type="text/html")


# ---------------------------------------------------------------------------
# Content types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ctype", [
    "application/rss+xml", "application/atom+xml", "application/xml",
    "text/xml", "text/xml; charset=utf-8",
])
def test_feed_policy_accepts_xml_equivalents(ctype):
    assert content_type_allowed(ctype, AcceptPolicy.FEED)


def test_feed_policy_rejects_html():
    assert not content_type_allowed("text/html", AcceptPolicy.FEED)


def test_article_policy_rejects_xml():
    assert not content_type_allowed("application/rss+xml", AcceptPolicy.ARTICLE)


def test_missing_content_type_is_permitted():
    assert content_type_allowed("", AcceptPolicy.FEED)


@pytest.mark.parametrize("ctype", ["application/pdf", "application/zip",
                                   "image/png", "application/octet-stream"])
def test_unsupported_types_are_detected(ctype):
    assert is_unsupported_document(ctype)


def test_pdf_magic_bytes_detected_despite_html_content_type():
    assert is_unsupported_document("text/html", PDF_BYTES)


# ---------------------------------------------------------------------------
# Fetch outcomes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_normal_html_article_succeeds():
    send, _ = _responder({"https://example.test/a": _html(ARTICLE_HTML)})
    result = await _fetch_via(send, "https://example.test/a", accept=AcceptPolicy.ARTICLE)
    assert isinstance(result, FetchResult)
    assert result.status == 200
    assert "wire fraud" in result.text


@pytest.mark.asyncio
async def test_challenge_response_raises_rather_than_returning_empty_article():
    send, _ = _responder({"https://x.test/a": _html(DOJ_INTERSTITIAL)})
    with pytest.raises(ChallengeDetected) as exc:
        await _fetch_via(send, "https://x.test/a", accept=AcceptPolicy.ARTICLE)
    assert "doj_interstitial" in exc.value.signals
    assert exc.value.status == 200


@pytest.mark.asyncio
async def test_rss_request_receiving_challenge_html_fails_as_challenge():
    """Not as an empty XML parse — the adapter must know it was blocked."""
    send, _ = _responder({"https://x.test/feed": _html(DOJ_INTERSTITIAL)})
    with pytest.raises(ChallengeDetected):
        await _fetch_via(send, "https://x.test/feed", accept=AcceptPolicy.FEED)


@pytest.mark.asyncio
async def test_rss_request_receiving_ordinary_html_fails_content_type():
    send, _ = _responder({"https://x.test/feed": _html(ORDINARY_HTML_LISTING)})
    with pytest.raises(ContentTypeMismatch) as exc:
        await _fetch_via(send, "https://x.test/feed", accept=AcceptPolicy.FEED)
    assert not isinstance(exc.value, UnsupportedDocument)
    assert exc.value.content_type.startswith("text/html")


@pytest.mark.asyncio
async def test_rss_accepts_declared_xml_content_types():
    for ctype in ("text/xml", "application/xml", "application/rss+xml"):
        send, _ = _responder({"https://x.test/f": _html(RSS_FEED, ctype)})
        result = await _fetch_via(send, "https://x.test/f", accept=AcceptPolicy.FEED)
        assert "<rss" in result.text


@pytest.mark.asyncio
async def test_pdf_detail_raises_unsupported_document():
    send, _ = _responder({
        "https://x.test/doc": (200, {"content-type": "application/pdf"}, "%PDF-1.4", PDF_BYTES)
    })
    with pytest.raises(UnsupportedDocument):
        await _fetch_via(send, "https://x.test/doc", accept=AcceptPolicy.ARTICLE)


@pytest.mark.asyncio
async def test_binary_body_mislabelled_as_html_is_not_decoded_as_article():
    send, _ = _responder({
        "https://x.test/doc": (200, {"content-type": "text/html"}, "%PDF-1.4 garbage", PDF_BYTES)
    })
    with pytest.raises(UnsupportedDocument):
        await _fetch_via(send, "https://x.test/doc", accept=AcceptPolicy.ARTICLE)


@pytest.mark.asyncio
async def test_http_error_raises_permanent_error():
    send, _ = _responder({"https://x.test/gone": _html("nope", status=404)})
    with pytest.raises(PermanentFetchError):
        await _fetch_via(send, "https://x.test/gone")


@pytest.mark.asyncio
async def test_retryable_status_raises_transient_error():
    send, _ = _responder({"https://x.test/x": _html("busy", status=503)})
    with pytest.raises(TransientFetchError):
        await _fetch_via(send, "https://x.test/x")


# ---------------------------------------------------------------------------
# Redirects
# ---------------------------------------------------------------------------


def _redirect(location, status=302):
    return status, {"location": location}, "", b""


@pytest.mark.asyncio
async def test_relative_redirect_resolves_against_the_current_url():
    send, seen = _responder({
        "https://x.test/news/old": _redirect("/news/new"),
        "https://x.test/news/new": _html(ARTICLE_HTML),
    })
    result = await _fetch_via(send, "https://x.test/news/old", accept=AcceptPolicy.ARTICLE)
    assert result.final_url == "https://x.test/news/new"
    assert result.redirects == 1
    assert seen == ["https://x.test/news/old", "https://x.test/news/new"]


@pytest.mark.asyncio
async def test_redirect_loop_is_explicit():
    send, _ = _responder({
        "https://x.test/a": _redirect("/b"),
        "https://x.test/b": _redirect("/a"),
    })
    with pytest.raises(RedirectLoop):
        await _fetch_via(send, "https://x.test/a")


@pytest.mark.asyncio
async def test_maximum_redirects_is_enforced():
    mapping = {f"https://x.test/{i}": _redirect(f"/{i + 1}") for i in range(MAX_REDIRECTS + 3)}
    send, _ = _responder(mapping)
    with pytest.raises(TooManyRedirects):
        await _fetch_via(send, "https://x.test/0")


@pytest.mark.asyncio
async def test_non_http_redirect_scheme_is_rejected():
    send, _ = _responder({"https://x.test/a": _redirect("ftp://x.test/file")})
    with pytest.raises(UnsupportedRedirectScheme):
        await _fetch_via(send, "https://x.test/a")


@pytest.mark.asyncio
async def test_cross_host_redirect_applies_both_host_policies():
    """fbi.gov → justice.gov must be spaced under justice.gov's interval too."""
    clock = _Clock()
    limiter = _limiter(clock, intervals={"www.fbi.gov": 1.0, "www.justice.gov": 10.0})
    send, seen = _responder({
        "https://www.fbi.gov/news/press-releases/x": _redirect("https://www.justice.gov/opa/pr/x"),
        "https://www.justice.gov/opa/pr/x": _html(ARTICLE_HTML),
    })
    # Prime justice.gov so the hop has to wait on its own policy.
    await limiter.acquire("www.justice.gov")
    clock.slept.clear()

    result = await _fetch_via(send, "https://www.fbi.gov/news/press-releases/x",
                              accept=AcceptPolicy.ARTICLE, limiter=limiter, clock=clock)

    assert result.hosts == ("www.fbi.gov", "www.justice.gov")
    assert any(abs(s - 10.0) < 0.01 for s in clock.slept), clock.slept


# ---------------------------------------------------------------------------
# Cross-host headers
# ---------------------------------------------------------------------------


def test_sensitive_headers_are_dropped_across_origins():
    headers = {
        "User-Agent": "HiddenAlerts Research bot@hiddenalerts.com",
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.5",
        "Authorization": "Bearer secret-token",
        "Cookie": "session=abc",
        "X-Api-Key": "k",
    }
    out = safe_redirect_headers(headers, cross_origin=True)
    assert "Authorization" not in out
    assert "Cookie" not in out
    assert "X-Api-Key" not in out


def test_ordinary_public_headers_survive_a_cross_host_redirect():
    headers = dict(source_base._BROWSER_HEADERS) | {"Authorization": "Bearer x"}
    out = safe_redirect_headers(headers, cross_origin=True)
    assert out["User-Agent"] == source_base._BROWSER_HEADERS["User-Agent"]
    assert out["Accept"] == source_base._BROWSER_HEADERS["Accept"]
    assert out["Accept-Language"] == source_base._BROWSER_HEADERS["Accept-Language"]


def test_same_origin_redirect_keeps_all_headers():
    headers = {"User-Agent": "ua", "Authorization": "Bearer x"}
    assert safe_redirect_headers(headers, cross_origin=False) == headers


# ---------------------------------------------------------------------------
# Host limiter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_host_requests_are_spaced():
    clock = _Clock()
    limiter = _limiter(clock, default_interval=2.0)
    assert await limiter.acquire("example.test") == 0.0
    waited = await limiter.acquire("example.test")
    assert waited == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_different_hosts_are_not_globally_serialized():
    clock = _Clock()
    limiter = _limiter(clock, default_interval=5.0)
    await limiter.acquire("a.test")
    assert await limiter.acquire("b.test") == 0.0
    assert clock.slept == []


@pytest.mark.asyncio
async def test_a_slow_host_does_not_block_another_host():
    """The limiter must never hold a global lock while waiting."""
    clock = _Clock()
    limiter = _limiter(clock, intervals={"slow.test": 30.0}, default_interval=0.0)
    await limiter.acquire("slow.test")

    order: list[str] = []

    async def slow():
        await limiter.acquire("slow.test")
        order.append("slow")

    async def fast():
        await limiter.acquire("fast.test")
        order.append("fast")

    task = asyncio.create_task(slow())
    await asyncio.sleep(0)
    await fast()
    await task
    assert order[0] == "fast"


@pytest.mark.asyncio
async def test_host_key_is_case_insensitive():
    clock = _Clock()
    limiter = _limiter(clock, default_interval=3.0)
    await limiter.acquire("Example.TEST")
    assert await limiter.acquire("example.test") == pytest.approx(3.0)


def test_configured_intervals_cover_the_requested_hosts():
    limiter = HostRateLimiter()
    assert limiter.interval_for("www.justice.gov") == 10.0
    assert limiter.interval_for("www.ftc.gov") == 5.0
    assert limiter.interval_for("unknown.test") == 1.0


@pytest.mark.asyncio
async def test_every_redirect_hop_acquires_the_limiter():
    clock = _Clock()
    limiter = _limiter(clock, default_interval=1.0)
    send, _ = _responder({
        "https://x.test/1": _redirect("/2"),
        "https://x.test/2": _redirect("/3"),
        "https://x.test/3": _html(ARTICLE_HTML),
    })
    await _fetch_via(send, "https://x.test/1", accept=AcceptPolicy.ARTICLE,
                     limiter=limiter, clock=clock)
    # Hops 2 and 3 each wait on the same host.
    assert len(clock.slept) == 2


# ---------------------------------------------------------------------------
# Tier behaviour through the adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_challenge_stops_retries_and_skips_every_other_tier(monkeypatch):
    clock = _Clock()
    attempts: list[str] = []

    def handler(request):
        attempts.append("httpx")
        return httpx.Response(200, headers={"content-type": "text/html"}, text=DOJ_INTERSTITIAL)

    adapter, send, _ = _transport(handler)
    monkeypatch.setattr(source_base, "_sync_requests_get",
                        lambda *a, **k: attempts.append("requests") or (200, "text/html", "", ""))

    async def _no_browser(*a, **k):
        attempts.append("playwright")
        return ""

    monkeypatch.setattr(source_base, "_playwright_get", _no_browser)

    _patch_httpx(monkeypatch, handler)

    with pytest.raises(ChallengeDetected):
        await adapter.fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                            limiter=_limiter(clock))

    assert attempts == ["httpx"], attempts
    assert "requests" not in attempts
    assert "playwright" not in attempts


@pytest.mark.asyncio
async def test_unsupported_document_does_not_launch_a_browser(monkeypatch):
    clock = _Clock()
    launched: list[str] = []

    def handler(request):
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=PDF_BYTES)

    adapter, _, _ = _transport(handler)

    async def _no_browser(*a, **k):
        launched.append("playwright")
        return ""

    monkeypatch.setattr(source_base, "_playwright_get", _no_browser)
    _patch_httpx(monkeypatch, handler)

    with pytest.raises(UnsupportedDocument):
        await adapter.fetch("https://x.test/doc", accept=AcceptPolicy.ARTICLE,
                            limiter=_limiter(clock))
    assert launched == []


@pytest.mark.asyncio
async def test_retry_attempts_each_acquire_the_limiter(monkeypatch):
    clock = _Clock()
    limiter = _limiter(clock, default_interval=1.0)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503, headers={"content-type": "text/html"}, text="busy")

    adapter, _, _ = _transport(handler)
    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(asyncio, "sleep", clock.sleep)

    acquired: list[str] = []
    real_acquire = limiter.acquire

    async def _spy(host):
        acquired.append(host)
        return await real_acquire(host)

    limiter.acquire = _spy

    with pytest.raises(TransientFetchError):
        await adapter.fetch("https://x.test/a", retries=3, limiter=limiter)

    # Every attempt is a real network request and must pass the limiter.
    assert calls["n"] == 3
    assert acquired == ["x.test", "x.test", "x.test"]


@pytest.mark.asyncio
async def test_fetch_full_article_propagates_challenge(monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text=DOJ_INTERSTITIAL)

    adapter, _, _ = _transport(handler)
    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(source_base, "host_limiter", _limiter(_Clock()))

    with pytest.raises(ChallengeDetected):
        await adapter.fetch_full_article("https://x.test/a")


@pytest.mark.asyncio
async def test_fetch_full_article_returns_text_and_html(monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text=ARTICLE_HTML)

    adapter, _, _ = _transport(handler)
    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(source_base, "host_limiter", _limiter(_Clock()))

    text, html = await adapter.fetch_full_article("https://x.test/a")
    assert "wire fraud" in text
    assert html.startswith("<!DOCTYPE html>")


def test_source_label_includes_id_and_name():
    assert _adapter()._source_label() == "source 42 'Fixture Source'"


def test_safe_url_strips_the_query_string():
    assert source_base._safe_url("https://x.test/p?token=secret&a=1") == "https://x.test/p"


def test_normalize_host_lowercases_and_trims():
    assert normalize_host("  WWW.Example.TEST ") == "www.example.test"
