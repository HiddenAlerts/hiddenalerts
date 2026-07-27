from pydantic import BaseModel


class AlertCategoryRead(BaseModel):
    """One canonical category with the number of alerts in the requested scope."""

    value: str
    label: str
    count: int


class AlertCategoriesResponse(BaseModel):
    """Full category list. Always contains every canonical category, in order."""

    categories: list[AlertCategoryRead]
    total: int
