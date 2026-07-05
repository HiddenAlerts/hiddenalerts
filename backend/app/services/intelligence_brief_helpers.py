"""Pure helper functions for the Intelligence Brief module (Slice 1).

These are deliberately side-effect-free and DB-agnostic so they are trivially
unit-testable. Anything that needs a database (slug/brief-code *uniqueness*, the
daily brief-code *sequence* lookup) is intentionally left to the service/API
layer in a later slice — these helpers only produce well-formed values from
their inputs.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime, timezone

from app.models.intelligence_brief_constants import MIN_READ_TIME_MINUTES

logger = logging.getLogger(__name__)

# Default reading speed used to estimate read time. 200 wpm is a common average
# for online prose and matches the read-time estimates shown in the sample
# payloads.
DEFAULT_WORDS_PER_MINUTE = 200

# Fallback slug base used when a title normalises to an empty string (e.g. a
# title that is entirely punctuation/emoji). The API layer appends a uniqueness
# suffix; this only guarantees a non-empty, URL-safe base.
SLUG_FALLBACK = "brief"

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BRIEF_CODE_RE = re.compile(r"^HA-\d{8}-\d{3,}$")


def normalize_slug(title: str | None, *, fallback: str = SLUG_FALLBACK) -> str:
    """Normalise a title into a URL-safe slug.

    Lowercases, transliterates accented/unicode characters to ASCII, and
    collapses any run of non-alphanumeric characters into a single hyphen with
    no leading/trailing hyphens (e.g. ``"The Account Takeover Economy!"`` ->
    ``"the-account-takeover-economy"``).

    Returns ``fallback`` when the title is empty/None or contains no
    slug-friendly characters, so callers always receive a non-empty base.
    Uniqueness is the caller's responsibility (handled at the DB/API layer).
    """
    if not title:
        return fallback

    # Transliterate unicode to closest ASCII (drops accents, non-latin glyphs).
    ascii_title = (
        unicodedata.normalize("NFKD", title)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    slug = _SLUG_STRIP_RE.sub("-", ascii_title.lower()).strip("-")
    return slug or fallback


def generate_brief_code(sequence: int, *, on_date: date | None = None) -> str:
    """Build a human-readable brief code of the form ``HA-YYYYMMDD-NNN``.

    ``sequence`` is the 1-based ordinal of the brief *within its creation day*
    (the caller computes it, typically ``count_for_day + 1``). It is zero-padded
    to three digits (``001``). Sequences above 999 keep all their digits rather
    than truncating (``HA-20260626-1000``); this is an accepted, non-lossy
    overflow for the unlikely case of 1000+ briefs in a single day.

    ``on_date`` defaults to the current UTC date. Passing it explicitly keeps
    the function pure for testing.
    """
    if sequence < 1:
        raise ValueError(f"brief-code sequence must be >= 1, got {sequence}")
    if on_date is None:
        on_date = datetime.now(timezone.utc).date()
    return f"HA-{on_date:%Y%m%d}-{sequence:03d}"


def is_valid_brief_code(code: str | None) -> bool:
    """Return True if ``code`` matches the ``HA-YYYYMMDD-NNN`` shape."""
    return bool(code) and bool(_BRIEF_CODE_RE.match(code))


def _strip_html(value: str | None) -> str:
    """Remove HTML tags and collapse whitespace, returning plain text."""
    if not value:
        return ""
    text = _HTML_TAG_RE.sub(" ", value)
    return " ".join(text.split())


def calculate_read_time(
    *text_fields: str | None,
    words_per_minute: int = DEFAULT_WORDS_PER_MINUTE,
) -> int:
    """Estimate reading time in minutes from the given (HTML or plain) fields.

    HTML tags are stripped before counting words, and the result is rounded up
    to the nearest minute with a floor of ``MIN_READ_TIME_MINUTES`` so a brief
    never advertises a 0-minute read. Pass the subscriber-visible content
    fields (executive summary, why-this-matters, main brief, etc.).
    """
    if words_per_minute < 1:
        raise ValueError("words_per_minute must be >= 1")

    word_count = sum(len(_strip_html(field).split()) for field in text_fields)
    if word_count == 0:
        return MIN_READ_TIME_MINUTES

    # Ceiling division without floats.
    minutes = (word_count + words_per_minute - 1) // words_per_minute
    return max(MIN_READ_TIME_MINUTES, minutes)


def count_supporting_alerts(supporting_alerts: object) -> int:
    """Count valid supporting-alert entries in the stored JSON structure.

    ``supporting_alerts`` is stored as a JSON array. Phase 1 stores objects like
    ``{"url": "https://...", "title": "..."}`` (admin pastes published-alert
    URLs), but this helper is defensive and also accepts bare URL strings. An
    entry counts when it is a non-empty URL string, or a mapping carrying a
    truthy ``url``. Anything else (``None``, wrong type, blank or URL-less
    entries) is ignored and contributes 0.
    """
    if not isinstance(supporting_alerts, (list, tuple)):
        return 0

    count = 0
    for entry in supporting_alerts:
        if isinstance(entry, str):
            if entry.strip():
                count += 1
        elif isinstance(entry, dict):
            url = entry.get("url")
            if isinstance(url, str) and url.strip():
                count += 1
    return count
