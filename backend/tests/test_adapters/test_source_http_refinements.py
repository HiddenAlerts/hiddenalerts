"""Refinements to the shared source HTTP boundary.

Challenge-before-status ordering, body sniffing, empty-content failures, captcha
false-positive protection, browser-result validation, tier-escalation limits,
requests-tier fidelity, redirect hardening and limiter validation.

All responses are local fixtures behind an injected send function or an
httpx.MockTransport. No network, no real sleeps.
"""
import asyncio

import httpx
import pytest

from app.sources import base as source_base
from app.sources.base import (
    BaseSourceAdapter,
    _follow,
    _origin,
    _sync_requests_get,
    safe_redirect_headers,
)
from app.sources.host_limiter import HostRateLimiter, normalize_host
from app.sources.http_errors import (
    ChallengeDetected,
    UnsafeRequestTarget,
    ContentTypeMismatch,
    EmptyContent,
    PermanentFetchError,
    RateLimitedError,
    RedirectLoop,
    TransientFetchError,
    UnsupportedDocument,
    UnsupportedRedirectScheme,
)
from app.sources.response_policy import (
    AcceptPolicy,
    BodyKind,
    classify_challenge,
    sniff_body_kind,
)
from tests.test_adapters.fixtures import (
    ARTICLE_HTML,
    ARTICLE_WITH_FOOTER_RECAPTCHA,
    ARTICLE_WITH_NO_TEXT,
    CAPTCHA_CHALLENGE,
    CLOUDFLARE_CHALLENGE,
    DOJ_INTERSTITIAL,
    EMPTY_RSS_FEED,
    IC3_ARTICLE,
    ORDINARY_HTML_LISTING,
    PDF_BYTES,
    RSS_FEED,
)

_REAL_ASYNC_CLIENT = httpx.AsyncClient
_REAL_SLEEP = asyncio.sleep


class _Clock:
    def __init__(self):
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds
        await _REAL_SLEEP(0)


def _limiter(clock=None, **kw):
    clock = clock or _Clock()
    return HostRateLimiter(monotonic=clock.monotonic, sleep=clock.sleep, **kw)


class _Adapter(BaseSourceAdapter):
    async def fetch_item_stubs(self):  # pragma: no cover
        return []

    async def fetch_items(self):  # pragma: no cover
        return []


class _Source:
    id = 7
    name = "Refinement Source"


def _adapter():
    return _Adapter(_Source())


