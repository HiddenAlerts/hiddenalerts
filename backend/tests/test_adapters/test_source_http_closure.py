"""Security closure for the shared source HTTP boundary.

Legacy numeric address rejection, total URL redaction, explicit browser opt-in,
browser result validation, challenge false-positive reduction in security
articles, and 401/429/403/503 semantics.

Local fixtures and mocked transports only. No network, no real sleeps.
"""
import asyncio

import httpx
import pytest

from app.sources import base as source_base
from app.sources.base import (
    BaseSourceAdapter,
    _follow,
    _safe_url,
    assert_safe_target,
)
from app.sources.host_limiter import HostRateLimiter
from app.sources.http_errors import (
    ChallengeDetected,
    ContentTypeMismatch,
    EmptyContent,
    INVALID_URL,
    PermanentFetchError,
    RateLimitedError,
    SourceFetchError,
    TransientFetchError,
    UnsafeRequestTarget,
    UnsupportedDocument,
    redact_url,
)
from app.sources.response_policy import AcceptPolicy, classify_challenge
from tests.test_adapters.fixtures import (
    ACCESS_DENIED_403,
    ARTICLE_HTML,
    BROWSER_PDF_HTML,
    CLOUDFLARE_CHALLENGE,
    DOJ_INTERSTITIAL,
    PLAIN_FORBIDDEN_403,
    RATE_LIMITED_BODY,
    RATE_LIMITED_WITH_CHALLENGE,
    RSS_FEED,
    large_article_mentioning,
)

_REAL_ASYNC_CLIENT = httpx.AsyncClient
_REAL_SLEEP = asyncio.sleep

# Legacy numeric spellings the OS resolver maps to 127.0.0.1.
LEGACY_LOOPBACK = ["2130706433", "0x7f000001", "017700000001", "127.1", "127.0.1"]


class _Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    async def sleep(self, seconds):
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
    id = 11
    name = "Closure Source"


def _adapter():
    return _Adapter(_Source())


def _patch_httpx(monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def _factory(**kw):
        kw.pop("transport", None)
        return _REAL_ASYNC_CLIENT(**kw, transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


def _all_403(monkeypatch, browser_result=None):
    """Both direct tiers return an ordinary 403; browser returns what is given."""
    def handler(request):
        return httpx.Response(403, headers={"content-type": "text/html"},
                              text=PLAIN_FORBIDDEN_403)

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(
        source_base, "_sync_requests_get",
        lambda *a, **k: (403, {"content-type": "text/html"}, PLAIN_FORBIDDEN_403, b"x"),
    )
    launched: list[str] = []

    async def _browser(*a, **k):
        launched.append("playwright")
        return browser_result or (200, "https://x.test/a", "text/html", ARTICLE_HTML)

    monkeypatch.setattr(source_base, "_playwright_get", _browser)
    return launched


# ---------------------------------------------------------------------------
# 1. Legacy numeric IP representations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("host", LEGACY_LOOPBACK)
@pytest.mark.asyncio
async def test_legacy_numeric_initial_target_issues_no_request(host, monkeypatch):
    issued: list[str] = []

    def handler(request):  # pragma: no cover - must never run
        issued.append(str(request.url))
        return httpx.Response(200, text="x")

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(source_base, "_sync_requests_get",
                        lambda *a, **k: issued.append("requests") or (200, {}, "", b""))

    with pytest.raises(UnsafeRequestTarget) as exc:
        await _adapter().fetch(f"http://{host}/", limiter=_limiter())
    assert "numeric" in str(exc.value)
    assert issued == []


@pytest.mark.parametrize("host", LEGACY_LOOPBACK)
@pytest.mark.asyncio
async def test_legacy_numeric_redirect_target_is_rejected(host):
    sent: list[str] = []

    async def _send(target, headers):
        sent.append(target)
        return 302, {"location": f"http://{host}/x"}, "", b""

    with pytest.raises(UnsafeRequestTarget):
        await _follow("https://x.test/a", policy=AcceptPolicy.ARTICLE, headers={},
                      timeout=5.0, send=_send, limiter=_limiter(), source_label="s")
    assert sent == ["https://x.test/a"], "the unsafe hop must never be requested"


def test_canonical_public_addresses_are_still_accepted():
    assert_safe_target("http://8.8.8.8/a")
    assert_safe_target("https://www.justice.gov/opa/pr/x")


def test_decimal_form_of_a_public_address_is_also_rejected():
    """134744072 is 8.8.8.8 — still ambiguous notation, still refused."""
    with pytest.raises(UnsafeRequestTarget):
        assert_safe_target("http://134744072/a")


def test_canonical_loopback_keeps_its_own_reason():
    with pytest.raises(UnsafeRequestTarget) as exc:
        assert_safe_target("http://127.0.0.1/a")
    assert "non-public" in str(exc.value)


# ---------------------------------------------------------------------------
# 2. Total, centralized URL redaction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url,expected", [
    ("https://user:hunter2@x.test/p?token=SECRET#frag", "https://x.test/p"),
    ("https://x.test:8443/p", "https://x.test:8443/p"),
    ("https://x.test:443/p", "https://x.test/p"),
    ("http://x.test:80/p", "http://x.test/p"),
    ("https://x.test:99999/p", "https://x.test/p"),
    ("https://[::1]/p", "https://[::1]/p"),
    ("", ""),
])
def test_redact_url_shapes(url, expected):
    assert redact_url(url) == expected


