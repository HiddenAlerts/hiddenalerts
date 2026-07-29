"""Challenge-signal decision rules for the shared source HTTP boundary.

Size is not evidence, technical tokens are not evidence on their own, structural
evidence requires a mechanism actually being used, and 429 keeps its rate-limit
semantics unless a real challenge mechanism is present.

Local fixtures only. No network.
"""
import asyncio

import pytest

from app.sources import base as source_base
from app.sources.base import _follow
from app.sources.host_limiter import HostRateLimiter
from app.sources.http_errors import ChallengeDetected, PermanentFetchError, RateLimitedError
from app.sources.response_policy import (
    SMALL_BODY_BYTES,
    AcceptPolicy,
    classify_challenge,
)
from tests.test_adapters.fixtures import (
    ACCESS_DENIED_403,
    ARTICLE_WITH_FOOTER_RECAPTCHA,
    CLOUDFLARE_CHALLENGE,
    DOJ_INTERSTITIAL,
    IC3_ARTICLE,
    PLAIN_FORBIDDEN_403,
    RATE_LIMITED_BODY,
    RATE_LIMITED_WITH_CHALLENGE,
    large_article_quoting_mechanism,
    small_article_mentioning,
)

TECHNICAL_MARKERS = ["bm-verify", "AkamaiGHost", "cf_chl_ctx", "akamai.net/errorpage"]
MECHANISM_TOKENS = [
    "/_sec/verify", "doj-interstitial", "cf-challenge",
    "/cdn-cgi/challenge-platform", "akam-logo",
]

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


async def _fetch_body(body, *, status=200, headers=None, accept=AcceptPolicy.ARTICLE):
    hdrs = {"content-type": "text/html"}
    hdrs.update(headers or {})

    async def _send(target, request_headers):
        return status, hdrs, body, body.encode()

    return await _follow("https://x.test/a", policy=accept, headers={}, timeout=5.0,
                         send=_send, limiter=_limiter(), source_label="s")


# ---------------------------------------------------------------------------
# 1. Small size is not proof
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("marker", TECHNICAL_MARKERS)
def test_small_legitimate_article_with_a_technical_marker_stays_usable(marker):
    body = small_article_mentioning(marker)
    assert len(body) < SMALL_BODY_BYTES, "fixture must be in the short-release range"
    assert not classify_challenge(body, content_type="text/html", status=200)


def test_short_release_is_in_the_audited_fincen_size_range():
    """FinCEN detail pages extracted 912–2960 chars in the source audit."""
    body = small_article_mentioning("bm-verify")
    assert 900 <= len(source_base.extract_text_from_html(body)) <= 3200


@pytest.mark.parametrize("marker", TECHNICAL_MARKERS)
@pytest.mark.asyncio
async def test_small_article_with_a_technical_marker_fetches_successfully(marker):
    result = await _fetch_body(small_article_mentioning(marker))
    assert marker.split("/")[0][:6].lower() in result.text.lower()


@pytest.mark.parametrize("marker", TECHNICAL_MARKERS)
def test_technical_marker_is_conclusive_at_a_denial_status(marker):
    assert classify_challenge(small_article_mentioning(marker),
                              content_type="text/html", status=403)
    assert classify_challenge(small_article_mentioning(marker),
                              content_type="text/html", status=503)


def test_technical_marker_with_corroboration_on_a_small_body_is_conclusive():
    body = ('<html><head><meta http-equiv="refresh" content="2; url=/x"></head>'
            "<body>bm-verify — please wait while we verify your browser</body></html>")
    assert classify_challenge(body, content_type="text/html", status=200)


def test_two_technical_markers_on_a_short_document_are_conclusive():
    body = "<html><body><p>AkamaiGHost bm-verify</p></body></html>"
    assert classify_challenge(body, content_type="text/html", status=200)


def test_technical_marker_in_challenge_markup_is_conclusive_at_any_size():
    body = ('<html><body><form action="/verify">bm-verify</form>'
            + ("padding text. " * 2000) + "</body></html>")
    assert len(body) > SMALL_BODY_BYTES
    assert classify_challenge(body, content_type="text/html", status=200)


# ---------------------------------------------------------------------------
# 2. 429 semantics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body", [
    "<html><body>bm-verify</body></html>",
    "<html><body>AkamaiGHost</body></html>",
    "<html><body>cf_chl_ctx</body></html>",
    RATE_LIMITED_BODY,
])
@pytest.mark.asyncio
async def test_429_without_a_mechanism_stays_rate_limited(body):
    with pytest.raises(RateLimitedError) as exc:
        await _fetch_body(body, status=429, headers={"retry-after": "11"})
    assert exc.value.status == 429
    assert exc.value.retry_after == 11.0


@pytest.mark.asyncio
async def test_429_with_a_challenge_form_is_a_challenge():
    with pytest.raises(ChallengeDetected):
        await _fetch_body(RATE_LIMITED_WITH_CHALLENGE, status=429,
                          headers={"retry-after": "11"})


@pytest.mark.asyncio
async def test_429_with_a_sec_verify_mechanism_is_a_challenge():
    body = ('<html><body><script>xhr.open("POST", "/_sec/verify?p=1", false);'
            "</script></body></html>")
    with pytest.raises(ChallengeDetected):
        await _fetch_body(body, status=429, headers={"retry-after": "11"})