def _patch_httpx(monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def _factory(**kw):
        kw.pop("transport", None)
        return _REAL_ASYNC_CLIENT(**kw, transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


def _responder(mapping):
    seen: list[str] = []

    async def _send(target, headers):
        seen.append(target)
        return mapping[target]

    return _send, seen


def _resp(body, ctype="text/html; charset=utf-8", status=200, raw=None, **extra):
    headers = {"content-type": ctype} if ctype is not None else {}
    headers.update(extra)
    return status, headers, body, (raw if raw is not None else body.encode())


async def _fetch(send, url, *, accept=AcceptPolicy.ANY_TEXT, limiter=None):
    return await _follow(
        url, policy=accept, headers=dict(source_base._BROWSER_HEADERS), timeout=5.0,
        send=send, limiter=limiter or _limiter(), source_label="source 7",
    )


# ---------------------------------------------------------------------------
# 1. Challenge classified before status handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_403_doj_interstitial_is_a_challenge_not_a_403():
    send, _ = _responder({"https://x.test/a": _resp(DOJ_INTERSTITIAL, status=403)})
    with pytest.raises(ChallengeDetected) as exc:
        await _fetch(send, "https://x.test/a", accept=AcceptPolicy.ARTICLE)
    assert exc.value.status == 403
    assert "akamai_bm_verify" in exc.value.signals


@pytest.mark.asyncio
async def test_http_403_cloudflare_challenge_is_a_challenge():
    send, _ = _responder({"https://x.test/a": _resp(CLOUDFLARE_CHALLENGE, status=403)})
    with pytest.raises(ChallengeDetected):
        await _fetch(send, "https://x.test/a", accept=AcceptPolicy.ARTICLE)


@pytest.mark.asyncio
async def test_http_503_challenge_is_a_challenge_not_a_transient_error():
    send, _ = _responder({"https://x.test/a": _resp(DOJ_INTERSTITIAL, status=503)})
    with pytest.raises(ChallengeDetected):
        await _fetch(send, "https://x.test/a", accept=AcceptPolicy.ARTICLE)


@pytest.mark.asyncio
async def test_ordinary_403_is_still_a_permanent_error():
    send, _ = _responder({"https://x.test/a": _resp("<html><body>Forbidden</body></html>", status=403)})
    with pytest.raises(PermanentFetchError) as exc:
        await _fetch(send, "https://x.test/a", accept=AcceptPolicy.ARTICLE)
    assert exc.value.status == 403


@pytest.mark.asyncio
async def test_pdf_served_with_an_error_status_is_still_unsupported():
    send, _ = _responder({"https://x.test/d": _resp("%PDF", "application/pdf", 403, PDF_BYTES)})
    with pytest.raises(UnsupportedDocument):
        await _fetch(send, "https://x.test/d", accept=AcceptPolicy.ARTICLE)


@pytest.mark.asyncio
async def test_403_challenge_skips_every_fallback_tier(monkeypatch):
    tiers: list[str] = []

    def handler(request):
        tiers.append("httpx")
        return httpx.Response(403, headers={"content-type": "text/html"}, text=DOJ_INTERSTITIAL)

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(source_base, "_sync_requests_get",
                        lambda *a, **k: tiers.append("requests") or (200, {}, "", b""))

    async def _no_browser(*a, **k):
        tiers.append("playwright")
        return 200, "", ""

    monkeypatch.setattr(source_base, "_playwright_get", _no_browser)

    with pytest.raises(ChallengeDetected):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               limiter=_limiter())
    assert tiers == ["httpx"]


# ---------------------------------------------------------------------------
# 2. Body sniffing and missing content types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body,raw,expected", [
    (RSS_FEED, b"", BodyKind.XML),
    (ARTICLE_HTML, b"", BodyKind.HTML),
    ('{"a": 1}', b"", BodyKind.JSON),
    ("   \n\t ", b"", BodyKind.EMPTY),
    ("", b"", BodyKind.EMPTY),
    ("%PDF junk", PDF_BYTES, BodyKind.BINARY),
    ("plain text with no markup", b"", BodyKind.UNKNOWN_TEXT),
])
def test_body_kind_sniffing(body, raw, expected):
    assert sniff_body_kind(body, raw) is expected


@pytest.mark.asyncio
async def test_rss_without_content_type_is_accepted_under_feed():
    send, _ = _responder({"https://x.test/f": _resp(RSS_FEED, ctype=None)})
    result = await _fetch(send, "https://x.test/f", accept=AcceptPolicy.FEED)
    assert "<rss" in result.text


@pytest.mark.asyncio
async def test_html_without_content_type_is_rejected_under_feed():
    send, _ = _responder({"https://x.test/f": _resp(ORDINARY_HTML_LISTING, ctype=None)})
    with pytest.raises(ContentTypeMismatch):
        await _fetch(send, "https://x.test/f", accept=AcceptPolicy.FEED)


@pytest.mark.asyncio
async def test_challenge_html_mislabelled_as_xml_is_still_a_challenge():
    send, _ = _responder({"https://x.test/f": _resp(DOJ_INTERSTITIAL, "application/xml")})
    with pytest.raises(ChallengeDetected):
        await _fetch(send, "https://x.test/f", accept=AcceptPolicy.FEED)


@pytest.mark.asyncio
async def test_ordinary_html_mislabelled_as_xml_is_a_content_mismatch():
    send, _ = _responder({"https://x.test/f": _resp(ORDINARY_HTML_LISTING, "application/xml")})
    with pytest.raises(ContentTypeMismatch) as exc:
        await _fetch(send, "https://x.test/f", accept=AcceptPolicy.FEED)
    assert "html" in str(exc.value)


