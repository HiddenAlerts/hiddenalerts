"""Classification rules for source responses: challenge detection and content types.

Pure functions, no IO. Two jobs:

* decide whether a body is an anti-bot verification page rather than content;
* decide whether a response's content type is one the caller asked for.

Challenge evidence is graded. A verification *mechanism* the document actually
uses — a challenge endpoint in a form action, an interstitial loaded as a
resource, a challenge element, an executable verification call — is conclusive.
Vendor tokens and denial wording are weaker: they only count in context, and are
never combined on a page that has real article content. Quoted documentation
(``pre``/``code``/``textarea``) is excluded from structural scanning, so an
article demonstrating ``fetch('/_sec/verify')`` is not mistaken for one running
it. These are heuristics, not a parser.
"""
import re
from enum import Enum

from bs4 import BeautifulSoup
from bs4.element import Comment

# Verification shells observed in the source audits are 2.3–2.6 KB. Legitimate
# pages are not reliably larger — FinCEN releases extract to roughly 0.9–3 KB —
# so size is never proof on its own. This bound only limits where the weakest
# evidence is trusted, and is always combined with a check for real article
# content.
SMALL_BODY_BYTES = 15_000

# Parsing is bounded; a challenge shell is tiny and never buried past this.
_MAX_SCAN_BYTES = 200_000

# Containers whose contents are quoted documentation, not executable markup. A
# security article showing `fetch('/_sec/verify')` in a code block is describing
# a mechanism, not running one, so these are removed before structural scanning.
_DOC_CONTAINERS = ("pre", "code", "textarea", "samp", "kbd", "xmp", "template")

# Tags whose src/data actually loads a resource.
_RESOURCE_TAGS = ("iframe", "script", "embed", "object", "frame")

# Article-content length above which a page is treated as real content rather
# than a verification shell. Weak evidence is not combined on such a page. This
# is not a minimum length for accepting a document — short releases are fine; it
# only decides whether weak signals may be believed.
_CONTENT_TEXT_FLOOR = 400


class _ScanView:
    """Executable view of a document, with quoted documentation removed.

    Pure and I/O-free. Falls back to raw-text scanning if parsing fails, which
    is more conservative rather than less.
    """

    __slots__ = ("soup", "scripts", "content_len", "parsed")

    def __init__(self, body: str) -> None:
        self.soup = None
        self.scripts = ""
        self.content_len = 0
        self.parsed = False
        try:
            soup = BeautifulSoup(body[:_MAX_SCAN_BYTES], "lxml")
            for tag in soup.find_all(_DOC_CONTAINERS):
                tag.decompose()
            for node in soup.find_all(string=lambda t: isinstance(t, Comment)):
                node.extract()
            self.scripts = "\n".join(t.get_text() for t in soup.find_all("script"))
            self.content_len = _article_text_length(soup)
            self.soup = soup
            self.parsed = True
        except Exception:  # pragma: no cover - defensive
            pass

    def form_action(self, pattern: re.Pattern) -> bool:
        if not self.parsed:
            return False
        return any(pattern.search(f.get("action") or "") for f in self.soup.find_all("form"))

    def resource_src(self, pattern: re.Pattern) -> bool:
        if not self.parsed:
            return False
        for tag in self.soup.find_all(_RESOURCE_TAGS):
            for attr in ("src", "data"):
                if pattern.search(tag.get(attr) or ""):
                    return True
        return False

    def id_or_class(self, pattern: re.Pattern, *, tags=None) -> bool:
        if not self.parsed:
            return False
        for tag in self.soup.find_all(tags or True):
            if pattern.search(tag.get("id") or ""):
                return True
            classes = tag.get("class") or []
            if any(pattern.search(c) for c in classes):
                return True
        return False

    def script_call(self, pattern: re.Pattern) -> bool:
        return bool(self.scripts) and bool(pattern.search(self.scripts))

    def has_article_content(self) -> bool:
        return self.content_len >= _CONTENT_TEXT_FLOOR


