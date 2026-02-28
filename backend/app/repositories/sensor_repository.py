from collections import defaultdict
from datetime import datetime

from sqlalchemy import Float, case, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import ConfigKV
from app.models.heating import HeatingCircuit
from app.models.sensor import (
    MountPoint,
    Place,
    Sensor,
    SensorData,
    SensorDataHistory,
    SensorDataType,
    SensorType,
    SystemType,
)


class SensorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_sensors(self) -> list[dict]:
        """List all sensors with their type, mount point, place, and system."""
        stmt = (
            select(
                Sensor.id,
                Sensor.name,
                SensorType.name.label("sensor_type"),
                MountPoint.name.label("mount_point"),
                Place.name.label("place"),
                SystemType.name.label("system"),
            )
            .join(SensorType, Sensor.sensor_type_id == SensorType.id)
            .join(MountPoint, Sensor.mount_point_id == MountPoint.id)
            .join(Place, MountPoint.place_id == Place.id)
            .join(SystemType, MountPoint.system_id == SystemType.id)
            .order_by(Sensor.id)
        )
        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result]

    async def get_climate_data(self) -> list[dict]:
        """Get current climate readings by room (system_id=3 = Climate)."""
        stmt = (
            select(
                Place.name.label("room"),
                case(
                    (SensorDataType.name == "Temperature", SensorData.value),
                    else_=None,
                ).label("temperature"),
                case(
                    (SensorDataType.name == "Humidity", SensorData.value),
                    else_=None,
                ).label("humidity"),
                case(
                    (SensorDataType.name == "Pressure", SensorData.value),
                    else_=None,
                ).label("pressure"),
            )
            .outerjoin(MountPoint, (MountPoint.place_id == Place.id) & (MountPoint.system_id == 3))
            .outerjoin(Sensor, Sensor.mount_point_id == MountPoint.id)
            .outerjoin(SensorData, Sensor.id == SensorData.sensor_id)
            .outerjoin(SensorDataType, SensorData.datatype_id == SensorDataType.id)
            .group_by(Place.name, SensorDataType.name, SensorData.value)
        )
        rows = (await self.db.execute(stmt)).all()

        merged: dict[str, dict] = {}
        for row in rows:
            room = row.room
            if room not in merged:
                merged[room] = {"room": room}
            if row.temperature is not None:
                merged[room]["temperature"] = row.temperature
            if row.humidity is not None:
                merged[room]["humidity"] = row.humidity
            if row.pressure is not None:
                merged[room]["pressure"] = row.pressure

        return list(merged.values())

    async def get_heating_status(self) -> list[dict]:
        """Get heating circuit status using HeatingCircuit config (no hardcoded IDs)."""
        circuits = (
            await self.db.execute(
                select(HeatingCircuit).order_by(HeatingCircuit.display_order)
            )
        ).scalars().all()

        results = []
        for c in circuits:
            # Get supply temp
            temp_sup = await self._get_sensor_value(c.supply_sensor_id, 1)
            temp_ret = await self._get_sensor_value(c.return_sensor_id, 1)
            pressure = await self._get_sensor_value(c.pressure_sensor_id, 2)

            # Get config values
            temp_set = await self._get_config_value(c.config_temp_key)
            pump = await self._get_config_value(c.config_pump_key)

            results.append({
                "circuit": c.circuit_name,
                "TempSet": float(temp_set) if temp_set else None,
                "TempSup": temp_sup,
                "TempRet": temp_ret,
                "Pressure": pressure,
                "Pump": pump,
            })

        return results

    async def get_water_supply_status(self) -> list[dict]:
        """Get water supply status (system_id=2)."""
        stmt = (
            select(
                MountPoint.id,
                MountPoint.name.label("type"),
                SensorData.value.label("tempFact"),
            )
            .select_from(MountPoint)
            .join(SystemType, SystemType.id == MountPoint.system_id)
            .outerjoin(Sensor, Sensor.mount_point_id == MountPoint.id)
            .outerjoin(SensorData, (SensorData.sensor_id == Sensor.id) & (SensorData.datatype_id == 1))
            .where(SystemType.id == 2)
        )
        rows = (await self.db.execute(stmt)).all()

        ihb_temp = await self._get_config_value("watersupply_ihb_temp")
        cold_pump = await self._get_config_value("watersupply_pump")
        hot_pump = await self._get_config_value("watersupply_pump_hot")

        results = []
        for row in rows:
            results.append({
                "type": row.type,
                "tempSet": float(ihb_temp) if row.id == 10 and ihb_temp else None,
                "tempFact": row.tempFact,
                "pressure": None,
                "Pump": hot_pump if row.id == 10 else cold_pump,
            })

        return results

    async def get_sensor_value(self, sensor_id: int, datatype_id: int) -> float | None:
        return await self._get_sensor_value(sensor_id, datatype_id)

    async def get_history_for_stats(
        self, sensor_ids: list[int], datatype_id: int, since: datetime
    ) -> list[dict]:
        """Get history rows for 24h stats calculation."""
        stmt = (
            select(
                SensorDataHistory.sensor_id,
                SensorDataHistory.timestamp,
                SensorDataHistory.value,
            )
            .where(
                SensorDataHistory.datatype_id == datatype_id,
                SensorDataHistory.timestamp >= since,
                SensorDataHistory.sensor_id.in_(sensor_ids),
            )
        )
        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result]

    async def _get_sensor_value(self, sensor_id: int | None, datatype_id: int) -> float | None:
        if sensor_id is None:
            return None
        stmt = select(SensorData.value).where(
            SensorData.sensor_id == sensor_id,
            SensorData.datatype_id == datatype_id,
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return float(row) if row is not None else None

    async def _get_config_value(self, key: str | None) -> str | None:
        if key is None:
            return None
        stmt = select(ConfigKV.value).where(ConfigKV.key == key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
