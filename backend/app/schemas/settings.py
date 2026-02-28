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