def _article_text_length(soup) -> int:
    """Length of body prose, ignoring navigation, footers and forms."""
    total = 0
    paragraphs = [
        t for t in soup.find_all("p")
        if not t.find_parent(["footer", "nav", "aside", "form", "header"])
    ]
    if not paragraphs:
        paragraphs = [
            t for t in soup.find_all(["article", "main"])
            if not t.find_parent(["footer", "nav", "aside", "form"])
        ]
    for tag in paragraphs:
        total += len(" ".join(tag.get_text(" ", strip=True).split()))
    return total


def _js_call(token: str) -> re.Pattern:
    """A request/navigation call whose argument references the token."""
    return re.compile(
        rf"""(?:\.open|fetch|\.ajax|\.post|\.get|location\.(?:href|replace|assign))"""
        rf"""\s*\([^)]{{0,160}}["'][^"']*(?:{token})""",
        re.I,
    )


def _dom_lookup(token: str) -> re.Pattern:
    return re.compile(
        rf"""getElementById\s*\(\s*["'](?:{token})"""
        rf"""|querySelector(?:All)?\s*\(\s*["'][^"']*(?:{token})""",
        re.I,
    )


_SEC_VERIFY = re.compile(r"/_sec/verify", re.I)
_DOJ_INTERSTITIAL = re.compile(r"doj-interstitial", re.I)
_AKAM_LOGO = re.compile(r"akam-logo", re.I)
_CF_ELEMENT = re.compile(r"cf-browser-verification|cf-challenge", re.I)
_CF_PLATFORM = re.compile(r"/cdn-cgi/challenge-platform", re.I)
_CHALLENGE_FORM_ID = re.compile(r"challenge-form|challenge", re.I)
_CHALLENGE_ACTION = re.compile(r"challenge-form|captcha-delivery|/cdn-cgi/challenge-platform", re.I)


def _structural_signals(view: _ScanView) -> tuple[str, ...]:
    """Names of verification mechanisms the document actually uses.

    Each check is bound to a specific place a mechanism can live — a form action,
    a loaded resource, a challenge element, or an executable script call — so a
    token quoted in prose, a documentation link or a data attribute never counts.
    """
    found = []
    if view.form_action(_SEC_VERIFY) or view.script_call(_js_call(r"/_sec/verify")):
        found.append("akamai_sec_verify")
    if view.resource_src(_DOJ_INTERSTITIAL):
        found.append("doj_interstitial")
    if view.id_or_class(_AKAM_LOGO) or view.script_call(_dom_lookup(r"akam-logo")):
        found.append("akamai_interstitial_logo")
    if (
        view.id_or_class(_CF_ELEMENT)
        or view.resource_src(_CF_PLATFORM)
        or view.form_action(_CF_PLATFORM)
        or view.script_call(_js_call(r"/cdn-cgi/challenge-platform"))
    ):
        found.append("cloudflare_challenge")
    if view.id_or_class(_CHALLENGE_FORM_ID, tags=["form"]) or view.form_action(_CHALLENGE_ACTION):
        found.append("challenge_form")
    return tuple(found)


# Technical markers: real vendor tokens that a security article can legitimately
# quote. Never conclusive on their own — see ``classify_challenge``.
_TECHNICAL = (
    ("akamai_bm_verify", re.compile(r"bm-verify", re.I)),
    ("akamai_ghost", re.compile(r"AkamaiGHost", re.I)),
    ("akamai_reference", re.compile(r"Reference&#32;&#35;\d|akamai\.net/errorpage", re.I)),
    ("cloudflare_token", re.compile(r"cf_chl_", re.I)),
)


def _has_challenge_context(view: _ScanView) -> bool:
    """A form, loaded resource or script call that is about verification."""
    token = r"challenge|verify"
    return (
        view.form_action(re.compile(token, re.I))
        or view.resource_src(re.compile(token, re.I))
        or view.script_call(_js_call(token))
    )


