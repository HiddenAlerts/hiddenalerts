import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source
from app.pipeline.deduplicator import get_known_url_hashes, is_content_duplicate
from app.pipeline.normalizer import compute_content_hash, compute_url_hash
from app.services.collection_guard import claim_source_run, release_source_run
from app.sources.base import RawItemStub
from app.sources.registry import get_adapter

log = logging.getLogger(__name__)


async def run_source(source: Source, session: AsyncSession) -> RunLog:
    """Fetch, deduplicate, and store items for one source using a 2-stage pipeline.

    Stage 1 — Fetch stubs (cheap): parse feed/listing to get article URLs + metadata.
    Pre-filter — URL hash batch check: one DB query eliminates URLs already stored,
                 plus repeats within this batch; skipped stubs need no HTTP fetch.
    Stage 2 — Fetch full articles (expensive): only for genuinely new URLs.
    Content dedup — SHA-256 content hash check: catches the same article at a new URL.

    A stub's ``published_at`` is stored for ordering and health reporting but never
    gates ingestion: eligibility is decided by the normalized URL alone, so an old
    item that reaches a feed late is still collected.

    Callers must hold the source's collection claim — use :func:`collect_source`
    rather than calling this directly outside tests.

    On a run that completes successfully the counters account for every fetched
    stub: ``items_fetched == items_new + items_skipped_url + items_skipped_content
    + items_skipped_invalid``. A run that fails part-way keeps whatever counts it
    reached, so that identity does not hold for ``status='failed'`` rows.

    Raises if the final commit fails, because in that case nothing was persisted
    and the returned counters would be fiction.
    """
    cancelled = False
    run_log = RunLog(
        source_id=source.id,
        run_started_at=datetime.utcnow(),
        status="running",
        items_fetched=0,
        items_new=0,
        items_duplicate=0,
        items_skipped_url=0,
        items_skipped_content=0,
        items_skipped_invalid=0,
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
            log.info("Source %s '%s': feed returned no items", source.id, source.name)
            return run_log

        # ── Pre-filter: URL hash, deduplicated within the batch ──────────────────
        # A feed listing the same article twice stores it once. The last stub for a
        # normalized URL wins, matching the dict-comprehension this replaced, so the
        # metadata a feed revises later in the document is the metadata kept.
        batch: dict[str, RawItemStub] = {}
        for stub in stubs:
            url = (stub.item_url or "").strip()
            if not url:
                run_log.items_skipped_invalid += 1
                log.debug("Source %s: stub with no URL discarded", source.id)
                continue
            url_hash = compute_url_hash(url)
            if url_hash in batch:
                run_log.items_skipped_url += 1
                log.debug("Source %s: repeated URL within batch: %s", source.id, url)
            batch[url_hash] = stub

        known_hashes = await get_known_url_hashes(session, set(batch))
        new_stubs = [(h, stub) for h, stub in batch.items() if h not in known_hashes]
        run_log.items_skipped_url += len(batch) - len(new_stubs)

        log.info(
            "Source %s '%s': %d fetched → %d skipped by URL → %d to retrieve",
            source.id,
            source.name,
            run_log.items_fetched,
            run_log.items_skipped_url,
            len(new_stubs),
        )

        # ── Stage 2: Full article fetch — only for new stubs ─────────────────────
        for url_hash, stub in new_stubs:
            try:
                raw_text, raw_html = await adapter.fetch_full_article(stub.item_url)
            except Exception as exc:
                log.warning(
                    "Source %s: full article fetch failed for %s (%s) — falling back to feed summary",
                    source.id,
                    stub.item_url,
                    exc,
                )
                raw_text = stub.summary
                raw_html = ""

            # Nothing usable to persist. Left unstored on purpose so a later run can
            # retry the URL once the upstream fetch recovers.
            if not (raw_text or "").strip():
                run_log.items_skipped_invalid += 1
                log.debug("Source %s: no usable content for %s", source.id, stub.item_url)
                continue

            content_hash = compute_content_hash(raw_text)

            # Content-hash dedup: same article republished at a different URL
            if await is_content_duplicate(session, content_hash):
                run_log.items_skipped_content += 1
                log.debug("Source %s: content duplicate for %s", source.id, stub.item_url)
                continue

            raw_item = RawItem(
                source_id=source.id,
                item_url=stub.item_url,
                title=stub.title,
                published_at=stub.published_at,
                raw_text=raw_text,
                raw_html=raw_html,
                content_hash=content_hash,
                url_hash=url_hash,
                is_duplicate=False,
                fetched_at=datetime.utcnow(),
            )

            try:
                # add() must happen inside the savepoint: begin_nested() flushes
                # pending state before emitting SAVEPOINT, so an item added first
                # would raise outside it and poison the outer transaction.
                async with session.begin_nested():
                    session.add(raw_item)
                    await session.flush()
                run_log.items_new += 1
            except IntegrityError:
                # The unique constraint on url_hash is the final safeguard against a
                # concurrent writer. The savepoint rolls back just this insert, so
                # the run continues and everything already stored stays committed.
                run_log.items_skipped_url += 1
                log.info(
                    "Source %s: url_hash already present for %s (concurrent insert), skipping",
                    source.id,
                    stub.item_url,
                )

        run_log.status = "success"
        log.info(
            "Source %s '%s': stored %d, skipped %d url / %d content / %d unusable, of %d fetched",
            source.id,
            source.name,
            run_log.items_new,
            run_log.items_skipped_url,
            run_log.items_skipped_content,
            run_log.items_skipped_invalid,
            run_log.items_fetched,
        )

    except asyncio.CancelledError:
        cancelled = True
        run_log.status = "failed"
        run_log.error_message = (
            "Collection cancelled before completion — counters are partial and the "
            "source was not fully collected. Re-run to finish."
        )
        log.warning(
            "Source %s '%s': collection cancelled after storing %d item(s)",
            source.id,
            source.name,
            run_log.items_new,
        )
        raise

    except Exception as exc:
        run_log.status = "failed"
        run_log.error_message = str(exc)
        log.error(
            "Source %s '%s' collection failed: %s", source.id, source.name, exc, exc_info=True
        )

    finally:
        # Retained for existing readers; the split counters above are authoritative.
        run_log.items_duplicate = run_log.items_skipped_url + run_log.items_skipped_content
        run_log.run_finished_at = datetime.utcnow()
        try:
            await session.commit()
        except Exception as commit_exc:
            log.error(
                "Source %s: failed to commit run log: %s", source.id, commit_exc, exc_info=True
            )
            await session.rollback()
            # Nothing was persisted, so the caller must not treat the in-memory
            # counters as real work — a rolled-back items_new would otherwise make
            # the scheduler kick off AI processing for data that does not exist.
            # A pending cancellation still wins: it must not be masked.
            if not cancelled:
                raise

    return run_log


async def reserve_source_collection(source_id: int) -> bool:
    """Atomically reserve a source for collection.

    For callers that must know the outcome before the work starts — the manual
    trigger answers 202 or 409 on this. A successful reservation must be handed to
    :func:`collect_reserved_source`, which releases it; if the caller cannot get
    that far it must call :func:`release_source_collection` itself.
    """
    return await claim_source_run(source_id)


async def release_source_collection(source_id: int) -> None:
    """Release a reservation that never reached :func:`collect_reserved_source`."""
    await release_source_run(source_id)


async def collect_reserved_source(source_id: int) -> RunLog | None:
    """Collect a source whose reservation the caller already holds.

    Always releases the reservation, including on failure and cancellation.
    Returns ``None`` without creating a run log if the source no longer exists.
    """
    try:
        async with AsyncSessionLocal() as session:
            source = await session.get(Source, source_id)
            if source is None:
                log.warning("Source %s: no longer exists, nothing collected", source_id)
                return None
            return await run_source(source, session)
    finally:
        await release_source_run(source_id)


async def collect_source(source_id: int) -> RunLog | None:
    """Reserve and collect one source — the scheduler/internal entry point.

    Returns ``None`` without creating a run log when a collection for this source
    is already in flight, or when the source no longer exists.
    """
    if not await reserve_source_collection(source_id):
        log.info("Source %s: collection already in progress, skipping this run", source_id)
        return None

    return await collect_reserved_source(source_id)


async def run_all_sources() -> list[RunLog]:
    """Collect every active source in turn, one claim and one session each."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Source.id).where(Source.is_active.is_(True)).order_by(Source.id)
        )
        source_ids = list(result.scalars().all())

    run_logs: list[RunLog] = []
    for source_id in source_ids:
        try:
            run_log = await collect_source(source_id)
        except Exception as exc:
            log.error("Source %s: unexpected collection error: %s", source_id, exc, exc_info=True)
            continue
        if run_log is not None:
            run_logs.append(run_log)

    return run_logs
