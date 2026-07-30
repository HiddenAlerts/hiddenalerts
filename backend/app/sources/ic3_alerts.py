"""IC3 Public Service Announcements — yearly HTML listing pages.

The listing is a div/card layout: the audit measured ~42 KB of HTML, 16 ``<time>``
elements and **zero** ``<table>``/``<tr>`` elements. The previous parser read a
date only from a ``<tr>`` ancestor, so it found none and every IC3 row landed with
``published_at = NULL``. It also accepted any href containing ``/PSA/``, which is
why ``/PSA/Archive`` is stored as if it were an article.

Discovery now starts from links that match the real PSA URL shape and reads each
card's own date, falling back to the date encoded in the URL slug.
"""
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.sources.base import (
    RawItemData,
    RawItemStub,
    _safe_url,
    _unsafe_target_reason,
)
from app.sources.html_listing import item_date, item_scope
from app.sources.http_errors import SourceFetchError
from app.sources.response_policy import AcceptPolicy
from app.sources.rss_adapter import HTMLScraperAdapter

log = logging.getLogger(__name__)

# Real PSA articles: /PSA/<4-digit year>/PSA<YYMMDD>, optionally suffixed when
# more than one lands on a day (…/PSA260515-2). A positive rule like this needs
# no exclusion list: /PSA/Archive, /PSA/RSS, category and pagination links simply
# do not match it.
_PSA_PATH = re.compile(r"^/PSA/(?P<year>\d{4})/PSA(?P<slug>\d{6})(?:-\d+)?/?$", re.I)

# The listing pages the adapter walks each run: the current UTC year and the two
# before it. This is the depth the hardcoded [2026, 2025, 2024] list covered, and
# this slice does not change crawl depth — only where the years come from.
LISTING_YEAR_DEPTH = 3