@pytest.mark.asyncio
async def test_html_content_type_with_pdf_magic_is_unsupported():
    send, _ = _responder({"https://x.test/d": _resp("%PDF-1.4 x", "text/html", 200, PDF_BYTES)})
    with pytest.raises(UnsupportedDocument):
        await _fetch(send, "https://x.test/d", accept=AcceptPolicy.ARTICLE)


# ---------------------------------------------------------------------------
# 3. Empty / unusable content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_successful_body_raises_empty_content():
    send, _ = _responder({"https://x.test/a": _resp("")})
    with pytest.raises(EmptyContent):
        await _fetch(send, "https://x.test/a", accept=AcceptPolicy.ARTICLE)


@pytest.mark.asyncio
async def test_whitespace_only_body_raises_empty_content():
    send, _ = _responder({"https://x.test/a": _resp("   \n\t  ")})
    with pytest.raises(EmptyContent):
        await _fetch(send, "https://x.test/a", accept=AcceptPolicy.ARTICLE)


@pytest.mark.asyncio
async def test_valid_but_empty_rss_feed_is_not_empty_content():
    """A feed with zero items is a valid document, not a failed response."""
    send, _ = _responder({"https://x.test/f": _resp(EMPTY_RSS_FEED, "application/rss+xml")})
    result = await _fetch(send, "https://x.test/f", accept=AcceptPolicy.FEED)
    assert "News Blog" in result.text


@pytest.mark.asyncio
async def test_article_with_no_extractable_text_raises_empty_content(monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"},
                              text=ARTICLE_WITH_NO_TEXT)

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(source_base, "host_limiter", _limiter())

    with pytest.raises(EmptyContent):
        await _adapter().fetch_full_article("https://x.test/a")


@pytest.mark.asyncio
async def test_article_with_text_still_succeeds(monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text=ARTICLE_HTML)

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(source_base, "host_limiter", _limiter())
    text, html = await _adapter().fetch_full_article("https://x.test/a")
    assert "wire fraud" in text


# ---------------------------------------------------------------------------
# 4. CAPTCHA false positives
# ---------------------------------------------------------------------------


def test_article_with_footer_recaptcha_widget_stays_usable():
    """A contact-form widget must not disable a healthy source."""
    assert not classify_challenge(ARTICLE_WITH_FOOTER_RECAPTCHA, content_type="text/html")


def test_ic3_recaptcha_preconnect_regression_still_green():
    assert not classify_challenge(IC3_ARTICLE, content_type="text/html")


def test_captcha_widget_with_verification_wording_is_a_challenge():
    verdict = classify_challenge(CAPTCHA_CHALLENGE, content_type="text/html")
    assert verdict
    assert "captcha_widget" in verdict.signals
    assert "verification_wording" in verdict.signals


def test_bare_sitekey_on_a_small_page_is_not_conclusive():
    body = '<html><body><div class="g-recaptcha" data-sitekey="abc"></div></body></html>'
    assert not classify_challenge(body, content_type="text/html")


@pytest.mark.asyncio
async def test_footer_recaptcha_article_fetches_successfully():
    send, _ = _responder({"https://x.test/a": _resp(ARTICLE_WITH_FOOTER_RECAPTCHA)})
    result = await _fetch(send, "https://x.test/a", accept=AcceptPolicy.ARTICLE)
    assert "grant fraud" in result.text.lower()


# ---------------------------------------------------------------------------
# 5. Playwright result validation
# ---------------------------------------------------------------------------


def _force_browser(monkeypatch, browser_result):
    """Make tiers 1 and 2 return 403 so the browser tier is reached."""
    def handler(request):
        return httpx.Response(403, headers={"content-type": "text/html"}, text="Forbidden")

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(source_base, "_sync_requests_get",
                        lambda *a, **k: (403, {"content-type": "text/html"}, "Forbidden", b"Forbidden"))

    async def _browser(*a, **k):
        return browser_result

    monkeypatch.setattr(source_base, "_playwright_get", _browser)


@pytest.mark.asyncio
async def test_playwright_challenge_result_is_rejected(monkeypatch):
    _force_browser(monkeypatch, (200, "https://x.test/a", DOJ_INTERSTITIAL))
    with pytest.raises(ChallengeDetected):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               limiter=_limiter())


