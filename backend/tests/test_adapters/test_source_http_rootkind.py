"""Body-kind is decided by the document root, not by nested markup.

A JSON object whose value contains ``<html>`` is JSON; an XML ``<response>``
holding a ``<p>`` is XML; and a token that merely appears inside a longer name is
not a challenge mechanism.

Local fixtures only. Every rule is exercised through the full ``_follow``
boundary as well as ``sniff_body_kind`` directly.
"""
import asyncio

import pytest

from app.sources.base import _follow
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
    DIV_AKAM_LOGO_ANALYSIS,
    DIV_CF_CHALLENGE_ANALYSIS,
    DOJ_INTERSTITIAL,
    FORM_ACTION_CHALLENGE_ENTRY,
    GENERIC_XML,
    HTML_ARTICLE_FRAGMENT,
    HTML_DIV_FRAGMENT,
    JSON_ARRAY_WITH_DIV_STRING,
    JSON_WITH_HTML_STRING,
    JSON_WITH_P_STRING,
    ORDINARY_HTML_LISTING,
    RATE_LIMITED_WITH_CHALLENGE,
    RSS_WITH_DECLARATION,
    XHTML_ARTICLE,
    XHTML_CHALLENGE,
    XML_DOCUMENT_WITH_DIV,
    XML_RESPONSE_WITH_BODY,
    XML_ROOT_WITH_P,
)

_REAL_SLEEP = asyncio.sleep

JSON_BODIES = [JSON_WITH_HTML_STRING, JSON_WITH_P_STRING, JSON_ARRAY_WITH_DIV_STRING]
GENERIC_XML_BODIES = [XML_RESPONSE_WITH_BODY, XML_ROOT_WITH_P, XML_DOCUMENT_WITH_DIV]
BENIGN_NAMES = [
    FORM_ACTION_CHALLENGE_ENTRY, DIV_CF_CHALLENGE_ANALYSIS, DIV_AKAM_LOGO_ANALYSIS,
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


async def _fetch(body, *, content_type, accept, status=200):
    async def _send(target, headers):
        return status, {"content-type": content_type}, body, body.encode()

    return await _follow("https://x.test/a", policy=accept, headers={}, timeout=5.0,
                         send=_send, limiter=_limiter(), source_label="s")


def _page(markup: str) -> str:
    return ("<!DOCTYPE html><html><body><main><article><p>"
            + ("Ordinary article prose continues here. " * 40)
            + f"</p></article></main>{markup}</body></html>")


# ---------------------------------------------------------------------------
# 1. JSON is decided at the top level
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body", JSON_BODIES, ids=["html-string", "p-string", "div-string"])
def test_json_document_with_embedded_markup_is_json(body):
    assert sniff_body_kind(body, b"", "application/json") is BodyKind.JSON


@pytest.mark.parametrize("body", JSON_BODIES, ids=["html-string", "p-string", "div-string"])
def test_json_document_with_embedded_markup_is_json_without_a_content_type(body):
    assert sniff_body_kind(body, b"", "") is BodyKind.JSON


@pytest.mark.parametrize("body", JSON_BODIES, ids=["html-string", "p-string", "div-string"])
@pytest.mark.asyncio
async def test_json_with_markup_is_accepted_under_json_listing(body):
    result = await _fetch(body, content_type="application/json",
                          accept=AcceptPolicy.JSON_LISTING)
    assert result.status == 200
    assert result.text == body


@pytest.mark.parametrize("body", JSON_BODIES, ids=["html-string", "p-string", "div-string"])
@pytest.mark.parametrize("accept", [AcceptPolicy.FEED, AcceptPolicy.ARTICLE])
@pytest.mark.asyncio
async def test_json_with_markup_is_rejected_under_incompatible_policies(body, accept):
    with pytest.raises(ContentTypeMismatch):
        await _fetch(body, content_type="application/json", accept=accept)


def test_non_json_text_starting_with_a_brace_is_not_json():
    """A bounded parse confirms the document rather than trusting the first byte."""
    assert sniff_body_kind("{not json at all", b"", "") is not BodyKind.JSON


def test_declared_json_is_taken_at_its_word():
    assert sniff_body_kind('{"truncated": ', b"", "application/json") is BodyKind.JSON


def test_ordinary_html_is_still_html():
    assert sniff_body_kind(ORDINARY_HTML_LISTING, b"", "text/html") is BodyKind.HTML


@pytest.mark.asyncio
async def test_challenge_html_is_still_classified_as_a_challenge():
    with pytest.raises(ChallengeDetected):
        await _fetch(DOJ_INTERSTITIAL, content_type="text/html",
                     accept=AcceptPolicy.ARTICLE)


# ---------------------------------------------------------------------------
# 2. XML/HTML is decided by the root element
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body", GENERIC_XML_BODIES,
                         ids=["response-body", "root-p", "document-div"])
