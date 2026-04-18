from datetime import datetime

from pydantic import BaseModel


class RunLogRead(BaseModel):
    id: int
    source_id: int | None
    run_started_at: datetime
    run_finished_at: datetime | None
    status: str | None
    items_fetched: int
    items_new: int
    items_duplicate: int
    error_message: str | None

    model_config = {"from_attributes": True}
