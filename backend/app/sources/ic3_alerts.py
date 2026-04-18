import logging
from datetime import datetime

from bs4 import BeautifulSoup

from app.sources.base import RawItemData, RawItemStub
from app.sources.rss_adapter import HTMLScraperAdapter, _parse_feed_date

log = logging.getLogger(__name__)

_LISTING_YEARS = [2026, 2025, 2024]
_BASE = "https://www.ic3.gov"
_NON_HTML_EXTS = (".pdf", ".doc", ".docx", ".xlsx", ".zip", ".ppt", ".pptx")


class IC3AlertsAdapter(HTMLScraperAdapter):
    """IC3 Public Service Announcements — HTML scrape of yearly listing pages."""

    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Scrape all year listing pages and return stubs — no full article fetches."""
        stubs: list[RawItemStub] = []
        seen_urls: set[str] = set()

        for year in _LISTING_YEARS:
            listing_url = f"{_BASE}/PSA/{year}"
            try:
                listing_html = await self._http_get(listing_url)
            except Exception as exc:
                log.warning(f"Could not fetch IC3 listing {listing_url}: {exc}")
                continue

            refs = await self.parse_listing_page(listing_html)
            for ref in refs:
                url = ref.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

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

        log.info(f"IC3: found {len(stubs)} stubs across {_LISTING_YEARS}")
        return stubs

    async def fetch_items(self) -> list[RawItemData]:
        """Full fetch: collect stubs then fetch each article."""
        stubs = await self.fetch_item_stubs()
        items: list[RawItemData] = []

        for stub in stubs:
            try:
                raw_text, raw_html = await self.fetch_full_article(stub.item_url)
            except Exception as exc:
                log.warning(f"Could not fetch IC3 article {stub.item_url}: {exc}")
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

        log.info(f"IC3: fetched {len(items)} full items")
        return items

    async def parse_listing_page(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        for a_tag in soup.find_all("a", href=True):
            href: str = a_tag["href"]
            if "/PSA/" not in href:
                continue
            # Skip non-HTML documents (PDFs, Office files, etc.)
            if any(href.lower().endswith(ext) for ext in _NON_HTML_EXTS):
                continue
            url = href if href.startswith("http") else f"{_BASE}{href}"

            title = a_tag.get_text(strip=True)
            if not title:
                continue

            date_str: str | None = None
            parent = a_tag.find_parent("tr")
            if parent:
                tds = parent.find_all("td")
                for td in tds:
                    text = td.get_text(strip=True)
                    if len(text) <= 15 and any(c.isdigit() for c in text):
                        date_str = text
                        break

            results.append({"url": url, "title": title, "date": date_str})

        return results
