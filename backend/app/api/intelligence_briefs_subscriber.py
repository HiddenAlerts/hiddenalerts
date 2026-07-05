"""Subscriber-facing Intelligence Brief endpoints.

Read-only access to published critical/high briefs for paid subscribers: the
Brief Library, Brief Detail by slug, and the single Featured Brief. Every route
requires an active subscription; hidden briefs (draft, archived, medium/low)
return 404 so their existence is never disclosed.

Mounted under ``/api/v1`` in ``app.main`` at
``/api/v1/subscriber/intelligence-briefs``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.subscriber_access import (
    ActiveSubscriberContext,
    require_active_subscription,
)
from app.database import get_db
from app.models.intelligence_brief_constants import SUBSCRIBER_VISIBLE_RISK_LEVELS
from app.schemas.intelligence_brief import (
    SubscriberBriefDetail,
    SubscriberBriefListResponse,
)
from app.services import intelligence_brief_service as service

router = APIRouter(
    prefix="/subscriber/intelligence-briefs", tags=["subscriber-intelligence-briefs"]
)


@router.get("", response_model=SubscriberBriefListResponse)
async def list_intelligence_briefs(
    q: str | None = Query(None, description="Case-insensitive search over title, executive summary, main brief"),
    category: str | None = Query(None),
    risk_level: str | None = Query(None, description="Filter within visible briefs: critical or high"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> SubscriberBriefListResponse:
    """Paginated library of published critical/high briefs, newest first."""
    if risk_level is not None and risk_level not in SUBSCRIBER_VISIBLE_RISK_LEVELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid risk_level: {risk_level!r}. Allowed: {sorted(SUBSCRIBER_VISIBLE_RISK_LEVELS)}",
        )

    items, total = await service.list_subscriber_briefs(
        db, q=q, category=category, risk_level=risk_level, limit=limit, offset=offset
    )
    return SubscriberBriefListResponse(
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/featured", response_model=SubscriberBriefDetail)
async def featured_intelligence_brief(
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> SubscriberBriefDetail:
    """Return the single subscriber-visible featured brief, or 404 if none."""
    brief = await service.get_featured_subscriber_brief(db)
    if brief is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Featured intelligence brief not found",
        )
    return brief


@router.get("/{slug}", response_model=SubscriberBriefDetail)
async def get_intelligence_brief(
    slug: str,
    _: ActiveSubscriberContext = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> SubscriberBriefDetail:
    """Return a published critical/high brief by slug, or 404 if not visible."""
    brief = await service.get_subscriber_brief_by_slug(db, slug)
    if brief is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intelligence brief not found",
        )
    return brief
