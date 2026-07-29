import asyncio
import ipaddress
import logging
import socket
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
    UnsafeRequestTarget,
    redact_url,
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
# Dropped on any origin change. Host goes too: it names the previous origin.
_SENSITIVE_HEADERS = frozenset(
    {"authorization", "cookie", "proxy-authorization", "x-api-key", "host"}
)
_MAX_RETRY_AFTER_SECONDS = 30.0
_DEFAULT_PORTS = {"http": 80, "https": 443}

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


def safe_redirect_headers(headers: dict, *, cross_origin: bool) -> dict:
    """Headers to send on a redirect hop.

    Credential-bearing headers and Host are dropped whenever the *origin* changes
    — a different hostname, scheme or effective port — so nothing leaks across a
    security boundary, including an HTTPS→HTTP downgrade. Matching is
    case-insensitive. Ordinary public headers (User-Agent, Accept,
    Accept-Language) are preserved so the request keeps identifying itself the
    same way.
    """
    if not cross_origin:
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
    try:
        with _requests.Session() as session:
            session.headers.update(headers)
            resp = session.get(url, timeout=timeout, allow_redirects=False)
            return resp.status_code, dict(resp.headers), resp.text, resp.content
    except _requests.RequestException as exc:
        raise TransientFetchError(
            f"requests transport error: {type(exc).__name__}", url=url
        ) from exc


def _safe_url(url: str) -> str:
    """Log-safe URL. Single implementation lives in ``http_errors.redact_url``."""
    return redact_url(url)


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

    verdict = classify_challenge(
        body, content_type=content_type, body_kind=kind, status=status
    )
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


def _is_noncanonical_numeric_host(host: str) -> str | bool:
    """True for numeric host forms the OS resolves but ``ipaddress`` rejects.

    Uses ``inet_aton``, which parses the legacy dotted/octal/hex/integer forms
    without touching DNS. A host that ``ipaddress`` already accepted is canonical
    and is handled by the caller's normal address checks.
    """
    bare = host.strip("[]")
    try:
        ipaddress.ip_address(bare)
        return False  # canonical — caller applies the private/loopback rules
    except ValueError:
        pass
    try:
        socket.inet_aton(bare)
    except OSError:
        # Not numeric at all; a genuine hostname.
        return False
    return True


def _unsafe_target_reason(url: str) -> str | None:
    """Reason a URL must not be requested, or None if it is fine.

    Blocks non-http(s) schemes, credentials in the URL, malformed hosts and ports,
    and literal internal addresses. This is a *literal*-address check only — a
    public hostname that resolves to a private address is not caught, so full
    DNS-rebinding protection is NOT implemented.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "malformed URL"
    scheme = (parts.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        return f"unsupported scheme {scheme or '(none)'}"
    if parts.username or parts.password or "@" in (parts.netloc.split("]")[-1]):
        return "credentials embedded in URL"
    try:
        parts.port
    except ValueError:
        return "invalid port"
    try:
        parts.hostname
    except ValueError:
        return "malformed host"
    try:
        host = normalize_host(parts.hostname)
    except ValueError:
        return "malformed host"
    if not host:
        return "URL has no host"
    if _is_noncanonical_numeric_host(host):
        # 2130706433 / 0x7f000001 / 017700000001 / 127.1 all resolve to
        # 127.0.0.1 in the OS resolver. Only canonical notation is accepted.
        return f"ambiguous numeric address {host}"
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


def assert_safe_target(url: str) -> None:
    """Raise :class:`UnsafeRequestTarget` if this URL must not be requested."""
    reason = _unsafe_target_reason(url)
    if reason:
        raise UnsafeRequestTarget(f"refusing to request URL: {reason}", url=_safe_url(url))


def _resolve_redirect(current_url: str, location: str) -> str:
    """Resolve a Location header into a target we are willing to request.

    Every parsing failure is converted to a typed error, so a malformed Location
    can never escape as a raw ``ValueError``. The Location value itself is never
    put in the message or the log — only the redacted current URL is.
    """
    try:
        target = urljoin(current_url, (location or "").strip())
        scheme = urlsplit(target).scheme.lower()
    except (ValueError, TypeError) as exc:
        raise UnsafeRequestTarget(
            "refusing redirect: malformed Location header", url=current_url
        ) from exc

    if scheme not in _ALLOWED_SCHEMES:
        raise UnsupportedRedirectScheme(
            f"refusing redirect to {scheme or 'relative'} scheme", url=current_url
        )
    reason = _unsafe_target_reason(target)
    if reason:
        raise UnsafeRequestTarget(f"refusing redirect: {reason}", url=current_url)
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
                current_headers = safe_redirect_headers(current_headers, cross_origin=True)
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
        kind = sniff_body_kind(body, raw, content_type)
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


async def _playwright_get(
    url: str, timeout: float, *, limiter=None
) -> tuple[int | None, str, str, str]:
    """Headless Chromium fetch. Returns (status, final_url, content_type, html).

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
            content_type = ""
            if response is not None:
                content_type = (response.headers or {}).get("content-type", "")
            final_url = page.url or url
            return status, final_url, content_type, await page.content()
        finally:
            await browser.close()


