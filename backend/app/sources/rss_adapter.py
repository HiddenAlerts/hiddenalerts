import calendar
import logging
import re
from abc import abstractmethod
from datetime import datetime
from urllib.parse import urljoin

import feedparser
from dateutil import parser as dateutil_parser

from app.sources.base import (
    BaseSourceAdapter,
    RawItemData,
    RawItemStub,
    _safe_url,
    _unsafe_target_reason,
)
from app.sources.http_errors import ContentTypeMismatch
from app.sources.response_policy import AcceptPolicy

log = logging.getLogger(__name__)


# Everything that may legally precede a feed's root element: a byte-order mark,
# whitespace, the XML declaration, comments, and a DOCTYPE.
_FEED_PROLOGUE = re.compile(
    r"\A(?:\ufeff|\s+|<\?xml[^>]*\?>|<!--.*?-->|<!DOCTYPE[^>]*>)*", re.I | re.S
)
# The three feed roots, with or without a namespace prefix: RSS, Atom and RDF.
_FEED_ROOT = re.compile(r"<(?:[A-Za-z_][\w.-]*:)?(?:rss|feed|RDF)\b", re.I)


def has_feed_root(text: str) -> bool:
    """True when the document's *top-level element* is rss, feed or rdf:RDF.

    Root-driven on purpose: a feed element nested inside an HTML page — an
    example in an article, say — must not make that page look like a feed.
    """
    if not text or not text.strip():
        return False
    body = _FEED_PROLOGUE.sub("", text, count=1)
    return bool(_FEED_ROOT.match(body))


def parse_feed_document(text: str):
    """Parse ``text`` as a feed, or return ``None`` if it is not one.

    Two independent signals must agree: the top-level element is a feed root,
    **and** feedparser recognized a feed version (``rss20``, ``atom10``, ``rdf``…).
    Requiring both is what keeps ordinary HTML and arbitrary XML out — neither
    gets a version, and neither has a feed root.

    Entry count is deliberately *not* a signal: a valid feed with nothing in it is
    a healthy empty feed, and an HTML page also has zero entries. Treating "zero
    entries" as evidence either way is exactly the confusion this function exists
    to prevent.
    """
    if not has_feed_root(text):
        return None
    parsed = feedparser.parse(text)
    if not parsed.get("version"):
        return None
    return parsed


def _parse_feed_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        dt = dateutil_parser.parse(date_str)
        # Store as naive UTC — columns are TIMESTAMP WITHOUT TIME ZONE
        if dt.tzinfo is not None:
            dt = datetime.utcfromtimestamp(calendar.timegm(dt.utctimetuple()))
        return dt
    except Exception:
        return None


