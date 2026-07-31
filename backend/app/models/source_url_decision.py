from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

#: A URL whose content is owned by a different source. FBI feeds routinely
#: redirect to justice.gov, where DOJ is canonical, so the FBI sources refuse
#: those destinations — see ``DestinationExcluded``.
EXTERNAL_DESTINATION_EXCLUDED = "external_destination_excluded"

#: Decisions that stop the collector requesting an article at all. Kept as a set
#: so a future terminal decision can join it without touching call sites.
SUPPRESSING_DECISIONS = frozenset({EXTERNAL_DESTINATION_EXCLUDED})


class SourceURLDecision(Base):
    """A durable, source-specific verdict about one URL.

    Without this, an excluded URL creates no ``RawItem``, so it stays "unseen"
    and is requested again on every scheduled run — the expanded FBI preview
    measured 45 such URLs in a 50-item sample. Recording the decision stops the
    repeat request without pretending the item was collected.

    The decision belongs to a *source*, not to a URL: the same justice.gov
    article is excluded under an FBI source and collected normally under DOJ.
    That is what the ``(source_id, url_hash)`` uniqueness expresses.

    Nothing about the response is kept — no body, summary, header or cookie —
    and ``item_url`` is a redacted snapshot with query and fragment removed.
    """

    __tablename__ = "source_url_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    #: Production ``compute_url_hash`` of the item URL — the same value the
    #: collector's RawItem pre-filter compares against.
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Redacted URL, for humans reading the table. Never the query string.
    item_url: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Normalized lowercase host the item resolved to, without a trailing dot.
    destination_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: The item's own publication date, when the listing carried one.
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    #: How many runs have re-encountered this URL. 1 on the run that recorded it.
    occurrence_count: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )

    __table_args__ = (
        # One verdict per URL per source; the upsert key.
        UniqueConstraint("source_id", "url_hash", name="uq_source_url_decisions_source_url"),
        Index("idx_source_url_decisions_source_id", "source_id"),
        Index("idx_source_url_decisions_decision", "decision"),
        # The collector's per-run lookup: this source's suppressing decisions.
        Index("idx_source_url_decisions_source_decision", "source_id", "decision"),
    )

    source: Mapped["Source"] = relationship(  # noqa: F821
        "Source", back_populates="url_decisions"
    )

    def __repr__(self) -> str:
        return (
            f"<SourceURLDecision source_id={self.source_id} "
            f"decision={self.decision!r} url={self.item_url!r}>"
        )
