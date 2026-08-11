from pydantic import BaseModel, Field

from app.domain.alert_categories import AlertCategory


class AlertCategoryRead(BaseModel):
    """One canonical category with the number of alerts in the requested scope."""

    value: AlertCategory = Field(
        description="Exact string to pass to the `category` filter on the alerts endpoints.",
    )
    label: str = Field(description="Display name.")
    count: int = Field(
        ge=0,
        description="Alerts in this category within the endpoint's scope.",
    )


class AlertCategoriesResponse(BaseModel):
    """Full category list. Always contains every canonical category, in order."""

    categories: list[AlertCategoryRead] = Field(
        description=(
            "Every canonical category, always in the same order — safe to build "
            "a filter dropdown from without it reordering between requests."
        ),
    )
    total: int = Field(
        ge=0,
        description=(
            "Total number of **alerts** represented by the counts above "
            "(the sum of `categories[].count`) — **not** the number of "
            "category definitions, which is fixed."
        ),
    )
