from datetime import datetime

from pydantic import BaseModel, Field


class EventLogResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    source: str
    method: str | None = None
    path: str | None = None
    remote_addr: str | None = None
    message: str | None = None
    payload: str | None = None
    user_id: int | None = None

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list[EventLogResponse] = []
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 0