@pytest.mark.parametrize("url", [
    "https://[:::1]/p", "https://[not-an-ipv6/p", "not a url at all",
    "://missing-scheme", "https://", "http://@@/x",
])
def test_redact_url_tolerates_malformed_input(url):
    out = redact_url(url)
    assert isinstance(out, str)
    assert out in (INVALID_URL,) or out.startswith(("http://", "https://"))


def test_redact_url_never_raises_on_arbitrary_input():
    for bad in ["\x00", "http://[", "https://x.test:port/p", "%%%", "//"]:
        redact_url(bad)


def test_safe_url_delegates_to_the_single_helper():
    url = "https://user:pw@x.test/p?t=SECRET#f"
    assert _safe_url(url) == redact_url(url) == "https://x.test/p"


@pytest.mark.parametrize("exc_type", [
    SourceFetchError, TransientFetchError, PermanentFetchError, RateLimitedError,
    ChallengeDetected, ContentTypeMismatch, UnsupportedDocument, EmptyContent,
    UnsafeRequestTarget,
])
def test_every_exception_type_redacts_its_url(exc_type):
    exc = exc_type("boom", url="https://user:hunter2@x.test/p?token=SUPERSECRET#f")
    blob = f"{exc.url} {exc} {exc!r}"
    assert "hunter2" not in blob
    assert "SUPERSECRET" not in blob
    assert exc.url == "https://x.test/p"


def test_assert_safe_target_raises_typed_error_on_malformed_url():
    for bad in ["https://[:::1]/p", "not a url", "://x", "http://[", ""]:
        with pytest.raises(UnsafeRequestTarget):
            assert_safe_target(bad)


@pytest.mark.asyncio
async def test_no_secret_reaches_logs_or_exception(caplog, monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text=DOJ_INTERSTITIAL)

    _patch_httpx(monkeypatch, handler)

    # A query token on an otherwise safe URL reaches the fetch path.
    with caplog.at_level("DEBUG", logger="app.sources.base"):
        with pytest.raises(ChallengeDetected) as exc:
            await _adapter().fetch("https://x.test/a?token=SUPERSECRET",
                                   accept=AcceptPolicy.ARTICLE, limiter=_limiter())
    ours = " ".join(r.getMessage() for r in caplog.records if r.name == "app.sources.base")
    assert ours, "the boundary must log the challenge"
    assert "SUPERSECRET" not in ours
    assert "SUPERSECRET" not in f"{exc.value.url} {exc.value}"

    # Credentials are refused before any request, and are still redacted.
    caplog.clear()
    with caplog.at_level("DEBUG", logger="app.sources.base"):
        with pytest.raises(UnsafeRequestTarget) as unsafe:
            await _adapter().fetch("https://u:hunter2@x.test/a?token=SUPERSECRET",
                                   accept=AcceptPolicy.ARTICLE, limiter=_limiter())
    blob = f"{unsafe.value.url} {unsafe.value} " + " ".join(
        r.getMessage() for r in caplog.records
    )
    assert "hunter2" not in blob
    assert "SUPERSECRET" not in blob


# ---------------------------------------------------------------------------
# 3. Explicit browser opt-in
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_browser_is_not_launched_without_opt_in(monkeypatch):
    launched = _all_403(monkeypatch)
    with pytest.raises(PermanentFetchError) as exc:
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               limiter=_limiter())
    assert launched == []
    assert exc.value.status == 403
    assert exc.value.url == "https://x.test/a"


@pytest.mark.asyncio
async def test_browser_runs_only_with_opt_in(monkeypatch):
    launched = _all_403(monkeypatch)
    result = await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                                    allow_browser=True, limiter=_limiter())
    assert launched == ["playwright"]
    assert result.status == 200


