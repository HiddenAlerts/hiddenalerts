"""DOJ Press Releases — official RSS feed.

The justice.gov HTML listing sits behind an Akamai verification interstitial that
returns HTTP 200 with no articles, so scraping it produced hundreds of
"successful" zero-item runs. Discovery now uses DOJ's own press-release feed.

Article pages under ``/opa/`` fetch normally. Pages under ``/usao-*`` are served
the same interstitial, so for those the feed summary may stand in — but only when
the individual summary is substantial enough to classify on. See
:func:`is_usable_summary`.
"""
import logging
import re

from app.sources.base import RawItemStub, _safe_url, clean_summary_text
from app.sources.rss_adapter import RSSAdapter

log = logging.getLogger(__name__)

# DOJ publishes no feed URL in the source row today, so this is the default. A
# populated ``source.rss_url`` always wins, letting the feed be repointed without
# a code change.
OFFICIAL_FEED_URL = "https://www.justice.gov/news/rss?type=press_release"

# --- Summary quality thresholds -------------------------------------------
#
# The 2026-07-28 audit measured 25 DOJ feed entries: 22 with a summary, 3 empty,
# cleaned length min 68 / median 213 / p90 620, with no near-title and no
# boilerplate cases. Its own bars were recorded as audit-only, so these are the
# production rule, deliberately set between them: stricter than the audit's
# "keyword usable" (>=40 chars), looser than "AI usable" (>=200 chars and two
# sentences), which would have discarded 56% of real DOJ summaries.
#
# A summary only substitutes for an article when it carries enough substance to
# classify on, so length alone is never sufficient.
MIN_SUMMARY_CHARS = 120
MIN_SUMMARY_WORDS = 15

_SENTENCE_END = re.compile(r"[.!?]")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_BOILERPLATE = re.compile(
    r"^\s*(?:read (?:the )?(?:full|more)|continue reading|view (?:the )?press release|"
    r"click here|for more information|see the announcement)\b",
    re.I,
)


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split())


def is_usable_summary(summary: str, title: str = "") -> bool:
    """True when a DOJ feed summary is substantial enough to store as article text.

    Pure and deterministic — no network, no model call. Rejects a summary that is
    empty, merely restates the title, is feed boilerplate, is little more than a
    link, or is too thin to support fraud/security classification.
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


class DOJPressAdapter(RSSAdapter):
    """DOJ Press Releases via the official RSS feed."""

    @property
    def rss_url(self) -> str:
        """A configured feed wins; otherwise the official one.

        Blank and whitespace-only column values resolve to the default rather
        than to an unfetchable URL, so the source keeps collecting if someone
        clears the field.
        """
        configured = (getattr(self.source, "rss_url", None) or "").strip()
        return configured or OFFICIAL_FEED_URL

    def summary_fallback(self, stub: RawItemStub, error: Exception) -> str | None:
        """Use the feed summary for an unreachable article, if it is good enough.

        Most ``/usao-*`` article pages sit behind the interstitial, so without
        this those items would be lost entirely; without the quality check they
        would be stored as a sentence fragment.
        """
        cleaned = clean_summary_text(stub.summary)
        if not is_usable_summary(stub.summary, stub.title):
            log.info(
                "Source %s: DOJ summary for %s is not substantial enough to "
                "substitute for the article (%d chars after cleaning)",
                getattr(self.source, "id", "?"),
                _safe_url(stub.item_url),
                len(cleaned),
            )
            return None
        return cleaned
