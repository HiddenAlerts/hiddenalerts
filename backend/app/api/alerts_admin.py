"""Admin alert metadata endpoints.

Mounted under ``/api/v1`` in ``app.main``, giving paths such as
``/api/v1/admin/alerts/categories``. All routes require an admin user.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.alert_category import AlertCategoriesResponse
from app.services import alert_category_service

router = APIRouter(prefix="/admin/alerts", tags=["alerts-admin"])


@router.get("/categories", response_model=AlertCategoriesResponse)
async def admin_alert_categories(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> AlertCategoriesResponse:
    """Canonical alert categories with counts across all processed alerts.

    Always returns all six categories in canonical order, including any with a
    count of 0. Unlike the subscriber endpoint, counts are not limited to
    published alerts.
    """
    return await alert_category_service.get_category_metadata(db, published_only=False)
