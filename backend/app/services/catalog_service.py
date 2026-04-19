from fastapi import HTTPException, status

from app.repositories.catalog_repository import CatalogRepository


class CatalogService:
    def __init__(self, repo: CatalogRepository):
        self.repo = repo

    # ---- Reference data ----

    async def get_system_types(self):
        return await self.repo.get_system_types()

    async def get_sensor_types(self):
        return await self.repo.get_sensor_types_with_datatypes()

    async def create_sensor_type(self, name: str, datatype_ids: list[int] | None = None):
        st = await self.repo.create_sensor_type(name)
        if datatype_ids:
            await self.repo.set_sensor_type_datatypes(st.id, datatype_ids)
        return {
            "id": st.id,
            "name": st.name,
            "datatype_ids": await self.repo.get_datatype_ids_for_sensor_type(st.id),
        }

    async def update_sensor_type(
        self, st_id: int, name: str, datatype_ids: list[int] | None = None
    ):
        st = await self.repo.update_sensor_type(st_id, name)
        if st is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тип датчика не найден")
        if datatype_ids is not None:
            await self.repo.set_sensor_type_datatypes(st_id, datatype_ids)
        return {
            "id": st.id,
            "name": st.name,
            "datatype_ids": await self.repo.get_datatype_ids_for_sensor_type(st.id),
        }

    async def delete_sensor_type(self, st_id: int):
        if await self.repo.sensor_type_has_sensors(st_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Невозможно удалить тип датчика: есть связанные датчики",
            )
        deleted = await self.repo.delete_sensor_type(st_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тип датчика не найден")

    async def get_sensor_data_types(self):
        return await self.repo.get_sensor_data_types()

    async def get_mount_points(self):
        return await self.repo.get_mount_points()

    # ---- Place CRUD ----

    async def get_all_places(self):
        return await self.repo.get_all_places()

    async def create_place(self, name: str):
        return await self.repo.create_place(name)

    async def update_place(self, place_id: int, name: str):
        place = await self.repo.update_place(place_id, name)
        if place is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Помещение не найдено",
            )
        return place

    async def delete_place(self, place_id: int):
        if await self.repo.place_has_mount_points(place_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Невозможно удалить помещение: есть связанные точки монтажа",
            )
        deleted = await self.repo.delete_place(place_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Помещение не найдено",
            )

    # ---- MountPoint CRUD ----

    async def create_mount_point(self, **kwargs):
        conflict = await self.repo.check_sensor_binding_conflicts(
            None,
            kwargs.get("temperature_sensor_id"),
            kwargs.get("pressure_sensor_id"),
            kwargs.get("humidity_sensor_id"),
        )
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict)
        return await self.repo.create_mount_point(**kwargs)

    async def update_mount_point(self, mp_id: int, **kwargs):
        conflict = await self.repo.check_sensor_binding_conflicts(
            mp_id,
            kwargs.get("temperature_sensor_id"),
            kwargs.get("pressure_sensor_id"),
            kwargs.get("humidity_sensor_id"),
        )
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict)
        mp = await self.repo.update_mount_point(mp_id, **kwargs)
        if mp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Точка монтажа не найдена",
            )
        return mp

    async def delete_mount_point(self, mp_id: int):
        if await self.repo.mount_point_has_sensors(mp_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Невозможно удалить точку монтажа: есть связанные датчики",
            )
        deleted = await self.repo.delete_mount_point(mp_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Точка монтажа не найдена",
            )

    # ---- Sensor CRUD ----

    async def get_all_sensors_detail(self):
        return await self.repo.get_all_sensors_detail()

    async def create_sensor(
        self,
        name: str,
        sensor_type_id: int,
        mount_point_id: int,
        actuator_id: int | None = None,
    ):
        return await self.repo.create_sensor(
            name, sensor_type_id, mount_point_id, actuator_id
        )

    async def update_sensor(
        self,
        sensor_id: int,
        name: str,
        sensor_type_id: int,
        mount_point_id: int,
        actuator_id: int | None = None,
    ):
        sensor = await self.repo.update_sensor(
            sensor_id, name, sensor_type_id, mount_point_id, actuator_id
        )
        if sensor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Датчик не найден",
            )
        return sensor

    async def delete_sensor(self, sensor_id: int):
        if await self.repo.sensor_has_history(sensor_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Невозможно удалить датчик: есть связанные данные",
            )
        # Clean up current values / data type config rows
        await self.repo.delete_sensor_data(sensor_id)
        deleted = await self.repo.delete_sensor(sensor_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Датчик не найден",
            )

    # ---- Sensor Offsets ----

    async def get_sensor_offsets(self, sensor_id: int):
        sensor = await self.repo.get_sensor_by_id(sensor_id)
        if sensor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Датчик не найден",
            )
        return await self.repo.get_sensor_offsets(sensor_id)

    async def update_sensor_offset(
        self, sensor_id: int, datatype_id: int, value: float
    ) -> tuple[dict, dict | None]:
        """Save offset; return (offset_dict, publish_info_or_none).

        publish_info is {mqtt_device_name, sensor_name, datatype_code, value}
        when the sensor is bound to an actuator — lets the caller trigger
        the gateway push without re-querying.
        """
        sensor = await self.repo.get_sensor_by_id(sensor_id)
        if sensor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Датчик не найден",
            )
        dt = await self.repo.get_data_type_by_id(datatype_id)
        if dt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Тип данных не найден",
            )

        await self.repo.upsert_sensor_offset(sensor_id, datatype_id, value)

        publish = None
        if sensor.actuator_id is not None:
            # Inline lookup — we need mqtt_device_name for the gateway call.
            from app.models.config import Actuator
            from sqlalchemy import select
            result = await self.repo.db.execute(
                select(Actuator.mqtt_device_name).where(Actuator.id == sensor.actuator_id)
            )
            mqtt_name = result.scalar_one_or_none()
            if mqtt_name:
                publish = {
                    "mqtt_device_name": mqtt_name,
                    "sensor_name": sensor.name,
                    "datatype_code": dt.code,
                    "value": value,
                }

        return (
            {
                "sensor_id": sensor_id,
                "datatype_id": datatype_id,
                "datatype_code": dt.code,
                "datatype_name": dt.name,
                "value": value,
            },
            publish,
        )

    # ---- Heating Circuits CRUD ----

    async def get_heating_circuits(self):
        return await self.repo.get_heating_circuits()

    async def create_heating_circuit(self, **kwargs):
        return await self.repo.create_heating_circuit(**kwargs)

    async def update_heating_circuit(self, circuit_id: int, **kwargs):
        circuit = await self.repo.update_heating_circuit(circuit_id, **kwargs)
        if circuit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Контур не найден",
            )
        return circuit

    async def delete_heating_circuit(self, circuit_id: int):
        deleted = await self.repo.delete_heating_circuit(circuit_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Контур не найден",
            )

    # ---- Pending Sensors ----

    async def get_pending_sensors(self):
        return await self.repo.get_pending_sensors()

    async def accept_pending_sensor(
        self, ps_id: int, sensor_type_id: int, mount_point_id: int
    ):
        try:
            return await self.repo.accept_pending_sensor(
                ps_id, sensor_type_id, mount_point_id
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Обнаруженный датчик не найден",
            )

    async def dismiss_pending_sensor(self, ps_id: int):
        deleted = await self.repo.delete_pending_sensor(ps_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Обнаруженный датчик не найден",
            )
