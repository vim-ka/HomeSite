from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.config import Actuator
from app.models.heating import HeatingCircuit
from app.models.pending_sensor import PendingSensor
from app.models.sensor import (
    MountPoint,
    Place,
    Sensor,
    SensorData,
    SensorDataHistory,
    SensorDataType,
    SensorOffset,
    SensorType,
    SystemType,
    sensor_type_datatype_link,
)


class CatalogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- Reference data ----

    async def get_system_types(self) -> list[SystemType]:
        result = await self.db.execute(select(SystemType).order_by(SystemType.id))
        return list(result.scalars().all())

    async def get_sensor_types(self) -> list[SensorType]:
        result = await self.db.execute(select(SensorType).order_by(SensorType.id))
        return list(result.scalars().all())

    async def get_sensor_types_with_datatypes(self) -> list[dict]:
        rows = await self.get_sensor_types()
        link_rows = await self.db.execute(
            select(
                sensor_type_datatype_link.c.sensor_type_id,
                sensor_type_datatype_link.c.datatype_id,
            )
        )
        dt_map: dict[int, list[int]] = {}
        for r in link_rows.all():
            dt_map.setdefault(r.sensor_type_id, []).append(r.datatype_id)
        return [
            {"id": st.id, "name": st.name, "datatype_ids": sorted(dt_map.get(st.id, []))}
            for st in rows
        ]

    async def get_sensor_type_by_id(self, st_id: int) -> SensorType | None:
        result = await self.db.execute(select(SensorType).where(SensorType.id == st_id))
        return result.scalar_one_or_none()

    async def create_sensor_type(self, name: str) -> SensorType:
        st = SensorType(name=name)
        self.db.add(st)
        await self.db.commit()
        await self.db.refresh(st)
        return st

    async def update_sensor_type(self, st_id: int, name: str) -> SensorType | None:
        st = await self.get_sensor_type_by_id(st_id)
        if st is None:
            return None
        st.name = name
        await self.db.commit()
        await self.db.refresh(st)
        return st

    async def set_sensor_type_datatypes(self, st_id: int, datatype_ids: list[int]) -> None:
        result = await self.db.execute(
            select(sensor_type_datatype_link.c.datatype_id).where(
                sensor_type_datatype_link.c.sensor_type_id == st_id
            )
        )
        current = set(r[0] for r in result.all())
        desired = set(datatype_ids)

        to_remove = current - desired
        if to_remove:
            await self.db.execute(
                sa_delete(sensor_type_datatype_link).where(
                    sensor_type_datatype_link.c.sensor_type_id == st_id,
                    sensor_type_datatype_link.c.datatype_id.in_(to_remove),
                )
            )
        for dt_id in desired - current:
            await self.db.execute(
                sensor_type_datatype_link.insert().values(
                    sensor_type_id=st_id, datatype_id=dt_id
                )
            )
        if to_remove or (desired - current):
            await self.db.commit()

    async def get_datatype_ids_for_sensor_type(self, st_id: int) -> list[int]:
        result = await self.db.execute(
            select(sensor_type_datatype_link.c.datatype_id).where(
                sensor_type_datatype_link.c.sensor_type_id == st_id
            )
        )
        return sorted(r[0] for r in result.all())

    async def delete_sensor_type(self, st_id: int) -> bool:
        st = await self.get_sensor_type_by_id(st_id)
        if st is None:
            return False
        await self.db.delete(st)
        await self.db.commit()
        return True

    async def sensor_type_has_sensors(self, st_id: int) -> bool:
        result = await self.db.execute(
            select(func.count()).select_from(Sensor).where(Sensor.sensor_type_id == st_id)
        )
        return (result.scalar() or 0) > 0

    async def get_sensor_data_types(self) -> list[SensorDataType]:
        result = await self.db.execute(select(SensorDataType).order_by(SensorDataType.id))
        return list(result.scalars().all())

    async def get_mount_points(self) -> list[dict]:
        s_temp = Sensor.__table__.alias("s_temp")
        s_pres = Sensor.__table__.alias("s_pres")
        s_hum = Sensor.__table__.alias("s_hum")

        stmt = (
            select(
                MountPoint.id,
                MountPoint.name,
                MountPoint.system_id,
                MountPoint.place_id,
                SystemType.name.label("system_name"),
                Place.name.label("place_name"),
                MountPoint.temperature_sensor_id,
                MountPoint.pressure_sensor_id,
                MountPoint.humidity_sensor_id,
                s_temp.c.name.label("temperature_sensor_name"),
                s_pres.c.name.label("pressure_sensor_name"),
                s_hum.c.name.label("humidity_sensor_name"),
            )
            .join(SystemType, MountPoint.system_id == SystemType.id)
            .join(Place, MountPoint.place_id == Place.id)
            .outerjoin(s_temp, MountPoint.temperature_sensor_id == s_temp.c.id)
            .outerjoin(s_pres, MountPoint.pressure_sensor_id == s_pres.c.id)
            .outerjoin(s_hum, MountPoint.humidity_sensor_id == s_hum.c.id)
            .order_by(MountPoint.id)
        )
        result = await self.db.execute(stmt)
        return [row._asdict() for row in result.all()]

    # ---- Place CRUD ----

    async def get_all_places(self) -> list[Place]:
        result = await self.db.execute(select(Place).order_by(Place.id))
        return list(result.scalars().all())

    async def get_place_by_id(self, place_id: int) -> Place | None:
        result = await self.db.execute(select(Place).where(Place.id == place_id))
        return result.scalar_one_or_none()

    async def create_place(self, name: str) -> Place:
        place = Place(name=name)
        self.db.add(place)
        await self.db.commit()
        await self.db.refresh(place)
        return place

    async def update_place(self, place_id: int, name: str) -> Place | None:
        place = await self.get_place_by_id(place_id)
        if place is None:
            return None
        place.name = name
        await self.db.commit()
        await self.db.refresh(place)
        return place

    async def delete_place(self, place_id: int) -> bool:
        place = await self.get_place_by_id(place_id)
        if place is None:
            return False
        await self.db.delete(place)
        await self.db.commit()
        return True

    async def place_has_mount_points(self, place_id: int) -> bool:
        result = await self.db.execute(
            select(func.count()).select_from(MountPoint).where(MountPoint.place_id == place_id)
        )
        return (result.scalar() or 0) > 0

    # ---- MountPoint CRUD ----

    async def get_mount_point_by_id(self, mp_id: int) -> MountPoint | None:
        result = await self.db.execute(select(MountPoint).where(MountPoint.id == mp_id))
        return result.scalar_one_or_none()

    async def create_mount_point(self, **kwargs) -> MountPoint:
        mp = MountPoint(**kwargs)
        self.db.add(mp)
        await self.db.commit()
        await self.db.refresh(mp)
        return mp

    async def update_mount_point(self, mp_id: int, **kwargs) -> MountPoint | None:
        mp = await self.get_mount_point_by_id(mp_id)
        if mp is None:
            return None
        for k, v in kwargs.items():
            setattr(mp, k, v)
        await self.db.commit()
        await self.db.refresh(mp)
        return mp

    async def delete_mount_point(self, mp_id: int) -> bool:
        mp = await self.get_mount_point_by_id(mp_id)
        if mp is None:
            return False
        await self.db.delete(mp)
        await self.db.commit()
        return True

    async def mount_point_has_sensors(self, mp_id: int) -> bool:
        result = await self.db.execute(
            select(func.count()).select_from(Sensor).where(Sensor.mount_point_id == mp_id)
        )
        return (result.scalar() or 0) > 0

    async def check_sensor_binding_conflicts(
        self,
        mp_id: int | None,
        temperature_sensor_id: int | None,
        pressure_sensor_id: int | None,
        humidity_sensor_id: int | None,
    ) -> str | None:
        """Check if any sensor is already bound to another mount point for the same data type.

        Returns error message or None if no conflict.
        """
        checks = [
            (temperature_sensor_id, MountPoint.temperature_sensor_id, "температуры"),
            (pressure_sensor_id, MountPoint.pressure_sensor_id, "давления"),
            (humidity_sensor_id, MountPoint.humidity_sensor_id, "влажности"),
        ]
        for sensor_id, col, label in checks:
            if sensor_id is None:
                continue
            stmt = select(MountPoint.id, MountPoint.name).where(
                col == sensor_id,
            )
            if mp_id is not None:
                stmt = stmt.where(MountPoint.id != mp_id)
            result = await self.db.execute(stmt)
            row = result.first()
            if row:
                return f"Датчик {label} (id={sensor_id}) уже привязан к точке \"{row.name}\""
        return None

    # ---- Sensor CRUD ----

    async def get_all_sensors_detail(self) -> list[dict]:
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
                Sensor.sensor_type_id,
                SensorType.name.label("sensor_type_name"),
                Sensor.mount_point_id,
                MountPoint.name.label("mount_point_name"),
                Place.name.label("place_name"),
                SystemType.name.label("system_name"),
                Sensor.actuator_id,
                Actuator.name.label("actuator_name"),
                Actuator.mqtt_device_name.label("actuator_mqtt_device_name"),
                last_reading_sq.c.last_reading,
            )
            .join(SensorType, Sensor.sensor_type_id == SensorType.id)
            .join(MountPoint, Sensor.mount_point_id == MountPoint.id)
            .join(Place, MountPoint.place_id == Place.id)
            .join(SystemType, MountPoint.system_id == SystemType.id)
            .outerjoin(Actuator, Sensor.actuator_id == Actuator.id)
            .outerjoin(last_reading_sq, Sensor.id == last_reading_sq.c.sensor_id)
            .order_by(Sensor.id)
        )
        result = await self.db.execute(stmt)
        rows = [row._asdict() for row in result.all()]

        # Fetch datatype_ids per sensor_type (now normalised at the type level).
        dt_stmt = select(
            sensor_type_datatype_link.c.sensor_type_id,
            sensor_type_datatype_link.c.datatype_id,
        )
        dt_result = await self.db.execute(dt_stmt)
        dt_map: dict[int, list[int]] = {}
        for r in dt_result.all():
            dt_map.setdefault(r.sensor_type_id, []).append(r.datatype_id)

        # Non-zero offsets, joined with datatype code, for badge display.
        off_stmt = (
            select(
                SensorOffset.sensor_id,
                SensorDataType.code,
                SensorOffset.value,
            )
            .join(SensorDataType, SensorDataType.id == SensorOffset.datatype_id)
            .where(SensorOffset.value != 0)
        )
        off_result = await self.db.execute(off_stmt)
        off_map: dict[int, list[dict]] = {}
        for r in off_result.all():
            off_map.setdefault(r.sensor_id, []).append(
                {"datatype_code": r.code, "value": r.value}
            )

        for row in rows:
            row["datatype_ids"] = sorted(dt_map.get(row["sensor_type_id"], []))
            row["offsets"] = off_map.get(row["id"], [])

        return rows

    async def get_sensor_by_id(self, sensor_id: int) -> Sensor | None:
        result = await self.db.execute(select(Sensor).where(Sensor.id == sensor_id))
        return result.scalar_one_or_none()

    async def create_sensor(
        self,
        name: str,
        sensor_type_id: int,
        mount_point_id: int,
        actuator_id: int | None = None,
    ) -> Sensor:
        sensor = Sensor(
            name=name,
            sensor_type_id=sensor_type_id,
            mount_point_id=mount_point_id,
            actuator_id=actuator_id,
        )
        self.db.add(sensor)
        await self.db.commit()
        await self.db.refresh(sensor)
        return sensor

    async def update_sensor(
        self,
        sensor_id: int,
        name: str,
        sensor_type_id: int,
        mount_point_id: int,
        actuator_id: int | None = None,
    ) -> Sensor | None:
        sensor = await self.get_sensor_by_id(sensor_id)
        if sensor is None:
            return None
        sensor.name = name
        sensor.sensor_type_id = sensor_type_id
        sensor.mount_point_id = mount_point_id
        sensor.actuator_id = actuator_id
        await self.db.commit()
        await self.db.refresh(sensor)
        return sensor

    async def get_sensor_by_name(self, name: str) -> Sensor | None:
        result = await self.db.execute(select(Sensor).where(Sensor.name == name))
        return result.scalar_one_or_none()

    async def get_actuator_by_mqtt_name(self, mqtt_device_name: str) -> Actuator | None:
        result = await self.db.execute(
            select(Actuator).where(Actuator.mqtt_device_name == mqtt_device_name)
        )
        return result.scalar_one_or_none()

    async def delete_sensor(self, sensor_id: int) -> bool:
        sensor = await self.get_sensor_by_id(sensor_id)
        if sensor is None:
            return False
        await self.db.delete(sensor)
        await self.db.commit()
        return True

    # ---- Sensor Offsets ----

    async def get_sensor_offsets(self, sensor_id: int) -> list[dict]:
        """Return one offset row per datatype the sensor's TYPE exposes.

        Missing rows surface as value=0.0 so the UI can edit them without a
        prior insert.
        """
        sensor = await self.get_sensor_by_id(sensor_id)
        if sensor is None:
            return []

        dt_rows = await self.db.execute(
            select(SensorDataType.id, SensorDataType.code, SensorDataType.name)
            .join(
                sensor_type_datatype_link,
                sensor_type_datatype_link.c.datatype_id == SensorDataType.id,
            )
            .where(sensor_type_datatype_link.c.sensor_type_id == sensor.sensor_type_id)
            .order_by(SensorDataType.id)
        )
        datatypes = [dict(r._mapping) for r in dt_rows.all()]

        # Existing offsets
        off_rows = await self.db.execute(
            select(SensorOffset.datatype_id, SensorOffset.value).where(
                SensorOffset.sensor_id == sensor_id
            )
        )
        offsets = {r.datatype_id: r.value for r in off_rows.all()}

        return [
            {
                "sensor_id": sensor_id,
                "datatype_id": dt["id"],
                "datatype_code": dt["code"],
                "datatype_name": dt["name"],
                "value": offsets.get(dt["id"], 0.0),
            }
            for dt in datatypes
        ]

    async def upsert_sensor_offset(
        self, sensor_id: int, datatype_id: int, value: float
    ) -> SensorOffset:
        result = await self.db.execute(
            select(SensorOffset).where(
                SensorOffset.sensor_id == sensor_id,
                SensorOffset.datatype_id == datatype_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = SensorOffset(sensor_id=sensor_id, datatype_id=datatype_id, value=value)
            self.db.add(row)
        else:
            row.value = value
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def get_data_type_by_id(self, dt_id: int) -> SensorDataType | None:
        result = await self.db.execute(
            select(SensorDataType).where(SensorDataType.id == dt_id)
        )
        return result.scalar_one_or_none()

    async def sensor_has_history(self, sensor_id: int) -> bool:
        """Check if sensor has historical data that would be lost on deletion."""
        r = await self.db.execute(
            select(func.count())
            .select_from(SensorDataHistory)
            .where(SensorDataHistory.sensor_id == sensor_id)
        )
        return (r.scalar() or 0) > 0

    async def delete_sensor_data(self, sensor_id: int) -> None:
        """Remove all SensorData rows for a sensor (current values / config)."""
        await self.db.execute(
            sa_delete(SensorData).where(SensorData.sensor_id == sensor_id)
        )
        await self.db.commit()

    # ---- Pending Sensors (auto-discovery) ----

    async def get_pending_sensors(self) -> list[PendingSensor]:
        result = await self.db.execute(
            select(PendingSensor).order_by(PendingSensor.last_seen.desc())
        )
        return list(result.scalars().all())

    async def get_pending_sensor_by_id(self, ps_id: int) -> PendingSensor | None:
        result = await self.db.execute(
            select(PendingSensor).where(PendingSensor.id == ps_id)
        )
        return result.scalar_one_or_none()

    async def delete_pending_sensor(self, ps_id: int) -> bool:
        ps = await self.get_pending_sensor_by_id(ps_id)
        if ps is None:
            return False
        await self.db.delete(ps)
        await self.db.commit()
        return True

    # ---- Heating Circuits CRUD ----

    async def get_heating_circuits(self) -> list[dict]:
        mp_supply = MountPoint.__table__.alias("mp_supply")
        mp_return = MountPoint.__table__.alias("mp_return")

        stmt = (
            select(
                HeatingCircuit.id,
                HeatingCircuit.circuit_name,
                HeatingCircuit.supply_mount_point_id,
                HeatingCircuit.return_mount_point_id,
                mp_supply.c.name.label("supply_mount_point_name"),
                mp_return.c.name.label("return_mount_point_name"),
                HeatingCircuit.config_temp_key,
                HeatingCircuit.config_pump_key,
                HeatingCircuit.config_prefix,
                HeatingCircuit.mqtt_device_name,
                HeatingCircuit.delta_threshold,
                HeatingCircuit.show_on_dashboard,
                HeatingCircuit.display_order,
            )
            .outerjoin(mp_supply, HeatingCircuit.supply_mount_point_id == mp_supply.c.id)
            .outerjoin(mp_return, HeatingCircuit.return_mount_point_id == mp_return.c.id)
            .order_by(HeatingCircuit.display_order)
        )
        result = await self.db.execute(stmt)
        return [row._asdict() for row in result.all()]

    async def get_heating_circuit_by_id(self, circuit_id: int) -> HeatingCircuit | None:
        result = await self.db.execute(
            select(HeatingCircuit).where(HeatingCircuit.id == circuit_id)
        )
        return result.scalar_one_or_none()

    async def create_heating_circuit(self, **kwargs) -> HeatingCircuit:
        circuit = HeatingCircuit(**kwargs)
        self.db.add(circuit)
        await self.db.commit()
        await self.db.refresh(circuit)
        return circuit

    async def update_heating_circuit(self, circuit_id: int, **kwargs) -> HeatingCircuit | None:
        circuit = await self.get_heating_circuit_by_id(circuit_id)
        if circuit is None:
            return None
        for k, v in kwargs.items():
            setattr(circuit, k, v)
        await self.db.commit()
        await self.db.refresh(circuit)
        return circuit

    async def delete_heating_circuit(self, circuit_id: int) -> bool:
        circuit = await self.get_heating_circuit_by_id(circuit_id)
        if circuit is None:
            return False
        await self.db.delete(circuit)
        await self.db.commit()
        return True

    async def accept_pending_sensor(
        self, ps_id: int, sensor_type_id: int, mount_point_id: int
    ) -> Sensor:
        """Accept a pending sensor: create a real Sensor and remove from pending.

        Datatypes are derived from the chosen sensor type — no per-sensor
        configuration needed.
        """
        ps = await self.get_pending_sensor_by_id(ps_id)
        if ps is None:
            raise ValueError("Pending sensor not found")

        sensor = Sensor(
            name=ps.device_name,
            sensor_type_id=sensor_type_id,
            mount_point_id=mount_point_id,
        )
        self.db.add(sensor)
        await self.db.flush()

        await self.db.delete(ps)
        await self.db.commit()
        await self.db.refresh(sensor)
        return sensor