class RSSAdapter(BaseSourceAdapter):
    """Generic RSS adapter — handles any source with a valid RSS/Atom feed URL.

    Stage 1 (fetch_item_stubs): fetches the RSS feed via httpx and parses it with
    feedparser — returns one RawItemStub per entry, including the feed summary as a
    fallback in case the full article fetch later fails.

    Stage 2 (fetch_items / full fetch): calls fetch_full_article() for each stub
    to get the complete raw_text and raw_html. Falls back to stub.summary if the
    article page is unreachable.
    """

    @property
    def rss_url(self) -> str:
        return self.source.rss_url  # type: ignore[attr-defined]

    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Parse RSS feed — returns stubs with no full article fetches.

        One fetch under :data:`AcceptPolicy.FEED`, the long-standing behaviour for
        every RSS source.
        """
        log.info(f"Fetching RSS feed (stubs): {self.rss_url}")
        result = await self.fetch(self.rss_url, accept=AcceptPolicy.FEED)
        return self.stubs_from_document(result.text)

    def stubs_from_document(self, text: str) -> list[RawItemStub]:
        """Turn one feed body into stubs, or raise if it is not a feed.

        Shared with any adapter that has to obtain the body differently — the
        recognition rule and the entry handling stay in one place.
        """
        feed = parse_feed_document(text)
        if feed is None:
            raise ContentTypeMismatch(
                "feed URL did not return a recognizable RSS/Atom/RDF document",
                url=_safe_url(self.rss_url),
            )

        if feed.bozo:
            log.warning(f"RSS feed {self.rss_url} has minor format issues: {feed.bozo_exception}")
        if not feed.entries:
            log.warning(f"RSS feed {self.rss_url} returned 0 entries (feed may be inactive)")
            return []

        stubs: list[RawItemStub] = []
        skipped = 0
        for entry in feed.entries:
            # An entry with no link must be dropped before urljoin, which would
            # otherwise resolve "" to the feed URL itself and turn a malformed
            # entry into an item pointing at the feed. Relative links are resolved
            # against the feed URL for the rare feeds that emit them; anything
            # that is not a public http(s) target is dropped rather than requested.
            link = (entry.get("link") or "").strip()
            title = (entry.get("title") or "").strip()
            if not link or not title:
                skipped += 1
                continue
            url = urljoin(self.rss_url, link)
            if _unsafe_target_reason(url):
                skipped += 1
                continue
            stubs.append(
                RawItemStub(
                    source_name=self.source.name,  # type: ignore[attr-defined]
                    item_url=url,
                    title=title,
                    published_at=_parse_feed_date(
                        entry.get("published") or entry.get("updated")
                    ),
                    summary=entry.get("summary", ""),
                )
            )
        if skipped:
            log.info(
                "RSS feed %s: skipped %d entr%s missing a title or usable link",
                self.rss_url, skipped, "y" if skipped == 1 else "ies",
            )

        log.info(f"RSS feed {self.rss_url}: found {len(stubs)} stubs")
        return stubs

    async def fetch_items(self) -> list[RawItemData]:
        """Full fetch: parse feed stubs then fetch each article page."""
        stubs = await self.fetch_item_stubs()
        items: list[RawItemData] = []

        for stub in stubs:
            try:
                raw_text, raw_html = await self.fetch_full_article(stub.item_url)
            except Exception as exc:
                log.warning(f"Could not fetch full article {stub.item_url}: {exc}")
                raw_text = stub.summary  # fall back to RSS summary
                raw_html = ""

            items.append(
                RawItemData(
                    source_name=stub.source_name,
                    item_url=stub.item_url,
                    title=stub.title,
                    published_at=stub.published_at,
                    raw_text=raw_text,
                    raw_html=raw_html,
                )
            )

        log.info(f"RSS feed {self.rss_url}: fetched {len(items)} full items")
        return items


class HTMLScraperAdapter(BaseSourceAdapter):
    """Base adapter for sources that require HTML listing-page scraping."""

    @abstractmethod
    async def parse_listing_page(self, html: str) -> list[dict]:
        """Parse listing HTML. Return list of dicts with keys: url, title, date (optional)."""
        pass

    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Fetch listing page and parse article refs — no full article fetches."""
        listing_url = self.source.base_url  # type: ignore[attr-defined]
        log.info(f"Fetching HTML listing (stubs): {listing_url}")
        listing_html = (await self.fetch(listing_url, accept=AcceptPolicy.HTML_LISTING)).text
        refs = await self.parse_listing_page(listing_html)

        stubs: list[RawItemStub] = []
        for ref in refs:
            url = ref.get("url", "")
            if not url:
                continue
            stubs.append(
                RawItemStub(
                    source_name=self.source.name,  # type: ignore[attr-defined]
                    item_url=url,
                    title=ref.get("title", ""),
                    published_at=_parse_feed_date(ref.get("date")),
                )
            )

        log.info(f"HTML scraper {listing_url}: found {len(stubs)} stubs")
        return stubs

    async def fetch_items(self) -> list[RawItemData]:
        """Full fetch: parse listing stubs then fetch each article page."""
        stubs = await self.fetch_item_stubs()
        items: list[RawItemData] = []

        for stub in stubs:
            try:
                raw_text, raw_html = await self.fetch_full_article(stub.item_url)
            except Exception as exc:
                log.warning(f"Could not fetch article {stub.item_url}: {exc}")
                continue

            items.append(
                RawItemData(
                    source_name=stub.source_name,
                    item_url=stub.item_url,
                    title=stub.title,
                    published_at=stub.published_at,
                    raw_text=raw_text,
                    raw_html=raw_html,
                )
            )

        log.info(f"HTML scraper: fetched {len(items)} full items")
        return items