@pytest.mark.parametrize("marker", TECHNICAL_MARKERS)
def test_429_technical_markers_are_never_conclusive(marker):
    body = f"<html><body>{marker}</body></html>"
    assert not classify_challenge(body, content_type="text/html", status=429)


def test_429_corroborating_wording_is_never_conclusive():
    body = ('<html><head><meta http-equiv="refresh" content="1; url=/x"></head>'
            "<body>automated access detected, security check</body></html>")
    assert not classify_challenge(body, content_type="text/html", status=429)


# ---------------------------------------------------------------------------
# 3. Structural signals need mechanism context
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", MECHANISM_TOKENS)
def test_large_article_quoting_a_mechanism_token_stays_usable(token):
    body = large_article_quoting_mechanism(token)
    assert len(body) > SMALL_BODY_BYTES
    assert not classify_challenge(body, content_type="text/html", status=200)


@pytest.mark.parametrize("token", MECHANISM_TOKENS)
@pytest.mark.asyncio
async def test_large_article_quoting_a_mechanism_token_fetches(token):
    result = await _fetch_body(large_article_quoting_mechanism(token))
    assert token in result.text


@pytest.mark.parametrize("markup", [
    '<form action="/_sec/verify"><button>Go</button></form>',
    '<script>xhr.open("POST", "/_sec/verify", false);</script>',
    '<iframe src="https://x.test/objects/doj-interstitial.html"></iframe>',
    '<div class="cf-browser-verification"></div>',
    '<script src="/cdn-cgi/challenge-platform/h/b/orchestrate"></script>',
    '<img id="akam-logo" src="/logo.png">',
    '<script>document.getElementById("akam-logo").onload = go;</script>',
    '<form id="challenge-form" action="/verify"></form>',
])
def test_mechanism_context_is_still_conclusive(markup):
    body = f"<html><body>{markup}</body></html>"
    assert classify_challenge(body, content_type="text/html", status=200)


def test_mechanism_context_is_conclusive_even_in_a_large_document():
    body = ('<html><body><iframe src="/x/doj-interstitial.html"></iframe>'
            + ("padding text. " * 2000) + "</body></html>")
    assert len(body) > SMALL_BODY_BYTES
    assert classify_challenge(body, content_type="text/html", status=200)


# ---------------------------------------------------------------------------
# Preserved regressions
# ---------------------------------------------------------------------------


def test_observed_doj_interstitial_remains_a_challenge():
    verdict = classify_challenge(DOJ_INTERSTITIAL, content_type="text/html", status=200)
    assert verdict
    assert "doj_interstitial" in verdict.signals


def test_observed_cloudflare_fixture_remains_a_challenge():
    assert classify_challenge(CLOUDFLARE_CHALLENGE, content_type="text/html", status=403)
    assert classify_challenge(CLOUDFLARE_CHALLENGE, content_type="text/html", status=200)


def test_challenge_form_fixture_remains_a_challenge():
    assert classify_challenge(RATE_LIMITED_WITH_CHALLENGE, content_type="text/html", status=200)


def test_ic3_recaptcha_preconnect_regression():
    assert not classify_challenge(IC3_ARTICLE, content_type="text/html", status=200)


def test_footer_recaptcha_regression():
    assert not classify_challenge(ARTICLE_WITH_FOOTER_RECAPTCHA, content_type="text/html",
                                  status=200)


# ---------------------------------------------------------------------------
# 4. Denial behaviour stays narrow
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [403, 503])
def test_short_denial_pages_remain_terminal(status):
    assert classify_challenge(ACCESS_DENIED_403, content_type="text/html", status=status)


@pytest.mark.asyncio
async def test_plain_forbidden_keeps_ordinary_403_behaviour():
    with pytest.raises(PermanentFetchError) as exc:
        await _fetch_body(PLAIN_FORBIDDEN_403, status=403)
    assert exc.value.status == 403


@pytest.mark.asyncio
async def test_ordinary_401_remains_a_permanent_error():
    with pytest.raises(PermanentFetchError) as exc:
        await _fetch_body(ACCESS_DENIED_403, status=401)
    assert exc.value.status == 401


def test_denial_statuses_were_not_broadened():
    from app.sources.response_policy import _DENIAL_STATUSES

    assert _DENIAL_STATUSES == frozenset({403, 503})


# ---------------------------------------------------------------------------
# 5. Cleanup
# ---------------------------------------------------------------------------


def test_conclusive_errors_tuple_is_gone():
    assert not hasattr(source_base, "_CONCLUSIVE_ERRORS")


def test_requests_transport_error_carries_a_redacted_url(monkeypatch):
    import requests as _requests

    class _Sess:
        headers: dict = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            raise _requests.exceptions.ConnectTimeout("nope")

    monkeypatch.setattr(source_base._requests, "Session", _Sess)
    from app.sources.http_errors import TransientFetchError

    with pytest.raises(TransientFetchError) as exc:
        source_base._sync_requests_get("https://u:pw@x.test/a?token=SECRET", {}, 1.0)

    assert exc.value.url == "https://x.test/a"
    assert "SECRET" not in f"{exc.value} {exc.value.url}"
    assert "pw" not in exc.value.url
