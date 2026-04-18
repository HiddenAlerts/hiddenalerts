import asyncio
import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import certifi
import httpx
import requests as _requests
from bs4 import BeautifulSoup
from pydantic import BaseModel

log = logging.getLogger(__name__)

# Tier 1: Browser-like UA — works for most sites
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Tier 2a: Bot-identifying UA — accepted by many .gov sites per robots.txt etiquette
_BOT_HEADERS_FULL = {
    "User-Agent": "HiddenAlerts Research bot@hiddenalerts.com",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Tier 2b: Minimal headers — sometimes less is more with aggressive WAFs
_BOT_HEADERS_MINIMAL = {
    "User-Agent": "HiddenAlerts Research bot@hiddenalerts.com",
    "Accept-Encoding": "gzip, deflate",
}

# Shared thread pool for running synchronous requests calls from async context
_THREAD_POOL = ThreadPoolExecutor(max_workers=4)

# Keep DEFAULT_HEADERS as alias so existing adapter code still works
DEFAULT_HEADERS = _BROWSER_HEADERS


class RawItemStub(BaseModel):
    """Lightweight descriptor for a discovered article — no full content yet.

    Stage 1 of the pipeline: adapters return stubs (just URL + metadata) so the
    collector can pre-filter by URL hash and publication date before spending HTTP
    calls on full article fetches.
    """

    source_name: str
    item_url: str
    title: str
    published_at: datetime | None
    summary: str = ""  # RSS/feed summary — used as raw_text fallback if full fetch fails


class RawItemData(BaseModel):
    """Full article data including raw text and HTML — produced after fetch_full_article."""

    source_name: str
    item_url: str
    title: str
    published_at: datetime | None
    raw_text: str
    raw_html: str


def extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML, stripping scripts/styles."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return " ".join(text.split())


def _is_bot_challenge(html: str) -> bool:
    """Detect bot-protection challenge pages that return HTTP 200 but no real content.

    Akamai, Cloudflare, and similar CDNs sometimes serve a JS challenge or interstitial
    page with a 200 status code. These pages are tiny (< 10 KB) and contain telltale
    markers. When detected, the caller should escalate to Playwright so the challenge
    can be rendered and bypassed.
    """
    if len(html) > 15_000:
        return False  # Real content pages are large — skip the check
    markers = (
        "akamai-privacy",
        "_cdn.akam.net",
        "AkamaiGHost",
        "cf-browser-verification",
        "Just a moment",
        "Enable JavaScript and cookies",
        "Please enable cookies",
        "Checking if the site connection is secure",
        "DDoS protection by",
        "Ray ID",
    )
    lower = html.lower()
    return any(m.lower() in lower for m in markers)


def _sync_requests_get(url: str, headers: dict, timeout: float) -> str:
    """Synchronous requests.get — runs in a thread pool from async context."""
    session = _requests.Session()
    session.headers.update(headers)
    resp = session.get(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


async def _playwright_get(url: str, timeout: float) -> str:
    """Headless Chromium fetch via Playwright. Last-resort fallback."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("playwright is not installed — run: playwright install chromium")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=_BROWSER_HEADERS["User-Agent"],
                extra_http_headers={"Accept-Language": "en-US,en;q=0.5"},
            )
            page = await context.new_page()
            await page.goto(url, timeout=int(timeout * 1000), wait_until="domcontentloaded")
            content = await page.content()
            return content
        finally:
            await browser.close()


class BaseSourceAdapter(ABC):
    def __init__(self, source: object) -> None:
        self.source = source

    @abstractmethod
    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Stage 1: Fetch lightweight stubs (URL + metadata only, no full article fetch).

        Parses the feed/listing page and returns one stub per discovered article.
        The collector uses this for URL-hash and date pre-filtering before deciding
        which articles actually need to be fetched.
        """
        pass

    @abstractmethod
    async def fetch_items(self) -> list[RawItemData]:
        """Full fetch: stubs + full article content. Used for direct/legacy calls."""
        pass

    async def fetch_full_article(self, url: str) -> tuple[str, str]:
        """Fetch article page. Returns (extracted_text, raw_html)."""
        html = await self._http_get(url)
        text = extract_text_from_html(html)
        return text, html

    async def _http_get(self, url: str, retries: int = 3, timeout: float = 30.0) -> str:
        """3-tier fetch with fallback chain:

        Tier 1 — httpx with browser User-Agent (primary, handles most sites)
        Tier 2a — requests with bot-identifying UA (accepted by .gov sites per robots.txt)
        Tier 2b — requests with minimal headers (bypasses some WAF over-matching)
        Tier 3 — Playwright headless Chromium (JS rendering + Cloudflare bypass)

        Each tier is only attempted if the previous one returns HTTP 403.
        Network errors (timeouts, connection refused) are retried within Tier 1 only.
        """
        loop = asyncio.get_event_loop()

        # ── Tier 1: httpx + browser UA ──────────────────────────────────────────
        last_exc: Exception | None = None
        got_403 = False

        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(
                    headers=_BROWSER_HEADERS,
                    timeout=timeout,
                    follow_redirects=True,
                    verify=certifi.where(),
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    if _is_bot_challenge(response.text):
                        log.info(f"[Tier 1] Bot-challenge page detected for {url} — escalating to Playwright")
                        return await _playwright_get(url, timeout=60.0)
                    return response.text
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code == 403:
                    got_403 = True
                    break  # 403 won't change on retry — skip straight to Tier 2
                if exc.response.status_code == 404:
                    log.warning(f"404 Not Found for {url} — skipping retries.")
                    raise RuntimeError(f"404 Not Found for {url}") from exc
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    log.warning(f"Retry {attempt + 1}/{retries} for {url}: {exc}")
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    log.warning(f"Retry {attempt + 1}/{retries} for {url}: {exc}")

        if not got_403:
            raise RuntimeError(f"Failed to fetch {url} after {retries} attempts") from last_exc

        # ── Tier 2a: requests + bot-identifying UA ───────────────────────────────
        log.info(f"[Tier 2a] httpx got 403 for {url} — trying requests bot UA")
        try:
            text = await loop.run_in_executor(
                _THREAD_POOL, _sync_requests_get, url, _BOT_HEADERS_FULL, timeout,
            )
            log.info(f"[Tier 2a] SUCCESS for {url}")
            return text
        except _requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 403:
                log.info(f"[Tier 2a] Still 403 for {url} — trying minimal headers")
            else:
                log.warning(f"[Tier 2a] Failed for {url}: {exc}")
        except Exception as exc:
            log.warning(f"[Tier 2a] Failed for {url}: {exc}")

        # ── Tier 2b: requests + minimal headers ─────────────────────────────────
        log.info(f"[Tier 2b] Trying minimal headers for {url}")
        try:
            text = await loop.run_in_executor(
                _THREAD_POOL, _sync_requests_get, url, _BOT_HEADERS_MINIMAL, timeout,
            )
            log.info(f"[Tier 2b] SUCCESS for {url}")
            return text
        except _requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 403:
                log.info(f"[Tier 2b] Still 403 for {url} — escalating to Playwright")
            else:
                log.warning(f"[Tier 2b] Failed for {url}: {exc}")
        except Exception as exc:
            log.warning(f"[Tier 2b] Failed for {url}: {exc}")

        # ── Tier 3: Playwright headless Chromium ─────────────────────────────────
        log.info(f"[Tier 3] Launching Playwright for {url}")
        try:
            text = await _playwright_get(url, timeout=60.0)
            log.info(f"[Tier 3] SUCCESS for {url}")
            return text
        except Exception as exc:
            log.warning(f"[Tier 3] Playwright failed for {url}: {exc}")

        raise RuntimeError(
            f"All fetch tiers failed for {url} (httpx 403 → requests 403 → Playwright failed)"
        ) from last_exc
