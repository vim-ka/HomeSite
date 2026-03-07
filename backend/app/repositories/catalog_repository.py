from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.pending_sensor import PendingSensor
from app.models.sensor import (
    MountPoint,
    Place,
    Sensor,
    SensorData,
    SensorDataHistory,
    SensorDataType,
    SensorType,
    SystemType,
    sensor_datatype_link,
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

    async def get_sensor_data_types(self) -> list[SensorDataType]:
        result = await self.db.execute(select(SensorDataType).order_by(SensorDataType.id))
        return list(result.scalars().all())

    async def get_mount_points(self) -> list[dict]:
        stmt = (
            select(
                MountPoint.id,
                MountPoint.name,
                MountPoint.system_id,
                MountPoint.place_id,
                SystemType.name.label("system_name"),
                Place.name.label("place_name"),
            )
            .join(SystemType, MountPoint.system_id == SystemType.id)
            .join(Place, MountPoint.place_id == Place.id)
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

    async def create_mount_point(self, name: str, system_id: int, place_id: int) -> MountPoint:
        mp = MountPoint(name=name, system_id=system_id, place_id=place_id)
        self.db.add(mp)
        await self.db.commit()
        await self.db.refresh(mp)
        return mp

    async def update_mount_point(
        self, mp_id: int, name: str, system_id: int, place_id: int
    ) -> MountPoint | None:
        mp = await self.get_mount_point_by_id(mp_id)
        if mp is None:
            return None
        mp.name = name
        mp.system_id = system_id
        mp.place_id = place_id
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

    # ---- Sensor CRUD ----

    async def get_all_sensors_detail(self) -> list[dict]:
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
            )
            .join(SensorType, Sensor.sensor_type_id == SensorType.id)
            .join(MountPoint, Sensor.mount_point_id == MountPoint.id)
            .join(Place, MountPoint.place_id == Place.id)
            .join(SystemType, MountPoint.system_id == SystemType.id)
            .order_by(Sensor.id)
        )
        result = await self.db.execute(stmt)
        rows = [row._asdict() for row in result.all()]

        # Fetch datatype_ids from link table
        dt_stmt = select(sensor_datatype_link.c.sensor_id, sensor_datatype_link.c.datatype_id)
        dt_result = await self.db.execute(dt_stmt)
        dt_map: dict[int, list[int]] = {}
        for r in dt_result.all():
            dt_map.setdefault(r.sensor_id, []).append(r.datatype_id)

        for row in rows:
            row["datatype_ids"] = sorted(dt_map.get(row["id"], []))

        return rows

    async def get_sensor_by_id(self, sensor_id: int) -> Sensor | None:
        result = await self.db.execute(select(Sensor).where(Sensor.id == sensor_id))
        return result.scalar_one_or_none()

    async def create_sensor(self, name: str, sensor_type_id: int, mount_point_id: int) -> Sensor:
        sensor = Sensor(name=name, sensor_type_id=sensor_type_id, mount_point_id=mount_point_id)
        self.db.add(sensor)
        await self.db.commit()
        await self.db.refresh(sensor)
        return sensor

    async def update_sensor(
        self, sensor_id: int, name: str, sensor_type_id: int, mount_point_id: int
    ) -> Sensor | None:
        sensor = await self.get_sensor_by_id(sensor_id)
        if sensor is None:
            return None
        sensor.name = name
        sensor.sensor_type_id = sensor_type_id
        sensor.mount_point_id = mount_point_id
        await self.db.commit()
        await self.db.refresh(sensor)
        return sensor

    async def delete_sensor(self, sensor_id: int) -> bool:
        sensor = await self.get_sensor_by_id(sensor_id)
        if sensor is None:
            return False
        await self.db.delete(sensor)
        await self.db.commit()
        return True

    async def set_sensor_datatypes(self, sensor_id: int, datatype_ids: list[int]) -> None:
        """Sync sensor_datatype_link rows for the given sensor."""
        result = await self.db.execute(
            select(sensor_datatype_link.c.datatype_id).where(
                sensor_datatype_link.c.sensor_id == sensor_id
            )
        )
        current = set(r[0] for r in result.all())
        desired = set(datatype_ids)

        to_remove = current - desired
        if to_remove:
            await self.db.execute(
                sa_delete(sensor_datatype_link).where(
                    sensor_datatype_link.c.sensor_id == sensor_id,
                    sensor_datatype_link.c.datatype_id.in_(to_remove),
                )
            )

        to_add = desired - current
        for dt_id in to_add:
            await self.db.execute(
                sensor_datatype_link.insert().values(sensor_id=sensor_id, datatype_id=dt_id)
            )

        if to_remove or to_add:
            await self.db.commit()

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

    async def accept_pending_sensor(
        self, ps_id: int, sensor_type_id: int, mount_point_id: int, datatype_ids: list[int]
    ) -> Sensor:
        """Accept a pending sensor: create a real Sensor and remove from pending."""
        ps = await self.get_pending_sensor_by_id(ps_id)
        if ps is None:
            raise ValueError("Pending sensor not found")

        sensor = Sensor(
            name=ps.device_name,
            sensor_type_id=sensor_type_id,
            mount_point_id=mount_point_id,
        )
        self.db.add(sensor)
        await self.db.flush()  # get sensor.id

        for dt_id in datatype_ids:
            await self.db.execute(
                sensor_datatype_link.insert().values(sensor_id=sensor.id, datatype_id=dt_id)
            )

        await self.db.delete(ps)
        await self.db.commit()
        await self.db.refresh(sensor)
        return sensor
