from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor import MountPoint, Place, Sensor, SensorDataHistory

# Target max data points per chart to keep frontend responsive
MAX_POINTS = 500


class ChartRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_history(
        self,
        datatype_id: int,
        start: datetime,
        end: datetime,
        sensor_ids: list[int] | None = None,
        system_id: int | None = None,
    ) -> dict:
        """Fetch SensorDataHistory and return chart-ready {labels, datasets}."""
        stmt = (
            select(
                SensorDataHistory.sensor_id,
                SensorDataHistory.timestamp,
                SensorDataHistory.value,
            )
            .where(
                SensorDataHistory.datatype_id == datatype_id,
                SensorDataHistory.timestamp >= start,
                SensorDataHistory.timestamp <= end,
            )
            .order_by(SensorDataHistory.timestamp)
        )

        if sensor_ids:
            stmt = stmt.where(SensorDataHistory.sensor_id.in_(sensor_ids))

        if system_id is not None:
            system_sensor_ids = select(Sensor.id).join(
                MountPoint, Sensor.mount_point_id == MountPoint.id
            ).where(MountPoint.system_id == system_id)
            stmt = stmt.where(SensorDataHistory.sensor_id.in_(system_sensor_ids))

        result = await self.db.execute(stmt)
        rows = result.all()

        # Group by sensor_id, collect timestamps
        labels_set: set[str] = set()
        sensor_data: dict[int, dict[str, float]] = defaultdict(dict)

        for row in rows:
            ts = row.timestamp.strftime("%Y-%m-%d %H:%M:%S") if isinstance(row.timestamp, datetime) else str(row.timestamp)
            labels_set.add(ts)
            sensor_data[row.sensor_id][ts] = row.value

        labels = sorted(labels_set)

        # Downsample if too many points
        if len(labels) > MAX_POINTS:
            step = len(labels) / MAX_POINTS
            sampled = [labels[int(i * step)] for i in range(MAX_POINTS)]
            labels = sampled

        # Resolve sensor labels: "Place (MountPoint)"
        sensor_names = {}
        if sensor_data:
            name_result = await self.db.execute(
                select(Sensor.id, Place.name.label("place_name"), MountPoint.name.label("mount_name"))
                .join(MountPoint, Sensor.mount_point_id == MountPoint.id)
                .join(Place, MountPoint.place_id == Place.id)
                .where(Sensor.id.in_(list(sensor_data.keys())))
            )
            for row in name_result:
                sensor_names[row.id] = f"{row.place_name} ({row.mount_name})"

        datasets = [
            {
                "label": sensor_names.get(sid, f"Датчик {sid}"),
                "data": [values.get(ts) for ts in labels],
            }
            for sid, values in sensor_data.items()
        ]

        return {"labels": labels, "datasets": datasets}
