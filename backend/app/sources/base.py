import asyncio
import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import certifi
import httpx
import requests as _requests
from bs4 import BeautifulSoup
from pydantic import BaseModel

from app.sources.host_limiter import host_limiter, normalize_host
from app.sources.http_errors import (
    ChallengeDetected,
    ContentTypeMismatch,
    PermanentFetchError,
    RateLimitedError,
    RedirectLoop,
    TooManyRedirects,
    TransientFetchError,
    UnsupportedDocument,
    UnsupportedRedirectScheme,
)
from app.sources.response_policy import (
    AcceptPolicy,
    classify_challenge,
    content_type_allowed,
    is_unsupported_document,
)

log = logging.getLogger(__name__)

MAX_REDIRECTS = 5
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_ALLOWED_SCHEMES = frozenset({"http", "https"})
# Never replayed to a different host on a redirect.
_SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "proxy-authorization", "x-api-key"})
_MAX_RETRY_AFTER_SECONDS = 30.0

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


@dataclass
class FetchResult:
    """Structured outcome of a successful fetch."""

    url: str
    final_url: str
    status: int
    content_type: str
    text: str
    redirects: int = 0
    hosts: tuple[str, ...] = field(default_factory=tuple)


def safe_redirect_headers(headers: dict, *, cross_host: bool) -> dict:
    """Headers to send on a redirect hop.

    Credential-bearing headers are dropped when the destination host differs, so
    a redirect can never leak them to another origin. Ordinary public headers
    (User-Agent, Accept, Accept-Language) are preserved so the request keeps
    identifying itself the same way.
    """
    if not cross_host:
        return dict(headers)
    return {k: v for k, v in headers.items() if k.lower() not in _SENSITIVE_HEADERS}


def _retry_after_seconds(value: str | None) -> float | None:
    """Parse a numeric Retry-After, clamped so a hostile value cannot stall a run."""
    if not value:
        return None
    try:
        return max(0.0, min(float(value.strip()), _MAX_RETRY_AFTER_SECONDS))
    except (TypeError, ValueError):
        return None


def _sync_requests_get(url: str, headers: dict, timeout: float) -> tuple[int, str, str, str]:
    """One synchronous request with redirects disabled.

    Returns (status, content_type, body, location). Runs in a thread pool; the
    caller owns redirect following and rate limiting.
    """
    session = _requests.Session()
    session.headers.update(headers)
    resp = session.get(url, timeout=timeout, allow_redirects=False)
    return (
        resp.status_code,
        resp.headers.get("content-type", ""),
        resp.text,
        resp.headers.get("location", ""),
    )


