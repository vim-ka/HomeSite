from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.session import get_db
from app.models.config import Actuator
from app.models.event import EventLog
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
    SensorOffsetResponse,
    SensorOffsetUpdateRequest,
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
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    result = await service.create_sensor_type(payload.name, payload.datatype_ids)
    db.add(EventLog(level="INFO", source="catalog", method="POST", path="/api/v1/catalog/sensor-types",
                    message=f"Создан тип датчика: {payload.name}", user_id=user.id))
    return result


@router.put("/sensor-types/{st_id}", response_model=SensorTypeResponse)
async def update_sensor_type(
    st_id: int,
    payload: SensorTypeUpdateRequest,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    result = await service.update_sensor_type(st_id, payload.name, payload.datatype_ids)
    db.add(EventLog(level="INFO", source="catalog", method="PUT", path=f"/api/v1/catalog/sensor-types/{st_id}",
                    message=f"Обновлён тип датчика id={st_id}: {payload.name}", user_id=user.id))
    return result


@router.delete("/sensor-types/{st_id}", status_code=204)
async def delete_sensor_type(
    st_id: int,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_sensor_type(st_id)
    db.add(EventLog(level="INFO", source="catalog", method="DELETE", path=f"/api/v1/catalog/sensor-types/{st_id}",
                    message=f"Удалён тип датчика id={st_id}", user_id=user.id))


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
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.create_mount_point(**payload.model_dump())
    mps = await service.get_mount_points()
    db.add(EventLog(level="INFO", source="catalog", method="POST", path="/api/v1/catalog/mount-points",
                    message=f"Создана точка монтажа: {payload.name}", user_id=user.id))
    return mps[-1]


@router.put("/mount-points/{mp_id}", response_model=MountPointResponse)
async def update_mount_point(
    mp_id: int,
    payload: MountPointUpdateRequest,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.update_mount_point(mp_id, **payload.model_dump())
    mps = await service.get_mount_points()
    db.add(EventLog(level="INFO", source="catalog", method="PUT", path=f"/api/v1/catalog/mount-points/{mp_id}",
                    message=f"Обновлена точка монтажа id={mp_id}: {payload.name}", user_id=user.id))
    return next(m for m in mps if m["id"] == mp_id)


@router.delete("/mount-points/{mp_id}", status_code=204)
async def delete_mount_point(
    mp_id: int,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_mount_point(mp_id)
    db.add(EventLog(level="INFO", source="catalog", method="DELETE", path=f"/api/v1/catalog/mount-points/{mp_id}",
                    message=f"Удалена точка монтажа id={mp_id}", user_id=user.id))


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
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    result = await service.create_place(payload.name)
    db.add(EventLog(level="INFO", source="catalog", method="POST", path="/api/v1/catalog/places",
                    message=f"Создана комната: {payload.name}", user_id=user.id))
    return result


@router.put("/places/{place_id}", response_model=PlaceResponse)
async def update_place(
    place_id: int,
    payload: PlaceUpdateRequest,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    result = await service.update_place(place_id, payload.name)
    db.add(EventLog(level="INFO", source="catalog", method="PUT", path=f"/api/v1/catalog/places/{place_id}",
                    message=f"Обновлена комната id={place_id}: {payload.name}", user_id=user.id))
    return result


@router.delete("/places/{place_id}", status_code=204)
async def delete_place(
    place_id: int,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_place(place_id)
    db.add(EventLog(level="INFO", source="catalog", method="DELETE", path=f"/api/v1/catalog/places/{place_id}",
                    message=f"Удалена комната id={place_id}", user_id=user.id))


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
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    sensor = await service.create_sensor(
        payload.name,
        payload.sensor_type_id,
        payload.mount_point_id,
        payload.actuator_id,
    )
    sensors = await service.get_all_sensors_detail()
    db.add(EventLog(level="INFO", source="catalog", method="POST", path="/api/v1/catalog/sensors",
                    message=f"Создан датчик: {payload.name}", user_id=user.id))
    return next(s for s in sensors if s["id"] == sensor.id)


@router.put("/sensors/{sensor_id}", response_model=SensorDetailResponse)
async def update_sensor(
    sensor_id: int,
    payload: SensorUpdateRequest,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.update_sensor(
        sensor_id,
        payload.name,
        payload.sensor_type_id,
        payload.mount_point_id,
        payload.actuator_id,
    )
    sensors = await service.get_all_sensors_detail()
    db.add(EventLog(level="INFO", source="catalog", method="PUT", path=f"/api/v1/catalog/sensors/{sensor_id}",
                    message=f"Обновлён датчик id={sensor_id}: {payload.name}", user_id=user.id))
    return next(s for s in sensors if s["id"] == sensor_id)


@router.delete("/sensors/{sensor_id}", status_code=204)
async def delete_sensor(
    sensor_id: int,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_sensor(sensor_id)
    db.add(EventLog(level="INFO", source="catalog", method="DELETE", path=f"/api/v1/catalog/sensors/{sensor_id}",
                    message=f"Удалён датчик id={sensor_id}", user_id=user.id))


# ---- Sensor Offsets ----


@router.get("/sensors/{sensor_id}/offsets", response_model=list[SensorOffsetResponse])
async def list_sensor_offsets(
    sensor_id: int,
    _user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
):
    return await service.get_sensor_offsets(sensor_id)


@router.put("/sensors/{sensor_id}/offsets/{datatype_id}", response_model=SensorOffsetResponse)
async def update_sensor_offset(
    sensor_id: int,
    datatype_id: int,
    payload: SensorOffsetUpdateRequest,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    offset, publish = await service.update_sensor_offset(sensor_id, datatype_id, payload.value)

    # Best-effort push to the device. If the sensor isn't bound to an actuator
    # yet, or the gateway is offline, the DB value remains authoritative —
    # offsets are re-pushable via the settings-resync flow later.
    if publish is not None:
        from app.services.gateway_client import GatewayClient
        await GatewayClient().sensor_offset(
            publish["mqtt_device_name"],
            publish["sensor_name"],
            publish["datatype_code"],
            publish["value"],
        )

    db.add(EventLog(
        level="INFO", source="catalog", method="PUT",
        path=f"/api/v1/catalog/sensors/{sensor_id}/offsets/{datatype_id}",
        message=f"Оффсет датчика id={sensor_id} datatype={offset['datatype_code']}: {payload.value}",
        user_id=user.id,
    ))
    return offset


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
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    sensor = await service.accept_pending_sensor(
        ps_id, payload.sensor_type_id, payload.mount_point_id
    )
    sensors = await service.get_all_sensors_detail()
    db.add(EventLog(level="INFO", source="catalog", method="POST", path=f"/api/v1/catalog/pending-sensors/{ps_id}/accept",
                    message=f"Принят новый датчик id={ps_id} → sensor id={sensor.id}", user_id=user.id))
    return next(s for s in sensors if s["id"] == sensor.id)


# ---- Device Sensor Scanning (OneWire via MQTT) ----


class SensorAssignRequest(BaseModel):
    address: str
    name: str


class SensorRemoveRequest(BaseModel):
    address: str


@router.post("/devices/{mqtt_device_name}/scan-sensors")
async def scan_device_sensors(
    mqtt_device_name: str,
    user: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """Trigger OneWire scan on ESP32 device, wait for result."""
    from app.services.gateway_client import GatewayClient

    result = await GatewayClient().scan_sensors(mqtt_device_name)
    if result is None:
        raise HTTPException(status_code=504, detail="Device did not respond")

    db.add(EventLog(
        level="INFO", source="catalog", method="POST",
        path=f"/api/v1/catalog/devices/{mqtt_device_name}/scan-sensors",
        message=f"Сканирование датчиков на {mqtt_device_name}: найдено {len(result)}",
        user_id=user.id,
    ))
    return {"device": mqtt_device_name, "sensors": result}


@router.post("/devices/{mqtt_device_name}/sensor-assign")
async def assign_device_sensor(
    mqtt_device_name: str,
    payload: SensorAssignRequest,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    """Assign a logical name to a sensor on ESP32 device."""
    from app.services.gateway_client import GatewayClient

    ok = await GatewayClient().sensor_assign(mqtt_device_name, payload.address, payload.name)
    if not ok:
        raise HTTPException(status_code=502, detail="Gateway error")

    # If a Sensor row already exists with this logical name, bind it to the
    # actuator we just provisioned it on. Lets the offset-publish path know
    # which device to target.
    actuator = await service.repo.get_actuator_by_mqtt_name(mqtt_device_name)
    sensor = await service.repo.get_sensor_by_name(payload.name)
    if actuator is not None and sensor is not None and sensor.actuator_id != actuator.id:
        sensor.actuator_id = actuator.id
        await db.flush()

    db.add(EventLog(
        level="INFO", source="catalog", method="POST",
        path=f"/api/v1/catalog/devices/{mqtt_device_name}/sensor-assign",
        message=f"Назначен датчик {payload.address} → {payload.name} на {mqtt_device_name}",
        user_id=user.id,
    ))
    return {"status": "ok"}


@router.post("/devices/{mqtt_device_name}/sensor-remove")
async def remove_device_sensor(
    mqtt_device_name: str,
    payload: SensorRemoveRequest,
    user: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """Remove sensor mapping from ESP32 device."""
    from app.services.gateway_client import GatewayClient

    ok = await GatewayClient().sensor_remove(mqtt_device_name, payload.address)
    if not ok:
        raise HTTPException(status_code=502, detail="Gateway error")

    db.add(EventLog(
        level="INFO", source="catalog", method="POST",
        path=f"/api/v1/catalog/devices/{mqtt_device_name}/sensor-remove",
        message=f"Удалён датчик {payload.address} с {mqtt_device_name}",
        user_id=user.id,
    ))
    return {"status": "ok"}


class DeviceCommandRequest(BaseModel):
    params: dict[str, str]


@router.post("/devices/{mqtt_device_name}/command")
async def send_device_command(
    mqtt_device_name: str,
    payload: DeviceCommandRequest,
    user: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    """Push arbitrary device-local commands (restart, node_name, interval, timezone, raw_debug, ...)
    via gateway → MQTT cmd topic. Bypasses config_kv (these are NVS-resident on the device)."""
    from app.services.gateway_client import GatewayClient

    if not payload.params:
        raise HTTPException(status_code=400, detail="params required")

    ok = await GatewayClient().dispatch_command(mqtt_device_name, payload.params)
    if not ok:
        raise HTTPException(status_code=502, detail="Gateway error")

    summary = ", ".join(f"{k}={v}" for k, v in payload.params.items())
    db.add(EventLog(
        level="INFO", source="catalog", method="POST",
        path=f"/api/v1/catalog/devices/{mqtt_device_name}/command",
        message=f"Команда устройству {mqtt_device_name}: {summary}",
        user_id=user.id,
    ))
    return {"status": "ok"}


@router.delete("/pending-sensors/{ps_id}", status_code=204)
async def dismiss_pending_sensor(
    ps_id: int,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.dismiss_pending_sensor(ps_id)
    db.add(EventLog(level="INFO", source="catalog", method="DELETE", path=f"/api/v1/catalog/pending-sensors/{ps_id}",
                    message=f"Отклонён новый датчик id={ps_id}", user_id=user.id))


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
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.create_heating_circuit(**payload.model_dump())
    circuits = await service.get_heating_circuits()
    db.add(EventLog(level="INFO", source="catalog", method="POST", path="/api/v1/catalog/heating-circuits",
                    message=f"Создан контур отопления: {payload.circuit_name}", user_id=user.id))
    return circuits[-1]


@router.put("/heating-circuits/{circuit_id}", response_model=HeatingCircuitResponse)
async def update_heating_circuit(
    circuit_id: int,
    payload: HeatingCircuitUpdateRequest,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.update_heating_circuit(circuit_id, **payload.model_dump())
    circuits = await service.get_heating_circuits()
    db.add(EventLog(level="INFO", source="catalog", method="PUT", path=f"/api/v1/catalog/heating-circuits/{circuit_id}",
                    message=f"Обновлён контур отопления id={circuit_id}: {payload.circuit_name}", user_id=user.id))
    return next(c for c in circuits if c["id"] == circuit_id)


@router.delete("/heating-circuits/{circuit_id}", status_code=204)
async def delete_heating_circuit(
    circuit_id: int,
    user: User = Depends(admin_only),
    service: CatalogService = Depends(get_catalog_service),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_heating_circuit(circuit_id)
    db.add(EventLog(level="INFO", source="catalog", method="DELETE", path=f"/api/v1/catalog/heating-circuits/{circuit_id}",
                    message=f"Удалён контур отопления id={circuit_id}", user_id=user.id))


# ---- Actuators (physical MQTT devices) ----


class ActuatorRequest(BaseModel):
    name: str
    mqtt_device_name: str
    description: str | None = None


@router.get("/actuators")
async def list_actuators(
    _user: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Actuator).order_by(Actuator.id))
    return [
        {"id": a.id, "name": a.name, "mqtt_device_name": a.mqtt_device_name, "description": a.description}
        for a in result.scalars().all()
    ]


@router.post("/actuators", status_code=201)
async def create_actuator(
    payload: ActuatorRequest,
    user: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    actuator = Actuator(**payload.model_dump())
    db.add(actuator)
    await db.flush()
    await db.refresh(actuator)
    db.add(EventLog(level="INFO", source="catalog", method="POST", path="/api/v1/catalog/actuators",
                    message=f"Создан актуатор: {payload.name} ({payload.mqtt_device_name})", user_id=user.id))
    return {"id": actuator.id, "name": actuator.name, "mqtt_device_name": actuator.mqtt_device_name, "description": actuator.description}


@router.put("/actuators/{actuator_id}")
async def update_actuator(
    actuator_id: int,
    payload: ActuatorRequest,
    user: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    actuator = await db.get(Actuator, actuator_id)
    if not actuator:
        raise HTTPException(status_code=404, detail="Actuator not found")
    actuator.name = payload.name
    actuator.mqtt_device_name = payload.mqtt_device_name
    actuator.description = payload.description
    db.add(EventLog(level="INFO", source="catalog", method="PUT", path=f"/api/v1/catalog/actuators/{actuator_id}",
                    message=f"Обновлён актуатор id={actuator_id}: {payload.name}", user_id=user.id))
    return {"id": actuator.id, "name": actuator.name, "mqtt_device_name": actuator.mqtt_device_name, "description": actuator.description}


@router.delete("/actuators/{actuator_id}", status_code=204)
async def delete_actuator(
    actuator_id: int,
    user: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
):
    actuator = await db.get(Actuator, actuator_id)
    if actuator:
        await db.delete(actuator)
        db.add(EventLog(level="INFO", source="catalog", method="DELETE", path=f"/api/v1/catalog/actuators/{actuator_id}",
                        message=f"Удалён актуатор: {actuator.name}", user_id=user.id))
