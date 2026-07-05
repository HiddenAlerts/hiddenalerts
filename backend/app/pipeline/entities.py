"""Shared entity-name utilities — agency stoplist + normalization.

Single source of truth for deciding whether a named entity is a generic
prosecutor / regulator / law-enforcement reference (FBI, DOJ, SEC, …) rather
than a real *subject* (company, individual, domain). Agencies appear in almost
every fraud article, so allowing them to drive matching collapses thematically
unrelated alerts together.

Consumers:
  * ``app.pipeline.event_grouper`` — agency / generic governmental names must not
    drive event clustering; an alert whose only entities are agencies has no
    usable subject and must not group by category alone.
  * ``app.api.public_alerts`` — agency mentions are excluded from related-signals
    / top-alerts dedup (this module is the extracted home of the logic that used
    to live there).

Matching is whole-word / phrase via ``\\b`` boundaries so substrings inside real
names ("sec" in "securities") don't false-positive. The list stays conservative
to avoid filtering genuine company / person / publisher names (Coinbase,
John Smith, KrebsOnSecurity, BleepingComputer all pass through untouched).
"""
from __future__ import annotations

import re
from collections.abc import Iterable

# Lowercase phrases identifying a prosecutor / regulator / law-enforcement agency
# or generic governmental reference. Extends the original public-API list with a
# few broader generic terms so event grouping never clusters on agency or
# "law enforcement" / "government" mentions.
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
    "law enforcement",
    "federal authorities",
)

_AGENCY_REGEX = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in _AGENCY_PATTERNS) + r")\b",
    flags=re.IGNORECASE,
)

# Broad single-word generic terms. These are useful generic-entity filters
# (e.g. "government", "Operation Winter SHIELD") but the bare words also appear
# inside real organization names ("Government Employees Insurance Company",
# "Operation Finance LLC"). To avoid false positives they are treated as agency
# markers ONLY when the entity is not clearly a real organization — i.e. it does
# not end with a corporate / legal suffix.
_BROAD_GENERIC_REGEX = re.compile(r"\b(?:government|operation)\b", flags=re.IGNORECASE)

# Corporate / legal suffixes that mark a name as a real organization. Anchored to
# the END of the (trimmed) entity so only a true suffix counts, not a mid-name
# word (so "Operation Bank Heist" is unaffected, "Operation Finance LLC" is).
_CORP_SUFFIX_REGEX = re.compile(
    r"\b(?:llc|l\.l\.c\.|inc|inc\.|incorporated|corp|corp\.|corporation|co|co\.|"
    r"company|companies|ltd|ltd\.|limited|lp|llp|plc|holdings|group|gmbh|ag|"
    r"s\.a\.|n\.v\.|pty)\.?$",
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

    Empty / whitespace-only / ``None`` → False (absent, not an agency).

    Specific agency/regulator references (FBI, DOJ, SEC, "fraud control unit",
    …) match anywhere in the name. Broad generic words ("government",
    "operation") only count when the entity is not clearly a real organization
    (no corporate/legal suffix), so "Government Employees Insurance Company" and
    "Operation Finance LLC" are NOT treated as agencies while "government" and
    "Operation Winter SHIELD" still are.
    """
    if not name or not name.strip():
        return False
    if _AGENCY_REGEX.search(name) is not None:
        return True
    if _BROAD_GENERIC_REGEX.search(name) is not None and _CORP_SUFFIX_REGEX.search(
        name.strip()
    ) is None:
        return True
    return False


def filter_non_agency_entities(entities: Iterable[str] | None) -> list[str]:
    """Return the real-subject entities, preserving order and original spelling.
    Drops empty / whitespace-only names and agency references.
    """
    if not entities:
        return []
    return [e for e in entities if e and e.strip() and not is_agency_name(e)]
