import calendar
import logging
from abc import abstractmethod
from datetime import datetime

import feedparser
from dateutil import parser as dateutil_parser

from app.sources.base import BaseSourceAdapter, RawItemData, RawItemStub

log = logging.getLogger(__name__)


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
        """Parse RSS feed — returns stubs with no full article fetches."""
        log.info(f"Fetching RSS feed (stubs): {self.rss_url}")
        rss_content = await self._http_get(self.rss_url)
        feed = feedparser.parse(rss_content)

        if feed.bozo:
            log.warning(f"RSS feed {self.rss_url} has minor format issues: {feed.bozo_exception}")
        if not feed.entries:
            log.warning(f"RSS feed {self.rss_url} returned 0 entries (feed may be inactive)")
            return []

        stubs: list[RawItemStub] = []
        for entry in feed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            stubs.append(
                RawItemStub(
                    source_name=self.source.name,  # type: ignore[attr-defined]
                    item_url=url,
                    title=entry.get("title", ""),
                    published_at=_parse_feed_date(
                        entry.get("published") or entry.get("updated")
                    ),
                    summary=entry.get("summary", ""),
                )
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
        listing_html = await self._http_get(listing_url)
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
