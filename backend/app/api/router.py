from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.charts import router as chart_router
from app.api.v1.internal import router as internal_router
from app.api.v1.sensors import router as sensor_router
from app.api.v1.settings import router as settings_router
from app.api.v1.ws import router as ws_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(sensor_router, prefix="/sensors", tags=["sensors"])
api_v1_router.include_router(chart_router, prefix="/charts", tags=["charts"])
api_v1_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_v1_router.include_router(ws_router, prefix="/ws", tags=["websocket"])
api_v1_router.include_router(internal_router, prefix="/internal", tags=["internal"])

# Routers will be included here as they are created in subsequent phases:
# api_v1_router.include_router(event_router, prefix="/events", tags=["events"])
