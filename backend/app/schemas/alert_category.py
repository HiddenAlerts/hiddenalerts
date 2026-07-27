from pydantic import BaseModel, Field

from app.domain.alert_categories import AlertCategory


class AlertCategoryRead(BaseModel):
    """One canonical category with the number of alerts in the requested scope."""

    value: AlertCategory
    label: str
    count: int = Field(ge=0)


class AlertCategoriesResponse(BaseModel):
    """Full category list. Always contains every canonical category, in order."""

    categories: list[AlertCategoryRead]
    total: int = Field(ge=0)