@pytest.mark.asyncio
async def test_playwright_http_error_result_is_rejected(monkeypatch):
    _force_browser(monkeypatch, (404, "https://x.test/a", "<html><body>Not found</body></html>"))
    with pytest.raises(PermanentFetchError) as exc:
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               limiter=_limiter())
    assert "404" in str(exc.value)


@pytest.mark.asyncio
async def test_playwright_empty_result_is_rejected(monkeypatch):
    _force_browser(monkeypatch, (200, "https://x.test/a", "   "))
    with pytest.raises(EmptyContent):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               limiter=_limiter())


@pytest.mark.asyncio
async def test_playwright_preserves_status_and_final_url(monkeypatch):
    _force_browser(monkeypatch, (200, "https://x.test/final-page", ARTICLE_HTML))
    result = await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                                    limiter=_limiter())
    assert result.final_url == "https://x.test/final-page"
    assert result.status == 200
    assert result.hosts == ("x.test",)


@pytest.mark.asyncio
async def test_playwright_result_must_satisfy_the_content_policy(monkeypatch):
    _force_browser(monkeypatch, (200, "https://x.test/a", ORDINARY_HTML_LISTING))
    with pytest.raises(ContentTypeMismatch):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.FEED,
                               limiter=_limiter())


# ---------------------------------------------------------------------------
# 6. Tier escalation limits
# ---------------------------------------------------------------------------


def _tier2_raises(monkeypatch, exc_factory):
    """Tier 1 returns 403; tier 2 raises whatever the factory produces."""
    def handler(request):
        return httpx.Response(403, headers={"content-type": "text/html"}, text="Forbidden")

    _patch_httpx(monkeypatch, handler)
    launched: list[str] = []

    def _requests(*a, **k):
        raise exc_factory()

    async def _browser(*a, **k):
        launched.append("playwright")
        return 200, "", ARTICLE_HTML

    monkeypatch.setattr(source_base, "_sync_requests_get", _requests)
    monkeypatch.setattr(source_base, "_playwright_get", _browser)
    return launched


@pytest.mark.asyncio
async def test_tier2_rate_limit_does_not_launch_playwright(monkeypatch):
    launched = _tier2_raises(monkeypatch, lambda: RateLimitedError("429", status=429))
    with pytest.raises(RateLimitedError):
        await _adapter().fetch("https://x.test/a", limiter=_limiter())
    assert launched == []


@pytest.mark.asyncio
async def test_tier2_redirect_loop_does_not_launch_playwright(monkeypatch):
    launched = _tier2_raises(monkeypatch, lambda: RedirectLoop("loop"))
    with pytest.raises(RedirectLoop):
        await _adapter().fetch("https://x.test/a", limiter=_limiter())
    assert launched == []


@pytest.mark.asyncio
async def test_tier2_empty_content_does_not_launch_playwright(monkeypatch):
    launched = _tier2_raises(monkeypatch, lambda: EmptyContent("empty"))
    with pytest.raises(EmptyContent):
        await _adapter().fetch("https://x.test/a", limiter=_limiter())
    assert launched == []


@pytest.mark.asyncio
async def test_non_403_permanent_error_does_not_reach_tier_two(monkeypatch):
    reached: list[str] = []

    def handler(request):
        return httpx.Response(404, headers={"content-type": "text/html"}, text="gone")

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(source_base, "_sync_requests_get",
                        lambda *a, **k: reached.append("requests") or (200, {}, "", b""))

    with pytest.raises(PermanentFetchError):
        await _adapter().fetch("https://x.test/a", limiter=_limiter())
    assert reached == []


# ---------------------------------------------------------------------------
# 7. Requests tier fidelity
# ---------------------------------------------------------------------------


class _FakeRequestsResponse:
    def __init__(self, status, headers, text, content):
        self.status_code, self.headers, self.text, self.content = status, headers, text, content


