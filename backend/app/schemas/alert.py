"""Pydantic schemas for processed alerts, events, and reviews."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProcessedAlertRead(BaseModel):
    """Summary view of a processed alert — used in list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_item_id: int
    # Joined fields from raw_item / source (populated by API layer)
    title: str | None = None
    source_name: str | None = None
    item_url: str | None = None
    # Core alert fields
    risk_level: str | None
    primary_category: str | None
    # M3 final (Ken-approved 2026-05-06): API exposes signal_score_total on the
    # 0–100 frontend scale. Internal sum is still 5–25 in the DB; mappers
    # normalize on the way out so no frontend change is required.
    signal_score_total: int | None
    # Normalized 0.0–1.0 score (legacy convenience). Computed from the internal
    # 5–25 sum, not the exposed 0–100 value.
    relevance_score: float | None = None
    matched_keywords: list[str] | None
    is_relevant: bool
    processed_at: datetime
    # Original source/press-release publication date (parsed from RSS pubDate or
    # listing page). Distinct from `published_at` which is when an admin published
    # the alert on this platform.
    source_published_at: datetime | None = None
    # Publication state (M3)
    is_published: bool = False
    published_at: datetime | None = None
    # V1 Alert Publishing state (Slice 6 — internal/admin visibility; additive).
    # These mirror the processed_alerts columns written by the V1 pipeline so
    # review queues can see WHY an alert was published / reviewed / excluded /
    # held without opening the detail page. Never exposed on public endpoints.
    risk_band: str | None = None
    publish_decision: str | None = None
    publish_decision_reason: str | None = None
    pending_review_reason: str | None = None
    is_excluded: bool | None = None
    excluded_reason: str | None = None
    is_manual_hold: bool | None = None
    published_by_rule: bool | None = None
    publishing_policy_version: str | None = None
    publication_state_source: str | None = None
    publication_state_updated_at: datetime | None = None


class RiskExplanation(BaseModel):
    """Deterministic, internal-only explanation of an alert's risk + V1 decision.

    Built in the API mapping layer from already-stored fields (no DB writes).
    `score_total` is the raw internal 5–25 sum; `score_100` is the normalized
    0–100 value. `risk_band` falls back to a computed band when the column is
    null (the fallback is response-only and never persisted).
    """

    score_total: int | None = None
    score_100: int | None = None
    risk_level: str | None = None
    risk_band: str | None = None
    factors: dict[str, int | None] | None = None
    publication_decision: str | None = None
    publication_reason: str | None = None
    pending_review_reason: str | None = None
    source: str | None = None
    source_credibility: int | None = None


class ProcessedAlertDetail(ProcessedAlertRead):
    """Full detail view — includes AI outputs and score breakdown."""

    summary: str | None = None
    secondary_category: str | None = None
    entities_json: dict | None = None
    # AI raw outputs (for audit/recalculation)
    financial_impact_estimate: str | None = None
    victim_scale_raw: str | None = None
    ai_model: str | None = None
    # Score breakdown
    score_source_credibility: int | None = None
    score_financial_impact: int | None = None
    score_victim_scale: int | None = None
    score_cross_source: int | None = None
    score_trend_acceleration: int | None = None
    # Event linkage (populated by API layer)
    event_id: int | None = None
    event_title: str | None = None
    # Latest review status (populated by API layer)
    review_status: str | None = None
    # V1 internal detail extras (Slice 6). The reason/state fields are inherited
    # from ProcessedAlertRead; detail adds the publishing user id (raw nullable
    # int — no user/profile join) and the structured risk explanation.
    published_by_user_id: int | None = None
    risk_explanation: RiskExplanation | None = None


class AlertReviewCreate(BaseModel):
    """Request body for submitting a review action."""

    review_status: str  # "approved" | "false_positive" | "edited"
    edited_summary: str | None = None
    adjusted_risk_level: str | None = None


class AlertReviewRead(BaseModel):
    """Response after creating a review."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int | None
    user_id: int | None
    review_status: str | None
    edited_summary: str | None = None
    adjusted_risk_level: str | None = None
    reviewed_at: datetime


class EventRead(BaseModel):
    """Summary view of a grouped event."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    risk_level: str | None
    category: str | None
    primary_entity: str | None
    first_detected_at: datetime
    last_updated_at: datetime
    source_count: int = 0  # Computed: len(event_sources)