class BaseSourceAdapter(ABC):
    def __init__(self, source: object) -> None:
        self.source = source

    @abstractmethod
    async def fetch_item_stubs(self) -> list[RawItemStub]:
        """Stage 1: Fetch lightweight stubs (URL + metadata only, no full article fetch).

        Parses the feed/listing page and returns one stub per discovered article.
        The collector pre-filters these by normalized URL hash to decide which
        articles actually need fetching; publication dates never gate ingestion.
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
        allow_browser: bool = False,
        limiter=None,
    ) -> FetchResult:
        """Fetch one URL through the shared boundary and return a structured result.

        Tier 1  — httpx with a browser User-Agent (primary)
        Tier 2a — requests with a bot-identifying User-Agent
        Tier 2b — requests with minimal headers
        Tier 3  — Playwright, only for pages that need JavaScript rendering

        Tiers 2 and 3 are reached only after an ordinary HTTP 403. A detected
        challenge or an unsupported document is conclusive: it stops retries,
        skips the remaining tiers, never launches a browser, and propagates
        immediately. Every attempt, retry and redirect hop passes through the host
        limiter.

        Browser rendering is **opt-in**: ``allow_browser=True`` is required, and
        even then it runs only after ordinary 403s from every direct tier. No
        current source enables it. A future adapter must justify the need and test
        it explicitly rather than inheriting browser mode by default.
        """
        assert_safe_target(url)
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
            if isinstance(last_exc, SourceFetchError):
                # Keep the type and status the upstream actually produced —
                # repeated 503 stays TransientFetchError(status=503).
                raise last_exc
            raise TransientFetchError(
                f"failed after {retries} attempt(s): "
                f"{type(last_exc).__name__ if last_exc else 'no response'}",
                url=url,
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
            except PermanentFetchError as exc:
                if exc.status != 403:
                    raise
                # An ordinary 403 is the only reason to try the next fingerprint.
                last_exc = exc
            except SourceFetchError:
                # Every other typed failure is terminal: another fingerprint or a
                # browser cannot turn it into a usable document.
                raise
            except Exception as exc:
                raise TransientFetchError(
                    f"tier {tier} request failed", url=url
                ) from exc

        if not allow_browser:
            log.debug(
                "%s: browser rendering not permitted for %s, stopping after direct tiers",
                label, _safe_url(url),
            )
            if isinstance(last_exc, SourceFetchError):
                raise last_exc
            raise PermanentFetchError(
                "all direct tiers returned HTTP 403", url=url, status=403
            ) from last_exc

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
        status, final_url, content_type, html = await _playwright_get(
            url, timeout=60.0, limiter=limiter
        )
        final_url = final_url or url

        if status is None:
            # No HTTP response reached the page. Inventing a 200 would report a
            # navigation failure as a successful fetch.
            raise TransientFetchError(
                "browser navigation produced no HTTP response", url=final_url
            )

        # The navigation already happened, so this check stops unsafe *content*
        # from being returned — it cannot prevent the browser request itself.
        # Preventive interception of browser navigation is out of scope.
        assert_safe_target(final_url)

        if status in _REDIRECT_STATUSES or 300 <= status < 400:
            raise PermanentFetchError(
                f"browser navigation ended on HTTP {status}", url=final_url, status=status
            )
        if not (200 <= status < 300):
            if status in _RETRY_STATUSES:
                raise TransientFetchError(
                    "browser navigation failed", url=final_url, status=status
                )
            raise PermanentFetchError(
                f"browser navigation returned HTTP {status}", url=final_url, status=status
            )

        kind = sniff_body_kind(html, b"", content_type)
        _reject_challenge_or_binary(
            final_url, status, content_type, html, b"", kind, accept
        )
        _validate_success_body(final_url, status, content_type, html, kind, accept)

        # Only the initial and final hosts are knowable: intermediate browser
        # redirect hops are not observable without request interception.
        initial_host = normalize_host(urlsplit(url).hostname)
        final_host = normalize_host(urlsplit(final_url).hostname)
        hosts = (initial_host,) if final_host in ("", initial_host) else (initial_host, final_host)

        return FetchResult(
            url=url, final_url=final_url, status=status,
            content_type=content_type or "text/html", text=html, redirects=0, hosts=hosts,
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
