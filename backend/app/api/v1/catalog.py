from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.catalog_repository import CatalogRepository
from app.schemas.catalog import (
    AcceptPendingSensorRequest,
    HeatingCircuitCreateRequest,
    HeatingCircuitResponse,
    HeatingCircuitUpdateRequest,
    MountPointCreateRequest,
    MountPointResponse,
    MountPointUpdateRequest,
    PendingSensorResponse,
    PlaceCreateRequest,
    PlaceResponse,
    PlaceUpdateRequest,
    SensorCreateRequest,
    SensorDataTypeResponse,
    SensorDetailResponse,
    SensorTypeCreateRequest,
    SensorTypeResponse,
    SensorTypeUpdateRequest,
    SensorUpdateRequest,
    SystemTypeResponse,
)
from app.services.catalog_service import CatalogService

router = APIRouter()

admin_only = require_role([UserRole.ADMIN])


def get_catalog_service(db: AsyncSession = Depends(get_db)) -> CatalogService:
    return CatalogService(CatalogRepository(db))


# ---- Reference data (dropdowns) ----


@router.get("/system-types", response_model=list[SystemTypeResponse])
async def list_system_types(
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.get_system_types()


@router.get("/sensor-types", response_model=list[SensorTypeResponse])
async def list_sensor_types(
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.get_sensor_types()


@router.post("/sensor-types", response_model=SensorTypeResponse, status_code=201)
async def create_sensor_type(
    payload: SensorTypeCreateRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.create_sensor_type(payload.name)


@router.put("/sensor-types/{st_id}", response_model=SensorTypeResponse)
async def update_sensor_type(
    st_id: int,
    payload: SensorTypeUpdateRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.update_sensor_type(st_id, payload.name)


@router.delete("/sensor-types/{st_id}", status_code=204)
async def delete_sensor_type(
    st_id: int,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.delete_sensor_type(st_id)


@router.get("/data-types", response_model=list[SensorDataTypeResponse])
async def list_data_types(
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.get_sensor_data_types()


@router.get("/mount-points", response_model=list[MountPointResponse])
async def list_mount_points(
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.get_mount_points()


# ---- Mount Points CRUD ----


@router.post("/mount-points", response_model=MountPointResponse, status_code=201)
async def create_mount_point(
    payload: MountPointCreateRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.create_mount_point(**payload.model_dump())
    mps = await service.get_mount_points()
    return mps[-1]


@router.put("/mount-points/{mp_id}", response_model=MountPointResponse)
async def update_mount_point(
    mp_id: int,
    payload: MountPointUpdateRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.update_mount_point(mp_id, **payload.model_dump())
    mps = await service.get_mount_points()
    return next(m for m in mps if m["id"] == mp_id)


@router.delete("/mount-points/{mp_id}", status_code=204)
async def delete_mount_point(
    mp_id: int,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.delete_mount_point(mp_id)


# ---- Places CRUD ----


@router.get("/places", response_model=list[PlaceResponse])
async def list_places(
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.get_all_places()


@router.post("/places", response_model=PlaceResponse, status_code=201)
async def create_place(
    payload: PlaceCreateRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.create_place(payload.name)


@router.put("/places/{place_id}", response_model=PlaceResponse)
async def update_place(
    place_id: int,
    payload: PlaceUpdateRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.update_place(place_id, payload.name)


@router.delete("/places/{place_id}", status_code=204)
async def delete_place(
    place_id: int,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.delete_place(place_id)


# ---- Sensors CRUD ----


@router.get("/sensors", response_model=list[SensorDetailResponse])
async def list_sensors(
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.get_all_sensors_detail()


@router.post("/sensors", response_model=SensorDetailResponse, status_code=201)
async def create_sensor(
    payload: SensorCreateRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    sensor = await service.create_sensor(
        payload.name, payload.sensor_type_id, payload.mount_point_id, payload.datatype_ids
    )
    # Re-fetch with joins to return full detail
    sensors = await service.get_all_sensors_detail()
    return next(s for s in sensors if s["id"] == sensor.id)


@router.put("/sensors/{sensor_id}", response_model=SensorDetailResponse)
async def update_sensor(
    sensor_id: int,
    payload: SensorUpdateRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.update_sensor(
        sensor_id, payload.name, payload.sensor_type_id, payload.mount_point_id, payload.datatype_ids
    )
    sensors = await service.get_all_sensors_detail()
    return next(s for s in sensors if s["id"] == sensor_id)


@router.delete("/sensors/{sensor_id}", status_code=204)
async def delete_sensor(
    sensor_id: int,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.delete_sensor(sensor_id)


# ---- Pending Sensors (auto-discovery) ----


@router.get("/pending-sensors", response_model=list[PendingSensorResponse])
async def list_pending_sensors(
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.get_pending_sensors()


@router.post("/pending-sensors/{ps_id}/accept", response_model=SensorDetailResponse, status_code=201)
async def accept_pending_sensor(
    ps_id: int,
    payload: AcceptPendingSensorRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    sensor = await service.accept_pending_sensor(
        ps_id, payload.sensor_type_id, payload.mount_point_id, payload.datatype_ids
    )
    sensors = await service.get_all_sensors_detail()
    return next(s for s in sensors if s["id"] == sensor.id)


@router.delete("/pending-sensors/{ps_id}", status_code=204)
async def dismiss_pending_sensor(
    ps_id: int,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.dismiss_pending_sensor(ps_id)


# ---- Heating Circuits CRUD ----


@router.get("/heating-circuits", response_model=list[HeatingCircuitResponse])
async def list_heating_circuits(
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.get_heating_circuits()


@router.post("/heating-circuits", response_model=HeatingCircuitResponse, status_code=201)
async def create_heating_circuit(
    payload: HeatingCircuitCreateRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.create_heating_circuit(**payload.model_dump())
    circuits = await service.get_heating_circuits()
    return circuits[-1]


@router.put("/heating-circuits/{circuit_id}", response_model=HeatingCircuitResponse)
async def update_heating_circuit(
    circuit_id: int,
    payload: HeatingCircuitUpdateRequest,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.update_heating_circuit(circuit_id, **payload.model_dump())
    circuits = await service.get_heating_circuits()
    return next(c for c in circuits if c["id"] == circuit_id)


@router.delete("/heating-circuits/{circuit_id}", status_code=204)
async def delete_heating_circuit(
    circuit_id: int,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    await service.delete_heating_circuit(circuit_id)
