"""FinCEN Press Releases — HTML listing scrape.

FinCEN publishes no RSS feed. The audit found ~15 ``<time datetime>`` elements on
the listing but only one broad ``<article>``/page wrapper, so the previous primary
selector matched the wrapper, took *its* first link — routinely a navigation link
rather than a press release — and then fell through to a link-scan fallback that
emitted no dates at all. Every stored FinCEN row has ``published_at = NULL``.

Discovery now starts from links that match the press-release URL shape and reads
each row's own ``<time>``.
"""
import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.sources.base import RawItemData, RawItemStub, _unsafe_target_reason
from app.sources.html_listing import item_date, item_scope
from app.sources.response_policy import AcceptPolicy
from app.sources.rss_adapter import HTMLScraperAdapter

log = logging.getLogger(__name__)

# Every FinCEN press release stored to date lives under this path with a slug:
# /news/news-releases/<slug>. Starting from links that match keeps the page
# wrapper, the section navigation and unrelated links out without an exclusion
# list, and without the dateless fallback that used to carry the source.
_PRESS_RELEASE_PATH = re.compile(r"^/news/news-releases/(?P<slug>[^/]+)/?$", re.I)


class FinCENPressAdapter(HTMLScraperAdapter):
    """FinCEN Press Releases — HTML scrape of the configured listing page."""

    @property
    def listing_url(self) -> str:
        """The listing page from the source row.

        Configuration is required: a blank or non-http(s) ``base_url`` raises
        rather than silently falling back to a hardcoded host.
        """
        configured = (getattr(self.source, "base_url", None) or "").strip()
        if not configured or urlparse(configured).scheme not in ("http", "https"):
            raise ValueError(
                f"{self._source_label()}: base_url must be an http(s) listing URL, "
                f"got {configured!r}"
            )
        return configured

    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Fetch the listing page and return stubs — no full article fetches."""
        result = await self.fetch(self.listing_url, accept=AcceptPolicy.HTML_LISTING)
        stubs = self._parse_items(result.text, result.final_url)

        dated = sum(1 for stub in stubs if stub.published_at is not None)
        log.info("FinCEN listing: found %d stubs, %d dated", len(stubs), dated)
        return stubs

    async def fetch_items(self) -> list[RawItemData]:
        """Full fetch: collect stubs then fetch each article."""
        stubs = await self.fetch_item_stubs()
        items: list[RawItemData] = []

        for stub in stubs:
            try:
                raw_text, raw_html = await self.fetch_full_article(stub.item_url)
            except Exception as exc:
                log.warning("FinCEN: could not fetch article %s: %s", stub.item_url, exc)
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

        log.info("FinCEN: fetched %d full items", len(items))
        return items

    def _parse_items(self, html: str, listing_url: str) -> list[RawItemStub]:
        soup = BeautifulSoup(html, "lxml")
        listing_host = urlparse(listing_url).netloc.lower()

        # Pass 1: which links are press releases at all. Pass 2 needs the whole
        # set so each row's scope can be bounded by its neighbours.
        accepted: list[tuple] = []
        for anchor in soup.find_all("a", href=True):
            url = self._press_release_url(anchor["href"], listing_url, listing_host)
            if url is None:
                continue
            title = anchor.get_text(" ", strip=True)
            if not title:
                continue
            accepted.append((anchor, url, title))

        anchor_ids = {id(entry[0]) for entry in accepted}

        return [
            RawItemStub(
                source_name=self.source.name,  # type: ignore[attr-defined]
                item_url=url,
                title=title,
                published_at=item_date(item_scope(anchor, anchor_ids)),
            )
            for anchor, url, title in accepted
        ]

    def _press_release_url(self, href: str, listing_url: str, listing_host: str) -> str | None:
        """The absolute URL for a real press-release link, else ``None``."""
        url = urljoin(listing_url, href.strip())
        parsed = urlparse(url)
        if parsed.netloc.lower() != listing_host or _unsafe_target_reason(url):
            return None
        if not _PRESS_RELEASE_PATH.match(parsed.path):
            return None
        return url

    async def parse_listing_page(self, html: str) -> list[dict]:
        """Legacy dict view of the listing, kept for the base-class contract."""
        return [
            {"url": stub.item_url, "title": stub.title, "date": stub.published_at}
            for stub in self._parse_items(html, self.listing_url)
        ]
