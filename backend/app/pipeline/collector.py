import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source
from app.pipeline.deduplicator import get_known_url_hashes, is_content_duplicate
from app.pipeline.normalizer import compute_content_hash, compute_url_hash
from app.sources.registry import get_adapter

log = logging.getLogger(__name__)


def _to_naive_utc(dt: datetime) -> datetime:
    """Strip timezone info from a datetime, converting to UTC first if needed."""
    if dt.tzinfo is not None:
        import calendar as _cal
        return datetime.utcfromtimestamp(_cal.timegm(dt.utctimetuple()))
    return dt


async def _get_last_successful_run_at(session: AsyncSession, source_id: int) -> datetime | None:
    """Return the start time of the most recent successful run for this source."""
    result = await session.execute(
        select(RunLog.run_started_at)
        .where(RunLog.source_id == source_id, RunLog.status == "success")
        .order_by(RunLog.run_started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def run_source(source: Source, session: AsyncSession) -> RunLog:
    """Fetch, deduplicate, and store items for one source using a 2-stage pipeline.

    Stage 1 — Fetch stubs (cheap): parse feed/listing to get article URLs + metadata.
    Pre-filter 1 — Date check: skip stubs whose published_at is older than the last
                   successful run (only when published_at is available).
    Pre-filter 2 — URL hash batch check: single DB query to find already-stored URLs;
                   skip those entirely — no HTTP fetch needed.
    Stage 2 — Fetch full articles (expensive): only for genuinely new URLs.
    Content dedup  — SHA-256 content hash check: catches same article at a new URL.
    """
    run_log = RunLog(
        source_id=source.id,
        run_started_at=datetime.utcnow(),
        status="running",
        items_fetched=0,
        items_new=0,
        items_duplicate=0,
    )
    session.add(run_log)
    await session.flush()

    try:
        adapter = get_adapter(source)

        # ── Stage 1: Lightweight stub fetch (feed/listing only, no article fetches) ──
        stubs = await adapter.fetch_item_stubs()
        run_log.items_fetched = len(stubs)

        if not stubs:
            run_log.status = "success"
            log.info(f"Source '{source.name}': no stubs returned")
            return run_log

        # ── Pre-filter 1: Date-based skip ────────────────────────────────────────
        # If a stub's published_at is known and predates the last successful run,
        # it was already ingested — skip it without even checking the DB.
        last_run_at = await _get_last_successful_run_at(session, source.id)
        date_skipped = 0

        if last_run_at:
            candidates = []
            for stub in stubs:
                if stub.published_at is not None and _to_naive_utc(stub.published_at) <= _to_naive_utc(last_run_at):
                    date_skipped += 1
                else:
                    candidates.append(stub)
            stubs = candidates
            if date_skipped:
                log.info(
                    f"Source '{source.name}': date filter skipped {date_skipped} stubs "
                    f"(published before {last_run_at.strftime('%Y-%m-%d %H:%M')})"
                )

        # ── Pre-filter 2: URL hash batch check ───────────────────────────────────
        # Build a map of {url_hash → stub} and eliminate known URLs in one query.
        url_hash_map: dict[str, object] = {
            compute_url_hash(stub.item_url): stub for stub in stubs
        }
        known_hashes = await get_known_url_hashes(session, set(url_hash_map.keys()))
        new_stubs = [
            stub for h, stub in url_hash_map.items() if h not in known_hashes
        ]
        url_skipped = len(url_hash_map) - len(new_stubs)
        run_log.items_duplicate += date_skipped + url_skipped

        log.info(
            f"Source '{source.name}': {run_log.items_fetched} in feed → "
            f"{date_skipped} date-skipped, {url_skipped} url-skipped → "
            f"{len(new_stubs)} to fetch"
        )

        # ── Stage 2: Full article fetch — only for new stubs ─────────────────────
        for stub in new_stubs:
            url_hash = compute_url_hash(stub.item_url)

            try:
                raw_text, raw_html = await adapter.fetch_full_article(stub.item_url)
            except Exception as exc:
                log.warning(f"Could not fetch full article {stub.item_url}: {exc}")
                # Use feed summary as fallback if available (RSS adapters populate this)
                raw_text = stub.summary  # type: ignore[attr-defined]
                raw_html = ""

            content_hash = compute_content_hash(raw_text)

            # Content-hash dedup: same article republished at a different URL
            if await is_content_duplicate(session, content_hash):
                run_log.items_duplicate += 1
                continue

            raw_item = RawItem(
                source_id=source.id,
                item_url=stub.item_url,  # type: ignore[attr-defined]
                title=stub.title,  # type: ignore[attr-defined]
                published_at=stub.published_at,  # type: ignore[attr-defined]
                raw_text=raw_text,
                raw_html=raw_html,
                content_hash=content_hash,
                url_hash=url_hash,
                is_duplicate=False,
                fetched_at=datetime.utcnow(),
            )
            from sqlalchemy.exc import IntegrityError
            
            session.add(raw_item)
            try:
                async with session.begin_nested():
                    await session.flush()
                run_log.items_new += 1
            except IntegrityError:
                log.warning(f"Concurrent insert / Duplicate URL detected for {stub.item_url}, skipping...")
                run_log.items_duplicate += 1
                session.expunge(raw_item)

        run_log.status = "success"
        log.info(
            f"Source '{source.name}': {run_log.items_new} new, "
            f"{run_log.items_duplicate} skipped/dup out of {run_log.items_fetched} in feed"
        )

    except Exception as exc:
        run_log.status = "failed"
        run_log.error_message = str(exc)
        log.error(f"Source '{source.name}' failed: {exc}", exc_info=True)

    finally:
        run_log.run_finished_at = datetime.utcnow()
        try:
            await session.commit()
        except Exception as commit_exc:
            log.error(f"Failed to commit run log for '{source.name}': {commit_exc}")
            await session.rollback()

    return run_log


async def run_all_sources() -> list[RunLog]:
    """Run all active sources. Each source gets its own fresh session for isolation."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Source).where(Source.is_active.is_(True)))
        sources = result.scalars().all()

    run_logs: list[RunLog] = []
    for source in sources:
        async with AsyncSessionLocal() as source_session:
            try:
                run_log = await run_source(source, source_session)
                run_logs.append(run_log)
            except Exception as exc:
                log.error(f"Unexpected error for source '{source.name}': {exc}", exc_info=True)

    return run_logs
