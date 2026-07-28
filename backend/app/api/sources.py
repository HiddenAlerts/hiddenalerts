"""Source administration endpoints — admin only.

Read routes expose full source configuration and operational telemetry; the
write routes change collection behaviour and can start outbound fetches. Every
route therefore requires an admin user.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.models.run_log import RunLog
from app.models.source import Source
from app.models.user import User
from app.schemas.run_log import RunLogRead
from app.schemas.source import SourceRead, SourceUpdate
from app.pipeline.collector import (
    collect_reserved_source,
    release_source_collection,
    reserve_source_collection,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceRead])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> list[Source]:
    result = await db.execute(select(Source).order_by(Source.id))
    return result.scalars().all()


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> Source:
    source = await db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.patch("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: int,
    payload: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> Source:
    source = await db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    await db.commit()
    await db.refresh(source)
    return source


@router.get("/{source_id}/runs", response_model=list[RunLogRead])
async def get_source_runs(
    source_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> list[RunLog]:
    source = await db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    result = await db.execute(
        select(RunLog)
        .where(RunLog.source_id == source_id)
        .order_by(RunLog.run_started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/{source_id}/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_source(
    source_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> dict:
    """Manually trigger a collection run for a single source (runs in background).

    Returns 409 when any collection for this source is already in flight —
    scheduled or manual — so a repeated click cannot stack outbound fetches
    against the same upstream.
    """
    source = await db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # Reserve before answering, so two near-simultaneous triggers cannot both be
    # accepted. The background run releases the reservation in every outcome.
    if not await reserve_source_collection(source_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A collection run for source '{source.name}' is already in "
                "progress. Wait for it to finish before triggering again."
            ),
        )

    async def _run() -> None:
        try:
            await collect_reserved_source(source_id)
        except Exception:
            log.exception("Manual collection failed for source %s", source_id)

    try:
        background_tasks.add_task(_run)
    except Exception:
        # Nothing will run, so the reservation would otherwise leak.
        await release_source_collection(source_id)
        raise
    return {"message": f"Collection triggered for source '{source.name}'", "source_id": source_id}