class _FakeSession:
    closed = False

    def __init__(self):
        self.headers = {}
        _FakeSession.closed = False
        self.kwargs = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        _FakeSession.closed = True
        return False

    def get(self, url, timeout=None, allow_redirects=None):
        self.kwargs = {"timeout": timeout, "allow_redirects": allow_redirects}
        return _FakeRequestsResponse(
            429,
            {"content-type": "application/pdf", "Retry-After": "7", "Location": "/next"},
            "%PDF-1.4 body",
            PDF_BYTES,
        )


def test_requests_tier_preserves_status_headers_text_and_raw_bytes(monkeypatch):
    monkeypatch.setattr(source_base._requests, "Session", _FakeSession)
    status, headers, text, raw = _sync_requests_get("https://x.test/a", {"User-Agent": "ua"}, 5.0)

    assert status == 429
    assert headers["Retry-After"] == "7"          # Retry-After survives
    assert headers["Location"] == "/next"          # redirect Location survives
    assert raw == PDF_BYTES                        # magic bytes preserved
    assert text == "%PDF-1.4 body"
    assert _FakeSession.closed is True             # session context-managed


def test_requests_tier_disables_automatic_redirects(monkeypatch):
    captured = {}

    class _Sess(_FakeSession):
        def get(self, url, timeout=None, allow_redirects=None):
            captured["allow_redirects"] = allow_redirects
            return _FakeRequestsResponse(200, {"content-type": "text/html"}, "x", b"x")

    monkeypatch.setattr(source_base._requests, "Session", _Sess)
    _sync_requests_get("https://x.test/a", {}, 5.0)
    assert captured["allow_redirects"] is False


@pytest.mark.asyncio
async def test_retry_after_header_is_parsed_and_clamped():
    send, _ = _responder({
        "https://x.test/a": _resp("busy", status=429, **{"retry-after": "5"})
    })
    with pytest.raises(RateLimitedError) as exc:
        await _fetch(send, "https://x.test/a")
    assert exc.value.retry_after == 5.0

    send, _ = _responder({
        "https://x.test/b": _resp("busy", status=429, **{"retry-after": "99999"})
    })
    with pytest.raises(RateLimitedError) as exc:
        await _fetch(send, "https://x.test/b")
    assert exc.value.retry_after == 30.0


# ---------------------------------------------------------------------------
# 8. Redirect hardening
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redirect_without_location_fails_explicitly():
    send, _ = _responder({"https://x.test/a": (302, {"content-type": "text/html"}, "", b"")})
    with pytest.raises(PermanentFetchError) as exc:
        await _fetch(send, "https://x.test/a")
    assert "Location" in str(exc.value)


@pytest.mark.asyncio
async def test_unexpected_304_fails_explicitly():
    send, _ = _responder({"https://x.test/a": (304, {}, "", b"")})
    with pytest.raises(PermanentFetchError) as exc:
        await _fetch(send, "https://x.test/a")
    assert "304" in str(exc.value)


@pytest.mark.asyncio
async def test_https_to_http_downgrade_strips_sensitive_headers():
    captured: list[dict] = []

    async def _send(target, headers):
        captured.append(dict(headers))
        if target == "https://x.test/a":
            return 302, {"location": "http://x.test/b"}, "", b""
        return _resp(ARTICLE_HTML)

    await _follow("https://x.test/a", policy=AcceptPolicy.ARTICLE,
                  headers={**source_base._BROWSER_HEADERS, "Authorization": "Bearer s"},
                  timeout=5.0, send=_send, limiter=_limiter(), source_label="s")

    assert "Authorization" in captured[0]
    assert "Authorization" not in captured[1]


@pytest.mark.asyncio
async def test_port_change_strips_sensitive_headers():
    captured: list[dict] = []

    async def _send(target, headers):
        captured.append(dict(headers))
        if target == "https://x.test/a":
            return 302, {"location": "https://x.test:8443/b"}, "", b""
        return _resp(ARTICLE_HTML)

    await _follow("https://x.test/a", policy=AcceptPolicy.ARTICLE,
                  headers={**source_base._BROWSER_HEADERS, "Cookie": "s=1"},
                  timeout=5.0, send=_send, limiter=_limiter(), source_label="s")

    assert "Cookie" in captured[0]
    assert "Cookie" not in captured[1]


