"""KrebsOnSecurity — official RSS feed.

The feed is healthy: the audit measured 10 entries, all dated, all with summaries
(median 395 cleaned characters, 90% AI-usable), and detail pages returning 9-18 KB
of real article text.

The HTML fallback this adapter used to carry was strictly worse — 20 references
collapsing to 10, half of them undated — and it was reachable through a broad
``except Exception`` that a transient feed hiccup was enough to trigger. It is
gone and does not come back: Krebs discovery is the feed, and a feed that stays
wrong fails the run visibly rather than degrading to a worse parser.

What *is* handled here is the reliability defect the 2026-07-31 recovery preview
exposed: two of three feed fetches came back declaring ``text/html`` and were
rejected on the header alone, before anything looked at the body. Under
:data:`AcceptPolicy.FEED` a mislabeled but perfectly valid feed is indistinguishable
from an actual web page, because the declared type is checked first.

So Krebs — and only Krebs — accepts the response as text, then decides what it
really is by :func:`parse_feed_document`. A valid feed is used whatever the header
said; anything else is retried a bounded number of times and then fails.
"""
import logging

from app.sources.base import RawItemStub, _safe_url
from app.sources.http_errors import ContentTypeMismatch
from app.sources.response_policy import AcceptPolicy
from app.sources.rss_adapter import RSSAdapter, parse_feed_document

log = logging.getLogger(__name__)

# The row already carries this value; it is the default only so a cleared column
# does not stop collection. A populated ``source.rss_url`` always wins.
OFFICIAL_FEED_URL = "https://krebsonsecurity.com/feed/"

#: Total attempts to obtain a *feed document*. Retries are spent only on a
#: successful response whose body is not a feed — the case the preview observed.
#: Every other outcome keeps its existing typed behaviour and does not retry here.
MAX_FEED_ATTEMPTS = 3


class KrebsAdapter(RSSAdapter):
    """KrebsOnSecurity via its official RSS feed."""

    @property
    def rss_url(self) -> str:
        """A configured feed wins; otherwise the official one.

        Blank and whitespace-only column values resolve to the default rather
        than to an unfetchable URL.
        """
        configured = (getattr(self.source, "rss_url", None) or "").strip()
        return configured or OFFICIAL_FEED_URL

    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Fetch the feed, tolerating a wrong Content-Type but not wrong content.

        The response is accepted as text so the body can be examined, then
        validated strictly: only a real RSS/Atom/RDF document is parsed. An
        ordinary HTML page can therefore never be mistaken for an empty feed —
        it is retried, and if it keeps coming back the run fails.

        Nothing else is caught. A challenge, an unsafe target, a redirect error,
        a 401/403/429/5xx and any unexpected error all propagate on the first
        attempt with their existing types and are never retried by this method.
        No browser, no HTML scraping.

        Pacing comes from the shared ``HostRateLimiter``, which every attempt
        passes through; this method adds no sleep of its own.
        """
        url = self.rss_url
        for attempt in range(1, MAX_FEED_ATTEMPTS + 1):
            log.info("Fetching RSS feed (stubs): %s (attempt %d)", url, attempt)
            result = await self.fetch(url, accept=AcceptPolicy.ANY_TEXT)

            if parse_feed_document(result.text) is not None:
                return self.stubs_from_document(result.text)

            log.warning(
                "KrebsOnSecurity: %s returned a non-feed document on attempt %d/%d "
                "(content_type=%s, %d bytes)",
                _safe_url(url), attempt, MAX_FEED_ATTEMPTS,
                result.content_type or "?", len(result.text),
            )

        raise ContentTypeMismatch(
            f"feed URL returned a non-feed document on {MAX_FEED_ATTEMPTS} attempts",
            url=_safe_url(url),
        )
