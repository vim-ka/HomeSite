from fastapi import APIRouter

api_v1_router = APIRouter(prefix="/api/v1")

# Routers will be included here as they are created in subsequent phases:
# api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
# api_v1_router.include_router(sensor_router, prefix="/sensors", tags=["sensors"])
# api_v1_router.include_router(chart_router, prefix="/charts", tags=["charts"])
# api_v1_router.include_router(settings_router, prefix="/settings", tags=["settings"])
# api_v1_router.include_router(event_router, prefix="/events", tags=["events"])
# api_v1_router.include_router(ws_router, tags=["websocket"])
