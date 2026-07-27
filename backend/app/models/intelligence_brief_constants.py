"""Controlled vocabulary for the Intelligence Brief module.

These string constants are the controlled vocabulary stored in the enum-like
text columns on ``intelligence_briefs`` (``status``, ``risk_level``,
``confidence_level``, ``time_horizon``, ``brief_type``).


Storage casing is snake_case (e.g. ``near_term``) so values are URL/JSON-safe
and match the sample payloads.
"""
from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    """str-valued Enum (members compare/serialize as their string value)."""

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class BriefStatus(_StrEnum):
    """Lifecycle state of a brief. Default on creation is ``DRAFT``."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class BriefRiskLevel(_StrEnum):
    """Analyst-assigned risk level. Only critical/high are subscriber-visible."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BriefConfidenceLevel(_StrEnum):
    """Analyst confidence in the assessment."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BriefTimeHorizon(_StrEnum):
    """Expected time horizon of the threat/trend the brief describes."""

    IMMEDIATE = "immediate"
    NEAR_TERM = "near_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class BriefType(_StrEnum):
    """Kind of content a record represents.

    Phase 1 only ever produces ``INTELLIGENCE_BRIEF``; the remaining members are
    forward-looking so later phases (weekly digests, threat updates, premium
    reports) can reuse the same table without a migration.
    """

    INTELLIGENCE_BRIEF = "intelligence_brief"
    WEEKLY_DIGEST = "weekly_digest"
    ANALYST_OBSERVATION = "analyst_observation"
    THREAT_UPDATE = "threat_update"
    EXECUTIVE_SUMMARY = "executive_summary"
    PREMIUM_REPORT = "premium_report"


# Frozenset views for validation and tests.
BRIEF_STATUSES: frozenset[str] = frozenset(v.value for v in BriefStatus)
BRIEF_RISK_LEVELS: frozenset[str] = frozenset(v.value for v in BriefRiskLevel)
BRIEF_CONFIDENCE_LEVELS: frozenset[str] = frozenset(v.value for v in BriefConfidenceLevel)
BRIEF_TIME_HORIZONS: frozenset[str] = frozenset(v.value for v in BriefTimeHorizon)
BRIEF_TYPES: frozenset[str] = frozenset(v.value for v in BriefType)

# Risk levels a subscriber is allowed to see. Enforced by the subscriber API;
# declared here so the model, schemas, and routes share one source of truth.
SUBSCRIBER_VISIBLE_RISK_LEVELS: frozenset[str] = frozenset(
    {BriefRiskLevel.CRITICAL.value, BriefRiskLevel.HIGH.value}
)

# Phase 1 lifecycle defaults (referenced by the model + migration).
DEFAULT_BRIEF_STATUS: str = BriefStatus.DRAFT.value
DEFAULT_BRIEF_TYPE: str = BriefType.INTELLIGENCE_BRIEF.value

# Read-time floor: a brief always shows at least a 1-minute read.
MIN_READ_TIME_MINUTES: int = 1
