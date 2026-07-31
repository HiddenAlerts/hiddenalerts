"""Typed failures raised by the shared source HTTP boundary.

Adapters branch on the exception type — never on message text — so a challenge, a
content-type mismatch, a transient outage and an unsupported document can be told
apart without parsing strings.

No exception carries a response body, cookies or an Authorization header, and the
URL on every exception is redacted on construction.
"""
from urllib.parse import urlsplit

_DEFAULT_PORTS = {"http": 80, "https": 443}
INVALID_URL = "<invalid-url>"


def redact_url(url: str) -> str:
    """Return a URL safe to log or attach to an exception.

    Drops credentials, query string and fragment; keeps scheme, hostname, a
    non-default port and the path. Never raises — an unparseable URL becomes
    ``"<invalid-url>"`` rather than leaking the original string.
    """
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        scheme = (parts.scheme or "").lower()
        host = (parts.hostname or "").strip().lower().rstrip(".")
        if not host:
            return INVALID_URL
        try:
            port = parts.port
        except ValueError:
            port = None
        netloc = f"[{host}]" if ":" in host else host
        if port and port != _DEFAULT_PORTS.get(scheme):
            netloc = f"{netloc}:{port}"
        return f"{scheme}://{netloc}{parts.path}" if scheme else INVALID_URL
    except Exception:
        return INVALID_URL


class SourceFetchError(Exception):
    """Base class for every failure the shared fetch layer raises.

    ``url`` is redacted on construction, so no caller can accidentally attach
    credentials or query tokens to an exception.
    """

    def __init__(self, message: str, *, url: str = "", status: int | None = None) -> None:
        super().__init__(message)
        self.url = redact_url(url)
        self.status = status


class TransientFetchError(SourceFetchError):
    """Retryable failure: network error, timeout, or a retryable 5xx."""


class RateLimitedError(TransientFetchError):
    """Upstream asked us to slow down (429), optionally with a Retry-After delay."""

    def __init__(self, message: str, *, url: str = "", status: int | None = None,
                 retry_after: float | None = None) -> None:
        super().__init__(message, url=url, status=status)
        self.retry_after = retry_after


class PermanentFetchError(SourceFetchError):
    """Non-retryable HTTP failure such as 404, or a tier chain that ran out."""


class ChallengeDetected(SourceFetchError):
    """Anti-bot verification page. Conclusive: never retried, never escalated.

    ``signals`` names the markers that fired, for logging and tests — it never
    contains page content.
    """

    def __init__(self, message: str, *, url: str = "", status: int | None = None,
                 signals: tuple[str, ...] = ()) -> None:
        super().__init__(message, url=url, status=status)
        self.signals = signals


class ContentTypeMismatch(SourceFetchError):
    """Response content type is not one the caller declared it accepts."""

    def __init__(self, message: str, *, url: str = "", status: int | None = None,
                 content_type: str = "", accepted: tuple[str, ...] = ()) -> None:
        super().__init__(message, url=url, status=status)
        self.content_type = content_type
        self.accepted = accepted


class UnsupportedDocument(ContentTypeMismatch):
    """Document we deliberately do not process here, such as PDF or binary.

    Separate from a plain mismatch so callers can distinguish "wrong kind of page"
    from "a real document this pipeline cannot read".
    """


class EmptyContent(SourceFetchError):
    """A 2xx response with nothing usable in it.

    Covers a missing or whitespace-only body, and an article page whose extracted
    text is empty. A valid but empty RSS feed is *not* this: that document parses
    fine and legitimately has zero entries.
    """


class UnsafeRequestTarget(SourceFetchError):
    """A URL we refuse to request at all.

    Covers non-http(s) schemes, credentials embedded in the URL, malformed hosts
    or ports, and literal internal addresses. Applied to the initial target and to
    every redirect destination.
    """


class RedirectLoop(SourceFetchError):
    """The redirect chain revisited a URL."""


class TooManyRedirects(SourceFetchError):
    """The redirect chain exceeded the configured maximum."""


class UnsupportedRedirectScheme(UnsafeRequestTarget):
    """Location pointed somewhere other than http/https."""


class DestinationExcluded(SourceFetchError):
    """A valid public URL that this source is not allowed to collect from.

    Raised when an article request — or a redirect it would follow — leaves the
    domains the adapter owns. FBI feeds routinely point at justice.gov, where DOJ
    is the canonical source, so following the redirect would collect the same
    release twice under two identities.

    This is *not* :class:`UnsafeRequestTarget`: the destination is a legitimate
    public site we simply do not want *this* source to speak for. It is also not
    a parser failure, and it is never eligible for a summary fallback — the item
    belongs to another source, so there is nothing here to substitute.

    ``destination`` is a normalized hostname only: no query string, no response
    body, and no raw Location header.
    """

    def __init__(
        self,
        message: str,
        *,
        url: str = "",
        destination: str = "",
        status: int | None = None,
    ) -> None:
        super().__init__(message, url=url, status=status)
        self.destination = (destination or "").strip().lower().rstrip(".")
