import logging

from bs4 import BeautifulSoup

from app.sources.rss_adapter import HTMLScraperAdapter

log = logging.getLogger(__name__)

_BASE = "https://www.justice.gov"
_LISTING_URL = "https://www.justice.gov/news"


class DOJPressAdapter(HTMLScraperAdapter):
    """DOJ Press Releases — HTML scrape of justice.gov/news listing."""

    async def parse_listing_page(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # DOJ news page: articles listed as <li> or <div> with h3/h2 links
        # The listing uses view-content with rows of articles
        for article in soup.select("li.views-row, div.views-row, article"):
            a_tag = article.find("a", href=True)
            if not a_tag:
                continue

            href: str = a_tag["href"]
            url = href if href.startswith("http") else f"{_BASE}{href}"
            title = a_tag.get_text(strip=True)

            # Try to extract date from <span class="date-display-single"> or similar
            date_str: str | None = None
            date_el = article.find(
                ["span", "div", "time"],
                class_=lambda c: c and any(
                    kw in c for kw in ("date", "time", "field-date")
                ),
            )
            if date_el:
                date_str = date_el.get_text(strip=True)
            elif article.find("time"):
                date_str = article.find("time").get("datetime") or article.find("time").get_text(strip=True)

            if title and url:
                results.append({"url": url, "title": title, "date": date_str})

        # Fallback: scan all links that look like DOJ press releases
        if not results:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "/opa/pr/" in href or "/usao/" in href:
                    url = href if href.startswith("http") else f"{_BASE}{href}"
                    title = a_tag.get_text(strip=True)
                    if title:
                        results.append({"url": url, "title": title, "date": None})

        log.info(f"DOJ listing: found {len(results)} article references")
        return results
