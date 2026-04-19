from datetime import datetime

from pydantic import BaseModel


# ---- Reference data (dropdowns) ----


class SystemTypeResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class SensorTypeResponse(BaseModel):
    id: int
    name: str
    datatype_ids: list[int] = []

    model_config = {"from_attributes": True}


class SensorTypeCreateRequest(BaseModel):
    name: str
    datatype_ids: list[int] = []


class SensorTypeUpdateRequest(BaseModel):
    name: str
    datatype_ids: list[int] = []


class MountPointResponse(BaseModel):
    id: int
    name: str
    system_id: int
    place_id: int
    system_name: str
    place_name: str
    temperature_sensor_id: int | None = None
    pressure_sensor_id: int | None = None
    humidity_sensor_id: int | None = None
    temperature_sensor_name: str | None = None
    pressure_sensor_name: str | None = None
    humidity_sensor_name: str | None = None

    model_config = {"from_attributes": True}


# ---- Place CRUD ----


class PlaceResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class PlaceCreateRequest(BaseModel):
    name: str


class PlaceUpdateRequest(BaseModel):
    name: str


# ---- MountPoint CRUD ----


class MountPointCreateRequest(BaseModel):
    name: str
    system_id: int
    place_id: int
    temperature_sensor_id: int | None = None
    pressure_sensor_id: int | None = None
    humidity_sensor_id: int | None = None


class MountPointUpdateRequest(BaseModel):
    name: str
    system_id: int
    place_id: int
    temperature_sensor_id: int | None = None
    pressure_sensor_id: int | None = None
    humidity_sensor_id: int | None = None


# ---- Sensor CRUD ----


class SensorDataTypeResponse(BaseModel):
    id: int
    name: str
    code: str

    model_config = {"from_attributes": True}


class SensorOffsetBadge(BaseModel):
    datatype_code: str
    value: float


class SensorDetailResponse(BaseModel):
    id: int
    name: str
    sensor_type_id: int
    sensor_type_name: str
    mount_point_id: int
    mount_point_name: str
    place_name: str
    system_name: str
    actuator_id: int | None = None
    actuator_name: str | None = None
    actuator_mqtt_device_name: str | None = None
    datatype_ids: list[int] = []
    offsets: list[SensorOffsetBadge] = []
    last_reading: datetime | None = None

    model_config = {"from_attributes": True}


class SensorCreateRequest(BaseModel):
    name: str
    sensor_type_id: int
    mount_point_id: int
    actuator_id: int | None = None


class SensorUpdateRequest(BaseModel):
    name: str
    sensor_type_id: int
    mount_point_id: int
    actuator_id: int | None = None


# ---- Sensor Offsets (per-datatype calibration correction) ----


class SensorOffsetResponse(BaseModel):
    sensor_id: int
    datatype_id: int
    datatype_code: str
    datatype_name: str
    value: float

    model_config = {"from_attributes": True}


class SensorOffsetUpdateRequest(BaseModel):
    value: float


# ---- Pending Sensors (auto-discovery) ----


class PendingSensorResponse(BaseModel):
    id: int
    device_name: str
    last_payload: str
    last_value: float | None
    message_count: int
    first_seen: datetime
    last_seen: datetime

    model_config = {"from_attributes": True}


class AcceptPendingSensorRequest(BaseModel):
    sensor_type_id: int
    mount_point_id: int


# ---- Heating Circuit CRUD ----


class HeatingCircuitResponse(BaseModel):
    id: int
    circuit_name: str
    supply_mount_point_id: int | None
    return_mount_point_id: int | None
    supply_mount_point_name: str | None = None
    return_mount_point_name: str | None = None
    config_temp_key: str | None
    config_pump_key: str | None
    config_prefix: str | None = None
    mqtt_device_name: str | None = None
    delta_threshold: float
    show_on_dashboard: bool = True
    display_order: int

    model_config = {"from_attributes": True}


class HeatingCircuitCreateRequest(BaseModel):
    circuit_name: str
    supply_mount_point_id: int | None = None
    return_mount_point_id: int | None = None
    config_temp_key: str | None = None
    config_pump_key: str | None = None
    config_prefix: str | None = None
    mqtt_device_name: str | None = None
    delta_threshold: float = 5.0
    show_on_dashboard: bool = True
    display_order: int = 0


class HeatingCircuitUpdateRequest(BaseModel):
    circuit_name: str
    supply_mount_point_id: int | None = None
    return_mount_point_id: int | None = None
    config_temp_key: str | None = None
    config_pump_key: str | None = None
    config_prefix: str | None = None
    mqtt_device_name: str | None = None
    delta_threshold: float = 5.0
    show_on_dashboard: bool = True
    display_order: int = 0
