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
    signal_score_total: int | None
    # Normalized 0.0–1.0 score for frontend convenience (signal_score_total / 25)
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


class ClientAlertRead(BaseModel):
    """Subscriber-safe alert summary — only published alerts are served via client endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None = None
    source_name: str | None = None
    item_url: str | None = None
    risk_level: str | None
    primary_category: str | None
    signal_score_total: int | None
    summary: str | None = None
    processed_at: datetime
    # Original source/press-release publication date.
    source_published_at: datetime | None = None
    published_at: datetime | None = None
    matched_keywords: list[str] | None = None


class ClientAlertDetail(ClientAlertRead):
    """Subscriber-safe alert detail — adds category and entities."""

    secondary_category: str | None = None
    # Normalised entity list — extracted from entities_json for stable frontend consumption.
    # Internal format {"names": [...]} is unwrapped to a plain list here.
    entities: list[str] = []


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
    signal_score: int | None = None
    source_name: str | None = None
    source_url: str | None = None
    # Original source/press-release publication date — what to display on the
    # frontend feed. Falls back to null when the source did not provide a date.
    source_published_at: datetime | None = None
    published_at: datetime | None = None


class PublicAlertsResponse(BaseModel):
    """Wrapper response for the public alerts feed.

    Returns { "alerts": [...] } so the frontend has a stable named key
    and the shape can be extended later (e.g. total count) without breaking clients.
    """

    alerts: list[PublicAlertRead]
