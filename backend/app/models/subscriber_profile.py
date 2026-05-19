from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SubscriberProfile(Base):
    __tablename__ = "subscriber_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supabase_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="subscriber")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "supabase_user_id", name="uq_subscriber_profiles_supabase_user_id"
        ),
        UniqueConstraint(
            "stripe_customer_id", name="uq_subscriber_profiles_stripe_customer_id"
        ),
        Index("idx_subscriber_profiles_email", "email"),
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(  # noqa: F821
        "Subscription", back_populates="subscriber_profile"
    )

    def __repr__(self) -> str:
        return (
            f"<SubscriberProfile id={self.id} "
            f"supabase_user_id={self.supabase_user_id!r}>"
        )
