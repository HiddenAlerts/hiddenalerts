import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import AsyncSessionLocal
from app.pipeline.collector import run_all_sources

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


def setup_scheduler() -> None:
    """Register all scheduled jobs."""
    # M1: Collect raw articles from all sources every 6 hours
    scheduler.add_job(
        _collect_all_sources_job,
        trigger=IntervalTrigger(hours=settings.scheduler_interval_hours),
        id="collect_all_sources",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    log.info(
        f"Scheduler: collect_all_sources every {settings.scheduler_interval_hours}h"
    )

    # M2: Process unprocessed raw_items through AI pipeline every 30 minutes
    # Also triggered immediately after each collection run (see _collect_all_sources_job)
    if settings.ai_processing_enabled:
        scheduler.add_job(
            _process_new_alerts_job,
            trigger=IntervalTrigger(minutes=30),
            id="process_new_alerts",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=120,
        )
        log.info("Scheduler: process_new_alerts every 30min")


async def _collect_all_sources_job() -> None:
    """Scheduled job: collect all active sources, then trigger AI processing."""
    log.info("Scheduled collection run starting")
    run_logs = await run_all_sources()
    new_items_total = sum(rl.items_new for rl in run_logs if rl.items_new)
    log.info(
        f"Scheduled collection run complete: {len(run_logs)} sources processed, "
        f"{new_items_total} new items"
    )

    # Immediately process new items after collection instead of waiting up to 30min
    if settings.ai_processing_enabled and new_items_total > 0:
        log.info("Triggering immediate AI processing after collection run")
        await _process_new_alerts_job()


async def _process_new_alerts_job() -> None:
    """Scheduled job: process unprocessed raw_items through the M2 AI pipeline."""
    from app.pipeline.alert_pipeline import is_processing, process_unprocessed_items

    if is_processing():
        log.info("Alert pipeline already running, skipping scheduled trigger")
        return

    log.info("Alert pipeline: scheduled processing run starting")
    async with AsyncSessionLocal() as session:
        stats = await process_unprocessed_items(session)
    log.info(
        f"Alert pipeline complete: processed={stats.items_processed}, "
        f"no_keywords={stats.items_skipped_no_keywords}, "
        f"failed={stats.items_failed}"
    )


async def trigger_source_by_id(source_id: int) -> None:
    """Manually trigger a collection for a single source (used by API endpoint)."""
    from app.models.source import Source
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            raise ValueError(f"Source {source_id} not found")
        from app.pipeline.collector import run_source
        await run_source(source, session)
