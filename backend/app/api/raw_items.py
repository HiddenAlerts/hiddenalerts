"""Raw-item and internal pipeline-statistics endpoints — admin only.

These expose the full ingested article corpus (including ``raw_text`` and
``raw_html``) and internal collection counts, so every route requires an admin
user.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.user import User
from app.schemas.raw_item import RawItemDetail, RawItemRead

router = APIRouter(tags=["raw-items"])


@router.get("/raw-items", response_model=list[RawItemRead])
async def list_raw_items(
    source_id: int | None = Query(None, description="Filter by source"),
    is_duplicate: bool | None = Query(None, description="Filter by duplicate flag"),
    since: datetime | None = Query(None, description="Items fetched after this datetime"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> list[RawItem]:
    stmt = select(RawItem).order_by(RawItem.fetched_at.desc())
    if source_id is not None:
        stmt = stmt.where(RawItem.source_id == source_id)
    if is_duplicate is not None:
        stmt = stmt.where(RawItem.is_duplicate == is_duplicate)
    if since is not None:
        stmt = stmt.where(RawItem.fetched_at >= since)
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/raw-items/{item_id}", response_model=RawItemDetail)
async def get_raw_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> RawItem:
    item = await db.get(RawItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Raw item not found")
    return item


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> dict:
    total_items = await db.scalar(select(func.count()).select_from(RawItem))
    total_sources = await db.scalar(select(func.count()).select_from(Source))
    active_sources = await db.scalar(
        select(func.count()).select_from(Source).where(Source.is_active.is_(True))
    )
    new_items = await db.scalar(
        select(func.count()).select_from(RawItem).where(RawItem.is_duplicate.is_(False))
    )

    # Per-source item counts
    per_source_result = await db.execute(
        select(Source.name, func.count(RawItem.id).label("item_count"))
        .outerjoin(RawItem, RawItem.source_id == Source.id)
        .group_by(Source.id, Source.name)
        .order_by(Source.name)
    )
    per_source = [
        {"source": row.name, "item_count": row.item_count}
        for row in per_source_result
    ]

    return {
        "total_raw_items": total_items,
        "unique_items": new_items,
        "total_sources": total_sources,
        "active_sources": active_sources,
        "items_per_source": per_source,
    }
