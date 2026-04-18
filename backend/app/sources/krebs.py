import logging

from bs4 import BeautifulSoup

from app.sources.base import RawItemData, RawItemStub
from app.sources.rss_adapter import HTMLScraperAdapter, RSSAdapter

log = logging.getLogger(__name__)

_RSS_URL = "https://krebsonsecurity.com/feed/"
_BASE = "https://krebsonsecurity.com"


class KrebsAdapter(HTMLScraperAdapter):
    """KrebsOnSecurity — try RSS first, fall back to HTML scraping."""

    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Try RSS stubs first; fall back to HTML listing stubs."""
        try:
            rss_adapter = _KrebsRSSAdapter(self.source)
            stubs = await rss_adapter.fetch_item_stubs()
            if stubs:
                log.info(f"KrebsOnSecurity: {len(stubs)} stubs via RSS")
                return stubs
        except Exception as exc:
            log.warning(f"KrebsOnSecurity RSS stubs failed, falling back to HTML: {exc}")
        return await super().fetch_item_stubs()

    async def fetch_items(self) -> list[RawItemData]:
        """Try RSS fetch first; fall back to HTML scraping."""
        try:
            rss_adapter = _KrebsRSSAdapter(self.source)
            items = await rss_adapter.fetch_items()
            if items:
                log.info(f"KrebsOnSecurity: fetched {len(items)} items via RSS")
                return items
        except Exception as exc:
            log.warning(f"KrebsOnSecurity RSS failed, falling back to HTML: {exc}")
        return await super().fetch_items()

    async def parse_listing_page(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        for article in soup.select("article, div.post, h2.entry-title"):
            a_tag = article.find("a", href=True) if article.name != "a" else article
            if not a_tag:
                continue

            href: str = a_tag.get("href", "")
            if not href.startswith("http"):
                href = f"{_BASE}{href}"

            title = a_tag.get_text(strip=True)

            # Try to find date
            date_str: str | None = None
            date_el = article.find(["time", "span"], class_=lambda c: c and "date" in c)
            if date_el:
                date_str = date_el.get("datetime") or date_el.get_text(strip=True)

            if title and href and "krebsonsecurity.com" in href:
                results.append({"url": href, "title": title, "date": date_str})

        log.info(f"KrebsOnSecurity HTML: found {len(results)} article references")
        return results


class _KrebsRSSAdapter(RSSAdapter):
    """Internal RSS adapter for Krebs."""

    @property
    def rss_url(self) -> str:
        return _RSS_URL
