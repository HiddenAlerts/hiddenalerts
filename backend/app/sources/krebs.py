"""KrebsOnSecurity — official RSS feed.

The feed is healthy: the audit measured 10 entries, all dated, all with summaries
(median 395 cleaned characters, 90% AI-usable), and detail pages returning 9-18 KB
of real article text.

The HTML fallback this adapter used to carry was strictly worse — 20 references
collapsing to 10, half of them undated — and it was reachable through a broad
``except Exception`` that a transient feed hiccup was enough to trigger. It is
gone: Krebs discovery is the feed, and a feed failure fails the run visibly rather
than quietly degrading to a worse parser.
"""
from app.sources.rss_adapter import RSSAdapter

# The row already carries this value; it is the default only so a cleared column
# does not stop collection. A populated ``source.rss_url`` always wins.
OFFICIAL_FEED_URL = "https://krebsonsecurity.com/feed/"


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
