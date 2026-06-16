from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, false, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProcessedAlert(Base):
    __tablename__ = "processed_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("raw_items.id"), unique=True, nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'low', 'medium', 'high'
    primary_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    secondary_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entities_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    matched_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_relevant: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    # Signal scoring fields (Milestone 2)
    score_source_credibility: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_financial_impact: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_victim_scale: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_cross_source: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_trend_acceleration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signal_score_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # AI raw output fields (Milestone 2) — stored for audit/recalculation
    financial_impact_estimate: Mapped[str | None] = mapped_column(String(200), nullable=True)
    victim_scale_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Publication fields (Milestone 3)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # V1 Alert Publishing state (Slice 1 — additive foundation only; NOT yet
    # populated by the pipeline). Controlled vocabulary lives in
    # app.pipeline.publishing.constants. All fields default to a neutral/empty
    # state so existing rows and current publish behaviour are unaffected.
    risk_band: Mapped[str | None] = mapped_column(String(20), nullable=True)  # critical|high|medium|below_60
    publish_decision: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # auto_publish|review|exclude|hold
    publish_decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_review_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_excluded: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    excluded_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_manual_hold: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    published_by_rule: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    publishing_policy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    publication_state_source: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # auto_policy|manual_admin|candidate_backfill|system_migration
    publication_state_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_processed_alerts_risk", "risk_level"),
        Index("idx_processed_alerts_category", "primary_category"),
        Index("idx_processed_alerts_score", "signal_score_total"),
        Index("idx_processed_alerts_risk_band", "risk_band"),
        Index("idx_processed_alerts_pending_review_reason", "pending_review_reason"),
        Index("idx_processed_alerts_publish_decision", "publish_decision"),
        Index("idx_processed_alerts_publication_state_source", "publication_state_source"),
    )

    # Relationships
    raw_item: Mapped["RawItem"] = relationship("RawItem", back_populates="processed_alert")  # noqa: F821
    event_sources: Mapped[list["EventSource"]] = relationship(  # noqa: F821
        "EventSource", back_populates="alert"
    )
    reviews: Mapped[list["AlertReview"]] = relationship("AlertReview", back_populates="alert")  # noqa: F821
    published_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[published_by_user_id]
    )

    def __repr__(self) -> str:
        return f"<ProcessedAlert id={self.id} risk={self.risk_level!r} published={self.is_published}>"