@pytest.mark.asyncio
async def test_same_origin_redirect_keeps_headers():
    captured: list[dict] = []

    async def _send(target, headers):
        captured.append(dict(headers))
        if target == "https://x.test/a":
            return 302, {"location": "https://x.test/b"}, "", b""
        return _resp(ARTICLE_HTML)

    await _follow("https://x.test/a", policy=AcceptPolicy.ARTICLE,
                  headers={**source_base._BROWSER_HEADERS, "Cookie": "s=1"},
                  timeout=5.0, send=_send, limiter=_limiter(), source_label="s")

    assert "Cookie" in captured[1]


@pytest.mark.parametrize("target", [
    "https://user:pass@evil.test/a",
    "http://localhost/a",
    "http://127.0.0.1/a",
    "http://10.0.0.5/a",
    "http://192.168.1.1/a",
    "http://169.254.169.254/latest/meta-data",
    "http://[::1]/a",
    "http://service.internal/a",
])
@pytest.mark.asyncio
async def test_unsafe_redirect_targets_are_rejected(target):
    send, _ = _responder({"https://x.test/a": (302, {"location": target}, "", b"")})
    with pytest.raises(UnsafeRequestTarget):
        await _fetch(send, "https://x.test/a")


@pytest.mark.asyncio
async def test_public_redirect_target_is_still_followed():
    send, _ = _responder({
        "https://www.fbi.gov/a": (302, {"location": "https://www.justice.gov/opa/pr/a"}, "", b""),
        "https://www.justice.gov/opa/pr/a": _resp(ARTICLE_HTML),
    })
    result = await _fetch(send, "https://www.fbi.gov/a", accept=AcceptPolicy.ARTICLE)
    assert result.final_url == "https://www.justice.gov/opa/pr/a"


def test_origin_uses_scheme_host_and_effective_port():
    assert _origin("https://x.test/a") == ("https", "x.test", 443)
    assert _origin("http://x.test/a") == ("http", "x.test", 80)
    assert _origin("https://x.test:443/a") == _origin("https://x.test/a")
    assert _origin("https://x.test:8443/a") != _origin("https://x.test/a")


# ---------------------------------------------------------------------------
# 9/10. Stale logic removed; limiter validation
# ---------------------------------------------------------------------------


def test_is_bot_challenge_helper_is_gone():
    assert not hasattr(source_base, "_is_bot_challenge")


def test_raw_item_stub_doc_no_longer_claims_a_date_filter():
    doc = source_base.RawItemStub.__doc__ or ""
    assert "never gates ingestion" in doc
    assert "publication date" not in doc


@pytest.mark.parametrize("bad", [-1.0, float("inf"), float("nan"), float("-inf")])
def test_invalid_default_intervals_are_rejected(bad):
    with pytest.raises(ValueError):
        HostRateLimiter(default_interval=bad)


@pytest.mark.parametrize("bad", [-0.5, float("inf"), float("nan")])
def test_invalid_configured_intervals_are_rejected(bad):
    with pytest.raises(ValueError):
        HostRateLimiter(intervals={"x.test": bad})


def test_set_interval_validates():
    limiter = HostRateLimiter()
    with pytest.raises(ValueError):
        limiter.set_interval("x.test", -3)


def test_zero_interval_is_permitted():
    assert HostRateLimiter(default_interval=0).interval_for("x.test") == 0


def test_trailing_dns_dot_normalizes():
    assert normalize_host("justice.gov.") == "justice.gov"
    assert normalize_host("WWW.Justice.GOV.") == "www.justice.gov"
    assert HostRateLimiter().interval_for("www.justice.gov.") == 10.0


def test_root_dot_alone_is_preserved():
    assert normalize_host(".") == "."


@pytest.mark.asyncio
async def test_trailing_dot_shares_one_limit():
    clock = _Clock()
    limiter = _limiter(clock, default_interval=4.0, intervals={})
    await limiter.acquire("justice.gov")
    assert await limiter.acquire("justice.gov.") == pytest.approx(4.0)
