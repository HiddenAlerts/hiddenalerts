from datetime import datetime

from pydantic import BaseModel


class RawItemRead(BaseModel):
    id: int
    source_id: int | None
    item_url: str
    title: str | None
    published_at: datetime | None
    content_hash: str | None
    url_hash: str | None
    is_duplicate: bool
    fetched_at: datetime

    model_config = {"from_attributes": True}


class RawItemDetail(RawItemRead):
    raw_text: str | None
    raw_html: str | None
