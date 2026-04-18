from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RawItem(Base):
    __tablename__ = "raw_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sources.id"), nullable=True)
    item_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_raw_items_url_hash"),
        Index("idx_raw_items_source_id", "source_id"),
        Index("idx_raw_items_content_hash", "content_hash"),
        Index("idx_raw_items_fetched_at", "fetched_at"),
    )

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="raw_items")  # noqa: F821
    processed_alert: Mapped["ProcessedAlert | None"] = relationship(  # noqa: F821
        "ProcessedAlert", back_populates="raw_item", uselist=False
    )

    def __repr__(self) -> str:
        return f"<RawItem id={self.id} url={self.item_url!r}>"
