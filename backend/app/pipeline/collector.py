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
from app.models.source_url_decision import EXTERNAL_DESTINATION_EXCLUDED
from app.pipeline.deduplicator import get_known_url_hashes, is_content_duplicate
from app.pipeline.normalizer import compute_content_hash, compute_url_hash
from app.services.collection_guard import claim_source_run, release_source_run
from app.services.source_url_decisions import (
    get_suppressing_decisions,
    record_external_exclusion,
    touch_seen_decisions,
)
from app.sources.base import RawItemStub, _safe_url, summary_fallback_allowed
from app.sources.http_errors import DestinationExcluded, SourceFetchError
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
    stub::

        items_fetched == items_new
                       + items_skipped_url
                       + items_skipped_content
                       + items_skipped_invalid
                       + items_skipped_external

    ``items_skipped_external`` counts items whose content belongs to another
    source — both a fresh ``DestinationExcluded`` and a URL a previous run already
    decided. Those are deliberate and are never also counted as invalid. A run
    that fails part-way keeps whatever counts it reached, so the identity does not
    hold for ``status='failed'`` rows.

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
        items_skipped_external=0,
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
        unstored = [(h, stub) for h, stub in batch.items() if h not in known_hashes]
        run_log.items_skipped_url += len(batch) - len(unstored)

        # A URL this source has already ruled out stays ruled out. Checked after
        # the RawItem filter and before any article request, so a terminal
        # decision costs nothing but the one batch query that found it.
        decisions = await get_suppressing_decisions(
            session, source.id, {h for h, _ in unstored}
        )
        new_stubs = [(h, stub) for h, stub in unstored if h not in decisions]
        seen_again = [decisions[h] for h, _ in unstored if h in decisions]
        if seen_again:
            run_log.items_skipped_external += len(seen_again)
            await touch_seen_decisions(session, seen_again)
            log.info(
                "Source %s '%s': %d listing item(s) already decided as external, "
                "not requested",
                source.id, source.name, len(seen_again),
            )
            for decision in seen_again:
                log.debug(
                    "Source %s: %s previously excluded → %s",
                    source.id, decision.item_url, decision.destination_host or "?",
                )

        log.info(
            "Source %s '%s': %d fetched → %d skipped by URL → %d already external "
            "→ %d to retrieve",
            source.id,
            source.name,
            run_log.items_fetched,
            run_log.items_skipped_url,
            len(seen_again),
            len(new_stubs),
        )

        # ── Stage 2: Full article fetch — only for new stubs ─────────────────────
        for url_hash, stub in new_stubs:
            # Article text first, unless the adapter says this item's detail page
            # is not worth requesting; then its own summary, but only where the
            # adapter accepts that summary as a substitute for *this* item. Both
            # choices are the adapter's — the collector holds no per-source
            # knowledge, and never inspects a source name, id or URL.
            if adapter.should_fetch_article(stub):
                try:
                    raw_text, raw_html = await adapter.fetch_full_article(stub.item_url)
                    content_origin = "article"
                except DestinationExcluded as exc:
                    # The item's content lives outside the domains this source
                    # owns, so another source is canonical for it. That is a
                    # deliberate skip, not a failure: no summary substitute, no
                    # stored item, no content hash, and the run continues.
                    #
                    # The verdict is recorded so later runs skip the URL before
                    # requesting it. A persistence failure is *not* swallowed —
                    # it fails the run, because a successful run must never claim
                    # an exclusion was remembered when it was not.
                    await record_external_exclusion(
                        session,
                        source_id=source.id,
                        url_hash=url_hash,
                        item_url=_safe_url(stub.item_url),
                        destination_host=exc.destination,
                        reason_code=type(exc).__name__,
                        published_at=stub.published_at,
                    )
                    run_log.items_skipped_external += 1
                    log.info(
                        "Source %s '%s': skipping %s (hash %s) — destination %s is "
                        "outside this source's domains, decision %s recorded",
                        source.id, source.name, _safe_url(stub.item_url),
                        url_hash[:12], exc.destination or "(unknown)",
                        EXTERNAL_DESTINATION_EXCLUDED,
                    )
                    continue
                except SourceFetchError as exc:
                    raw_text, raw_html = "", ""
                    content_origin = "none"
                    if summary_fallback_allowed(exc):
                        fallback = adapter.summary_fallback(stub, exc)
                        if fallback:
                            raw_text = fallback
                            content_origin = "summary"
                    log.info(
                        "Source %s '%s': article unavailable for %s (%s) — using %s",
                        source.id, source.name, _safe_url(stub.item_url),
                        type(exc).__name__,
                        "feed summary" if content_origin == "summary" else "no content",
                    )
            else:
                # No request is made, so there is no error to report and none is
                # invented; the summary is judged on its own merits.
                raw_html = ""
                raw_text = adapter.summary_fallback(stub, None) or ""
                content_origin = "summary" if raw_text else "none"
                log.info(
                    "Source %s '%s': article not requested for %s — using %s",
                    source.id, source.name, _safe_url(stub.item_url),
                    "feed summary" if content_origin == "summary" else "no content",
                )

            # Nothing usable to persist. Left unstored on purpose so a later run can
            # retry the URL once the upstream fetch recovers.
            if not (raw_text or "").strip():
                run_log.items_skipped_invalid += 1
                log.debug(
                    "Source %s: no usable content for %s", source.id, _safe_url(stub.item_url)
                )
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
