from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, desc, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sources.id"), nullable=True)
    run_started_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    run_finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'running', 'success', 'partial', 'failed'
    items_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Sum of the url + content skip counters. Kept for existing readers; the split
    # counters below are the authoritative breakdown.
    items_duplicate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # URL already stored, repeated within the fetched batch, or lost a unique-constraint race.
    items_skipped_url: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    # Content hash matched an already-stored item.
    items_skipped_content: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    # No usable URL or article text, so nothing could be persisted.
    items_skipped_invalid: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_run_logs_source_id", "source_id"),
        Index("idx_run_logs_status", "status"),
        # Serves the "latest runs for this source" lookups the health queries make.
        Index("idx_run_logs_source_started", "source_id", desc("run_started_at")),
    )

    # Relationships
    source: Mapped["Source | None"] = relationship("Source", back_populates="run_logs")  # noqa: F821

    def __repr__(self) -> str:
        return f"<RunLog id={self.id} source_id={self.source_id} status={self.status!r}>"
