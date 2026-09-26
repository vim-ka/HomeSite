from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.types import UTCDateTime


class EventLogResponse(BaseModel):
    id: int
    timestamp: UTCDateTime
    level: str
    source: str
    method: str | None = None
    path: str | None = None
    remote_addr: str | None = None
    message: str | None = None
    payload: str | None = None
    user_id: int | None = None
    username: str | None = None

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list[EventLogResponse] = []
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 0
