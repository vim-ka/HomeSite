from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.sensor_repository import SensorRepository
from app.schemas.sensor import DashboardResponse, SensorResponse
from app.services.sensor_service import SensorService

router = APIRouter()


def get_sensor_service(db: AsyncSession = Depends(get_db)) -> SensorService:
    return SensorService(SensorRepository(db))


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    user: User = Depends(get_current_user),
    service: SensorService = Depends(get_sensor_service),
):
    """Full dashboard data: climate, heating circuits, water supply, 24h stats."""
    return await service.get_dashboard_data()


@router.get("", response_model=list[SensorResponse])
async def list_sensors(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all registered sensors with metadata."""
    repo = SensorRepository(db)
    rows = await repo.get_all_sensors()
    return rows
