"""V1 publishing-state vocabulary (Slice 1 — definitions only).

These string constants are the controlled vocabulary stored in the new V1
columns on ``processed_alerts`` (``risk_band``, ``publish_decision``,
``pending_review_reason``, ``publication_state_source``) and ``alert_reviews``
(``decision_source``).

Slice 1 scope: these are *declarations only*. They are intentionally NOT
imported by the pipeline, scoring, grouping, or API layers yet — wiring happens
in later slices (risk bands → Slice 2, source rules → Slice 3, publish ordering
→ Slice 5). Keeping them in one place now means the migration, the models, and
the later logic all reference a single source of truth.

Values are plain ``str`` (stored as text columns) rather than DB enums so the
vocabulary can evolve without a migration. ``StrEnum``-style classes are
provided for ergonomic, typo-safe references in later code; the frozenset
constants are provided for validation/tests.
"""
from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    """str-valued Enum (members compare/serialize as their string value)."""

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class RiskBandValue(_StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    BELOW_60 = "below_60"


class PublishDecisionValue(_StrEnum):
    AUTO_PUBLISH = "auto_publish"
    REVIEW = "review"
    EXCLUDE = "exclude"
    HOLD = "hold"


class PendingReviewReason(_StrEnum):
    BLOCKED_BY_CREDIBILITY = "blocked_by_credibility"
    BLOCKED_BY_SCORE = "blocked_by_score"
    BLOCKED_BY_CATEGORY = "blocked_by_category"
    BLOCKED_BY_SOURCE_RULE = "blocked_by_source_rule"
    BLOCKED_BY_TOPIC_SCOPE = "blocked_by_topic_scope"
    MANUAL_REVIEW_ONLY = "manual_review_only"
    EXCLUDED_LOW_SCORE = "excluded_low_score"
    AI_REJECTED = "ai_rejected"
    MANUAL_HOLD = "manual_hold"
    MANUAL_REJECTED = "manual_rejected"


class DecisionSource(_StrEnum):
    AUTO_POLICY = "auto_policy"
    MANUAL_ADMIN = "manual_admin"
    CANDIDATE_BACKFILL = "candidate_backfill"
    SYSTEM_MIGRATION = "system_migration"


# Frozenset views for validation and tests.
RISK_BANDS: frozenset[str] = frozenset(v.value for v in RiskBandValue)
PUBLISH_DECISIONS: frozenset[str] = frozenset(v.value for v in PublishDecisionValue)
PENDING_REVIEW_REASONS: frozenset[str] = frozenset(v.value for v in PendingReviewReason)
DECISION_SOURCES: frozenset[str] = frozenset(v.value for v in DecisionSource)
