from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BillingCheckoutAttempt(Base):
    """Local record of a Stripe Checkout Session creation attempt.

    Powers checkout request idempotency (Auth/Payment Phase 1, Slice 6):
    - ``idempotency_key`` is unique globally; same key from the same subscriber
      returns the stored ``checkout_url`` without re-calling Stripe.
    - A different subscriber reusing the same key is rejected with 409.
    - ``status`` walks ``pending`` → ``succeeded`` | ``failed`` so retries
      know whether to reuse, wait, or try again.
    - When no header is supplied, the route also scans recent rows by
      ``(subscriber_profile_id, plan_type)`` to fold double-clicks together.

    ``expires_at`` is reserved for a future cleanup job; not used in this slice.
    """

    __tablename__ = "billing_checkout_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscriber_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subscriber_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_type: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_billing_checkout_attempts_idempotency_key",
        ),
        Index(
            "idx_billing_checkout_attempts_subscriber_profile_id",
            "subscriber_profile_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BillingCheckoutAttempt id={self.id} "
            f"subscriber_profile_id={self.subscriber_profile_id} "
            f"plan_type={self.plan_type!r} status={self.status!r}>"
        )
