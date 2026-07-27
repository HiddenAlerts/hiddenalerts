from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.intelligence_brief_constants import (
    DEFAULT_BRIEF_STATUS,
    DEFAULT_BRIEF_TYPE,
    MIN_READ_TIME_MINUTES,
)


class IntelligenceBrief(Base):
    """An analyst-authored intelligence brief (Intelligence Brief Module, Phase 1).

    Greenfield content table backing the admin CMS and the subscriber Brief Library. 

    Design notes:
      * Enum-like columns (``status``, ``risk_level``, ``confidence_level``,
        ``time_horizon``, ``brief_type``) are plain ``String`` columns whose
        controlled vocabulary lives in ``intelligence_brief_constants``;
        accepted-value validation happens at the API layer, matching the
        existing project convention (see ``processed_alerts``).
      * Repeatable fields (``primary_entities``, ``tags``, ``key_signals``,
        ``supporting_alerts``) are ``JSONB``.
      * Rich-text fields are ``Text`` and store sanitised HTML.
      * All timestamps are timezone-aware.
      * Content/metadata fields are nullable so an admin can save a sparse
        draft; "required" fields are enforced at publish time by the API, not
        by NOT NULL constraints. Only structural/lifecycle fields are NOT NULL.
    """

    __tablename__ = "intelligence_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # System-generated human-readable code, e.g. "HA-20260626-001".
    brief_code: Mapped[str] = mapped_column(String(32), nullable=False)

    # --- Basic information -------------------------------------------------
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    risk_level: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # critical|high|medium|low
    primary_entities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    featured_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    featured_image_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    time_horizon: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # immediate|near_term|medium_term|long_term

    # --- Intelligence content (sanitised HTML / JSON) ----------------------
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_this_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_signals: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    risk_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_others_miss: Mapped[str | None] = mapped_column(Text, nullable=True)
    implications: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_intelligence_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyst_notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # admin-only
    supporting_alerts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    alerts_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    # --- Publishing / lifecycle -------------------------------------------
    confidence_level: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # high|medium|low
    status: Mapped[str] = mapped_column(
        String(20),
        default=DEFAULT_BRIEF_STATUS,
        server_default=DEFAULT_BRIEF_STATUS,
        nullable=False,
    )  # draft|published|archived
    is_featured: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- Future-ready fields ----------------------------------------------
    # What kind of content this row is. Phase 1 always creates
    # "intelligence_brief"; other values are reserved for later phases.
    brief_type: Mapped[str] = mapped_column(
        String(50),
        default=DEFAULT_BRIEF_TYPE,
        server_default=DEFAULT_BRIEF_TYPE,
        nullable=False,
    )
    # Reserved for a future multi-featured ordering. Phase 1 enforces a single
    # global featured brief, so this stays NULL (nullable, no default) to avoid
    # seeding misleading ordering data on every row.
    featured_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read_time_minutes: Mapped[int] = mapped_column(
        Integer,
        default=MIN_READ_TIME_MINUTES,
        server_default=str(MIN_READ_TIME_MINUTES),
        nullable=False,
    )
    # Whether this brief is paid subscriber content. Phase 1 briefs are premium.
    is_premium: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("slug", name="uq_intelligence_briefs_slug"),
        UniqueConstraint("brief_code", name="uq_intelligence_briefs_brief_code"),
        Index("idx_intelligence_briefs_status", "status"),
        Index("idx_intelligence_briefs_risk_level", "risk_level"),
        Index("idx_intelligence_briefs_category", "category"),
        Index("idx_intelligence_briefs_is_featured", "is_featured"),
        Index("idx_intelligence_briefs_brief_type", "brief_type"),
        Index("idx_intelligence_briefs_is_premium", "is_premium"),
        Index("idx_intelligence_briefs_published_at", "published_at"),
        # GIN indexes accelerate JSONB containment/overlap filters in Postgres.
        # The ``postgresql_using`` directive is ignored by SQLite (test engine),
        # where these are created as ordinary indexes — verified harmless.
        Index(
            "idx_intelligence_briefs_tags_gin",
            "tags",
            postgresql_using="gin",
        ),
        Index(
            "idx_intelligence_briefs_primary_entities_gin",
            "primary_entities",
            postgresql_using="gin",
        ),
    )

    created_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[created_by_user_id]
    )
    updated_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[updated_by_user_id]
    )

    def __repr__(self) -> str:
        return (
            f"<IntelligenceBrief id={self.id} brief_code={self.brief_code!r} "
            f"status={self.status!r} risk_level={self.risk_level!r}>"
        )
