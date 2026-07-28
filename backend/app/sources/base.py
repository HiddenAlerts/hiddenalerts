import asyncio
import ipaddress
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
    EmptyContent,
    SourceFetchError,
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
    BodyKind,
    body_kind_allowed,
    classify_challenge,
    content_type_allowed,
    is_unsupported_document,
    sniff_body_kind,
)

log = logging.getLogger(__name__)

MAX_REDIRECTS = 5
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_ALLOWED_SCHEMES = frozenset({"http", "https"})
# Never replayed to a different host on a redirect.
_SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "proxy-authorization", "x-api-key"})
_MAX_RETRY_AFTER_SECONDS = 30.0
_DEFAULT_PORTS = {"http": 80, "https": 443}
# Outcomes no alternative fingerprint or browser can improve on.
_CONCLUSIVE_ERRORS = (
    ChallengeDetected, UnsupportedDocument, ContentTypeMismatch, EmptyContent,
    RedirectLoop, TooManyRedirects, UnsupportedRedirectScheme, RateLimitedError,
)

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
    collector can pre-filter by normalized URL hash before spending HTTP calls on
    full article fetches. ``published_at`` is stored for ordering and health
    reporting; it never gates ingestion.
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


@dataclass
class FetchResult:
    """Structured outcome of a successful fetch."""

    url: str
    final_url: str
    status: int
    content_type: str
    text: str
    redirects: int = 0
    #: Distinct hosts touched, in first-seen order — not one entry per hop.
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


def _sync_requests_get(url: str, headers: dict, timeout: float) -> tuple[int, dict, str, bytes]:
    """One synchronous request with redirects disabled.

    Returns (status, response headers, decoded text, raw bytes). The raw bytes are
    preserved so magic-byte detection works in this tier too, and the full header
    map is preserved so Retry-After and Location survive. Runs in a thread pool;
    the caller owns redirect following and rate limiting.
    """
    with _requests.Session() as session:
        session.headers.update(headers)
        resp = session.get(url, timeout=timeout, allow_redirects=False)
        return resp.status_code, dict(resp.headers), resp.text, resp.content