def test_browser_opt_in_defaults_to_false():
    import inspect
    assert inspect.signature(BaseSourceAdapter.fetch).parameters["allow_browser"].default is False


def test_no_current_source_enables_browser_mode():
    """No adapter opts in; a future one must justify and test it explicitly."""
    import pathlib
    src_dir = pathlib.Path(source_base.__file__).parent
    offenders = [
        f.name for f in src_dir.glob("*.py")
        if f.name != "base.py" and "allow_browser" in f.read_text()
    ]
    assert offenders == []


def test_browser_opt_in_is_documented():
    import inspect
    doc = inspect.getdoc(BaseSourceAdapter.fetch) or ""
    assert "opt-in" in doc
    assert "justify" in doc


# ---------------------------------------------------------------------------
# 4. Browser result validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_browser_304_is_rejected(monkeypatch):
    _all_403(monkeypatch, (304, "https://x.test/a", "text/html", ARTICLE_HTML))
    with pytest.raises(PermanentFetchError) as exc:
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               allow_browser=True, limiter=_limiter())
    assert exc.value.status == 304


@pytest.mark.asyncio
async def test_browser_302_is_rejected(monkeypatch):
    _all_403(monkeypatch, (302, "https://x.test/a", "text/html", ARTICLE_HTML))
    with pytest.raises(PermanentFetchError):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               allow_browser=True, limiter=_limiter())


@pytest.mark.parametrize("final", ["http://127.0.0.1/x", "http://2130706433/x",
                                   "http://localhost/x", "http://10.0.0.9/x"])
@pytest.mark.asyncio
async def test_browser_unsafe_final_url_is_rejected(final, monkeypatch):
    _all_403(monkeypatch, (200, final, "text/html", ARTICLE_HTML))
    with pytest.raises(UnsafeRequestTarget):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               allow_browser=True, limiter=_limiter())


@pytest.mark.asyncio
async def test_browser_pdf_content_type_is_rejected(monkeypatch):
    _all_403(monkeypatch, (200, "https://x.test/a", "application/pdf", BROWSER_PDF_HTML))
    with pytest.raises(UnsupportedDocument):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               allow_browser=True, limiter=_limiter())


@pytest.mark.asyncio
async def test_browser_xml_is_rejected_when_article_expected(monkeypatch):
    _all_403(monkeypatch, (200, "https://x.test/a", "application/rss+xml", RSS_FEED))
    with pytest.raises(ContentTypeMismatch):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               allow_browser=True, limiter=_limiter())


@pytest.mark.asyncio
async def test_browser_challenge_is_still_rejected(monkeypatch):
    _all_403(monkeypatch, (200, "https://x.test/a", "text/html", DOJ_INTERSTITIAL))
    with pytest.raises(ChallengeDetected):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               allow_browser=True, limiter=_limiter())


@pytest.mark.asyncio
async def test_browser_empty_is_still_rejected(monkeypatch):
    _all_403(monkeypatch, (200, "https://x.test/a", "text/html", "   "))
    with pytest.raises(EmptyContent):
        await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                               allow_browser=True, limiter=_limiter())


@pytest.mark.asyncio
async def test_browser_normal_200_html_is_accepted(monkeypatch):
    _all_403(monkeypatch, (200, "https://x.test/final", "text/html; charset=utf-8", ARTICLE_HTML))
    result = await _adapter().fetch("https://x.test/a", accept=AcceptPolicy.ARTICLE,
                                    allow_browser=True, limiter=_limiter())
    assert result.status == 200
    assert result.final_url == "https://x.test/final"
    assert result.content_type.startswith("text/html")
    assert result.hosts == ("x.test",)


def test_browser_navigation_limitation_is_documented():
    import inspect
    src = inspect.getsource(BaseSourceAdapter._browser_fetch)
    assert "cannot prevent the browser request itself" in src
    assert "out of scope" in src


# ---------------------------------------------------------------------------
# 5. Challenge false positives in security articles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("marker", [
    "AkamaiGHost", "bm-verify", "cf_chl_ctx", "akamai.net/errorpage",
])
def test_large_article_quoting_a_technical_marker_stays_usable(marker):
    body = large_article_mentioning(marker)
    assert len(body) > 15_000
    assert not classify_challenge(body, content_type="text/html", status=200)


@pytest.mark.parametrize("marker", ["AkamaiGHost", "bm-verify"])
def test_small_size_alone_does_not_make_a_technical_marker_conclusive(marker):
    """A short legitimate release is not a verification shell."""
    body = f"<html><body><p>{marker}</p></body></html>"
    assert not classify_challenge(body, content_type="text/html", status=200)