class EventDetail(EventRead):
    """Full event detail with linked alerts."""

    alerts: list[ProcessedAlertRead] = []


# ---------------------------------------------------------------------------
# Subscriber-safe schemas (M3 — client endpoints only)
# ---------------------------------------------------------------------------


class SubscriberRiskExplanation(BaseModel):
    """Curated, subscriber-safe "why this score" (OPEN-6) for the alert detail.

    Risk Score, Risk Level, Scoring Factors as High/Medium/Low, Primary Exposure, 
    and Reason for Score. Built deterministically from stored fields 
    (see ``app/api/_alert_enrichment.py``).
    Contains NO internal V1 moderation fields (publish_decision /
    pending_review_reason / publication_state_source / is_excluded / …).
    """

    score: int | None = None  # 0–100
    risk_band: str | None = None  # critical | high | medium | below_60
    risk_level: str | None = None  # legacy high | medium | low
    confidence: str | None = None  # High | Medium | Low
    factors: dict[str, int | None] | None = None  # raw per-factor scores
    factor_labels: dict[str, str] | None = None  # per-factor High/Medium/Low
    primary_exposure: list[str] = []
    reason_for_score: list[str] = []


class ClientAlertRead(BaseModel):
    """Subscriber-safe alert summary — only published alerts are served via client endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None = None
    source_name: str | None = None
    item_url: str | None = None
    risk_level: str | None
    # V1 risk band (OPEN-6) — enables a Critical badge + Critical/High/Medium
    # filtering on the subscriber UI (legacy `risk_level` cannot distinguish them).
    risk_band: str | None = None
    primary_category: str | None
    # 0–100 (Ken-approved 2026-05-06). DB column is 5–25 internally; mapper normalizes.
    signal_score_total: int | None
    summary: str | None = None
    processed_at: datetime
    # Original source/press-release publication date.
    source_published_at: datetime | None = None
    published_at: datetime | None = None
    matched_keywords: list[str] | None = None


class ClientAlertDetail(ClientAlertRead):
    """Subscriber-safe alert detail — adds category, entities, and risk explanation."""

    secondary_category: str | None = None
    # Normalised entity list — extracted from entities_json for stable frontend consumption.
    # Internal format {"names": [...]} is unwrapped to a plain list here.
    entities: list[str] = []
    # Curated "why this score" (OPEN-6).
    risk_explanation: SubscriberRiskExplanation | None = None


# ---------------------------------------------------------------------------
# Public feed schemas (GET /api/alerts — no auth, frontend MVP)
# ---------------------------------------------------------------------------


class PublicAlertRead(BaseModel):
    """Flat, frontend-safe schema for the unauthenticated public alerts feed.

    Only returned by GET /api/alerts. Does NOT include internal review fields,
    score breakdowns, moderation metadata, or raw AI structures.
    """

    id: int
    title: str | None = None
    summary: str | None = None
    category: str | None = None
    risk_level: str | None = None
    # 0–100 score (Ken-approved 2026-05-06). Internal sum is 5–25; mapper normalizes.
    signal_score: int | None = None
    source_name: str | None = None
    source_url: str | None = None
    # Original source/press-release publication date — what to display on the
    # frontend feed. Falls back to null when the source did not provide a date.
    source_published_at: datetime | None = None
    published_at: datetime | None = None


class PublicKeyIntelItem(BaseModel):
    """Structured key-intelligence data point for the public detail view.

    Values are short single-line strings (no narrative paragraphs).
    """

    label: str
    value: str


class PublicTimelineItem(BaseModel):
    """Single timeline entry on the public detail view."""

    date: str  # ISO 8601 string
    event: str


class PublicRelatedSignal(BaseModel):
    """Reference to another published alert linked via shared event."""

    id: int
    title: str | None = None
    # 0–100 score (Ken-approved 2026-05-06).
    score: int | None = None
    risk_level: str | None = None  # Title case: "High" | "Medium" | "Low"


class PublicSourceRef(BaseModel):
    """Source reference shown on the public detail view."""

    name: str
    url: str | None = None


class PublicAlertDetail(BaseModel):
    """Enriched public alert detail — Ken-approved frontend-facing schema (M3 frontend completion).

    Returned by GET /api/alerts/{id} for published alerts only.

    Fields are split into:
      1. Ken's primary frontend-facing fields (with derived enrichments).
      2. Backward-compatibility additive fields preserved from the prior contract.

    Optional sections (why_it_matters, key_intelligence, risk_assessment, sources,
    affected_group, timeline, related_signals, subcategory) are omitted from the
    JSON response when their underlying data is empty — the route uses
    response_model_exclude_none=True.

    Intentionally does NOT include: review history, score breakdowns,
    moderation state, raw entities_json, ai_model, raw financial_impact_estimate,
    raw victim_scale_raw, is_published, is_relevant, published_by_user_id,
    matched_keywords.
    """

    # ----- Ken's primary fields -----
    id: int
    title: str | None = None
    # 0–100 score (Ken-approved 2026-05-06). Internal sum is 5–25; mapper normalizes.
    score: int | None = None
    risk_level: str | None = None  # Title case: "High" | "Medium" | "Low"
    confidence: str | None = None  # Title case: "High" | "Medium" | "Low" — derived
    summary: str | None = None

    why_it_matters: list[str] | None = None
    key_intelligence: list[PublicKeyIntelItem] | None = None
    risk_assessment: str | None = None

    sources: list[PublicSourceRef] | None = None
    published_date: datetime | None = None

    category: str | None = None
    subcategory: str | None = None  # mirrors secondary_category
    affected_group: str | None = None

    timeline: list[PublicTimelineItem] | None = None
    related_signals: list[PublicRelatedSignal] | None = None

    # ----- Backward-compatibility additive fields (kept; do not remove) -----
    signal_score: int | None = None
    secondary_category: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_published_at: datetime | None = None
    published_at: datetime | None = None
    processed_at: datetime | None = None
    # Default [] preserves the prior contract — entities is always present even
    # when there are no extracted names.
    entities: list[str] = []


class PublicAlertsResponse(BaseModel):
    """Wrapper response for the public alerts feed.

    Returns { "alerts": [...] } so the frontend has a stable named key
    and the shape can be extended later (e.g. total count) without breaking clients.
    """

    alerts: list[PublicAlertRead]


# ---------------------------------------------------------------------------
# Subscriber-enriched feed schemas (OPEN-6) — used ONLY by /api/v1/subscriber/*.
# These extend the public schemas with the Critical-badge `risk_band` and the
# curated risk explanation, populated only on the authenticated subscriber path.
# The public PublicAlert* schemas above are intentionally left unchanged so the
# unauthenticated public feed never gains these fields (its leak tests stay valid).
# ---------------------------------------------------------------------------


class SubscriberAlertRead(PublicAlertRead):
    """Public list item + V1 `risk_band` for the Critical/High/Medium badge."""

    risk_band: str | None = None


class SubscriberAlertsResponse(BaseModel):
    """Wrapper for the subscriber alerts feed (mirrors PublicAlertsResponse)."""

    alerts: list[SubscriberAlertRead]


class SubscriberAlertDetail(PublicAlertDetail):
    """Public enriched detail + V1 `risk_band` + the curated risk explanation."""

    risk_band: str | None = None
    risk_explanation: SubscriberRiskExplanation | None = None


class PublicCategoryBreakdown(BaseModel):
    """Per-category count entry for the public stats endpoint."""

    category: str
    count: int


class PublicAlertStatsResponse(BaseModel):
    """Published-alert aggregate stats for the public frontend.

    All counts are derived exclusively from published alerts.
    No internal operational metadata is included.
    """

    total_alerts: int
    high_count: int
    medium_count: int
    low_count: int
    category_breakdown: list[PublicCategoryBreakdown]


class SubscriberAlertStatsResponse(BaseModel):
    """Published-alert stats for the paid subscriber feed.

    Unlike the public stats, the buckets use the V1 risk bands the subscriber UI
    renders as badges (Critical 80–100, High 70–79, Medium 60–69 on the 0–100
    scale), so ``critical_count`` is reported separately and the four bands are
    mutually exclusive.
    """

    total_alerts: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    category_breakdown: list[PublicCategoryBreakdown]
