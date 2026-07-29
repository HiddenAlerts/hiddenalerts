"""Classification rules for source responses: challenge detection and content types.

Pure functions, no IO. Two jobs:

* decide whether a body is an anti-bot verification page rather than content;
* decide whether a response's content type is one the caller asked for.

The challenge rules are deliberately two-tier. A handful of markers are specific
enough to be conclusive on their own; everything else is only corroborating and
needs a second signal on a small body. That is what keeps a real article carrying
an inert ``gstatic.com/recaptcha`` preconnect hint from being classified as
blocked, while a 2.4 KB Akamai interstitial still is.
"""
import re
from enum import Enum

# Interstitials observed in the source audits are 2.3–2.6 KB. Real articles from
# the same sites are 8 KB+ of extracted text and far larger raw. Corroborating
# signals only count below this bound.
SMALL_BODY_BYTES = 15_000

# Markers specific enough to stand alone. Each names a verification mechanism
# rather than a library that a normal page might merely reference.
_CONCLUSIVE = (
    ("akamai_bm_verify", re.compile(r"bm-verify", re.I)),
    ("akamai_sec_verify", re.compile(r"/_sec/verify", re.I)),
    ("doj_interstitial", re.compile(r"doj-interstitial", re.I)),
    ("akamai_interstitial_logo", re.compile(r"akam-logo", re.I)),
    ("akamai_ghost", re.compile(r"AkamaiGHost", re.I)),
    ("akamai_reference", re.compile(r"Reference&#32;&#35;\d|akamai\.net/errorpage", re.I)),
    ("cloudflare_challenge", re.compile(r"cf-browser-verification|cf_chl_|cf-challenge", re.I)),
    ("cloudflare_wait", re.compile(r"Checking if the site connection is secure", re.I)),
    ("challenge_form", re.compile(r"challenge-form|captcha-delivery|/cdn-cgi/challenge-platform", re.I)),
)

# Weaker hints. Any one of these can appear on a legitimate page, so a challenge
# is only declared when at least two fire on a small body.
_CORROBORATING = (
    ("meta_refresh", re.compile(r"<meta[^>]+http-equiv=[\"']?refresh", re.I)),
    ("noscript_js_required", re.compile(r"<noscript>(?:(?!</noscript>).){0,400}(enable\s+javascript|javascript\s+is\s+required)", re.I | re.S)),
    ("access_denied", re.compile(r"access denied|request unsuccessful|you don'?t have permission to access", re.I)),
    ("verification_wording", re.compile(r"verify(?:ing)?\s+you\s+are\s+human|security\s+check|please\s+wait\s+while\s+we\s+verify", re.I)),
    ("bot_wording", re.compile(r"automated\s+access|unusual\s+traffic|bot\s+detection", re.I)),
    # A widget alone is not proof: healthy pages embed reCAPTCHA in contact and
    # feedback forms. It only counts alongside a second signal on a small body.
    ("captcha_widget", re.compile(r"g-recaptcha[\"'\s>]|data-sitekey|h-captcha[\"'\s>]", re.I)),
)

_MIN_CORROBORATING = 2

# On an error status a single strong denial/verification marker is enough: a
# short 403/503 refusal page is terminal, and retrying it with another
# fingerprint or a browser only amplifies requests against a host already
# refusing us. A 200 article merely discussing access denial is unaffected.
_DENIAL_STATUSES = frozenset({401, 403, 429, 503})
_DENIAL_SIGNALS = frozenset({"access_denied", "verification_wording", "bot_wording"})
_DENIAL_BODY_BYTES = 4_000


class ChallengeVerdict:
    """Outcome of challenge classification. Truthy when the page is a challenge."""

    __slots__ = ("is_challenge", "signals")

    def __init__(self, is_challenge: bool, signals: tuple[str, ...]) -> None:
        self.is_challenge = is_challenge
        self.signals = signals

    def __bool__(self) -> bool:
        return self.is_challenge


def classify_challenge(
    body: str, *, content_type: str = "", body_kind: "BodyKind | None" = None,
    status: int | None = None,
) -> ChallengeVerdict:
    """Decide whether ``body`` is an anti-bot verification page.

    Keyed on what the body *is*, not on what the server said it is: an
    interstitial served as ``application/xml`` is still an interstitial. Only the
    first 30 KB is scanned; verification shells are tiny and this bounds the cost
    on large articles.
    """
    if not body:
        return ChallengeVerdict(False, ())
    kind = body_kind if body_kind is not None else sniff_body_kind(body)
    if kind is not BodyKind.HTML:
        # Genuine XML/JSON payloads are content, not interstitials.
        return ChallengeVerdict(False, ())

    head = body[:30_000]
    conclusive = tuple(name for name, pat in _CONCLUSIVE if pat.search(head))
    if conclusive:
        return ChallengeVerdict(True, conclusive)

    corroborating = tuple(name for name, pat in _CORROBORATING if pat.search(head))
    if len(body) < SMALL_BODY_BYTES and len(corroborating) >= _MIN_CORROBORATING:
        return ChallengeVerdict(True, corroborating)

    if (
        status in _DENIAL_STATUSES
        and len(body) < _DENIAL_BODY_BYTES
        and any(name in _DENIAL_SIGNALS for name in corroborating)
    ):
        return ChallengeVerdict(True, corroborating)

    return ChallengeVerdict(False, corroborating)


# ---------------------------------------------------------------------------
# Content types
# ---------------------------------------------------------------------------

