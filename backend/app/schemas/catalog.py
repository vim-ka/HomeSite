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

    model_config = {"from_attributes": True}


class MountPointResponse(BaseModel):
    id: int
    name: str
    system_id: int
    place_id: int
    system_name: str
    place_name: str

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


class MountPointUpdateRequest(BaseModel):
    name: str
    system_id: int
    place_id: int


# ---- Sensor CRUD ----


class SensorDataTypeResponse(BaseModel):
    id: int
    name: str
    code: str

    model_config = {"from_attributes": True}


class SensorDetailResponse(BaseModel):
    id: int
    name: str
    sensor_type_id: int
    sensor_type_name: str
    mount_point_id: int
    mount_point_name: str
    place_name: str
    system_name: str
    datatype_ids: list[int] = []

    model_config = {"from_attributes": True}


class SensorCreateRequest(BaseModel):
    name: str
    sensor_type_id: int
    mount_point_id: int
    datatype_ids: list[int] = []


class SensorUpdateRequest(BaseModel):
    name: str
    sensor_type_id: int
    mount_point_id: int
    datatype_ids: list[int] = []


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
    datatype_ids: list[int] = []
