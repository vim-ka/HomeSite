from fastapi import HTTPException, status

from app.repositories.catalog_repository import CatalogRepository


class CatalogService:
    def __init__(self, repo: CatalogRepository):
        self.repo = repo

    # ---- Reference data ----

    async def get_system_types(self):
        return await self.repo.get_system_types()

    async def get_sensor_types(self):
        return await self.repo.get_sensor_types()

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

    async def create_mount_point(self, name: str, system_id: int, place_id: int):
        return await self.repo.create_mount_point(name, system_id, place_id)

    async def update_mount_point(self, mp_id: int, name: str, system_id: int, place_id: int):
        mp = await self.repo.update_mount_point(mp_id, name, system_id, place_id)
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
        self, name: str, sensor_type_id: int, mount_point_id: int, datatype_ids: list[int] | None = None
    ):
        sensor = await self.repo.create_sensor(name, sensor_type_id, mount_point_id)
        if datatype_ids:
            await self.repo.set_sensor_datatypes(sensor.id, datatype_ids)
        return sensor

    async def update_sensor(
        self,
        sensor_id: int,
        name: str,
        sensor_type_id: int,
        mount_point_id: int,
        datatype_ids: list[int] | None = None,
    ):
        sensor = await self.repo.update_sensor(sensor_id, name, sensor_type_id, mount_point_id)
        if sensor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Датчик не найден",
            )
        if datatype_ids is not None:
            await self.repo.set_sensor_datatypes(sensor_id, datatype_ids)
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

    # ---- Pending Sensors ----

    async def get_pending_sensors(self):
        return await self.repo.get_pending_sensors()

    async def accept_pending_sensor(
        self, ps_id: int, sensor_type_id: int, mount_point_id: int, datatype_ids: list[int]
    ):
        try:
            return await self.repo.accept_pending_sensor(
                ps_id, sensor_type_id, mount_point_id, datatype_ids
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
