"""Pydantic schemas for the public search API — GET /api/search/alerts.

Schemas are intentionally separate from app/schemas/alert.py so the search
contract can evolve independently of the public list/detail contracts.

The per-alert shape (`SearchAlertItem`) mirrors `PublicAlertRead` and adds an
optional `matched_entity` field. Group-level field names use camelCase
(`alertCount`, `sourceCount`) per Ken's agreed contract.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SearchAlertItem(BaseModel):
    """Frontend-safe per-alert row in the search response.

    Same field set as `PublicAlertRead` plus `matched_entity` (the parsed
    entity name that matched the query, or null when the match was on
    title/summary/source). Internal/admin fields are intentionally absent.
    """

    id: int
    title: str | None = None
    summary: str | None = None
    category: str | None = None
    risk_level: str | None = None
    # 0–100 normalized score. DB stores internal 5–25; mapper normalizes.
    signal_score: int | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_published_at: datetime | None = None
    published_at: datetime | None = None
    matched_entity: str | None = None


class SearchGroup(BaseModel):
    """A grouped slice of search results.

    `group_type` is "entity" when grouping is driven by extracted entities
    matching the query, or "keyword" for the fallback group used when no
    entity match exists.

    camelCase field names (`alertCount`, `sourceCount`) are required by the
    agreed frontend contract and must not be renamed.
    """

    model_config = ConfigDict(populate_by_name=True)

    entity: str
    group_type: str  # "entity" | "keyword"
    alert_count: int = Field(serialization_alias="alertCount")
    source_count: int = Field(serialization_alias="sourceCount")
    sources: list[str] = []
    earliest: datetime | None = None
    latest: datetime | None = None
    alerts: list[SearchAlertItem] = []


class SearchResponse(BaseModel):
    """Top-level response shape for GET /api/search/alerts.

    `total_alerts` counts unique alerts across the response. When an alert is
    tagged with multiple matching entities and therefore appears in multiple
    entity groups, the sum of `alertCount` across groups can exceed
    `total_alerts` — this is intentional and documented in the API contract.
    The top-level `alerts` list itself is unique-by-id.
    """

    query: str
    normalized_query: str
    total_alerts: int
    group_count: int
    groups: list[SearchGroup]
    alerts: list[SearchAlertItem]
