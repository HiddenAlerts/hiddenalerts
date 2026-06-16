"""V1 publishing policy — generic band/category/credibility decision logic.

Slice 2 scope: **pure, deterministic, no DB, no side effects, no async, and not
wired into the live pipeline.** This module implements only the *generic* policy
— risk band, approved/manual-review category, and the credibility threshold.

Source-specific behaviour (KrebsOnSecurity promotion, BleepingComputer
conditional eligibility) is intentionally **out of scope** here and lands in
Slice 3 (`source_rules.py`); `evaluate_basic_publish_decision` deliberately
takes a plain ``source_credibility: int | None`` rather than a Source object so
it stays free of source identity.

Vocabulary (`RiskBandValue`, `PublishDecisionValue`, `PendingReviewReason`) is
the Slice 1 controlled vocabulary in :mod:`app.pipeline.publishing.constants`.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.publishing.constants import (
    PendingReviewReason,
    PublishDecisionValue,
    RiskBandValue,
)
from app.pipeline.publishing.risk_bands import compute_risk_band

# Approved auto-publish categories (Ken-locked V1 set).
_APPROVED_CATEGORIES: frozenset[str] = frozenset(
    {
        "Cybercrime",
        "Consumer Scam",
        "Investment Fraud",
        "Money Laundering",
        "Cryptocurrency Fraud",
    }
)

# Categories that always route to manual review (never auto-publish).
_MANUAL_REVIEW_CATEGORIES: frozenset[str] = frozenset({"Other"})


@dataclass(frozen=True)
class PublishingPolicy:
    """Immutable, versioned description of the generic publishing rules.

    Carries no source-specific rules (Slice 3 owns those). ``version`` is stamped
    onto every :class:`PublishDecision` so a stored decision is always traceable
    to the policy that produced it.
    """

    version: str
    auto_publish_bands: frozenset[RiskBandValue]
    review_bands: frozenset[RiskBandValue]
    excluded_bands: frozenset[RiskBandValue]
    approved_categories: frozenset[str]
    manual_review_categories: frozenset[str]
    min_source_credibility: int = 4


@dataclass(frozen=True)
class PublishDecision:
    """Result of a generic policy evaluation. Pure data, no behaviour.

    ``action`` is the routing outcome; ``reason`` is a stable machine/human
    readable explanation string; ``pending_review_reason`` is the Slice 1
    classification enum (``None`` when the alert auto-publishes).
    """

    action: PublishDecisionValue
    reason: str
    risk_band: RiskBandValue
    policy_version: str
    pending_review_reason: PendingReviewReason | None = None


DEFAULT_V1_POLICY = PublishingPolicy(
    version="v1.0",
    auto_publish_bands=frozenset({RiskBandValue.CRITICAL, RiskBandValue.HIGH}),
    review_bands=frozenset({RiskBandValue.MEDIUM}),
    excluded_bands=frozenset({RiskBandValue.BELOW_60}),
    approved_categories=_APPROVED_CATEGORIES,
    manual_review_categories=_MANUAL_REVIEW_CATEGORIES,
    min_source_credibility=4,
)


def is_approved_category(
    category: str | None,
    policy: PublishingPolicy = DEFAULT_V1_POLICY,
) -> bool:
    """True only when ``category`` is one of the policy's approved categories."""
    return category is not None and category in policy.approved_categories


def evaluate_basic_publish_decision(
    *,
    signal_score_total: int | None,
    primary_category: str | None,
    source_credibility: int | None,
    policy: PublishingPolicy = DEFAULT_V1_POLICY,
) -> PublishDecision:
    """Generic band/category/credibility publish decision (no source rules).

    Precedence (first match wins):

    1. Band ``below_60`` (incl. missing/invalid score) → **exclude**
       (``excluded_low_score``). Strongest gate — a low-score alert is excluded
       regardless of category or credibility.
    2. Band ``medium`` → **review** (``blocked_by_score``). V1 routes Medium to
       review-first categorically.
    3. (Band is now critical/high.) Missing category → **review**
       (``blocked_by_category``).
    4. Manual-review category (e.g. ``Other``) → **review**
       (``manual_review_only``).
    5. Category not in approved set → **review** (``blocked_by_category``).
    6. Missing credibility → **review** (``blocked_by_credibility``).
    7. Credibility below ``min_source_credibility`` → **review**
       (``blocked_by_credibility``).
    8. Otherwise (critical/high + approved category + credibility OK)
       → **auto_publish**.
    """
    band = compute_risk_band(signal_score_total)
    version = policy.version

    # 1. Below 60 → exclude (dominant).
    if band in policy.excluded_bands:
        return PublishDecision(
            action=PublishDecisionValue.EXCLUDE,
            reason="excluded_low_score",
            risk_band=band,
            policy_version=version,
            pending_review_reason=PendingReviewReason.EXCLUDED_LOW_SCORE,
        )

    # 2. Medium → review-first.
    if band in policy.review_bands:
        return PublishDecision(
            action=PublishDecisionValue.REVIEW,
            reason="medium_review_first",
            risk_band=band,
            policy_version=version,
            pending_review_reason=PendingReviewReason.BLOCKED_BY_SCORE,
        )

    # Band is critical or high from here on.

    # 3. Missing category.
    if primary_category is None:
        return PublishDecision(
            action=PublishDecisionValue.REVIEW,
            reason="missing_category",
            risk_band=band,
            policy_version=version,
            pending_review_reason=PendingReviewReason.BLOCKED_BY_CATEGORY,
        )

    # 4. Explicit manual-review category (Other).
    if primary_category in policy.manual_review_categories:
        return PublishDecision(
            action=PublishDecisionValue.REVIEW,
            reason="manual_review_category",
            risk_band=band,
            policy_version=version,
            pending_review_reason=PendingReviewReason.MANUAL_REVIEW_ONLY,
        )

    # 5. Category not approved.
    if primary_category not in policy.approved_categories:
        return PublishDecision(
            action=PublishDecisionValue.REVIEW,
            reason="category_not_approved",
            risk_band=band,
            policy_version=version,
            pending_review_reason=PendingReviewReason.BLOCKED_BY_CATEGORY,
        )

    # 6. Missing credibility.
    if source_credibility is None:
        return PublishDecision(
            action=PublishDecisionValue.REVIEW,
            reason="missing_source_credibility",
            risk_band=band,
            policy_version=version,
            pending_review_reason=PendingReviewReason.BLOCKED_BY_CREDIBILITY,
        )

    # 7. Credibility below threshold.
    if source_credibility < policy.min_source_credibility:
        return PublishDecision(
            action=PublishDecisionValue.REVIEW,
            reason="source_credibility_below_threshold",
            risk_band=band,
            policy_version=version,
            pending_review_reason=PendingReviewReason.BLOCKED_BY_CREDIBILITY,
        )

    # 8. Critical/High + approved category + credibility OK → auto-publish.
    return PublishDecision(
        action=PublishDecisionValue.AUTO_PUBLISH,
        reason="auto_publish_band_and_gates_passed",
        risk_band=band,
        policy_version=version,
        pending_review_reason=None,
    )
