from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SettingUpdateRequest(BaseModel):
    """Typed replacement for v1's SettingUpdateModel with extra='allow'."""

    settings: dict[str, int | float | str | bool | None]


class SettingResponse(BaseModel):
    key: str
    value: str

    model_config = {"from_attributes": True}


class MqttSettingsResponse(BaseModel):
    host: str = ""
    port: str = ""
    user: str = ""
    password: str = ""


class MqttSettingsRequest(BaseModel):
    host: str
    port: str
    user: str
    password: str


class ToggleRequest(BaseModel):
    id: str
    toggle: bool


class ToggleResponse(BaseModel):
    id: str
    status: str


# --- Database & Backup schemas ---


class DatabaseInfoResponse(BaseModel):
    type: Literal["sqlite", "postgresql"]
    url: str  # masked


class DatabaseUpdateRequest(BaseModel):
    type: Literal["sqlite", "postgresql"]
    host: str = ""
    port: int = 5432
    dbname: str = ""
    user: str = ""
    password: str = ""


class BackupResponse(BaseModel):
    filename: str
    size_bytes: int
    created_at: datetime


class BackupScheduleResponse(BaseModel):
    enabled: bool = False
    interval: Literal["daily", "weekly"] = "daily"
    time: str = "03:00"


class BackupScheduleRequest(BaseModel):
    enabled: bool
    interval: Literal["daily", "weekly"] = "daily"
    time: str = "03:00"
