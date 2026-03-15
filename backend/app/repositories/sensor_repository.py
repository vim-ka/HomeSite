from collections import defaultdict
from datetime import UTC, datetime, timedelta

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

DEFAULT_STALE_MINUTES = 5


class SensorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._stale_threshold: datetime | None = None

    async def _get_stale_threshold(self) -> datetime:
        """Load sensor_stale_minutes from config_kv and compute threshold."""
        if self._stale_threshold is not None:
            return self._stale_threshold
        result = await self.db.execute(
            select(ConfigKV.value).where(ConfigKV.key == "sensor_stale_minutes")
        )
        minutes = DEFAULT_STALE_MINUTES
        row = result.scalar_one_or_none()
        if row:
            try:
                minutes = int(row)
            except ValueError:
                pass
        self._stale_threshold = datetime.now(UTC) - timedelta(minutes=minutes)
        return self._stale_threshold

    async def get_all_sensors(self) -> list[dict]:
        """List all sensors with their type, mount point, place, system, and last reading time."""
        from sqlalchemy import func as sa_func

        # Subquery: latest timestamp per sensor from sensor_data
        last_reading_sq = (
            select(
                SensorData.sensor_id,
                sa_func.max(SensorData.timestamp).label("last_reading"),
            )
            .group_by(SensorData.sensor_id)
            .subquery()
        )

        stmt = (
            select(
                Sensor.id,
                Sensor.name,
                SensorType.name.label("sensor_type"),
                MountPoint.name.label("mount_point"),
                Place.name.label("place"),
                SystemType.name.label("system"),
                last_reading_sq.c.last_reading,
            )
            .join(SensorType, Sensor.sensor_type_id == SensorType.id)
            .join(MountPoint, Sensor.mount_point_id == MountPoint.id)
            .join(Place, MountPoint.place_id == Place.id)
            .join(SystemType, MountPoint.system_id == SystemType.id)
            .outerjoin(last_reading_sq, Sensor.id == last_reading_sq.c.sensor_id)
            .order_by(Sensor.id)
        )
        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result]

    async def get_climate_data(self) -> list[dict]:
        """Get current climate readings by room (system_id=3 = Climate). Stale data excluded."""
        stale_threshold = await self._get_stale_threshold()
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
            .outerjoin(SensorData, (Sensor.id == SensorData.sensor_id) & (SensorData.timestamp >= stale_threshold))
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
        """Get heating circuit status using mount point bindings (sensors resolved dynamically).

        Only circuits with show_on_dashboard=True are included.
        If PZA (weather-dependent) mode is enabled, temp_set is calculated from curve.
        """
        from app.services.pza import get_pza_target

        circuits = (
            await self.db.execute(
                select(HeatingCircuit)
                .where(HeatingCircuit.show_on_dashboard.is_(True))
                .order_by(HeatingCircuit.display_order)
            )
        ).scalars().all()

        # Get outdoor temperature for PZA (system_id=3, place_id=7=Улица)
        outdoor_temp: float | None = None
        outdoor_stmt = (
            select(SensorData.value)
            .join(Sensor, SensorData.sensor_id == Sensor.id)
            .join(MountPoint, Sensor.mount_point_id == MountPoint.id)
            .where(MountPoint.place_id == 7, MountPoint.system_id == 3, SensorData.datatype_id == 1)
        )
        outdoor_row = (await self.db.execute(outdoor_stmt)).scalar_one_or_none()
        if outdoor_row is not None:
            outdoor_temp = float(outdoor_row)

        # PZA config mapping: prefix → (wbm_key, curve_key, curve_type)
        pza_config = {
            "heating_radiator": ("heating_radiator_wbm", "heating_radiator_curve", "radiator"),
            "heating_floorheating": ("heating_floorheating_wbm", "heating_floorheating_curve", "floor"),
        }

        results = []
        for c in circuits:
            temp_sup = await self._get_mount_point_value(c.supply_mount_point_id, 1)
            temp_ret = await self._get_mount_point_value(c.return_mount_point_id, 1)
            pressure = await self._get_mount_point_value(c.supply_mount_point_id, 2)

            temp_set_raw = await self._get_config_value(c.config_temp_key)
            temp_set = float(temp_set_raw) if temp_set_raw else None
            pump = await self._get_config_value(c.config_pump_key)

            # Check PZA mode and override temp_set if enabled
            pza_mode = False
            pza_curve = None
            pza_capable = c.config_prefix is not None and c.config_prefix in pza_config
            if pza_capable and outdoor_temp is not None:
                wbm_key, curve_key, curve_type = pza_config[c.config_prefix]
                wbm = await self._get_config_value(wbm_key)
                if wbm == "1":
                    pza_mode = True
                    curve_str = await self._get_config_value(curve_key)
                    pza_curve = int(curve_str) if curve_str else 3
                    pza_target = get_pza_target(curve_type, pza_curve, outdoor_temp)
                    if pza_target is not None:
                        temp_set = pza_target

            results.append({
                "circuit": c.circuit_name,
                "TempSet": temp_set,
                "TempSup": temp_sup,
                "TempRet": temp_ret,
                "Pressure": pressure,
                "Pump": pump,
                "pza_mode": pza_mode,
                "pza_curve": pza_curve,
                "pza_capable": pza_capable,
            })

        return results

    async def get_water_supply_status(self) -> list[dict]:
        """Get water supply status (system_id=2). Stale data excluded."""
        stale_threshold = await self._get_stale_threshold()
        stmt = (
            select(
                MountPoint.id,
                MountPoint.name.label("type"),
                SensorData.value.label("tempFact"),
            )
            .select_from(MountPoint)
            .join(SystemType, SystemType.id == MountPoint.system_id)
            .outerjoin(Sensor, Sensor.mount_point_id == MountPoint.id)
            .outerjoin(SensorData, (SensorData.sensor_id == Sensor.id) & (SensorData.datatype_id == 1) & (SensorData.timestamp >= stale_threshold))
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
        stale_threshold = await self._get_stale_threshold()
        stmt = select(SensorData.value).where(
            SensorData.sensor_id == sensor_id,
            SensorData.datatype_id == datatype_id,
            SensorData.timestamp >= stale_threshold,
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return float(row) if row is not None else None

    async def _get_mount_point_value(self, mount_point_id: int | None, datatype_id: int) -> float | None:
        """Get sensor value using explicit sensor binding on the mount point.

        datatype_id: 1=Temperature, 2=Pressure, 3=Humidity
        """
        if mount_point_id is None:
            return None

        # Map datatype_id to the corresponding sensor_id column on MountPoint
        col_map = {
            1: MountPoint.temperature_sensor_id,
            2: MountPoint.pressure_sensor_id,
            3: MountPoint.humidity_sensor_id,
        }
        sensor_col = col_map.get(datatype_id)
        if sensor_col is None:
            return None

        # Get the explicit sensor_id from the mount point
        mp_stmt = select(sensor_col).where(MountPoint.id == mount_point_id)
        sensor_id = (await self.db.execute(mp_stmt)).scalar_one_or_none()
        if sensor_id is None:
            return None

        return await self._get_sensor_value(sensor_id, datatype_id)

    async def _get_config_value(self, key: str | None) -> str | None:
        if key is None:
            return None
        stmt = select(ConfigKV.value).where(ConfigKV.key == key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