def _safe_url(url: str) -> str:
    """URL without query string — query params can carry tokens."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _reject_challenge_or_binary(
    url: str, status: int, content_type: str, body: str, raw: bytes,
    kind: BodyKind, policy: AcceptPolicy,
) -> None:
    """Checks that apply to *any* status, before ordinary error handling.

    A challenge is a challenge whether the CDN labels it 200 or 403, and a PDF is
    a PDF regardless of the declared type — so both are settled here rather than
    being mistaken for a retryable status or an acceptable document.
    """
    if kind is BodyKind.BINARY or is_unsupported_document(content_type, raw):
        raise UnsupportedDocument(
            "unsupported document type", url=url, status=status,
            content_type=content_type, accepted=tuple(sorted(policy.accepted)),
        )

    verdict = classify_challenge(body, content_type=content_type, body_kind=kind)
    if verdict:
        raise ChallengeDetected(
            "anti-bot verification page", url=url, status=status, signals=verdict.signals
        )


def _validate_success_body(
    url: str, status: int, content_type: str, body: str, kind: BodyKind, policy: AcceptPolicy
) -> None:
    """Checks that only make sense once the response is known to be a 2xx."""
    if kind is BodyKind.EMPTY:
        raise EmptyContent("empty response body", url=url, status=status)

    declared = content_type_allowed(content_type, policy)
    if not declared:
        raise ContentTypeMismatch(
            "unexpected content type", url=url, status=status,
            content_type=content_type, accepted=tuple(sorted(policy.accepted)),
        )
    # A declared type we accept can still be contradicted by the body itself, and
    # a missing type has nothing to check but the body.
    if not body_kind_allowed(kind, policy):
        raise ContentTypeMismatch(
            f"body looks like {kind.value}", url=url, status=status,
            content_type=content_type, accepted=tuple(sorted(policy.accepted)),
        )


def _origin(url: str) -> tuple[str, str, int]:
    """(scheme, host, effective port) — the identity that decides header reuse."""
    parts = urlsplit(url)
    scheme = (parts.scheme or "").lower()
    port = parts.port or _DEFAULT_PORTS.get(scheme, 0)
    return scheme, normalize_host(parts.hostname), port


def _is_unsafe_redirect_target(url: str) -> str | None:
    """Reason a redirect target must not be followed, or None if it is fine.

    Blocks credentials in the URL and literal internal addresses. This is a
    literal-address check only — a public hostname that *resolves* to a private
    address is not caught, so full DNS-rebinding protection is NOT implemented.
    """
    parts = urlsplit(url)
    if parts.username or parts.password or "@" in (parts.netloc.split("]")[-1]):
        return "userinfo in redirect target"
    host = normalize_host(parts.hostname)
    if not host:
        return "redirect target has no host"
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".home.arpa")):
        return f"internal hostname {host}"
    try:
        addr = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None
    if (addr.is_private or addr.is_loopback or addr.is_link_local
            or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
        return f"non-public address {host}"
    return None


def _resolve_redirect(current_url: str, location: str) -> str:
    """Resolve a Location header and reject schemes and targets we will not follow."""
    target = urljoin(current_url, (location or "").strip())
    scheme = urlsplit(target).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UnsupportedRedirectScheme(
            f"refusing redirect to {scheme or 'relative'} scheme", url=current_url
        )
    reason = _is_unsafe_redirect_target(target)
    if reason:
        raise UnsupportedRedirectScheme(f"refusing redirect: {reason}", url=current_url)
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

        if status in _REDIRECT_STATUSES:
            if not location:
                raise PermanentFetchError(
                    f"HTTP {status} redirect without a Location header",
                    url=current, status=status,
                )
            if hop >= MAX_REDIRECTS:
                raise TooManyRedirects(
                    f"exceeded {MAX_REDIRECTS} redirects", url=current, status=status
                )
            target = _resolve_redirect(current, location)
            next_host = normalize_host(urlsplit(target).hostname)
            if _origin(target) != _origin(current):
                log.debug(
                    "%s: redirect %s → %s crosses origin, re-applying host policy",
                    source_label, host, next_host,
                )
                current_headers = safe_redirect_headers(current_headers, cross_host=True)
            current = target
            continue

        if 300 <= status < 400:
            # 304/305/306 and friends: we issue no conditional requests, so any
            # other 3xx here is an upstream contract we do not implement.
            raise PermanentFetchError(
                f"unexpected HTTP {status} redirect status", url=current, status=status
            )

        # Challenge and binary checks run BEFORE status handling: a CDN may serve
        # an interstitial as 200 or 403, and either way it is conclusive.
        kind = sniff_body_kind(body, raw)
        _reject_challenge_or_binary(current, status, content_type, body, raw, kind, policy)

        if status == 429:
            raise RateLimitedError(
                "rate limited", url=current, status=status,
                retry_after=_retry_after_seconds(lowered.get("retry-after")),
            )
        if status in _RETRY_STATUSES:
            raise TransientFetchError("retryable server error", url=current, status=status)
        if status >= 400:
            raise PermanentFetchError(f"HTTP {status}", url=current, status=status)

        _validate_success_body(current, status, content_type, body, kind, policy)
        return FetchResult(
            url=url, final_url=current, status=status, content_type=content_type,
            text=body, redirects=hop, hosts=tuple(hosts),
        )

    raise TooManyRedirects(f"exceeded {MAX_REDIRECTS} redirects", url=current)


async def _playwright_get(url: str, timeout: float, *, limiter=None) -> tuple[int | None, str, str]:
    """Headless Chromium fetch. Returns (status, final_url, html).

    The host limiter is applied to the initial navigation only. Redirects and
    sub-resources fetched inside the browser cannot be spaced individually
    without request interception, which is deliberately not implemented — so
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
            response = await page.goto(
                url, timeout=int(timeout * 1000), wait_until="domcontentloaded"
            )
            status = response.status if response is not None else None
            final_url = page.url or url
            return status, final_url, await page.content()
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
        text = extract_text_from_html(result.text)
        if not text.strip():
            # Nothing readable survived extraction. Raising lets the collector use
            # the feed summary instead of storing an article with no text.
            raise EmptyContent(
                "article has no extractable text", url=result.final_url, status=result.status
            )
        return text, result.text

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
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                _THREAD_POOL, _sync_requests_get, target, headers, timeout,
            )

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

        # Only an ordinary, non-challenge 403 reaches the fallback tiers. Every
        # conclusive outcome below is re-raised untouched: a different HTTP
        # fingerprint or a browser cannot change a PDF, a redirect loop, a rate
        # limit or a verification page into a usable document.
        for tier, headers in (("2a", _BOT_HEADERS_FULL), ("2b", _BOT_HEADERS_MINIMAL)):
            log.debug("%s: tier %s for %s", label, tier, _safe_url(url))
            try:
                return await _follow(
                    url, policy=accept, headers=headers, timeout=timeout,
                    send=_requests_send, limiter=limiter, source_label=label,
                )
            except _CONCLUSIVE_ERRORS:
                raise
            except PermanentFetchError as exc:
                if exc.status != 403:
                    raise
                last_exc = exc
            except Exception as exc:
                last_exc = exc

        log.debug("%s: escalating %s to browser rendering", label, _safe_url(url))
        try:
            return await self._browser_fetch(url, accept, limiter, label)
        except SourceFetchError:
            # The browser is the last tier, and it classified the response — that
            # verdict is the answer, not something to flatten into a generic error.
            raise
        except Exception as exc:
            last_exc = exc

        raise PermanentFetchError("all fetch tiers failed", url=url) from last_exc

    async def _browser_fetch(self, url, accept, limiter, label) -> FetchResult:
        """Render with a browser and validate the result like any other response.

        The rendered page gets the same treatment as a direct fetch: a challenge,
        an error status, an unsupported document, an unacceptable content kind or
        an empty page are all rejected rather than reported as a success.
        """
        status, final_url, html = await _playwright_get(url, timeout=60.0, limiter=limiter)
        kind = sniff_body_kind(html)
        effective_status = status if status is not None else 200

        _reject_challenge_or_binary(
            final_url, effective_status, "", html, b"", kind, accept
        )
        if status is not None and status >= 400:
            if status in _RETRY_STATUSES:
                raise TransientFetchError(
                    "browser navigation failed", url=final_url, status=status
                )
            raise PermanentFetchError(
                f"browser navigation returned HTTP {status}", url=final_url, status=status
            )
        _validate_success_body(final_url, effective_status, "", html, kind, accept)

        return FetchResult(
            url=url, final_url=final_url, status=effective_status,
            content_type="text/html", text=html, redirects=0,
            hosts=(normalize_host(urlsplit(final_url).hostname),),
        )

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
