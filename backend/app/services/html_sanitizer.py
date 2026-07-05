"""Centralised HTML sanitisation for user/admin-authored rich text.

The Intelligence Brief admin editor sends HTML for the long-form fields
(executive summary, why-this-matters, risk assessment, main brief, ...). That
HTML is attacker-influenced and must be sanitised **before it is stored** so it
is safe to render back to subscribers.

We use `nh3` (Python bindings for the Rust `ammonia` library) rather than
`bleach`: nh3 is actively maintained, considerably faster, and has safe
defaults, whereas bleach is now in maintenance-only mode and itself recommends
nh3 as its successor. (The Phase 1 plan mentioned bleach as a candidate; nh3 is
the drop-in, better-supported choice and stores the same sanitised HTML.)

This module is intentionally the single sanitisation entry point for the whole
app so the allowlist lives in exactly one place and can be tuned once as the
editor's needs evolve.
"""
from __future__ import annotations

import logging

import nh3

logger = logging.getLogger(__name__)

# Tags the admin rich-text editor is allowed to produce: headings, paragraphs,
# inline emphasis, lists, links, quotes and simple code. Anything not listed
# (script, style, iframe, img, form, ...) is stripped.
ALLOWED_TAGS: set[str] = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "ul",
    "ol",
    "li",
    "a",
    "h1",
    "h2",
    "h3",
    "h4",
    "blockquote",
    "code",
    "pre",
}

# Per-tag attribute allowlist. Only links carry attributes; everything else is
# stripped of all attributes (so inline ``style``, ``onclick`` and friends can
# never survive).
ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "title"},
}

# URL schemes permitted on ``href``. Excludes ``javascript:``/``data:`` so
# script-in-URL and data-URI payloads are dropped.
ALLOWED_URL_SCHEMES: set[str] = {"http", "https", "mailto"}


def sanitize_html(raw: str | None) -> str | None:
    """Sanitise a rich-text HTML string against the module allowlist.

    Returns ``None`` unchanged (so a nullable DB column stays NULL) and returns
    ``""`` for blank input. For real content, unsafe tags/attributes/URLs are
    removed while ordinary editor formatting (headings, bold/italic, lists,
    links, line breaks) is preserved. Outbound links are hardened with
    ``rel="noopener noreferrer"``.

    This is the only place HTML should be sanitised; call it for every
    admin-supplied HTML field before persisting.
    """
    if raw is None:
        return None
    if not raw.strip():
        return ""

    cleaned = nh3.clean(
        raw,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
    )

    if len(cleaned) != len(raw):
        logger.debug(
            "sanitize_html altered content (%d -> %d chars)", len(raw), len(cleaned)
        )
    return cleaned
