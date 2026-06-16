"""V1 Alert Publishing package.

Slice 1 ships only the lightweight shared vocabulary used by the V1 publishing
state fields (see ``constants``). Later slices add the active components here:
``risk_bands``, ``source_rules``, and ``publishing_policy``. Nothing in this
package is wired into the live pipeline yet.
"""
from app.pipeline.publishing.constants import (
    DECISION_SOURCES,
    PENDING_REVIEW_REASONS,
    PUBLISH_DECISIONS,
    RISK_BANDS,
    DecisionSource,
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
from app.pipeline.publishing.risk_bands import compute_risk_band, compute_score_100

__all__ = [
    # constants / vocabulary (Slice 1)
    "RISK_BANDS",
    "PUBLISH_DECISIONS",
    "PENDING_REVIEW_REASONS",
    "DECISION_SOURCES",
    "RiskBandValue",
    "PublishDecisionValue",
    "PendingReviewReason",
    "DecisionSource",
    # risk bands (Slice 2)
    "compute_risk_band",
    "compute_score_100",
    # publishing policy (Slice 2)
    "PublishingPolicy",
    "PublishDecision",
    "DEFAULT_V1_POLICY",
    "evaluate_basic_publish_decision",
    "is_approved_category",
]
