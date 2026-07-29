"""Precision rules for the response classifier.

Only executable scripts count as JavaScript, only known identifiers count as
verification forms, generic verify-named assets are weak evidence, and an XML
declaration does not make an XHTML document a feed.

Local fixtures only. Every rule is exercised through the full fetch boundary as
well as the classifier.
"""
import asyncio

import pytest

from app.sources.base import _follow, _is_noncanonical_numeric_host
from app.sources.host_limiter import HostRateLimiter
from app.sources.http_errors import ChallengeDetected, ContentTypeMismatch
from app.sources.response_policy import (
    AcceptPolicy,
    BodyKind,
    classify_challenge,
    sniff_body_kind,
)
from tests.test_adapters.fixtures import (
    ATOM_WITH_DECLARATION,
    CLOUDFLARE_CHALLENGE,
    DOJ_INTERSTITIAL,
    GENERIC_XML,
    JSONLD_WITH_CALLS,
    LEGITIMATE_CHALLENGE_ENTRY_FORM,
    RATE_LIMITED_WITH_CHALLENGE,
    RSS_WITH_DECLARATION,
    XHTML_ARTICLE,
    XHTML_CHALLENGE,
    article_with_data_script,
    article_with_executable_script,
    article_with_generic_asset,
)

_REAL_SLEEP = asyncio.sleep

CHALLENGE_CALLS = [
    "fetch('/_sec/verify')",
    "xhr.open('POST', '/_sec/verify')",
    "fetch('/cdn-cgi/challenge-platform/example')",
]

NON_EXECUTABLE_TYPES = [
    "application/ld+json", "application/json", "application/manifest+json",
    "text/template", "text/x-handlebars-template",
]

EXECUTABLE_TYPES = [
    "", "text/javascript", "application/javascript", "text/ecmascript",
    "application/ecmascript", "module",
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


async def _fetch(body, *, content_type="text/html", status=200,
                 accept=AcceptPolicy.ARTICLE):
    async def _send(target, headers):
        return status, {"content-type": content_type}, body, body.encode()

    return await _follow("https://x.test/a", policy=accept, headers={}, timeout=5.0,
                         send=_send, limiter=_limiter(), source_label="s")


# ---------------------------------------------------------------------------
# 1. Only executable scripts are JavaScript
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("script_type", NON_EXECUTABLE_TYPES)
def test_non_executable_script_data_is_not_a_mechanism(script_type):
    body = article_with_data_script(script_type, JSONLD_WITH_CALLS)
    assert not classify_challenge(body, content_type="text/html", status=200)


@pytest.mark.parametrize("script_type", NON_EXECUTABLE_TYPES)
@pytest.mark.asyncio
async def test_non_executable_script_data_fetches_successfully(script_type):
    result = await _fetch(article_with_data_script(script_type, JSONLD_WITH_CALLS))
    assert result.status == 200


@pytest.mark.parametrize("call", CHALLENGE_CALLS)
def test_jsonld_article_body_quoting_a_call_is_usable(call):
    body = article_with_data_script("application/ld+json",
                                    f'{{"articleBody":"the demo ran {call}"}}')
    assert not classify_challenge(body, content_type="text/html", status=200)


@pytest.mark.parametrize("call", CHALLENGE_CALLS)
def test_same_call_in_an_executable_script_is_a_challenge(call):
    assert classify_challenge(article_with_executable_script(call),
                              content_type="text/html", status=200)


@pytest.mark.parametrize("call", CHALLENGE_CALLS)
@pytest.mark.asyncio
async def test_executable_call_raises_through_the_boundary(call):
    with pytest.raises(ChallengeDetected):
        await _fetch(article_with_executable_script(call))


@pytest.mark.parametrize("script_type", EXECUTABLE_TYPES)
def test_declared_executable_types_are_scanned(script_type):
    attr = f' type="{script_type}"' if script_type else ""
    body = (f"<html><body><script{attr}>fetch('/_sec/verify')</script>"
            "</body></html>")
    assert classify_challenge(body, content_type="text/html", status=200)


def test_script_type_parameters_are_ignored():
    body = ('<html><body><script type="text/javascript; charset=utf-8">'
            "fetch('/_sec/verify')</script></body></html>")
    assert classify_challenge(body, content_type="text/html", status=200)


# ---------------------------------------------------------------------------
# 2. Challenge-form identifiers are precise
# ---------------------------------------------------------------------------


def test_legitimate_challenge_entry_form_is_usable():
    assert not classify_challenge(LEGITIMATE_CHALLENGE_ENTRY_FORM,
                                  content_type="text/html", status=200)


@pytest.mark.asyncio
async def test_legitimate_challenge_entry_form_fetches():
    result = await _fetch(LEGITIMATE_CHALLENGE_ENTRY_FORM)
    assert "challenge are open" in result.text


@pytest.mark.parametrize("name", [
    "challenge-entry-form", "photo-challenge", "challenger",
    "my-challenge-formatter", "challenge2026",
])
def test_unrelated_form_names_do_not_match(name):
    body = (f'<html><body><main><article><p>{"prose " * 200}</p></article></main>'
            f'<form id="{name}" action="/submit"></form></body></html>')
    assert not classify_challenge(body, content_type="text/html", status=200)


@pytest.mark.parametrize("name", [
    "challenge-form", "cf-challenge-form", "cf-browser-verification",
    "captcha-form", "verification-form",
])
def test_known_verification_form_identifiers_still_match(name):
    body = f'<html><body><form id="{name}" action="/x"></form></body></html>'
    assert classify_challenge(body, content_type="text/html", status=200)


def test_known_identifier_matches_as_a_class_too():
    body = '<html><body><form class="a challenge-form b" action="/x"></form></body></html>'
    assert classify_challenge(body, content_type="text/html", status=200)


# ---------------------------------------------------------------------------
# 3. Generic verify assets are weak evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("marker,asset", [
    ("bm-verify", "/assets/verify-signature.js"),
    ("cf_chl_ctx", "/scripts/challenge-helper.js"),
    ("AkamaiGHost", "/static/js/verify-email.js"),
])
def test_article_with_an_unrelated_verify_asset_is_usable(marker, asset):
    assert not classify_challenge(article_with_generic_asset(marker, asset),
                                  content_type="text/html", status=200)


