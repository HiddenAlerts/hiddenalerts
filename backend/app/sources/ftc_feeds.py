"""FTC Press Releases — HTML listing scrape.

The FTC RSS feed returns 403 to automated requests regardless of User-Agent, so
the HTML listing is the discovery path.

The previous parser selected ``div.view-content li, div.views-row, article``,
which matches *nested* containers on this page (the audit counted 24 ``<article>``,
24 ``.views-row`` and 5 ``.view-content`` in 1.04 MB of HTML). It captured the
same anchor repeatedly — 48 references collapsing to 4 unique URLs — and, taking
each container's *first* link, emitted the listing page itself and non-articles
such as ``/enforcement/competition-matters/…``. Production bears this out: of the
19 stored FTC items, **none** is a press release.

Discovery now starts from links that match the press-release URL shape and reads
each item's own date.
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

# ftc.gov dates its content in the path: a press release is
# /news-events/news/press-releases/<YYYY>/<MM>/<slug>. Requiring the full shape
# keeps out the listing page itself (/news-events/news/press-releases), its
# year and month index pages, the topic and pagination variants, and the
# neighbouring sections the old parser kept emitting — /news-events/events/…,
# /enforcement/competition-matters/…, /policy/advocacy-research, /microeconomics.
# Starting from links that match this needs no exclusion list and no fallback.
_PRESS_RELEASE_PATH = re.compile(
    r"^/news-events/news/press-releases/(?P<year>\d{4})/(?P<month>\d{2})/"
    r"(?P<slug>[^/]+)/?$",
    re.I,
)


class FTCFeedsAdapter(HTMLScraperAdapter):
    """FTC Press Releases — HTML scrape of the configured listing page."""

    @property
    def listing_url(self) -> str:
        """The listing page from the source row.

        Configuration is required and authoritative: a blank, non-http(s) or
        unsafe ``base_url`` raises rather than silently falling back to a
        hardcoded page, so a wrong row shows up as a failed run instead of
        collecting from somewhere nobody chose.
        """
        configured = (getattr(self.source, "base_url", None) or "").strip()
        reason = _unsafe_target_reason(configured) if configured else "not configured"
        if reason:
            raise ValueError(
                f"{self._source_label()}: base_url must be a public http(s) listing "
                f"URL ({reason})"
            )
        return configured

    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Fetch the listing page and return stubs — no full article fetches."""
        result = await self.fetch(self.listing_url, accept=AcceptPolicy.HTML_LISTING)
        stubs = self._parse_items(result.text, result.final_url)

        dated = sum(1 for stub in stubs if stub.published_at is not None)
        log.info("FTC listing: found %d stubs, %d dated", len(stubs), dated)
        return stubs

    async def fetch_items(self) -> list[RawItemData]:
        """Full fetch: collect stubs then fetch each article."""
        stubs = await self.fetch_item_stubs()
        items: list[RawItemData] = []

        for stub in stubs:
            try:
                raw_text, raw_html = await self.fetch_full_article(stub.item_url)
            except Exception as exc:
                log.warning("FTC: could not fetch article %s: %s", stub.item_url, exc)
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

        log.info("FTC: fetched %d full items", len(items))
        return items

    def _parse_items(self, html: str, listing_url: str) -> list[RawItemStub]:
        soup = BeautifulSoup(html, "lxml")
        listing_host = urlparse(listing_url).netloc.lower()

        # Pass 1: which links are press releases at all. Pass 2 needs the whole
        # set so each item's scope can be bounded by its neighbours. Repeated
        # anchors to the same release are left in — the collector deduplicates by
        # normalized URL hash, within the batch as well as against storage.
        accepted: list[tuple] = []
        for anchor in soup.find_all("a", href=True):
            url = self._press_release_url(anchor["href"], listing_url, listing_host)
            if url is None:
                continue
            title = anchor.get_text(" ", strip=True)
            if not title:
                continue
            accepted.append((anchor, url, title))

        # A card carries more than one link to the same release — a thumbnail as
        # well as the heading — so an item's scope must be bounded by anchors
        # pointing at a *different* release. Bounding on every accepted anchor
        # would stop inside the card and lose the date that sits beside it.
        ids_by_url: dict[str, set[int]] = {}
        for anchor, url, _ in accepted:
            ids_by_url.setdefault(url, set()).add(id(anchor))
        every_id = {anchor_id for ids in ids_by_url.values() for anchor_id in ids}

        return [
            RawItemStub(
                source_name=self.source.name,  # type: ignore[attr-defined]
                item_url=url,
                title=title,
                published_at=item_date(
                    item_scope(anchor, every_id - ids_by_url[url])
                ),
            )
            for anchor, url, title in accepted
        ]

    def _press_release_url(self, href, listing_url: str, listing_host: str) -> str | None:
        """The absolute URL for a real press-release link, else ``None``."""
        if not isinstance(href, str):
            return None
        try:
            url = urljoin(listing_url, href.strip())
            parsed = urlparse(url)
            host = parsed.netloc.lower()
        except (TypeError, ValueError):
            # An unparseable href costs us this one candidate, not the whole
            # listing. The raw value is page-controlled, so it is not logged.
            log.debug("FTC: skipping an unparseable listing href")
            return None
        if host != listing_host or _unsafe_target_reason(url):
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
