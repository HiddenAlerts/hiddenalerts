"""Shared entity-name utilities — agency stoplist + normalization.

Single source of truth for deciding whether a named entity is a generic
prosecutor / regulator / law-enforcement reference (FBI, DOJ, SEC, …) rather
than a real *subject* (company, individual, domain). Agencies appear in almost
every fraud article, so allowing them to drive matching collapses thematically
unrelated alerts together.

Consumers:
  * ``app.pipeline.event_grouper`` — agency names must not drive event clustering; 
  an alert whose only entities are agencies has no usable subject and must not group by category alone.
  * ``app.api.public_alerts`` — agency mentions are excluded from related-signals
    / top-alerts dedup (this module is the extracted home of the logic that used
    to live there).

Matching is whole-word / phrase via ``\\b`` boundaries so substrings inside real
names ("sec" in "securities") don't false-positive. The list stays conservative
to avoid filtering genuine company/person names.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

# Lowercase phrases identifying a prosecutor / regulator / law-enforcement agency
# or generic governmental reference. Extends the original public-API list with a
# few broader generic terms needed so event grouping never clusters on agency or
# "law enforcement"/"government" mentions.
_AGENCY_PATTERNS: tuple[str, ...] = (
    "fbi",
    "federal bureau of investigation",
    "doj",
    "department of justice",
    "justice department",
    "criminal division",
    "antitrust division",
    "u.s. attorney",
    "us attorney",
    "united states attorney",
    "attorney general",
    "sec",
    "securities and exchange commission",
    "ftc",
    "federal trade commission",
    "fincen",
    "financial crimes enforcement network",
    "ofac",
    "office of foreign assets control",
    "ic3",
    "internet crime complaint center",
    "irs",
    "irs-ci",
    "internal revenue service",
    "hhs",
    "hhs-oig",
    "office of inspector general",
    "atf",
    "drug enforcement administration",
    "dea",
    "secret service",
    "u.s. secret service",
    "cisa",
    "homeland security",
    "department of homeland security",
    "dhs",
    "u.s. postal",
    "postal inspection service",
    "u.s. postal inspection service",
    "fraud control unit",
    "task force",
    "project safe childhood",
    "operation",  # "Operation Winter SHIELD" etc.
    "law enforcement",
    "federal authorities",
    "government",
)

_AGENCY_REGEX = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in _AGENCY_PATTERNS) + r")\b",
    flags=re.IGNORECASE,
)


def normalize_entity_name(name: str | None) -> str:
    """Lowercase + trim an entity name for comparison. ``None`` → ""."""
    if not name:
        return ""
    return name.strip().lower()


def is_agency_name(name: str | None) -> bool:
    """True if ``name`` refers to a prosecutor / regulator / agency / generic
    governmental reference rather than a real subject entity.

    Empty / whitespace-only / ``None`` → False (not an agency, just absent).
    """
    if not name or not name.strip():
        return False
    return _AGENCY_REGEX.search(name) is not None


def filter_non_agency_entities(entities: Iterable[str] | None) -> list[str]:
    """Return the entities that are real subjects, preserving order and original
    spelling. Drops empty / whitespace-only names and agency references.
    """
    if not entities:
        return []
    return [e for e in entities if e and e.strip() and not is_agency_name(e)]
