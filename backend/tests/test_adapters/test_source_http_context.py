"""Executable-versus-documentation and contextual weak-signal rules.

A security article that *documents* a challenge mechanism must stay usable; a
page that actually *uses* one must not. Weak signals may not be combined across
unrelated regions of a page that has real article content.

Local fixtures only. Every case is exercised through the full fetch path as well
as the classifier, since the boundary is what production calls.
"""
import asyncio

import pytest

from app.sources.base import _follow, _resolve_redirect
from app.sources.host_limiter import HostRateLimiter
from app.sources.http_errors import (
    ChallengeDetected,
    PermanentFetchError,
    RateLimitedError,
    SourceFetchError,
    UnsafeRequestTarget,
)
from app.sources.response_policy import AcceptPolicy, classify_challenge
from tests.test_adapters.fixtures import (
    ACCESS_DENIED_403,
    ARTICLE_ACCESS_DENIED_WITH_FOOTER_CAPTCHA,
    ARTICLE_HTML,
    ARTICLE_WITH_FOOTER_RECAPTCHA,
    CLOUDFLARE_CHALLENGE,
    DOJ_INTERSTITIAL,
    IC3_ARTICLE,
    MALFORMED_LOCATIONS,
    RATE_LIMITED_BODY,
    RATE_LIMITED_WITH_CHALLENGE,
    REAL_CF_FORM,
    REAL_CF_RESOURCE,
    REAL_DOJ_IFRAME,
    REAL_SEC_VERIFY_SCRIPT,
    article_documenting,
    article_with_marker_and_wording,
)

_REAL_SLEEP = asyncio.sleep

DOC_SNIPPETS = [
    "<pre><code>fetch('/_sec/verify')</code></pre>",
    "<pre><code>xhr.open('POST', '/_sec/verify')</code></pre>",
    "<pre><code>fetch('/cdn-cgi/challenge-platform/example')</code></pre>",
    '<a href="/research/doj-interstitial">DOJ interstitial analysis</a>',
    '<div data-example="/_sec/verify">Example endpoint</div>',
]

REAL_MECHANISMS = [
    REAL_SEC_VERIFY_SCRIPT,
    REAL_DOJ_IFRAME,
    REAL_CF_RESOURCE,
    REAL_CF_FORM,
]


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


async def _fetch(body, *, status=200, headers=None, accept=AcceptPolicy.ARTICLE):
    hdrs = {"content-type": "text/html"}
    hdrs.update(headers or {})

    async def _send(target, request_headers):
        return status, hdrs, body, body.encode()

    return await _follow("https://x.test/a", policy=accept, headers={}, timeout=5.0,
                         send=_send, limiter=_limiter(), source_label="s")


# ---------------------------------------------------------------------------
# 1. Documentation is not a mechanism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("snippet", DOC_SNIPPETS, ids=[
    "fetch-in-code", "xhr-in-code", "cf-fetch-in-code", "doc-href", "data-example",
])
def test_documented_mechanism_is_not_a_challenge(snippet):
    assert not classify_challenge(article_documenting(snippet),
                                  content_type="text/html", status=200)


@pytest.mark.parametrize("snippet", DOC_SNIPPETS, ids=[
    "fetch-in-code", "xhr-in-code", "cf-fetch-in-code", "doc-href", "data-example",
])
@pytest.mark.asyncio
async def test_documented_mechanism_fetches_successfully(snippet):
    """The full boundary, not just the classifier — this is what production calls."""
    result = await _fetch(article_documenting(snippet))
    assert result.status == 200
    assert "Analysts documented" in result.text


def test_textarea_content_is_also_treated_as_documentation():
    body = article_documenting('<textarea>fetch("/_sec/verify")</textarea>')
    assert not classify_challenge(body, content_type="text/html", status=200)


def test_html_comment_containing_a_mechanism_is_ignored():
    body = article_documenting('<!-- <iframe src="/x/doj-interstitial.html"></iframe> -->')
    assert not classify_challenge(body, content_type="text/html", status=200)


