from datetime import datetime

from pydantic import BaseModel


class SourceRead(BaseModel):
    id: int
    name: str
    base_url: str
    source_type: str
    rss_url: str | None
    category: str | None
    primary_focus: str | None
    keywords: list[str] | None
    is_active: bool
    polling_frequency_minutes: int
    adapter_class: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceUpdate(BaseModel):
    is_active: bool | None = None
    polling_frequency_minutes: int | None = None
    notes: str | None = None
