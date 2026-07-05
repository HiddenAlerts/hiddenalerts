"""Pydantic schemas for the Intelligence Brief admin CMS.

Request/response contracts for the admin create/update/list/detail endpoints.
Enum-like fields are typed against the controlled vocabulary in
``app.models.intelligence_brief_constants`` so invalid values are rejected at
the schema boundary (HTTP 422) and stored as plain snake_case strings.

Lifecycle fields (``status``, ``is_featured``) are intentionally absent from the
create/update payloads — publishing, archiving and featuring are separate admin
actions with their own endpoints and are not settable through generic CRUD.
Featured-image fields are likewise managed by the dedicated upload endpoint, not
these payloads.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.intelligence_brief_constants import (
    BriefConfidenceLevel,
    BriefRiskLevel,
    BriefTimeHorizon,
    BriefType,
)


class SupportingAlert(BaseModel):
    """A manually-referenced published alert.

    Phase 1 supporting alerts are URLs an analyst pastes in while writing a
    brief; they are not relational links to ``processed_alerts``. Extra keys the
    editor may send are ignored.
    """

    url: str = Field(min_length=1)
    title: str | None = None


def _blank_to_error(value: str, field_name: str) -> str:
    """Reject strings that are empty or whitespace-only."""
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    return value.strip()


class IntelligenceBriefCreate(BaseModel):
    """Payload for creating a draft brief. Only ``title`` is required so an
    analyst can save a sparse draft and fill the rest in later."""

    model_config = ConfigDict(use_enum_values=True)

    title: str = Field(min_length=1, max_length=500)
    slug: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    risk_score: int | None = Field(default=None, ge=0, le=100)
    risk_level: BriefRiskLevel | None = None
    primary_entities: list[str] | None = None
    tags: list[str] | None = None
    time_horizon: BriefTimeHorizon | None = None

    executive_summary: str | None = None
    why_this_matters: str | None = None
    key_signals: list[str] | None = None
    risk_assessment: str | None = None
    what_others_miss: str | None = None
    implications: str | None = None
    main_intelligence_brief: str | None = None
    analyst_notes: str | None = None
    supporting_alerts: list[SupportingAlert] | None = None

    confidence_level: BriefConfidenceLevel | None = None

    # Future-ready fields (see model). brief_type defaults to intelligence_brief
    # in the service when omitted; is_premium defaults to True.
    brief_type: BriefType | None = None
    featured_order: int | None = None
    is_premium: bool | None = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        return _blank_to_error(value, "title")


class IntelligenceBriefUpdate(BaseModel):
    """Partial-update payload. Every field is optional; only fields present in
    the request are applied (``exclude_unset`` semantics in the service)."""

    model_config = ConfigDict(use_enum_values=True)

    title: str | None = Field(default=None, max_length=500)
    slug: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    risk_score: int | None = Field(default=None, ge=0, le=100)
    risk_level: BriefRiskLevel | None = None
    primary_entities: list[str] | None = None
    tags: list[str] | None = None
    time_horizon: BriefTimeHorizon | None = None

    executive_summary: str | None = None
    why_this_matters: str | None = None
    key_signals: list[str] | None = None
    risk_assessment: str | None = None
    what_others_miss: str | None = None
    implications: str | None = None
    main_intelligence_brief: str | None = None
    analyst_notes: str | None = None
    supporting_alerts: list[SupportingAlert] | None = None

    confidence_level: BriefConfidenceLevel | None = None

    brief_type: BriefType | None = None
    featured_order: int | None = None
    is_premium: bool | None = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _blank_to_error(value, "title")


class IntelligenceBriefListItem(BaseModel):
    """Lightweight brief representation for admin list/table views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    brief_code: str
    title: str
    slug: str
    category: str | None
    risk_score: int | None
    risk_level: str | None
    status: str
    is_featured: bool
    brief_type: str
    is_premium: bool
    featured_image_url: str | None
    alerts_count: int
    read_time_minutes: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IntelligenceBriefDetail(BaseModel):
    """Full admin view of a brief, including admin-only ``analyst_notes``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    brief_code: str
    title: str
    slug: str
    category: str | None
    risk_score: int | None
    risk_level: str | None
    primary_entities: list[str] | None
    tags: list[str] | None
    featured_image_url: str | None
    time_horizon: str | None

    executive_summary: str | None
    why_this_matters: str | None
    key_signals: list[str] | None
    risk_assessment: str | None
    what_others_miss: str | None
    implications: str | None
    main_intelligence_brief: str | None
    analyst_notes: str | None
    supporting_alerts: list[SupportingAlert] | None

    alerts_count: int
    confidence_level: str | None
    status: str
    is_featured: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    brief_type: str
    featured_order: int | None
    read_time_minutes: int
    is_premium: bool


class IntelligenceBriefListResponse(BaseModel):
    """Paginated envelope for the admin list endpoint."""

    items: list[IntelligenceBriefListItem]
    total: int
    limit: int
    offset: int
