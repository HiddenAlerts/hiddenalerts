import logging
from datetime import datetime

from bs4 import BeautifulSoup

from app.sources.base import RawItemData, RawItemStub
from app.sources.rss_adapter import HTMLScraperAdapter, _parse_feed_date

log = logging.getLogger(__name__)

_BASE = "https://www.ftc.gov"
_LISTING_URL = "https://www.ftc.gov/news-events/news/press-releases"


class FTCFeedsAdapter(HTMLScraperAdapter):
    """FTC Press Releases — HTML scrape of ftc.gov/news-events/news/press-releases.

    FTC RSS feed returns 403 for automated requests regardless of User-Agent,
    so we scrape the HTML listing page instead.
    """

    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Fetch FTC listing page and return stubs — no full article fetches."""
        listing_html = await self._http_get(_LISTING_URL)
        refs = await self.parse_listing_page(listing_html)
        log.info(f"FTC listing: found {len(refs)} stubs")

        stubs: list[RawItemStub] = []
        for ref in refs:
            url = ref.get("url", "")
            if not url:
                continue
            published_at: datetime | None = None
            if ref.get("date"):
                published_at = _parse_feed_date(ref["date"])
            stubs.append(
                RawItemStub(
                    source_name=self.source.name,  # type: ignore[attr-defined]
                    item_url=url,
                    title=ref.get("title", ""),
                    published_at=published_at,
                )
            )
        return stubs

    async def fetch_items(self) -> list[RawItemData]:
        """Full fetch: collect stubs then fetch each article."""
        stubs = await self.fetch_item_stubs()
        items: list[RawItemData] = []

        for stub in stubs:
            try:
                raw_text, raw_html = await self.fetch_full_article(stub.item_url)
            except Exception as exc:
                log.warning(f"Could not fetch FTC article {stub.item_url}: {exc}")
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

        log.info(f"FTC: fetched {len(items)} full items")
        return items

    async def parse_listing_page(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        for item in soup.select("div.view-content li, div.views-row, article"):
            a_tag = item.find("a", href=True)
            if not a_tag:
                continue
            href: str = a_tag["href"]
            url = href if href.startswith("http") else f"{_BASE}{href}"
            title = a_tag.get_text(strip=True)
            if not title:
                continue

            date_str: str | None = None
            date_el = item.find(["time", "span", "div"], class_=lambda c: c and "date" in c)
            if date_el:
                date_str = date_el.get("datetime") or date_el.get_text(strip=True)

            results.append({"url": url, "title": title, "date": date_str})

        # Fallback: grab all links that look like FTC press release paths
        if not results:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "/news-events/news/press-releases/" in href:
                    url = href if href.startswith("http") else f"{_BASE}{href}"
                    title = a_tag.get_text(strip=True)
                    if title and len(title) > 10:
                        results.append({"url": url, "title": title, "date": None})

        return results
