"""Typed failures raised by the shared source HTTP boundary.

Adapters branch on the exception type — never on message text — so a challenge, a
content-type mismatch, a transient outage and an unsupported document can be told
apart without parsing strings.

No exception carries a response body, cookies or an Authorization header.
"""


class SourceFetchError(Exception):
    """Base class for every failure the shared fetch layer raises."""

    def __init__(self, message: str, *, url: str = "", status: int | None = None) -> None:
        super().__init__(message)
        self.url = url
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


class RedirectLoop(SourceFetchError):
    """The redirect chain revisited a URL."""


class TooManyRedirects(SourceFetchError):
    """The redirect chain exceeded the configured maximum."""


class UnsupportedRedirectScheme(SourceFetchError):
    """Location pointed somewhere other than http/https."""
