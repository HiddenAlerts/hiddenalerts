from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_entity: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_detected_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    event_sources: Mapped[list["EventSource"]] = relationship(  # noqa: F821
        "EventSource", back_populates="event"
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} title={self.title!r}>"


class EventSource(Base):
    __tablename__ = "event_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"), nullable=True)
    alert_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("processed_alerts.id"), nullable=True
    )
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    # Relationships
    event: Mapped["Event | None"] = relationship("Event", back_populates="event_sources")
    alert: Mapped["ProcessedAlert | None"] = relationship(  # noqa: F821
        "ProcessedAlert", back_populates="event_sources"
    )

    def __repr__(self) -> str:
        return f"<EventSource id={self.id} event_id={self.event_id}>"