def test_generic_xml_with_html_like_children_stays_xml(body):
    assert sniff_body_kind(body, b"", "application/xml") is BodyKind.XML


def test_xml_declaration_alone_keeps_a_generic_root_as_xml():
    assert sniff_body_kind(XML_RESPONSE_WITH_BODY, b"", "") is BodyKind.XML


@pytest.mark.parametrize("body", GENERIC_XML_BODIES,
                         ids=["response-body", "root-p", "document-div"])
@pytest.mark.asyncio
async def test_generic_xml_is_accepted_under_feed(body):
    result = await _fetch(body, content_type="application/xml", accept=AcceptPolicy.FEED)
    assert result.text == body


@pytest.mark.parametrize("body", GENERIC_XML_BODIES,
                         ids=["response-body", "root-p", "document-div"])
@pytest.mark.asyncio
async def test_generic_xml_is_rejected_under_article(body):
    with pytest.raises(ContentTypeMismatch):
        await _fetch(body, content_type="application/xml", accept=AcceptPolicy.ARTICLE)


@pytest.mark.parametrize("body", [
    HTML_ARTICLE_FRAGMENT, HTML_DIV_FRAGMENT, "<p>A bare paragraph of text.</p>",
], ids=["article", "div", "p"])
def test_bare_html_fragment_roots_remain_html(body):
    assert sniff_body_kind(body, b"", "text/html") is BodyKind.HTML
    assert sniff_body_kind(body, b"", "") is BodyKind.HTML


@pytest.mark.parametrize("body", [
    HTML_ARTICLE_FRAGMENT, HTML_DIV_FRAGMENT, "<p>A bare paragraph of text.</p>",
], ids=["article", "div", "p"])
@pytest.mark.asyncio
async def test_bare_html_fragments_are_accepted_under_article(body):
    result = await _fetch(body, content_type="text/html", accept=AcceptPolicy.ARTICLE)
    assert result.text == body


def test_generic_catalog_xml_remains_xml():
    assert sniff_body_kind(GENERIC_XML, b"", "application/xml") is BodyKind.XML
    assert sniff_body_kind(GENERIC_XML, b"", "") is BodyKind.XML


@pytest.mark.parametrize("body", [RSS_WITH_DECLARATION, ATOM_WITH_DECLARATION],
                         ids=["rss", "atom"])
def test_feed_roots_remain_xml(body):
    for ctype in ("application/rss+xml", "application/atom+xml", "application/xml", ""):
        assert sniff_body_kind(body, b"", ctype) is BodyKind.XML


@pytest.mark.parametrize("body", [RSS_WITH_DECLARATION, ATOM_WITH_DECLARATION],
                         ids=["rss", "atom"])
@pytest.mark.asyncio
async def test_feeds_are_accepted_under_feed(body):
    result = await _fetch(body, content_type="application/rss+xml",
                          accept=AcceptPolicy.FEED)
    assert result.status == 200


@pytest.mark.parametrize("ctype", ["application/xml", "application/xhtml+xml", "text/html"])
def test_xml_declared_xhtml_challenge_is_html(ctype):
    assert sniff_body_kind(XHTML_CHALLENGE, b"", ctype) is BodyKind.HTML


@pytest.mark.parametrize("ctype", ["application/xml", "application/xhtml+xml"])
@pytest.mark.parametrize("accept", [AcceptPolicy.FEED, AcceptPolicy.ARTICLE])
@pytest.mark.asyncio
async def test_xml_declared_xhtml_challenge_raises(ctype, accept):
    with pytest.raises(ChallengeDetected):
        await _fetch(XHTML_CHALLENGE, content_type=ctype, accept=accept)


