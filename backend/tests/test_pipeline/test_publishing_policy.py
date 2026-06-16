"""V1 Slice 2 — generic publishing-policy tests (pure, deterministic, no DB)."""
import pytest

from app.pipeline.publishing.constants import (
    PendingReviewReason,
    PublishDecisionValue,
    RiskBandValue,
)
from app.pipeline.publishing.publishing_policy import (
    DEFAULT_V1_POLICY,
    PublishDecision,
    PublishingPolicy,
    evaluate_basic_publish_decision,
    is_approved_category,
)

# Internal scores that land squarely in each band.
_CRITICAL = 22  # -> 88/100
_HIGH = 18      # -> 72/100
_MEDIUM = 16    # -> 64/100
_BELOW = 10     # -> 40/100
_APPROVED = "Cybercrime"


def _decide(score, category, credibility):
    return evaluate_basic_publish_decision(
        signal_score_total=score,
        primary_category=category,
        source_credibility=credibility,
    )


# --- Auto-publish paths ------------------------------------------------------


def test_critical_approved_cred4_auto_publishes():
    d = _decide(_CRITICAL, _APPROVED, 4)
    assert d.action is PublishDecisionValue.AUTO_PUBLISH
    assert d.risk_band is RiskBandValue.CRITICAL
    assert d.pending_review_reason is None
    assert d.policy_version == "v1.0"


def test_critical_approved_cred5_auto_publishes():
    d = _decide(_CRITICAL, _APPROVED, 5)
    assert d.action is PublishDecisionValue.AUTO_PUBLISH
    assert d.pending_review_reason is None


def test_high_approved_cred4_auto_publishes():
    d = _decide(_HIGH, _APPROVED, 4)
    assert d.action is PublishDecisionValue.AUTO_PUBLISH
    assert d.risk_band is RiskBandValue.HIGH


@pytest.mark.parametrize("category", sorted(DEFAULT_V1_POLICY.approved_categories))
def test_all_approved_categories_auto_publish_when_high(category):
    d = _decide(_HIGH, category, 4)
    assert d.action is PublishDecisionValue.AUTO_PUBLISH


# --- Review / exclude paths --------------------------------------------------


def test_medium_routes_to_review_blocked_by_score():
    d = _decide(_MEDIUM, _APPROVED, 4)
    assert d.action is PublishDecisionValue.REVIEW
    assert d.risk_band is RiskBandValue.MEDIUM
    assert d.pending_review_reason is PendingReviewReason.BLOCKED_BY_SCORE
    assert d.reason == "medium_review_first"


def test_below_60_is_excluded():
    d = _decide(_BELOW, _APPROVED, 4)
    assert d.action is PublishDecisionValue.EXCLUDE
    assert d.risk_band is RiskBandValue.BELOW_60
    assert d.pending_review_reason is PendingReviewReason.EXCLUDED_LOW_SCORE
    assert d.reason == "excluded_low_score"


def test_critical_other_category_manual_review_only():
    d = _decide(_CRITICAL, "Other", 4)
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.MANUAL_REVIEW_ONLY


def test_critical_unknown_category_blocked_by_category():
    d = _decide(_CRITICAL, "Weather", 4)
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.BLOCKED_BY_CATEGORY


def test_critical_approved_cred3_blocked_by_credibility():
    d = _decide(_CRITICAL, _APPROVED, 3)
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.BLOCKED_BY_CREDIBILITY
    assert d.reason == "source_credibility_below_threshold"


def test_missing_category_blocked_by_category():
    d = _decide(_CRITICAL, None, 4)
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.BLOCKED_BY_CATEGORY


def test_missing_credibility_blocked_by_credibility():
    d = _decide(_CRITICAL, _APPROVED, None)
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.BLOCKED_BY_CREDIBILITY


# --- Precedence / edge behaviour --------------------------------------------


def test_below_60_excludes_even_when_other_category():
    # Below-60 dominates category — "clearly below 60" → exclude.
    d = _decide(_BELOW, "Other", 4)
    assert d.action is PublishDecisionValue.EXCLUDE
    assert d.pending_review_reason is PendingReviewReason.EXCLUDED_LOW_SCORE


def test_none_score_is_excluded():
    d = _decide(None, _APPROVED, 5)
    assert d.action is PublishDecisionValue.EXCLUDE
    assert d.risk_band is RiskBandValue.BELOW_60


def test_decision_is_frozen_dataclass():
    d = _decide(_CRITICAL, _APPROVED, 4)
    assert isinstance(d, PublishDecision)
    with pytest.raises(Exception):
        d.action = PublishDecisionValue.REVIEW  # frozen


# --- DEFAULT_V1_POLICY shape -------------------------------------------------


def test_default_policy_shape():
    p = DEFAULT_V1_POLICY
    assert isinstance(p, PublishingPolicy)
    assert p.version == "v1.0"
    assert p.auto_publish_bands == frozenset({RiskBandValue.CRITICAL, RiskBandValue.HIGH})
    assert p.review_bands == frozenset({RiskBandValue.MEDIUM})
    assert p.excluded_bands == frozenset({RiskBandValue.BELOW_60})
    assert p.approved_categories == frozenset(
        {"Cybercrime", "Consumer Scam", "Investment Fraud", "Money Laundering", "Cryptocurrency Fraud"}
    )
    assert p.manual_review_categories == frozenset({"Other"})
    assert p.min_source_credibility == 4


def test_is_approved_category():
    assert is_approved_category("Cybercrime") is True
    assert is_approved_category("Other") is False
    assert is_approved_category("Weather") is False
    assert is_approved_category(None) is False