@pytest.mark.parametrize("marker,asset", [
    ("bm-verify", "/assets/verify-signature.js"),
    ("cf_chl_ctx", "/scripts/challenge-helper.js"),
])
@pytest.mark.asyncio
async def test_article_with_an_unrelated_verify_asset_fetches(marker, asset):
    result = await _fetch(article_with_generic_asset(marker, asset))
    assert marker.split("_")[0][:6] in result.text


@pytest.mark.parametrize("marker,asset", [
    ("bm-verify", "/assets/verify-signature.js"),
    ("cf_chl_ctx", "/scripts/challenge-helper.js"),
])
def test_shell_with_the_same_evidence_remains_a_challenge(marker, asset):
    shell = f'<html><head><script src="{asset}"></script></head><body>{marker}</body></html>'
    assert classify_challenge(shell, content_type="text/html", status=200)


def test_denial_status_still_wins_over_article_content():
    body = article_with_generic_asset("bm-verify", "/assets/verify-signature.js")
    assert classify_challenge(body, content_type="text/html", status=403)


# ---------------------------------------------------------------------------
# 4. XML / XHTML precedence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ctype,expected", [
    ("application/xml", BodyKind.HTML),
    ("application/xhtml+xml", BodyKind.HTML),
    ("text/html", BodyKind.HTML),
    ("", BodyKind.HTML),
])
def test_xhtml_after_an_xml_declaration_is_html(ctype, expected):
    assert sniff_body_kind(XHTML_CHALLENGE, b"", ctype) is expected


@pytest.mark.parametrize("ctype", ["application/xml", "application/xhtml+xml"])
def test_xhtml_challenge_is_detected(ctype):
    assert classify_challenge(XHTML_CHALLENGE, content_type=ctype,
                              body_kind=sniff_body_kind(XHTML_CHALLENGE, b"", ctype),
                              status=200)


@pytest.mark.parametrize("ctype", ["application/xml", "application/xhtml+xml"])
@pytest.mark.asyncio
async def test_xhtml_challenge_cannot_be_returned_as_a_feed(ctype):
    """The boundary must raise a challenge, not hand back an empty parse."""
    with pytest.raises(ChallengeDetected):
        await _fetch(XHTML_CHALLENGE, content_type=ctype, accept=AcceptPolicy.FEED)


@pytest.mark.asyncio
async def test_normal_xhtml_article_is_accepted_under_article():
    result = await _fetch(XHTML_ARTICLE, content_type="application/xhtml+xml")
    assert "indictment" in result.text


@pytest.mark.asyncio
async def test_xhtml_article_is_rejected_under_feed():
    with pytest.raises(ContentTypeMismatch):
        await _fetch(XHTML_ARTICLE, content_type="application/xhtml+xml",
                     accept=AcceptPolicy.FEED)


@pytest.mark.parametrize("body", [RSS_WITH_DECLARATION, ATOM_WITH_DECLARATION])
def test_feed_roots_after_a_declaration_stay_xml(body):
    assert sniff_body_kind(body, b"", "application/rss+xml") is BodyKind.XML
    assert sniff_body_kind(body, b"", "") is BodyKind.XML


@pytest.mark.parametrize("body", [RSS_WITH_DECLARATION, ATOM_WITH_DECLARATION])
@pytest.mark.asyncio
async def test_declared_feeds_are_accepted_under_feed(body):
    result = await _fetch(body, content_type="application/rss+xml",
                          accept=AcceptPolicy.FEED)
    assert result.status == 200


def test_generic_xml_remains_xml():
    assert sniff_body_kind(GENERIC_XML, b"", "application/xml") is BodyKind.XML
    assert sniff_body_kind(GENERIC_XML, b"", "") is BodyKind.XML


@pytest.mark.asyncio
async def test_generic_xml_still_accepted_under_feed():
    result = await _fetch(GENERIC_XML, content_type="application/xml",
                          accept=AcceptPolicy.FEED)
    assert "<catalog>" in result.text


# ---------------------------------------------------------------------------
# 5. Cleanup and preserved regressions
# ---------------------------------------------------------------------------


def test_numeric_host_helper_returns_a_bool():
    for host in ("2130706433", "127.0.0.1", "www.justice.gov"):
        assert isinstance(_is_noncanonical_numeric_host(host), bool)


def test_scan_view_documents_the_absence_of_a_raw_text_fallback():
    from app.sources.response_policy import _ScanView

    doc = _ScanView.__doc__ or ""
    assert "no" in doc.lower() and "raw-text fallback" in doc


def test_unparsable_document_reports_no_structural_signals():
    from app.sources.response_policy import _ScanView, _structural_signals

    view = _ScanView("<html>")
    view.parsed = False
    view.soup = None
    assert _structural_signals(view) == ()


def test_doj_interstitial_regression():
    assert classify_challenge(DOJ_INTERSTITIAL, content_type="text/html", status=200)


def test_cloudflare_regression():
    assert classify_challenge(CLOUDFLARE_CHALLENGE, content_type="text/html", status=403)


def test_challenge_form_fixture_regression():
    assert classify_challenge(RATE_LIMITED_WITH_CHALLENGE, content_type="text/html",
                              status=200)