@pytest.mark.asyncio
async def test_normal_xhtml_article_remains_html_and_usable():
    assert sniff_body_kind(XHTML_ARTICLE, b"", "application/xhtml+xml") is BodyKind.HTML
    result = await _fetch(XHTML_ARTICLE, content_type="application/xhtml+xml",
                          accept=AcceptPolicy.ARTICLE)
    assert "indictment" in result.text


@pytest.mark.asyncio
async def test_challenge_html_mislabelled_as_xml_still_raises():
    with pytest.raises(ChallengeDetected):
        await _fetch(DOJ_INTERSTITIAL, content_type="application/xml",
                     accept=AcceptPolicy.FEED)


def test_nested_markup_does_not_decide_the_kind():
    """The old body-wide scan would have called both of these HTML."""
    assert sniff_body_kind("<catalog><body>x</body></catalog>", b"", "application/xml") is BodyKind.XML
    assert sniff_body_kind('{"v":"<head>x</head>"}', b"", "application/json") is BodyKind.JSON


# ---------------------------------------------------------------------------
# 3. Structural tokens match at their own boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("markup", BENIGN_NAMES,
                         ids=["challenge-form-entry", "cf-challenge-analysis",
                              "akam-logo-analysis"])
def test_names_merely_containing_a_token_are_usable(markup):
    assert not classify_challenge(_page(markup), content_type="text/html", status=200)


@pytest.mark.parametrize("markup", BENIGN_NAMES,
                         ids=["challenge-form-entry", "cf-challenge-analysis",
                              "akam-logo-analysis"])
@pytest.mark.asyncio
async def test_names_merely_containing_a_token_fetch_successfully(markup):
    result = await _fetch(_page(markup), content_type="text/html",
                          accept=AcceptPolicy.ARTICLE)
    assert "Ordinary article prose" in result.text


@pytest.mark.parametrize("markup", BENIGN_NAMES,
                         ids=["challenge-form-entry", "cf-challenge-analysis",
                              "akam-logo-analysis"])
def test_names_merely_containing_a_token_are_usable_on_a_shell_too(markup):
    """Boundaries, not page size, are what reject these."""
    assert not classify_challenge(f"<html><body>{markup}</body></html>",
                                  content_type="text/html", status=200)


@pytest.mark.parametrize("markup", [
    '<iframe src="https://x.test/o/doj-interstitial.html"></iframe>',
    '<script>xhr.open("POST", "/_sec/verify?p=1", false);</script>',
    '<script>document.getElementById("akam-logo").onload = go;</script>',
    '<div class="cf-browser-verification"></div>',
    '<script src="/cdn-cgi/challenge-platform/h/b/orchestrate"></script>',
    '<form action="/cdn-cgi/challenge-platform/verify"></form>',
    '<form id="challenge-form" action="/x"></form>',
    '<form class="captcha-form" action="/x"></form>',
    '<form id="verification-form" action="/x"></form>',
], ids=["doj-iframe", "sec-verify-xhr", "akam-logo-dom", "cf-class",
        "cf-resource", "cf-form-action", "challenge-form", "captcha-form",
        "verification-form"])
def test_exact_known_tokens_remain_conclusive(markup):
    assert classify_challenge(f"<html><body>{markup}</body></html>",
                              content_type="text/html", status=200)


@pytest.mark.parametrize("markup", [
    '<iframe src="https://x.test/o/doj-interstitial.html"></iframe>',
    '<script>xhr.open("POST", "/_sec/verify?p=1", false);</script>',
    '<form id="challenge-form" action="/x"></form>',
], ids=["doj-iframe", "sec-verify-xhr", "challenge-form"])
def test_exact_known_tokens_are_conclusive_beside_real_prose(markup):
    assert classify_challenge(_page(markup), content_type="text/html", status=200)


# ---------------------------------------------------------------------------
# Preserved regressions
# ---------------------------------------------------------------------------


def test_doj_regression():
    assert classify_challenge(DOJ_INTERSTITIAL, content_type="text/html", status=200)


def test_cloudflare_regression():
    assert classify_challenge(CLOUDFLARE_CHALLENGE, content_type="text/html", status=403)
    assert classify_challenge(CLOUDFLARE_CHALLENGE, content_type="text/html", status=200)


def test_challenge_form_fixture_regression():
    assert classify_challenge(RATE_LIMITED_WITH_CHALLENGE, content_type="text/html",
                              status=200)
