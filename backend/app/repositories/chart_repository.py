from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor import Sensor, SensorDataHistory


class ChartRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_history(
        self,
        datatype_id: int,
        start: datetime,
        end: datetime,
        sensor_ids: list[int] | None = None,
    ) -> dict:
        """Fetch SensorDataHistory and return chart-ready {labels, datasets}.

        Replaces both get_sensor_data_by_type() and fetch_chart_data() from v1.
        """
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

        # Resolve sensor names
        sensor_names = {}
        if sensor_data:
            name_result = await self.db.execute(
                select(Sensor.id, Sensor.name).where(
                    Sensor.id.in_(list(sensor_data.keys()))
                )
            )
            sensor_names = {row.id: row.name for row in name_result}

        datasets = [
            {
                "label": sensor_names.get(sid, f"Датчик {sid}"),
                "data": [values.get(ts) for ts in labels],
            }
            for sid, values in sensor_data.items()
        ]

        return {"labels": labels, "datasets": datasets}
