"""Category metadata shared by the subscriber and admin category endpoints.

The category list always comes from the canonical vocabulary, never from the
stored values, so the response is stable regardless of what happens to be
classified or published. Only the counts are read from the database.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.alert_categories import ALERT_CATEGORIES
from app.models.processed_alert import ProcessedAlert
from app.schemas.alert_category import AlertCategoriesResponse, AlertCategoryRead


def published_alert_filter():
    """Visibility predicate for the subscriber-facing alert surfaces.

    Publication is the only gate on the subscriber feed today, so category
    counts use the same rule and stay consistent with what ``?category=`` on
    ``GET /api/v1/subscriber/alerts`` actually returns.
    """
    return ProcessedAlert.is_published.is_(True)


async def get_category_metadata(
    db: AsyncSession, *, published_only: bool
) -> AlertCategoriesResponse:
    """Return every canonical category with its alert count.

    ``published_only`` selects the subscriber scope (published alerts) over the
    admin scope (all processed alerts). Rows whose ``primary_category`` is null,
    blank or outside the canonical vocabulary are never counted or exposed.
    """
    stmt = (
        select(ProcessedAlert.primary_category, func.count().label("count"))
        .where(ProcessedAlert.primary_category.in_(ALERT_CATEGORIES))
        .group_by(ProcessedAlert.primary_category)
    )
    if published_only:
        stmt = stmt.where(published_alert_filter())

    counts = {row.primary_category: row.count for row in (await db.execute(stmt)).all()}

    categories = [
        AlertCategoryRead(value=category, label=category, count=counts.get(category, 0))
        for category in ALERT_CATEGORIES
    ]
    return AlertCategoriesResponse(
        categories=categories,
        total=sum(category.count for category in categories),
    )