def listing_years(now: datetime | None = None) -> list[int]:
    """The years to crawl, newest first, derived from the current UTC date.

    ``now`` is injectable so the December/January boundary is testable; a naive
    value is read as UTC.
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
    return [moment.year - offset for offset in range(LISTING_YEAR_DEPTH)]


def psa_url_date(path_year: str, slug: str) -> datetime | None:
    """The date encoded in a PSA slug, or ``None`` if it is not a real date.

    ``/PSA/2026/PSA260720`` → 2026-07-20. The two-digit slug year must agree with
    the four-digit year in the path, and the day must exist — so a typo, a
    renumbered file or an unrelated six-digit identifier yields nothing rather
    than a wrong date.
    """
    year, month, day = 2000 + int(slug[:2]), int(slug[2:4]), int(slug[4:6])
    if year != int(path_year):
        return None
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


class IC3AlertsAdapter(HTMLScraperAdapter):
    """IC3 Public Service Announcements — HTML scrape of yearly listing pages."""

    @property
    def listing_root(self) -> str:
        """The PSA root from the source row, e.g. ``https://www.ic3.gov/PSA``.

        Configuration is required: a blank or non-http(s) ``base_url`` raises
        rather than silently falling back to a hardcoded host, so a bad row shows
        up as a failed run instead of collecting from somewhere nobody chose.
        """
        configured = (getattr(self.source, "base_url", None) or "").strip()
        if not configured or urlparse(configured).scheme not in ("http", "https"):
            raise ValueError(
                f"{self._source_label()}: base_url must be an http(s) PSA listing root, "
                f"got {configured!r}"
            )
        return configured.rstrip("/")

    def listing_urls(self, now: datetime | None = None) -> list[str]:
        return [f"{self.listing_root}/{year}" for year in listing_years(now)]

    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Scrape each year listing page and return stubs — no article fetches.

        The current UTC year — the first URL :meth:`listing_urls` returns — is
        **mandatory**: every new PSA appears there, so any failure fetching or
        parsing it propagates and fails the run. Swallowing it is exactly how a
        challenged listing becomes a "successful" zero-item run. The older year
        pages are optional history; a typed fetch failure there is logged and
        skipped, and the pages that answered still contribute.

        Parsing is never inside a catch-all: a parser defect must surface as a
        failed run rather than as silently missing items.

        Duplicate URLs across year pages are left in: the collector deduplicates
        by normalized URL hash, within the batch as well as against storage.
        """
        current_url, *historical_urls = self.listing_urls()

        result = await self.fetch(current_url, accept=AcceptPolicy.HTML_LISTING)
        stubs = self._parse_items(result.text, result.final_url)

        for listing_url in historical_urls:
            try:
                result = await self.fetch(listing_url, accept=AcceptPolicy.HTML_LISTING)
            except SourceFetchError as exc:
                log.warning(
                    "IC3: skipping historical listing %s (%s)",
                    _safe_url(listing_url), type(exc).__name__,
                )
                continue
            stubs.extend(self._parse_items(result.text, result.final_url))

        dated = sum(1 for stub in stubs if stub.published_at is not None)
        log.info("IC3: found %d stubs, %d dated", len(stubs), dated)
        return stubs

    async def fetch_items(self) -> list[RawItemData]:
        """Full fetch: collect stubs then fetch each article."""
        stubs = await self.fetch_item_stubs()
        items: list[RawItemData] = []

        for stub in stubs:
            try:
                raw_text, raw_html = await self.fetch_full_article(stub.item_url)
            except Exception as exc:
                log.warning("IC3: could not fetch article %s: %s", stub.item_url, exc)
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

        log.info("IC3: fetched %d full items", len(items))
        return items

    def _parse_items(self, html: str, listing_url: str) -> list[RawItemStub]:
        soup = BeautifulSoup(html, "lxml")
        listing_host = urlparse(listing_url).netloc.lower()

        # Pass 1: which links are PSA articles at all. Pass 2 needs the whole set
        # so each card's scope can be bounded by its neighbours.
        accepted: list[tuple] = []
        for anchor in soup.find_all("a", href=True):
            resolved = self._psa_url(anchor["href"], listing_url, listing_host)
            if resolved is None:
                continue
            title = anchor.get_text(" ", strip=True)
            if not title:
                continue
            accepted.append((anchor, *resolved, title))

        anchor_ids = {id(entry[0]) for entry in accepted}

        stubs: list[RawItemStub] = []
        for anchor, url, path_year, slug, title in accepted:
            published_at = item_date(item_scope(anchor, anchor_ids))
            if published_at is None:
                published_at = psa_url_date(path_year, slug)
            stubs.append(
                RawItemStub(
                    source_name=self.source.name,  # type: ignore[attr-defined]
                    item_url=url,
                    title=title,
                    published_at=published_at,
                )
            )
        return stubs

    def _psa_url(self, href, listing_url: str, listing_host: str):
        """``(absolute_url, path_year, slug)`` for a real PSA link, else ``None``."""
        if not isinstance(href, str):
            return None
        try:
            url = urljoin(listing_url, href.strip())
            parsed = urlparse(url)
            host = parsed.netloc.lower()
        except (TypeError, ValueError):
            # An unparseable href — an unclosed IPv6 bracket, an invalid host or
            # port — costs us this one candidate, not the whole listing. The raw
            # value is page-controlled, so it is not written to the log.
            log.debug("IC3: skipping an unparseable listing href")
            return None
        if host != listing_host or _unsafe_target_reason(url):
            return None
        match = _PSA_PATH.match(parsed.path)
        if not match:
            return None
        return url, match.group("year"), match.group("slug")

    async def parse_listing_page(self, html: str) -> list[dict]:
        """Legacy dict view of one listing page, kept for the base-class contract."""
        return [
            {"url": stub.item_url, "title": stub.title, "date": stub.published_at}
            for stub in self._parse_items(html, f"{self.listing_root}/")
        ]