@pytest.mark.parametrize("markup", REAL_MECHANISMS, ids=[
    "sec-verify-xhr", "doj-iframe", "cf-script-resource", "cf-challenge-form",
])
def test_real_mechanism_is_still_a_challenge(markup):
    assert classify_challenge(markup, content_type="text/html", status=200)


@pytest.mark.parametrize("markup", REAL_MECHANISMS, ids=[
    "sec-verify-xhr", "doj-iframe", "cf-script-resource", "cf-challenge-form",
])
@pytest.mark.asyncio
async def test_real_mechanism_raises_through_the_boundary(markup):
    with pytest.raises(ChallengeDetected):
        await _fetch(markup)


def test_real_mechanism_is_conclusive_even_beside_long_prose():
    body = article_documenting(REAL_DOJ_IFRAME)
    assert classify_challenge(body, content_type="text/html", status=200)


# ---------------------------------------------------------------------------
# 2. Weak signals are not combined across unrelated page regions
# ---------------------------------------------------------------------------


def test_article_about_access_denial_with_footer_captcha_is_usable():
    assert not classify_challenge(ARTICLE_ACCESS_DENIED_WITH_FOOTER_CAPTCHA,
                                  content_type="text/html", status=200)


@pytest.mark.asyncio
async def test_article_about_access_denial_with_footer_captcha_fetches():
    result = await _fetch(ARTICLE_ACCESS_DENIED_WITH_FOOTER_CAPTCHA)
    assert "access denied" in result.text.lower()


@pytest.mark.parametrize("marker,wording", [
    ("bm-verify", "security check"),
    ("AkamaiGHost", "automated access"),
    ("cf_chl_ctx", "unusual traffic"),
])
def test_short_article_with_marker_and_wording_is_usable(marker, wording):
    body = article_with_marker_and_wording(marker, wording)
    assert not classify_challenge(body, content_type="text/html", status=200)


@pytest.mark.parametrize("marker,wording", [
    ("bm-verify", "security check"),
    ("AkamaiGHost", "automated access"),
    ("cf_chl_ctx", "unusual traffic"),
])
@pytest.mark.asyncio
async def test_short_article_with_marker_and_wording_fetches(marker, wording):
    result = await _fetch(article_with_marker_and_wording(marker, wording))
    assert marker.split("_")[0][:6] in result.text


def test_same_signals_without_article_content_remain_a_challenge():
    """Strip the prose and the identical evidence is a verification shell."""
    body = ('<html><head><meta http-equiv="refresh" content="1; url=/x"></head>'
            "<body><h1>bm-verify — security check</h1></body></html>")
    assert classify_challenge(body, content_type="text/html", status=200)


def test_captcha_widget_needs_a_page_without_article_content():
    shell = ('<html><body><h1>Please verify you are human</h1>'
             '<div class="g-recaptcha" data-sitekey="k"></div></body></html>')
    assert classify_challenge(shell, content_type="text/html", status=200)
    assert not classify_challenge(ARTICLE_WITH_FOOTER_RECAPTCHA,
                                  content_type="text/html", status=200)


# ---------------------------------------------------------------------------
# 3. Malformed redirects stay inside the typed boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("location", MALFORMED_LOCATIONS)
def test_malformed_location_raises_a_typed_error(location):
    with pytest.raises(SourceFetchError) as exc:
        _resolve_redirect("https://x.test/a", location)
    assert isinstance(exc.value, UnsafeRequestTarget)
    # The Location value never appears in the message or the attached URL.
    blob = f"{exc.value} {exc.value.url}"
    assert location not in blob
    assert exc.value.url == "https://x.test/a"