# Weak hints. Any one can appear on a legitimate page, so they are only combined
# when the document has no real article content behind them.
_CORROBORATING = (
    ("meta_refresh", re.compile(r"<meta[^>]+http-equiv=[\"']?refresh", re.I)),
    ("noscript_js_required", re.compile(r"<noscript>(?:(?!</noscript>).){0,400}(enable\s+javascript|javascript\s+is\s+required)", re.I | re.S)),
    ("access_denied", re.compile(r"access denied|request unsuccessful|you don'?t have permission to access", re.I)),
    ("verification_wording", re.compile(r"verify(?:ing)?\s+you\s+are\s+human|security\s+check|please\s+wait\s+while\s+we\s+verify", re.I)),
    ("bot_wording", re.compile(r"automated\s+access|unusual\s+traffic|bot\s+detection", re.I)),
    ("cloudflare_wait", re.compile(r"Checking if the site connection is secure", re.I)),
    # A widget alone is not proof: healthy pages embed reCAPTCHA in contact and
    # feedback forms. It only counts on a page with no article content behind it.
    ("captcha_widget", re.compile(r"g-recaptcha[\"'\s>]|data-sitekey|h-captcha[\"'\s>]", re.I)),
)

_MIN_CORROBORATING = 2

# On an error status a single strong denial marker is enough: a short 403/503
# refusal page is terminal, and retrying it with another fingerprint or a browser
# only amplifies requests against a host already refusing us.
#
# 429 is deliberately absent — it means "slow down", and must keep producing
# RateLimitedError with its Retry-After rather than being reclassified. 401 is
# absent too: an ordinary authentication refusal is a permanent error, not a bot
# challenge. Both still become challenges if a structural mechanism is present.
_DENIAL_STATUSES = frozenset({403, 503})
RATE_LIMIT_STATUS = 429
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
    interstitial served as ``application/xml`` is still an interstitial.

    Evidence is weighed in a fixed order: a real verification mechanism, then an
    approved short 403/503 refusal, then contextual technical/weak evidence, then
    the document is usable. Structural scanning ignores quoted documentation
    (``pre``/``code``/``textarea``), and weak signals are only combined on a page
    with no article content behind them. All of this remains regex and
    lightweight-HTML heuristics, not a browser or JavaScript parser.
    """
    if not body:
        return ChallengeVerdict(False, ())
    kind = body_kind if body_kind is not None else sniff_body_kind(body)
    if kind is not BodyKind.HTML:
        # Genuine XML/JSON payloads are content, not interstitials.
        return ChallengeVerdict(False, ())

    view = _ScanView(body)
    head = body[:30_000]

    # 1. An actual verification mechanism is conclusive at any size or status.
    structural = _structural_signals(view)
    if structural:
        return ChallengeVerdict(True, structural)

    technical = tuple(name for name, pat in _TECHNICAL if pat.search(head))
    corroborating = tuple(name for name, pat in _CORROBORATING if pat.search(head))

    # 429 means "slow down", not "prove you are human". Only a real mechanism
    # (handled above) reclassifies it; everything else keeps RateLimitedError and
    # its Retry-After.
    if status == RATE_LIMIT_STATUS:
        return ChallengeVerdict(False, technical + corroborating)

    # 2. A short refusal page at a denial status is terminal.
    if (
        status in _DENIAL_STATUSES
        and len(body) < _DENIAL_BODY_BYTES
        and not view.has_article_content()
        and any(name in _DENIAL_SIGNALS for name in corroborating)
    ):
        return ChallengeVerdict(True, corroborating)

    # 3. Weak evidence is only believed on a page with no article behind it, so
    #    prose that merely discusses these topics is never combined into a verdict.
    shell = len(body) < SMALL_BODY_BYTES and not view.has_article_content()

    if technical:
        denied = status in _DENIAL_STATUSES
        in_context = _has_challenge_context(view)
        corroborated = shell and bool(corroborating)
        multi_signal = shell and (len(technical) + len(corroborating)) >= 2
        if denied or in_context or corroborated or multi_signal:
            return ChallengeVerdict(True, technical + corroborating)
        return ChallengeVerdict(False, technical)

    if shell and len(corroborating) >= _MIN_CORROBORATING:
        return ChallengeVerdict(True, corroborating)

    # 4. Otherwise the document is usable content.
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
