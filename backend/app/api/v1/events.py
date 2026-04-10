import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.event import EventLog
from app.models.user import User as UserModel
from app.schemas.event import EventLogResponse, PaginatedResponse

router = APIRouter()


def _to_response(event: EventLog, username: str | None) -> EventLogResponse:
    r = EventLogResponse.model_validate(event)
    r.username = username
    return r


@router.get("", response_model=PaginatedResponse)
async def get_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    level: str | None = Query(None),
):
    count_base = select(func.count(EventLog.id))
    if level:
        count_base = count_base.where(EventLog.level == level)
    total = (await db.execute(count_base)).scalar() or 0
    total_pages = max(1, (total + per_page - 1) // per_page)

    stmt = (
        select(EventLog, UserModel.username)
        .outerjoin(UserModel, EventLog.user_id == UserModel.id)
        .order_by(desc(EventLog.timestamp))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    if level:
        stmt = stmt.where(EventLog.level == level)
    rows = (await db.execute(stmt)).all()

    return PaginatedResponse(
        items=[_to_response(row[0], row[1]) for row in rows],
        total=total,
        page=page,
        page_size=per_page,
        total_pages=total_pages,
    )


@router.get("/export/csv")
async def export_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    level: str | None = Query(None),
):
    stmt = (
        select(EventLog, UserModel.username)
        .outerjoin(UserModel, EventLog.user_id == UserModel.id)
        .order_by(desc(EventLog.timestamp))
    )
    if level:
        stmt = stmt.where(EventLog.level == level)
    rows = (await db.execute(stmt)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "level", "source", "method", "path", "user", "message"])
    for event, username in rows:
        writer.writerow([event.id, event.timestamp, event.level, event.source,
                         event.method, event.path, username or "", event.message])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=events.csv"},
    )