def _safe_url(url: str) -> str:
    """URL without query string — query params can carry tokens."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _validate_response(
    url: str, status: int, content_type: str, body: str, raw: bytes, policy: AcceptPolicy
) -> None:
    """Raise the right typed error for a 2xx response we cannot use."""
    if is_unsupported_document(content_type, raw):
        raise UnsupportedDocument(
            "unsupported document type", url=url, status=status,
            content_type=content_type, accepted=tuple(sorted(policy.accepted)),
        )

    verdict = classify_challenge(body, content_type=content_type)
    if verdict:
        raise ChallengeDetected(
            "anti-bot verification page", url=url, status=status, signals=verdict.signals
        )

    if not content_type_allowed(content_type, policy):
        raise ContentTypeMismatch(
            "unexpected content type", url=url, status=status,
            content_type=content_type, accepted=tuple(sorted(policy.accepted)),
        )


def _resolve_redirect(current_url: str, location: str) -> str:
    """Resolve a Location header and reject anything not http(s)."""
    target = urljoin(current_url, (location or "").strip())
    scheme = urlsplit(target).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UnsupportedRedirectScheme(
            f"refusing redirect to {scheme or 'relative'} scheme", url=current_url
        )
    return target


async def _follow(
    url: str,
    *,
    policy: AcceptPolicy,
    headers: dict,
    timeout: float,
    send,
    limiter,
    source_label: str,
) -> FetchResult:
    """Issue one request and follow redirects manually, spacing every hop.

    ``send`` is an awaitable ``(url, headers) -> (status, response_headers, body,
    raw)`` so the httpx and requests tiers share this logic and tests can supply a
    transport without touching the network.
    """
    seen: set[str] = set()
    hosts: list[str] = []
    current = url
    current_headers = dict(headers)

    for hop in range(MAX_REDIRECTS + 1):
        if current in seen:
            raise RedirectLoop(f"redirect loop after {hop} hop(s)", url=current)
        seen.add(current)

        host = normalize_host(urlsplit(current).hostname)
        if host not in hosts:
            hosts.append(host)
        await limiter.acquire(host)

        status, resp_headers, body, raw = await send(current, current_headers)
        lowered = {str(k).lower(): v for k, v in dict(resp_headers).items()}
        content_type = lowered.get("content-type", "")
        location = lowered.get("location", "")

        if status in _REDIRECT_STATUSES and location:
            if hop >= MAX_REDIRECTS:
                raise TooManyRedirects(
                    f"exceeded {MAX_REDIRECTS} redirects", url=current, status=status
                )
            target = _resolve_redirect(current, location)
            next_host = normalize_host(urlsplit(target).hostname)
            cross_host = next_host != host
            if cross_host:
                log.debug(
                    "%s: redirect %s → %s crosses host, re-applying host policy",
                    source_label, host, next_host,
                )
                current_headers = safe_redirect_headers(current_headers, cross_host=True)
            current = target
            continue

        if status == 429:
            raise RateLimitedError(
                "rate limited", url=current, status=status,
                retry_after=_retry_after_seconds(lowered.get("retry-after")),
            )
        if status in _RETRY_STATUSES:
            raise TransientFetchError("retryable server error", url=current, status=status)
        if status >= 400:
            raise PermanentFetchError(f"HTTP {status}", url=current, status=status)

        _validate_response(current, status, content_type, body, raw, policy)
        return FetchResult(
            url=url, final_url=current, status=status, content_type=content_type,
            text=body, redirects=hop, hosts=tuple(hosts),
        )

    raise TooManyRedirects(f"exceeded {MAX_REDIRECTS} redirects", url=current)


async def _playwright_get(url: str, timeout: float, *, limiter=None) -> str:
    """Headless Chromium fetch via Playwright. Last-resort fallback.

    The host limiter is applied to the initial navigation only. Redirects and
    sub-resources fetched inside the browser cannot be spaced individually
    without request interception, which this slice deliberately does not add — so
    browser mode does not carry the same per-hop guarantee as the direct tiers.
    """
    await (limiter or host_limiter).acquire(normalize_host(urlsplit(url).hostname))
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
        """Fetch an article page. Returns (extracted_text, raw_html).

        Raises the typed errors from ``app.sources.http_errors`` — notably
        ``ChallengeDetected`` and ``UnsupportedDocument`` — so a blocked or
        non-readable page is never mistaken for an article with no text.
        """
        result = await self.fetch(url, accept=AcceptPolicy.ARTICLE)
        return extract_text_from_html(result.text), result.text

    async def fetch(
        self,
        url: str,
        *,
        accept: AcceptPolicy = AcceptPolicy.ANY_TEXT,
        retries: int = 3,
        timeout: float = 30.0,
        limiter=None,
    ) -> FetchResult:
        """Fetch one URL through the shared boundary and return a structured result.

        Tier 1  — httpx with a browser User-Agent (primary)
        Tier 2a — requests with a bot-identifying User-Agent
        Tier 2b — requests with minimal headers
        Tier 3  — Playwright, only for pages that need JavaScript rendering

        Tiers 2 and 3 are reached only after an HTTP 403. A detected challenge or
        an unsupported document is conclusive: it stops retries, skips the
        remaining tiers, never launches a browser, and propagates immediately.
        Every attempt, retry and redirect hop passes through the host limiter.
        """
        limiter = limiter or host_limiter
        label = self._source_label()

        async def _httpx_send(target: str, headers: dict):
            async with httpx.AsyncClient(
                headers=headers, timeout=timeout, follow_redirects=False,
                verify=certifi.where(),
            ) as client:
                r = await client.get(target)
                return r.status_code, r.headers, r.text, r.content

        async def _requests_send(target: str, headers: dict):
            loop = asyncio.get_event_loop()
            status, ctype, body, location = await loop.run_in_executor(
                _THREAD_POOL, _sync_requests_get, target, headers, timeout,
            )
            return status, {"content-type": ctype, "location": location}, body, body.encode("utf-8", "replace")

        got_403 = False
        last_exc: Exception | None = None

        for attempt in range(retries):
            try:
                return await _follow(
                    url, policy=accept, headers=_BROWSER_HEADERS, timeout=timeout,
                    send=_httpx_send, limiter=limiter, source_label=label,
                )
            except ChallengeDetected as exc:
                log.warning(
                    "%s: challenge page for %s, signals=%s — not retried, not escalated",
                    label, _safe_url(url), ",".join(exc.signals) or "?",
                )
                raise
            except ContentTypeMismatch as exc:
                log.warning(
                    "%s: %s for %s, content_type=%s",
                    label, type(exc).__name__, _safe_url(url), exc.content_type or "?",
                )
                raise
            except PermanentFetchError as exc:
                if exc.status == 403:
                    got_403 = True
                    last_exc = exc
                    break
                log.warning("%s: %s for %s", label, exc, _safe_url(url))
                raise
            except RateLimitedError as exc:
                last_exc = exc
                if attempt >= retries - 1:
                    raise
                delay = exc.retry_after if exc.retry_after is not None else 2 ** attempt
                log.debug("%s: 429 for %s, retry %d after %.1fs", label, _safe_url(url), attempt + 1, delay)
                await asyncio.sleep(delay)
            except (TransientFetchError, httpx.HTTPError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt >= retries - 1:
                    break
                log.debug("%s: transient failure for %s, retry %d", label, _safe_url(url), attempt + 1)
                await asyncio.sleep(2 ** attempt)

        if not got_403:
            raise TransientFetchError(
                f"failed after {retries} attempt(s)", url=url
            ) from last_exc

        for tier, headers in (("2a", _BOT_HEADERS_FULL), ("2b", _BOT_HEADERS_MINIMAL)):
            log.debug("%s: tier %s for %s", label, tier, _safe_url(url))
            try:
                return await _follow(
                    url, policy=accept, headers=headers, timeout=timeout,
                    send=_requests_send, limiter=limiter, source_label=label,
                )
            except (ChallengeDetected, UnsupportedDocument, ContentTypeMismatch):
                raise
            except Exception as exc:
                last_exc = exc

        log.debug("%s: escalating %s to browser rendering", label, _safe_url(url))
        try:
            text = await _playwright_get(url, timeout=60.0, limiter=limiter)
            return FetchResult(
                url=url, final_url=url, status=200, content_type="text/html",
                text=text, redirects=0, hosts=(normalize_host(urlsplit(url).hostname),),
            )
        except Exception as exc:
            last_exc = exc

        raise PermanentFetchError("all fetch tiers failed", url=url) from last_exc

    async def _http_get(self, url: str, retries: int = 3, timeout: float = 30.0) -> str:
        """Body-only wrapper over :meth:`fetch`, kept for existing call sites."""
        result = await self.fetch(url, retries=retries, timeout=timeout)
        return result.text

    def _source_label(self) -> str:
        sid = getattr(self.source, "id", None)
        name = getattr(self.source, "name", None)
        if sid is not None and name:
            return f"source {sid} '{name}'"
        return name or type(self).__name__