_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_FEED_TYPES = frozenset({
    "application/rss+xml", "application/atom+xml", "application/xml", "text/xml",
    "application/rdf+xml",
})
_JSON_TYPES = frozenset({"application/json", "text/json", "application/feed+json"})
_TEXT_TYPES = frozenset({"text/plain"})

# Documents this pipeline deliberately does not read. Rejected explicitly rather
# than handed to the HTML text extractor, which would happily decode bytes.
_UNSUPPORTED_TYPES = frozenset({
    "application/pdf", "application/msword", "application/zip",
    "application/octet-stream", "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
})
_UNSUPPORTED_PREFIXES = ("image/", "video/", "audio/", "font/")

# Magic bytes for servers that mislabel a document as text/html.
_BINARY_SIGNATURES = (b"%PDF-", b"PK\x03\x04", b"\xd0\xcf\x11\xe0", b"\x89PNG", b"GIF8", b"\xff\xd8\xff")


class AcceptPolicy(Enum):
    """What a caller is willing to receive. No universal default kind."""

    FEED = "feed"                 # RSS/Atom/XML listings
    HTML_LISTING = "html_listing"
    JSON_LISTING = "json_listing"
    ARTICLE = "article"           # HTML/text detail pages
    ANY_TEXT = "any_text"         # legacy call sites not yet migrated

    @property
    def accepted(self) -> frozenset[str]:
        return {
            AcceptPolicy.FEED: _FEED_TYPES,
            AcceptPolicy.HTML_LISTING: _HTML_TYPES,
            AcceptPolicy.JSON_LISTING: _JSON_TYPES,
            AcceptPolicy.ARTICLE: _HTML_TYPES | _TEXT_TYPES,
            AcceptPolicy.ANY_TEXT: _HTML_TYPES | _FEED_TYPES | _JSON_TYPES | _TEXT_TYPES,
        }[self]


class BodyKind(Enum):
    """What a response body actually looks like, independent of its headers."""

    HTML = "html"
    XML = "xml"
    JSON = "json"
    BINARY = "binary"
    EMPTY = "empty"
    UNKNOWN_TEXT = "unknown_text"


_XML_PROLOGUE = re.compile(r"^\s*<\?xml|^\s*<(rss|feed|rdf:RDF)\b", re.I)
_HTML_PROLOGUE = re.compile(r"^\s*<!doctype\s+html|^\s*<html\b", re.I)
_HTML_ANYWHERE = re.compile(r"<html\b|<head\b|<body\b|<!doctype\s+html", re.I)
# Structural tags that mean HTML even in a fragment with no document wrapper.
_HTML_FRAGMENT = re.compile(
    r"</?(article|section|main|div|p|span|table|tbody|tr|td|ul|ol|li|h[1-6]|"
    r"nav|form|figure|blockquote|img|br|hr|strong|em)\b", re.I
)


def sniff_body_kind(body: str, raw: bytes = b"", content_type: str = "") -> BodyKind:
    """Classify a body by inspection. Deliberately small — not a MIME parser.

    Explicit feed markers win outright. Otherwise HTML is identified structurally,
    including bare fragments, and the declared type only breaks a genuine tie —
    so a mislabelled challenge page is still seen as HTML while ordinary XML
    labelled ``application/xml`` stays XML.
    """
    if raw and any(raw.startswith(sig) for sig in _BINARY_SIGNATURES):
        return BodyKind.BINARY
    if not body or not body.strip():
        return BodyKind.EMPTY

    head = body[:4096]
    # Feed/XML declarations are unambiguous and take precedence.
    if _XML_PROLOGUE.search(head):
        return BodyKind.XML
    if _HTML_PROLOGUE.search(head) or _HTML_ANYWHERE.search(head):
        return BodyKind.HTML
    if _HTML_FRAGMENT.search(head):
        return BodyKind.HTML

    stripped = body.lstrip()
    if stripped[:1] in ("{", "["):
        return BodyKind.JSON
    if stripped.startswith("<"):
        # Ambiguous markup: honour the declared type before defaulting to XML.
        declared = _base_type(content_type)
        if declared in _HTML_TYPES:
            return BodyKind.HTML
        return BodyKind.XML
    return BodyKind.UNKNOWN_TEXT


_KIND_TO_TYPES = {
    BodyKind.HTML: _HTML_TYPES,
    BodyKind.XML: _FEED_TYPES,
    BodyKind.JSON: _JSON_TYPES,
    BodyKind.UNKNOWN_TEXT: _TEXT_TYPES,
}


def body_kind_allowed(kind: BodyKind, policy: AcceptPolicy) -> bool:
    """True when a sniffed body kind is compatible with the policy."""
    types = _KIND_TO_TYPES.get(kind)
    if types is None:
        return False
    return bool(types & policy.accepted)


def _base_type(content_type: str) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def is_unsupported_document(content_type: str, raw: bytes = b"") -> bool:
    """True for PDFs, Office files, archives and images, by header or magic bytes."""
    base = _base_type(content_type)
    if base in _UNSUPPORTED_TYPES or base.startswith(_UNSUPPORTED_PREFIXES):
        return True
    return any(raw.startswith(sig) for sig in _BINARY_SIGNATURES)


def content_type_allowed(content_type: str, policy: AcceptPolicy) -> bool:
    """True when the response type is one the policy accepts.

    A missing content type is allowed: some feeds omit it, and the parser is the
    next line of defence.
    """
    base = _base_type(content_type)
    return not base or base in policy.accepted
