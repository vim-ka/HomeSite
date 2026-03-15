from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heating import HeatingCircuit
from app.models.sensor import MountPoint, Sensor
from app.repositories.sensor_repository import SensorRepository
from app.schemas.sensor import (
    ClimateRoomResponse,
    DashboardResponse,
    HeatingCircuitStatus,
    Stats24h,
    WaterSupplyStatus,
)


class SensorService:
    def __init__(self, sensor_repo: SensorRepository):
        self.sensor_repo = sensor_repo

    async def get_dashboard_data(self) -> DashboardResponse:
        """Build full dashboard — replaces 70+ lines of inline queries in v1 views.py."""
        climate_raw = await self.sensor_repo.get_climate_data()
        climate = [ClimateRoomResponse(**c) for c in climate_raw]

        heating_raw = await self.sensor_repo.get_heating_status()
        heating = [
            HeatingCircuitStatus(
                circuit=h["circuit"],
                temp_set=h.get("TempSet"),
                temp_supply=h.get("TempSup"),
                temp_return=h.get("TempRet"),
                pressure=h.get("Pressure"),
                pump=h.get("Pump"),
                pza_mode=h.get("pza_mode", False),
                pza_curve=h.get("pza_curve"),
                pza_capable=h.get("pza_capable", False),
            )
            for h in heating_raw
        ]

        water_raw = await self.sensor_repo.get_water_supply_status()
        water_supply = [
            WaterSupplyStatus(
                type=w["type"],
                temp_set=w.get("tempSet"),
                temp_fact=w.get("tempFact"),
                pressure=w.get("pressure"),
                pump=w.get("Pump"),
            )
            for w in water_raw
        ]

        stats = await self._calc_24h_stats()

        return DashboardResponse(
            climate=climate,
            heating=heating,
            water_supply=water_supply,
            stats=stats,
        )

    async def _calc_24h_stats(self) -> Stats24h:
        """Compute 24h heating operation stats.

        Uses mount point bindings to resolve sensors dynamically.
        """
        db = self.sensor_repo.db

        # Load circuit definitions from DB
        circuits_result = await db.execute(
            select(HeatingCircuit)
            .where(HeatingCircuit.show_on_dashboard.is_(True))
            .order_by(HeatingCircuit.display_order)
        )
        circuits = circuits_result.scalars().all()

        if not circuits:
            return Stats24h()

        # Resolve temperature sensor IDs from mount points (explicit binding)
        async def temp_sensor_at_mount_point(mp_id: int | None) -> int | None:
            if mp_id is None:
                return None
            result = await db.execute(
                select(MountPoint.temperature_sensor_id).where(MountPoint.id == mp_id)
            )
            return result.scalar_one_or_none()

        # Build circuit → (supply_sensor_id, return_sensor_id) mapping
        circuit_sensors: dict[int, tuple[int | None, int | None]] = {}
        all_sensor_ids: set[int] = set()
        for c in circuits:
            sup_id = await temp_sensor_at_mount_point(c.supply_mount_point_id)
            ret_id = await temp_sensor_at_mount_point(c.return_mount_point_id)
            circuit_sensors[c.id] = (sup_id, ret_id)
            if sup_id is not None:
                all_sensor_ids.add(sup_id)
            if ret_id is not None:
                all_sensor_ids.add(ret_id)

        # Climate sensors: system_id=3, exclude street (place_id=7)
        climate_stmt = (
            select(Sensor.id)
            .join(MountPoint, Sensor.mount_point_id == MountPoint.id)
            .where(MountPoint.system_id == 3, MountPoint.place_id != 7)
        )
        climate_result = await db.execute(climate_stmt)
        climate_sensor_ids = [row[0] for row in climate_result]
        all_sensor_ids.update(climate_sensor_ids)

        if not all_sensor_ids:
            return Stats24h()

        # Fetch all history for last 24h (datatype_id=1 = Temperature)
        since = datetime.now(UTC) - timedelta(days=1)
        rows = await self.sensor_repo.get_history_for_stats(
            list(all_sensor_ids), datatype_id=1, since=since
        )

        if not rows:
            return Stats24h()

        # Group: timestamp (rounded to minute) → {sensor_id: value}
        # Sensors report at slightly different times — rounding ensures
        # supply and return readings are matched in the same time bucket.
        ts_data: dict[datetime, dict[int, float]] = defaultdict(dict)
        for row in rows:
            ts = row["timestamp"]
            bucket = ts.replace(second=0, microsecond=0)
            ts_data[bucket][row["sensor_id"]] = row["value"]

        # Calculate time span
        timestamps_sorted = sorted(ts_data.keys())
        if len(timestamps_sorted) >= 2:
            span_hours = (timestamps_sorted[-1] - timestamps_sorted[0]).total_seconds() / 3600
        else:
            span_hours = 24.0
        if span_hours <= 0:
            span_hours = 24.0

        # Map circuit_name -> stat key
        stat_key_map = {
            "Котёл": "whk24",
            "БКН": "whb24",
            "Радиаторы": "whr24",
            "Тёплый пол": "whf24",
        }

        result_dict: dict[str, float] = {}
        for c in circuits:
            key = stat_key_map.get(c.circuit_name)
            sup_id, ret_id = circuit_sensors.get(c.id, (None, None))
            if not key or sup_id is None or ret_id is None:
                continue
            total_samples = 0
            active_samples = 0
            for sensors in ts_data.values():
                sup_val = sensors.get(sup_id)
                ret_val = sensors.get(ret_id)
                if sup_val is not None and ret_val is not None:
                    total_samples += 1
                    if sup_val - ret_val >= c.delta_threshold:
                        active_samples += 1

            if total_samples > 0:
                ratio = active_samples / total_samples
                result_dict[key] = round(ratio * span_hours, 1)

        # Average home temperature (climate sensors, excluding street)
        climate_values = []
        for sensors in ts_data.values():
            for sid in climate_sensor_ids:
                val = sensors.get(sid)
                if val is not None:
                    climate_values.append(val)

        avght24 = round(sum(climate_values) / len(climate_values), 1) if climate_values else 0.0

        return Stats24h(
            whk24=result_dict.get("whk24", 0.0),
            whb24=result_dict.get("whb24", 0.0),
            whr24=result_dict.get("whr24", 0.0),
            whf24=result_dict.get("whf24", 0.0),
            avght24=avght24,
        )
