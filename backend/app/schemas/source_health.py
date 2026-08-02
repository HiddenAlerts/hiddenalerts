"""Response models for the read-only Source Health API."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.run_log import RunLogRead


class SourceHealthRead(BaseModel):
    """One source's derived health. Observational — nothing here triggers work."""

    # Identity
    source_id: int
    name: str
    source_type: str | None = None
    adapter_class: str | None = None
    is_active: bool
    credibility_score: int | None = None

    # Classification
    state: str = Field(description="healthy | warning | error | disabled")
    reason_code: str = Field(description="Machine-readable primary reason.")
    reason_detail: str = Field(default="", description="Human-readable explanation.")
    additional_reason_codes: list[str] = Field(
        default_factory=list,
        description="Other conditions that also matched, worst first.",
    )

    # Latest activity
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    last_run_duration_seconds: float | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None
    last_new_item_at: datetime | None = None
    latest_upstream_published_at: datetime | None = None

    # Streaks
    consecutive_failed_runs: int = 0
    consecutive_zero_fetch_runs: int = 0
    consecutive_zero_new_runs: int = 0

    # Window metrics
    runs_24h: int = 0
    items_fetched_24h: int = 0
    items_new_24h: int = 0
    items_new_7d: int = 0
    items_new_30d: int = 0
    items_skipped_invalid_24h: int = 0

    # External exclusions — deliberate policy outcomes, never invalid content.
    latest_run_items_skipped_external: int = 0
    items_skipped_external_24h: int = 0
    items_skipped_external_7d: int = 0

    # Totals
    total_raw_items: int = 0
    total_published_alerts: int = 0


class SourceHealthDetail(BaseModel):
    """One source's health plus its recent run history."""

    health: SourceHealthRead
    recent_runs: list[RunLogRead]


class AttentionSource(BaseModel):
    source_id: int
    name: str
    state: str
    reason_code: str


class SystemHealthSummary(BaseModel):
    """Instance-wide collection health."""

    sources_total: int
    by_state: dict[str, int] = Field(
        description="Counts keyed by healthy / warning / error / disabled."
    )
    sources_needing_attention: list[AttentionSource] = Field(
        description="Error sources first, then warning. Capped."
    )

    last_collection_cycle_at: datetime | None = None
    scheduler_running: bool
    scheduler_interval_hours: float

    items_new_24h: int = 0
    items_new_7d: int = 0
    items_skipped_external_24h: int = 0
    items_skipped_external_7d: int = 0

    raw_items_total: int = 0
    processed_alerts_total: int = 0
    published_alerts_total: int = 0
    published_last_7d: int = 0

    alembic_revision: str | None = None