@pytest.mark.parametrize("marker", ["AkamaiGHost", "bm-verify"])
def test_technical_marker_becomes_conclusive_with_corroboration(marker):
    body = (f'<html><head><meta http-equiv="refresh" content="1; url=/x"></head>'
            f"<body><p>{marker} — security check in progress</p></body></html>")
    assert classify_challenge(body, content_type="text/html", status=200)


@pytest.mark.parametrize("marker", ["AkamaiGHost", "bm-verify"])
def test_technical_marker_is_conclusive_at_a_denial_status(marker):
    body = large_article_mentioning(marker)
    assert classify_challenge(body, content_type="text/html", status=403)


def test_technical_marker_with_generic_verify_context_needs_a_shell():
    """Generic verify markup is weak: it only counts without article content."""
    shell = '<html><body><form action="/verify">bm-verify</form></body></html>'
    assert classify_challenge(shell, content_type="text/html", status=200)

    padded = ('<html><body><form action="/verify">bm-verify</form>'
              + ("padding text. " * 1500) + "</body></html>")
    assert not classify_challenge(padded, content_type="text/html", status=200)


@pytest.mark.asyncio
async def test_large_article_quoting_a_marker_fetches_successfully(monkeypatch):
    body = large_article_mentioning("AkamaiGHost")

    async def _send(target, headers):
        return 200, {"content-type": "text/html"}, body, body.encode()

    result = await _follow("https://x.test/a", policy=AcceptPolicy.ARTICLE, headers={},
                           timeout=5.0, send=_send, limiter=_limiter(), source_label="s")
    assert "AkamaiGHost" in result.text


def test_observed_doj_fixture_remains_a_challenge():
    assert classify_challenge(DOJ_INTERSTITIAL, content_type="text/html", status=200)


def test_observed_cloudflare_fixture_remains_a_challenge():
    assert classify_challenge(CLOUDFLARE_CHALLENGE, content_type="text/html", status=403)


# ---------------------------------------------------------------------------
# 6. 401 / 429 / 403 / 503 semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_429_mentioning_automated_access_stays_rate_limited():
    async def _send(target, headers):
        return (429, {"content-type": "text/html", "retry-after": "9"},
                RATE_LIMITED_BODY, RATE_LIMITED_BODY.encode())

    with pytest.raises(RateLimitedError) as exc:
        await _follow("https://x.test/a", policy=AcceptPolicy.ARTICLE, headers={},
                      timeout=5.0, send=_send, limiter=_limiter(), source_label="s")
    assert exc.value.status == 429
    assert exc.value.retry_after == 9.0


@pytest.mark.asyncio
async def test_429_with_a_conclusive_challenge_form_is_a_challenge():
    async def _send(target, headers):
        return (429, {"content-type": "text/html", "retry-after": "9"},
                RATE_LIMITED_WITH_CHALLENGE, RATE_LIMITED_WITH_CHALLENGE.encode())

    with pytest.raises(ChallengeDetected):
        await _follow("https://x.test/a", policy=AcceptPolicy.ARTICLE, headers={},
                      timeout=5.0, send=_send, limiter=_limiter(), source_label="s")


@pytest.mark.asyncio
async def test_ordinary_401_access_denied_is_a_permanent_error():
    async def _send(target, headers):
        return 401, {"content-type": "text/html"}, ACCESS_DENIED_403, ACCESS_DENIED_403.encode()

    with pytest.raises(PermanentFetchError) as exc:
        await _follow("https://x.test/a", policy=AcceptPolicy.ARTICLE, headers={},
                      timeout=5.0, send=_send, limiter=_limiter(), source_label="s")
    assert exc.value.status == 401
    assert not isinstance(exc.value, ChallengeDetected)


def test_401_is_not_in_the_denial_shortcut():
    assert not classify_challenge(ACCESS_DENIED_403, content_type="text/html", status=401)


def test_429_is_not_in_the_denial_shortcut():
    assert not classify_challenge(RATE_LIMITED_BODY, content_type="text/html", status=429)


@pytest.mark.parametrize("status", [403, 503])
def test_short_denial_pages_remain_terminal(status):
    assert classify_challenge(ACCESS_DENIED_403, content_type="text/html", status=status)


def test_plain_forbidden_is_still_not_a_challenge():
    assert not classify_challenge(PLAIN_FORBIDDEN_403, content_type="text/html", status=403)
