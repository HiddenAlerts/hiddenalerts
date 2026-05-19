from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscriber_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subscriber_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    stripe_price_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "stripe_subscription_id", name="uq_subscriptions_stripe_subscription_id"
        ),
        Index("idx_subscriptions_subscriber_profile_id", "subscriber_profile_id"),
        Index("idx_subscriptions_stripe_customer_id", "stripe_customer_id"),
        Index("idx_subscriptions_status", "status"),
    )

    subscriber_profile: Mapped["SubscriberProfile"] = relationship(  # noqa: F821
        "SubscriberProfile", back_populates="subscriptions"
    )

    def __repr__(self) -> str:
        return (
            f"<Subscription id={self.id} "
            f"stripe_subscription_id={self.stripe_subscription_id!r} "
            f"status={self.status!r}>"
        )
