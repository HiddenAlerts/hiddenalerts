"""OPEN-6 — unit tests for the subscriber risk-explanation builders.

Pure functions on an in-memory ProcessedAlert (no DB, no AI). Lock the curated
"why this score" Ken asked subscribers to see (Risk Score, Risk Level, Scoring
Factors as High/Medium/Low, Primary Exposure, Reason for Score) and prove no
internal V1 moderation fields are produced.
"""
from app.api._alert_enrichment import (
    band_from_score100,
    build_risk_explanation,
    factor_labels,
    primary_exposure,
    reason_for_score,
    risk_band_for,
    subscriber_confidence,
)
from app.models.processed_alert import ProcessedAlert

_FORBIDDEN = {
    "publish_decision", "publish_decision_reason", "pending_review_reason",
    "publication_state_source", "publication_state_updated_at", "is_excluded",
    "excluded_reason", "is_manual_hold", "published_by_rule",
    "publishing_policy_version", "published_by_user_id",
}


def _alert(**kw) -> ProcessedAlert:
    base = dict(
        signal_score_total=20, is_relevant=True,
        score_source_credibility=5, score_financial_impact=5,
        score_victim_scale=4, score_cross_source=5, score_trend_acceleration=3,
        primary_category="Consumer Scam", victim_scale_raw="nationwide",
        matched_keywords=["payment fraud"], summary="A payment fraud scam.",
        risk_band=None,
    )
    base.update(kw)
    return ProcessedAlert(**base)


def test_band_from_score100():
    assert band_from_score100(88) == "critical"
    assert band_from_score100(80) == "critical"
    assert band_from_score100(72) == "high"
    assert band_from_score100(64) == "medium"
    assert band_from_score100(40) == "below_60"
    assert band_from_score100(None) is None


def test_risk_band_for_uses_stored_then_computes():
    assert risk_band_for(_alert(risk_band="critical")) == "critical"
    assert risk_band_for(_alert(risk_band=None, signal_score_total=20)) == "critical"
    assert risk_band_for(_alert(risk_band=None, signal_score_total=18)) == "high"
    assert risk_band_for(_alert(risk_band=None, signal_score_total=15)) == "medium"
    assert risk_band_for(_alert(risk_band=None, signal_score_total=10)) == "below_60"


def test_factor_labels_high_medium_low():
    fl = factor_labels(_alert(
        score_source_credibility=5, score_victim_scale=2, score_trend_acceleration=1,
    ))
    assert fl["source_credibility"] == "High"
    assert fl["victim_scale"] == "Medium"
    assert fl["trend_acceleration"] == "Low"


def test_primary_exposure_derivation():
    exp = primary_exposure(_alert(
        primary_category="Consumer Scam", victim_scale_raw="nationwide",
        matched_keywords=["payment"],
    ))
    assert "Consumers" in exp and "Payment Systems" in exp and "Broad population" in exp
    exp2 = primary_exposure(_alert(
        primary_category="Money Laundering", victim_scale_raw="single",
        matched_keywords=["sanctions"], summary="OFAC enforcement action",
    ))
    assert exp2 == ["Financial Institutions"]


def test_reason_for_score_bullets():
    bullets = reason_for_score(_alert(
        score_cross_source=5, score_financial_impact=5, score_victim_scale=4,
        score_source_credibility=5, score_trend_acceleration=3,
    ))
    assert "Multiple independent sources" in bullets
    assert "Significant financial impact" in bullets
    assert "Broad geographic scope" in bullets
    assert "Confirmed by trusted sources" in bullets
    assert "Rising threat trend" in bullets
    # A weak alert yields no bullets.
    assert reason_for_score(_alert(
        score_cross_source=1, score_financial_impact=1, score_victim_scale=1,
        score_source_credibility=1, score_trend_acceleration=1, victim_scale_raw="single",
    )) == []


def test_subscriber_confidence():
    assert subscriber_confidence(_alert(score_source_credibility=5, is_relevant=True, signal_score_total=20)) == "High"
    assert subscriber_confidence(_alert(score_source_credibility=4, signal_score_total=12)) == "Medium"
    assert subscriber_confidence(_alert(score_source_credibility=2, signal_score_total=8, is_relevant=False)) == "Low"


def test_build_risk_explanation_shape_and_no_internal_fields():
    d = build_risk_explanation(_alert(signal_score_total=20)).model_dump()
    assert d["risk_band"] == "critical"
    assert d["score"] == 80  # round(20/25*100)
    assert d["risk_level"] in ("high", "medium", "low")
    assert d["confidence"] in ("High", "Medium", "Low")
    assert set(d["factors"].keys()) == {
        "source_credibility", "financial_impact", "victim_scale",
        "cross_source", "trend_acceleration",
    }
    assert d["factor_labels"]["source_credibility"] == "High"
    assert d["primary_exposure"]
    assert d["reason_for_score"]
    # The curated explanation never carries internal moderation fields.
    assert _FORBIDDEN.isdisjoint(d.keys())
