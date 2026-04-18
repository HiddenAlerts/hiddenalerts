import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.run_log import RunLog
from app.models.source import Source
from app.schemas.run_log import RunLogRead
from app.schemas.source import SourceRead, SourceUpdate

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceRead])
async def list_sources(db: AsyncSession = Depends(get_db)) -> list[Source]:
    result = await db.execute(select(Source).order_by(Source.id))
    return result.scalars().all()


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(source_id: int, db: AsyncSession = Depends(get_db)) -> Source:
    source = await db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.patch("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: int,
    payload: SourceUpdate,
    db: AsyncSession = Depends(get_db),
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


@router.post("/{source_id}/trigger", status_code=202)
async def trigger_source(
    source_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger a collection run for a single source (runs in background)."""
    source = await db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    async def _run() -> None:
        from app.scheduler.jobs import trigger_source_by_id
        try:
            await trigger_source_by_id(source_id)
        except Exception as exc:
            log.error(f"Manual trigger for source {source_id} failed: {exc}", exc_info=True)

    background_tasks.add_task(_run)
    return {"message": f"Collection triggered for source '{source.name}'", "source_id": source_id}
