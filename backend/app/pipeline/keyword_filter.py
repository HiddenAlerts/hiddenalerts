"""Keyword filtering gate — first step in the M2 processing pipeline.

Checks article text against a source's keyword list before sending to AI.
This significantly reduces OpenAI API costs by filtering out irrelevant articles.
"""
from __future__ import annotations

import re


def filter_by_keywords(text: str, keywords: list[str]) -> list[str]:
    """Case-insensitive substring scan of text against keyword list.

    Returns a deduplicated list of matched keywords.
    Empty list means no match — the caller should mark the item as not relevant
    and skip AI processing.

    Args:
        text: The article text to scan (raw_item.raw_text).
        keywords: The source's keyword list (source.keywords JSONB as list[str]).

    Returns:
        List of matched keywords (deduplicated, order preserved by first match).
    """
    if not text or not keywords:
        return []

    text_lower = text.lower()
    matched: list[str] = []
    seen: set[str] = set()

    for keyword in keywords:
        if not keyword:
            continue
        kw_lower = keyword.lower()
        if kw_lower in seen:
            continue
        # Use word-boundary-aware search for single words; substring for phrases
        if _keyword_matches(text_lower, kw_lower):
            matched.append(keyword)
            seen.add(kw_lower)

    return matched


def _keyword_matches(text_lower: str, keyword_lower: str) -> bool:
    """Check if keyword appears in text.

    For single-word keywords: requires word boundary match to avoid
    false positives (e.g. "fraud" matching "defrauded").
    For multi-word phrases: simple substring match is sufficient.
    """
    if " " in keyword_lower:
        # Multi-word phrase: substring match
        return keyword_lower in text_lower
    else:
        # Single word: word boundary match using regex
        pattern = r"\b" + re.escape(keyword_lower) + r"\b"
        return bool(re.search(pattern, text_lower))
