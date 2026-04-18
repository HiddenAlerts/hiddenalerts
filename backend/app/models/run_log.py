from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, func
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
    items_duplicate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_run_logs_source_id", "source_id"),
        Index("idx_run_logs_status", "status"),
    )

    # Relationships
    source: Mapped["Source | None"] = relationship("Source", back_populates="run_logs")  # noqa: F821

    def __repr__(self) -> str:
        return f"<RunLog id={self.id} source_id={self.source_id} status={self.status!r}>"