@pytest.mark.parametrize("location", MALFORMED_LOCATIONS)
@pytest.mark.asyncio
async def test_malformed_location_never_requests_the_destination(location):
    sent: list[str] = []

    async def _send(target, headers):
        sent.append(target)
        return 302, {"location": location}, "", b""

    with pytest.raises(SourceFetchError):
        await _follow("https://x.test/a", policy=AcceptPolicy.ARTICLE, headers={},
                      timeout=5.0, send=_send, limiter=_limiter(), source_label="s")
    assert sent == ["https://x.test/a"]


@pytest.mark.parametrize("location", MALFORMED_LOCATIONS)
def test_no_value_error_escapes(location):
    try:
        _resolve_redirect("https://x.test/a", location)
    except SourceFetchError:
        pass
    except ValueError as exc:  # pragma: no cover - the defect this guards
        pytest.fail(f"raw ValueError escaped: {exc}")


@pytest.mark.asyncio
async def test_valid_relative_redirect_still_succeeds():
    seen: list[str] = []

    async def _send(target, headers):
        seen.append(target)
        if target == "https://x.test/a/b":
            return 302, {"location": "/c/d"}, "", b""
        return 200, {"content-type": "text/html"}, ARTICLE_HTML, ARTICLE_HTML.encode()

    result = await _follow("https://x.test/a/b", policy=AcceptPolicy.ARTICLE, headers={},
                           timeout=5.0, send=_send, limiter=_limiter(), source_label="s")
    assert result.final_url == "https://x.test/c/d"
    assert seen == ["https://x.test/a/b", "https://x.test/c/d"]


def test_relative_resolution_is_unchanged():
    assert _resolve_redirect("https://x.test/a/b", "/c/d") == "https://x.test/c/d"
    assert _resolve_redirect("https://x.test/a/b", "e") == "https://x.test/a/e"


# ---------------------------------------------------------------------------
# 4. Preserved regressions
# ---------------------------------------------------------------------------


def test_doj_interstitial_regression():
    verdict = classify_challenge(DOJ_INTERSTITIAL, content_type="text/html", status=200)
    assert verdict
    assert "doj_interstitial" in verdict.signals


def test_cloudflare_regression():
    assert classify_challenge(CLOUDFLARE_CHALLENGE, content_type="text/html", status=403)
    assert classify_challenge(CLOUDFLARE_CHALLENGE, content_type="text/html", status=200)


def test_challenge_form_regression():
    assert classify_challenge(RATE_LIMITED_WITH_CHALLENGE, content_type="text/html",
                              status=200)


def test_ic3_recaptcha_preconnect_regression():
    assert not classify_challenge(IC3_ARTICLE, content_type="text/html", status=200)


def test_footer_recaptcha_regression():
    assert not classify_challenge(ARTICLE_WITH_FOOTER_RECAPTCHA, content_type="text/html",
                                  status=200)


@pytest.mark.parametrize("status", [403, 503])
def test_short_denial_fixtures_remain_challenges(status):
    assert classify_challenge(ACCESS_DENIED_403, content_type="text/html", status=status)


@pytest.mark.asyncio
async def test_ordinary_429_remains_rate_limited():
    with pytest.raises(RateLimitedError) as exc:
        await _fetch(RATE_LIMITED_BODY, status=429, headers={"retry-after": "6"})
    assert exc.value.retry_after == 6.0


@pytest.mark.asyncio
async def test_ordinary_401_remains_permanent():
    with pytest.raises(PermanentFetchError) as exc:
        await _fetch(ACCESS_DENIED_403, status=401)
    assert exc.value.status == 401


# ---------------------------------------------------------------------------
# 5. Documentation
# ---------------------------------------------------------------------------


def test_module_documents_its_heuristic_nature():
    from app.sources import response_policy

    doc = response_policy.__doc__ or ""
    assert "heuristics" in doc
    assert "pre" in doc and "code" in doc


def test_size_comment_no_longer_claims_articles_are_large():
    import inspect

    from app.sources import response_policy

    src = inspect.getsource(response_policy)
    assert "8 KB+" not in src
    assert "size is never proof" in src
