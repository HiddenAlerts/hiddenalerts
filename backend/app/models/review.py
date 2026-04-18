from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AlertReview(Base):
    __tablename__ = "alert_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("processed_alerts.id"), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    review_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'approved', 'false_positive', 'edited'
    edited_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjusted_risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    # Relationships
    alert: Mapped["ProcessedAlert | None"] = relationship(  # noqa: F821
        "ProcessedAlert", back_populates="reviews"
    )
    user: Mapped["User | None"] = relationship("User", back_populates="reviews")  # noqa: F821

    def __repr__(self) -> str:
        return f"<AlertReview id={self.id} status={self.review_status!r}>"
