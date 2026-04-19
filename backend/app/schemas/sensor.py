from datetime import datetime

from pydantic import BaseModel


class SensorResponse(BaseModel):
    id: int
    name: str
    sensor_type: str
    mount_point: str
    place: str
    system: str
    last_reading: datetime | None = None

    model_config = {"from_attributes": True}


class SensorDataResponse(BaseModel):
    sensor_id: int
    sensor_name: str
    datatype_name: str
    value: float
    timestamp: datetime

    model_config = {"from_attributes": True}


class ClimateRoomResponse(BaseModel):
    room: str
    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None


class HeatingCircuitStatus(BaseModel):
    circuit: str
    config_prefix: str | None = None
    temp_set: float | None = None
    temp_supply: float | None = None
    temp_return: float | None = None
    pressure: float | None = None
    pump: str | None = None
    pza_mode: bool = False
    pza_curve: int | None = None
    pza_capable: bool = False


class WaterSupplyStatus(BaseModel):
    type: str
    temp_set: float | None = None
    temp_fact: float | None = None
    pressure: float | None = None
    pump: str | None = None


class Stats24h(BaseModel):
    whk24: float = 0.0  # boiler hours
    whb24: float = 0.0  # IHB hours
    whr24: float = 0.0  # radiator hours
    whf24: float = 0.0  # floor heating hours
    avght24: float = 0.0  # average temperature


class DashboardResponse(BaseModel):
    climate: list[ClimateRoomResponse] = []
    heating: list[HeatingCircuitStatus] = []
    water_supply: list[WaterSupplyStatus] = []
    stats: Stats24h = Stats24h()
