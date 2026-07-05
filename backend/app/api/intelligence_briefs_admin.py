"""Admin CMS endpoints for Intelligence Briefs.

Create, list, detail and update for analysts managing briefs. All routes require
an admin user. Publishing, archiving, featuring, featured-image upload and the
subscriber-facing endpoints live elsewhere.

Mounted under ``/api/v1`` in ``app.main``, giving the public paths
``/api/v1/admin/intelligence-briefs`` and ``/api/v1/admin/intelligence-briefs/{brief_id}``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.models.intelligence_brief_constants import (
    BRIEF_RISK_LEVELS,
    BRIEF_STATUSES,
    BRIEF_TYPES,
)
from app.models.user import User
from app.schemas.intelligence_brief import (
    IntelligenceBriefCreate,
    IntelligenceBriefDetail,
    IntelligenceBriefListResponse,
    IntelligenceBriefUpdate,
)
from app.services import intelligence_brief_service as service

router = APIRouter(prefix="/admin/intelligence-briefs", tags=["intelligence-briefs-admin"])


def _validate_enum(value: str | None, allowed: frozenset[str], field: str) -> None:
    """Reject an out-of-vocabulary query-param value with a 422."""
    if value is not None and value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid {field}: {value!r}. Allowed: {sorted(allowed)}",
        )


@router.post(
    "",
    response_model=IntelligenceBriefDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_intelligence_brief(
    payload: IntelligenceBriefCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> IntelligenceBriefDetail:
    """Create a draft brief and return its full admin detail."""
    try:
        brief = await service.create_brief(db, payload, user_id=user.id)
    except service.InvalidSlugError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="slug is empty after normalization",
        ) from exc
    except service.SlugConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"slug already in use: {exc.slug}",
        ) from exc
    except service.BriefCodeAllocationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="could not allocate a unique brief code, please retry",
        ) from exc

    await db.commit()
    return brief


@router.get("", response_model=IntelligenceBriefListResponse)
async def list_intelligence_briefs(
    q: str | None = Query(None, description="Case-insensitive search over title, executive summary, main brief"),
    status_: str | None = Query(None, alias="status", description="Filter by lifecycle status"),
    category: str | None = Query(None),
    risk_level: str | None = Query(None),
    brief_type: str | None = Query(None),
    is_featured: bool | None = Query(None),
    is_premium: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> IntelligenceBriefListResponse:
    """Paginated admin list across all statuses and risk levels."""
    _validate_enum(status_, BRIEF_STATUSES, "status")
    _validate_enum(risk_level, BRIEF_RISK_LEVELS, "risk_level")
    _validate_enum(brief_type, BRIEF_TYPES, "brief_type")

    items, total = await service.list_briefs(
        db,
        q=q,
        status=status_,
        category=category,
        risk_level=risk_level,
        brief_type=brief_type,
        is_featured=is_featured,
        is_premium=is_premium,
        limit=limit,
        offset=offset,
    )
    return IntelligenceBriefListResponse(
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/{brief_id}", response_model=IntelligenceBriefDetail)
async def get_intelligence_brief(
    brief_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> IntelligenceBriefDetail:
    """Return the full admin detail for a single brief."""
    brief = await service.get_brief(db, brief_id)
    if brief is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Intelligence brief not found"
        )
    return brief


@router.put("/{brief_id}", response_model=IntelligenceBriefDetail)
async def update_intelligence_brief(
    brief_id: int,
    payload: IntelligenceBriefUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> IntelligenceBriefDetail:
    """Apply a partial update to a brief and return its refreshed detail."""
    try:
        brief = await service.update_brief(db, brief_id, payload, user_id=user.id)
    except service.BriefNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Intelligence brief not found"
        ) from exc
    except service.InvalidSlugError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="slug is empty after normalization",
        ) from exc
    except service.SlugConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"slug already in use: {exc.slug}",
        ) from exc

    await db.commit()
    return brief
