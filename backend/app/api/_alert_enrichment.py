"""Deterministic, subscriber-safe alert risk-explanation builders.

Produces the curated "why this score" subscribers to see:
Risk Score, Risk Level, Scoring Factors as **High/Medium/Low**, **Primary Exposure**, **Reason for Score**) 
from already-stored ``processed_alerts`` fields only — no DB query, no AI, and **none** of the internal V1 moderation fields
(``publish_decision`` / ``pending_review_reason`` / ``publication_state_source`` /
``is_excluded`` / ``is_manual_hold`` / ``published_by_rule`` / …).

Used by BOTH subscriber surfaces — ``app/api/subscriber.py`` (Supabase paid feed, ``PublicAlert*`` schema) and 
``app/api/client_alerts.py`` (``ClientAlert*`` schema).
Kept free of any import from the public/client routers so it can be reused without
a circular import; the public module is left byte-identical (its leak tests stay valid).
"""
from __future__ import annotations

from app.api._risk import risk_level_from_score, risk_score_100
from app.models.processed_alert import ProcessedAlert
from app.pipeline.publishing.risk_bands import compute_risk_band
from app.schemas.alert import SubscriberRiskExplanation

# Internal-score thresholds for the legacy 3-level confidence display (M3 bands).
_HIGH_INTERNAL = 18
_MEDIUM_INTERNAL = 10

_FACTOR_KEYS = (
    "source_credibility",
    "financial_impact",
    "victim_scale",
    "cross_source",
    "trend_acceleration",
)

# Category → primary exposure targets — mirrors Ken's example
# (Financial Institutions / Consumers / Payment Systems).
_CATEGORY_EXPOSURE: dict[str, list[str]] = {
    "Consumer Scam": ["Consumers"],
    "Investment Fraud": ["Investors", "Financial Institutions"],
    "Money Laundering": ["Financial Institutions"],
    "Cryptocurrency Fraud": ["Crypto Holders", "Payment Systems"],
    "Cybercrime": ["Businesses", "Consumers"],
}
_PAYMENT_HINTS = ("payment", "card", "bank", "wire", "ach", "account takeover")


def band_from_score100(score_100: int | None) -> str | None:
    """Map a normalized 0–100 score to a V1 band — for list items where only the
    0–100 score is at hand (no ORM)."""
    if score_100 is None:
        return None
    if score_100 >= 80:
        return "critical"
    if score_100 >= 70:
        return "high"
    if score_100 >= 60:
        return "medium"
    return "below_60"


def risk_band_for(alert: ProcessedAlert) -> str:
    """Stored V1 band with a computed fallback (matches the admin builder)."""
    return alert.risk_band or compute_risk_band(alert.signal_score_total).value


def _label(value: int | None) -> str | None:
    """Map a raw per-factor score to a High/Medium/Low display label."""
    if value is None:
        return None
    if value >= 4:
        return "High"
    if value >= 2:
        return "Medium"
    return "Low"


def factor_scores(alert: ProcessedAlert) -> dict[str, int | None]:
    return {k: getattr(alert, f"score_{k}", None) for k in _FACTOR_KEYS}


def factor_labels(alert: ProcessedAlert) -> dict[str, str]:
    out: dict[str, str] = {}
    for k in _FACTOR_KEYS:
        lab = _label(getattr(alert, f"score_{k}", None))
        if lab is not None:
            out[k] = lab
    return out


def subscriber_confidence(alert: ProcessedAlert) -> str:
    """High/Medium/Low confidence from the stored credibility factor + score +
    relevance. Uses ``score_source_credibility`` so no source join is required."""
    cred = alert.score_source_credibility
    score = alert.signal_score_total or 0
    if cred is not None:
        if cred >= 5 and alert.is_relevant and score >= _HIGH_INTERNAL:
            return "High"
        if cred >= 4 or score >= _MEDIUM_INTERNAL:
            return "Medium"
        return "Low"
    if score >= _HIGH_INTERNAL:
        return "High"
    if score >= _MEDIUM_INTERNAL:
        return "Medium"
    return "Low"


def primary_exposure(alert: ProcessedAlert) -> list[str]:
    """Derive Ken's 'Primary Exposure' targets from category + payment signals +
    victim scale. Deterministic; never returns internal fields."""
    out: list[str] = list(_CATEGORY_EXPOSURE.get(alert.primary_category or "", []))
    hay = " ".join(
        (
            alert.summary or "",
            " ".join(str(k) for k in (alert.matched_keywords or [])),
        )
    ).lower()
    if any(h in hay for h in _PAYMENT_HINTS) and "Payment Systems" not in out:
        out.append("Payment Systems")
    if (alert.victim_scale_raw or "").strip().lower() == "nationwide" and "Broad population" not in out:
        out.append("Broad population")
    return out


def reason_for_score(alert: ProcessedAlert) -> list[str]:
    """Ken's 'Reason for Score' bullets, derived from the per-factor scores."""
    bullets: list[str] = []
    if (alert.score_cross_source or 0) >= 3:
        bullets.append("Multiple independent sources")
    if (alert.score_financial_impact or 0) >= 4:
        bullets.append("Significant financial impact")
    if (alert.score_victim_scale or 0) >= 4 or (alert.victim_scale_raw or "").strip().lower() == "nationwide":
        bullets.append("Broad geographic scope")
    if (alert.score_source_credibility or 0) >= 4:
        bullets.append("Confirmed by trusted sources")
    if (alert.score_trend_acceleration or 0) >= 3:
        bullets.append("Rising threat trend")
    return bullets


def build_risk_explanation(alert: ProcessedAlert) -> SubscriberRiskExplanation:
    """Compose the full curated subscriber 'why this score' object."""
    return SubscriberRiskExplanation(
        score=risk_score_100(alert.signal_score_total),
        risk_band=risk_band_for(alert),
        risk_level=risk_level_from_score(alert.signal_score_total),
        confidence=subscriber_confidence(alert),
        factors=factor_scores(alert),
        factor_labels=factor_labels(alert),
        primary_exposure=primary_exposure(alert),
        reason_for_score=reason_for_score(alert),
    )
