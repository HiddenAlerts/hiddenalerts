"""SEC Press Releases — RSS feed, summary-only by policy.

The feed itself is healthy: the 2026-07-28 audit measured 25 dated entries, all
with a summary, cleaned length 212-255 characters, none near-title, none
boilerplate. The *article* pages are not: sec.gov returned HTTP 403 on every
sampled detail request, systematically rather than intermittently.

So SEC deliberately does not request article pages. Fetching one would cost a
request, add load to a host that is already refusing us, and end in the same
summary fallback anyway. The summary is the content — which is exactly why it is
checked per item before it is stored.
"""
import logging
import re

from app.sources.base import RawItemStub, _safe_url, clean_summary_text
from app.sources.rss_adapter import RSSAdapter

log = logging.getLogger(__name__)

OFFICIAL_FEED_URL = "https://www.sec.gov/news/pressreleases.rss"

# --- Summary quality thresholds -------------------------------------------
#
# SEC truncates feed summaries to a narrow band: the audit measured min 212 /
# median 249 / p90 254 / max 255 cleaned characters across 25 entries, with 100%
# clearing the audit's "keyword usable" bar. These thresholds sit well below the
# observed floor, so no real SEC release is discarded; they exist to reject a
# malformed, truncated or boilerplate entry.
#
# They are stricter than DOJ's (120 chars / 15 words) on purpose: DOJ falls back
# to a summary only when its article is blocked, whereas for SEC the summary is
# the *only* content this item will ever have. Nothing gets a second chance here.
MIN_SUMMARY_CHARS = 140
MIN_SUMMARY_WORDS = 20

_SENTENCE_END = re.compile(r"[.!?]")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_BOILERPLATE = re.compile(
    r"^\s*(?:read (?:the )?(?:full|more)|continue reading|view (?:the )?press release|"
    r"click here|for more information|see the announcement|for immediate release)\b",
    re.I,
)


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split())


def is_usable_summary(summary: str, title: str = "") -> bool:
    """True when an SEC feed summary is substantial enough to store as content.

    Pure and deterministic — no network, no model call. Rejects a summary that is
    empty, merely restates the title, is feed boilerplate, is little more than a
    link, or is too thin to support fraud/security classification. Length alone is
    never sufficient: a run of words with no sentence structure fails, as does a
    long title echo.
    """
    cleaned = clean_summary_text(summary)
    if not cleaned:
        return False
    if _BOILERPLATE.match(cleaned):
        return False

    # Strip URLs before measuring — a link is not substance.
    prose = _URL.sub(" ", cleaned).strip()
    if len(prose) < MIN_SUMMARY_CHARS:
        return False
    if len(_WORD.findall(prose)) < MIN_SUMMARY_WORDS:
        return False
    if not _SENTENCE_END.search(prose):
        return False

    summary_norm = _normalize(prose)
    title_norm = _normalize(title)
    if title_norm and (
        summary_norm == title_norm
        or summary_norm in title_norm
        or (title_norm in summary_norm and len(summary_norm) < len(title_norm) * 1.3)
    ):
        return False
    return True


class SECPressAdapter(RSSAdapter):
    """SEC Press Releases — RSS discovery, summary-only content."""

    @property
    def rss_url(self) -> str:
        """A configured feed wins; otherwise the official one."""
        configured = (getattr(self.source, "rss_url", None) or "").strip()
        return configured or OFFICIAL_FEED_URL

    def should_fetch_article(self, stub: RawItemStub) -> bool:
        """Never — sec.gov answers 403 to detail requests, systematically."""
        return False

    def summary_fallback(self, stub: RawItemStub, error: Exception | None) -> str | None:
        """The feed summary, if it carries enough to classify on.

        ``error`` is always ``None`` here: no request was made, so there is no
        failure to report and none is fabricated.
        """
        cleaned = clean_summary_text(stub.summary)
        if not is_usable_summary(stub.summary, stub.title):
            log.info(
                "Source %s: SEC summary for %s is not substantial enough to store "
                "(%d chars after cleaning)",
                getattr(self.source, "id", "?"),
                _safe_url(stub.item_url),
                len(cleaned),
            )
            return None
        return cleaned
