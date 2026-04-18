from datetime import date, datetime

from sqlalchemy import Date, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    report_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<WeeklyReport id={self.id} week_start={self.week_start}>"
