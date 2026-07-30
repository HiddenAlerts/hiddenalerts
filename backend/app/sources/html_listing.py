"""Item-scope and item-date helpers for HTML listing pages.

IC3 and FinCEN both publish card/row listings — neither is table-based — where
each item carries its own ``<time>``. Both lost every publication date because
their parsers started from a container and guessed which link and which date
belonged together.

These two functions hold the part the sources genuinely share: given an item's
own link, find the scope that belongs to that item alone, and read the date out
of it with the same naive-UTC conversion the rest of the codebase uses. Nothing
here knows a selector, a URL pattern or a host — each adapter keeps its own.
"""
import re
from datetime import datetime

from bs4.element import Tag

from app.sources.rss_adapter import _parse_feed_date

# A visible date has to look like a date. Anchoring on these three shapes keeps
# a heading such as "…During the 2026 FIFA World Cup" from being read as one.
_DATE_TEXT = re.compile(
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
    r"|\d{1,2}/\d{1,2}/\d{4}"
    r"|\d{4}-\d{2}-\d{2}",
    re.I,
)


def _has_date_class(value) -> bool:
    if not value:
        return False
    classes = value if isinstance(value, list) else [value]
    return any("date" in str(c).lower() for c in classes)


def item_scope(anchor: Tag, item_anchors: set[int]) -> Tag:
    """The largest ancestor of ``anchor`` that still contains no other item link.

    ``item_anchors`` holds ``id()`` of every anchor the caller accepted as an
    item link. Widening stops as soon as a second one comes into view, so a card
    can never borrow the date of the card next to it, and a page-level wrapper is
    never mistaken for a single item.
    """
    scope = anchor
    for parent in anchor.parents:
        if not isinstance(parent, Tag) or parent.name in ("body", "html"):
            break
        others = sum(
            1
            for link in parent.find_all("a", href=True)
            if id(link) in item_anchors and id(link) != id(anchor)
        )
        if others:
            break
        scope = parent
    return scope


def item_date(scope: Tag) -> datetime | None:
    """This item's publication date, or ``None``.

    Precedence: ``<time datetime>`` first, then visible date text on a ``<time>``
    or a date-classed element. Timezone offsets are converted to naive UTC,
    matching the ``TIMESTAMP WITHOUT TIME ZONE`` columns. Never guesses — an item
    with no date keeps ``None`` rather than inheriting the run time.
    """
    times = scope.find_all("time")

    for element in times:
        parsed = _parse_feed_date((element.get("datetime") or "").strip())
        if parsed is not None:
            return parsed

    for element in times + scope.find_all(class_=_has_date_class):
        match = _DATE_TEXT.search(element.get_text(" ", strip=True))
        if match:
            parsed = _parse_feed_date(match.group(0))
            if parsed is not None:
                return parsed

    return None
