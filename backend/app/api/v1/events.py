import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.event import EventLog
from app.schemas.event import EventLogResponse, PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def get_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    level: str | None = Query(None),
):
    base = select(EventLog)
    count_base = select(func.count(EventLog.id))

    if level:
        base = base.where(EventLog.level == level)
        count_base = count_base.where(EventLog.level == level)

    total = (await db.execute(count_base)).scalar() or 0
    total_pages = max(1, (total + per_page - 1) // per_page)

    stmt = (
        base
        .order_by(desc(EventLog.timestamp))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return PaginatedResponse(
        items=[EventLogResponse.model_validate(r) for r in rows],
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
    base = select(EventLog).order_by(desc(EventLog.timestamp))
    if level:
        base = base.where(EventLog.level == level)

    rows = (await db.execute(base)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "level", "source", "method", "path", "message"])
    for r in rows:
        writer.writerow([r.id, r.timestamp, r.level, r.source, r.method, r.path, r.message])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=events.csv"},
    )
