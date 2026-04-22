from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="subscriber")
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    wants_high_alert_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wants_digest_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wants_weekly_report_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    # Relationships
    reviews: Mapped[list["AlertReview"]] = relationship("AlertReview", back_populates="user")  # noqa: F821

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
