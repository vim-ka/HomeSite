from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.config import ConfigKV
from app.repositories.chart_repository import ChartRepository
from app.schemas.chart import ChartDataResponse
from app.services.chart_service import ChartService

router = APIRouter()


def get_chart_service(db: AsyncSession = Depends(get_db)) -> ChartService:
    return ChartService(ChartRepository(db))


@router.get("/{chart_type}", response_model=ChartDataResponse)
async def get_chart_data(
    chart_type: str,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    service: ChartService = Depends(get_chart_service),
    db: AsyncSession = Depends(get_db),
):
    """Get chart data. Static for PZA curves, dynamic for sensor history.

    chart_type: ChartTemperature | ChartPressure | ChartHumidity | ChartRadiators | ChartHeatFloor
    """
    default_days = 100
    result = await db.execute(
        select(ConfigKV.value).where(ConfigKV.key == "chart_history_days")
    )
    row = result.scalar_one_or_none()
    if row:
        try:
            default_days = int(row)
        except ValueError:
            pass

    return await service.get_chart_data(chart_type, start, end, default_days=default_days)
