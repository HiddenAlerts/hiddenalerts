"""Persistence for durable, source-specific URL decisions.

Two operations, both bounded: look up this source's suppressing decisions for a
batch of URL hashes in one query, and record a new exclusion idempotently.

Neither commits. The collector owns the transaction, so a decision and the run
log that counts it are written together or not at all — a run can never report
that an exclusion was durably remembered when it was not.
"""
import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_url_decision import (
    EXTERNAL_DESTINATION_EXCLUDED,
    SUPPRESSING_DECISIONS,
    SourceURLDecision,
)

log = logging.getLogger(__name__)

#: Chunk size for the batch lookup. Feeds top out around 300 stubs today; this
#: keeps the IN list bounded if one ever grows far beyond that.
_LOOKUP_CHUNK = 500


def normalize_destination_host(host: str | None) -> str | None:
    """Lowercase, trimmed, no trailing root dot — or ``None``."""
    cleaned = (host or "").strip().lower().rstrip(".")
    return cleaned or None


async def get_suppressing_decisions(
    session: AsyncSession, source_id: int, url_hashes: set[str]
) -> dict[str, SourceURLDecision]:
    """This source's terminal decisions for ``url_hashes``, keyed by hash.

    Only decisions that suppress an article fetch are returned. Scoped to one
    source: a decision recorded for an FBI source must never suppress DOJ.
    """
    if not url_hashes or source_id is None:
        return {}

    hashes = list(url_hashes)
    found: dict[str, SourceURLDecision] = {}
    for start in range(0, len(hashes), _LOOKUP_CHUNK):
        chunk = hashes[start:start + _LOOKUP_CHUNK]
        result = await session.execute(
            select(SourceURLDecision).where(
                SourceURLDecision.source_id == source_id,
                SourceURLDecision.decision.in_(SUPPRESSING_DECISIONS),
                SourceURLDecision.url_hash.in_(chunk),
            )
        )
        for decision in result.scalars().all():
            found[decision.url_hash] = decision
    return found


async def record_external_exclusion(
    session: AsyncSession,
    *,
    source_id: int,
    url_hash: str,
    item_url: str,
    destination_host: str | None = None,
    reason_code: str | None = None,
    published_at: datetime | None = None,
    now: datetime | None = None,
) -> SourceURLDecision:
    """Insert this exclusion, or refresh the one already recorded.

    Idempotent: repeated calls for the same (source, URL) advance
    ``last_seen_at`` and ``occurrence_count`` and leave ``first_seen_at`` alone.
    A concurrent writer that wins the unique-constraint race is handled by
    retrying as an update inside a savepoint, so the outer transaction survives.

    ``item_url`` must already be redacted by the caller — this function stores
    what it is given and never a query string.
    """
    moment = now or datetime.utcnow()
    host = normalize_destination_host(destination_host)

    existing = (
        await session.execute(
            select(SourceURLDecision).where(
                SourceURLDecision.source_id == source_id,
                SourceURLDecision.url_hash == url_hash,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        return _touch(existing, moment, host, reason_code)

    decision = SourceURLDecision(
        source_id=source_id,
        url_hash=url_hash,
        item_url=item_url,
        decision=EXTERNAL_DESTINATION_EXCLUDED,
        destination_host=host,
        reason_code=reason_code,
        published_at=published_at,
        first_seen_at=moment,
        last_seen_at=moment,
        occurrence_count=1,
    )
    try:
        # The savepoint keeps a lost race from poisoning the outer transaction.
        async with session.begin_nested():
            session.add(decision)
            await session.flush()
    except IntegrityError:
        row = (
            await session.execute(
                select(SourceURLDecision).where(
                    SourceURLDecision.source_id == source_id,
                    SourceURLDecision.url_hash == url_hash,
                )
            )
        ).scalar_one()
        return _touch(row, moment, host, reason_code)

    return decision


def _touch(
    decision: SourceURLDecision,
    moment: datetime,
    destination_host: str | None,
    reason_code: str | None,
) -> SourceURLDecision:
    """Advance the sighting fields; never rewrite when it was first seen."""
    decision.last_seen_at = moment
    decision.occurrence_count = (decision.occurrence_count or 0) + 1
    if destination_host:
        decision.destination_host = destination_host
    if reason_code:
        decision.reason_code = reason_code
    return decision


async def touch_seen_decisions(
    session: AsyncSession, decisions: list[SourceURLDecision], *, now: datetime | None = None
) -> None:
    """Mark already-recorded decisions as seen again, in one statement.

    Called once per run for every previously excluded URL the listing still
    carries, so ``occurrence_count`` measures how persistent the upstream link
    is without costing a query per item.
    """
    if not decisions:
        return
    moment = now or datetime.utcnow()
    await session.execute(
        update(SourceURLDecision)
        .where(SourceURLDecision.id.in_([d.id for d in decisions]))
        .values(
            last_seen_at=moment,
            occurrence_count=SourceURLDecision.occurrence_count + 1,
        )
        .execution_options(synchronize_session=False)
    )
