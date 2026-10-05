from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heating import HeatingCircuit
from app.models.sensor import MountPoint, Place, Sensor, SensorDataHistory

# Target max data points per chart to keep frontend responsive
MAX_POINTS = 500
MIN_BUCKET_SECONDS = 60


class ChartRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _epoch_bucket(self, step: int):
        """SQL expression: bucket index = floor(epoch(timestamp) / step)."""
        ts = SensorDataHistory.timestamp
        if self.db.bind.dialect.name == "postgresql":
            return func.floor(func.extract("epoch", ts) / step)
        # SQLite stores naive UTC text; strftime('%s') treats it as UTC
        return cast(func.strftime("%s", ts), Integer) / step

    @staticmethod
    def _labels(ordered: list[int], step: int) -> list[str]:
        return [datetime.fromtimestamp(b * step, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ") for b in ordered]

    async def _bucketed(self, stmt, step: int) -> tuple[list[int], int, dict[int, dict[int, float]]]:
        """Run a (sensor_id, bucket, value) query: sorted buckets and each sensor's value per bucket."""
        rows = (await self.db.execute(stmt)).all()
        buckets: set[int] = set()
        sensor_data: dict[int, dict[int, float]] = defaultdict(dict)
        for row in rows:
            b = int(row.bucket)
            buckets.add(b)
            sensor_data[row.sensor_id][b] = round(float(row.value), 2)
        return sorted(buckets), step, sensor_data

    async def circuit_sensors(self) -> dict[str, tuple[int | None, int | None]]:
        """config_prefix → (supply, return) temperature sensor ids from the circuits' mount points."""
        circuits = (await self.db.execute(select(HeatingCircuit))).scalars().all()
        mp_ids = {i for c in circuits for i in (c.supply_mount_point_id, c.return_mount_point_id) if i}
        temp = {mp.id: mp.temperature_sensor_id for mp in
                (await self.db.execute(select(MountPoint).where(MountPoint.id.in_(mp_ids)))).scalars()} if mp_ids else {}
        return {c.config_prefix: (temp.get(c.supply_mount_point_id), temp.get(c.return_mount_point_id))
                for c in circuits if c.config_prefix}

    async def get_differences(self, pairs: list[tuple[str, int, int]], start: datetime, end: datetime) -> dict:
        """Chart-ready supply − return per (label, supply sensor, return sensor), bucketed like get_history."""
        ids = sorted({sid for _, a, b in pairs for sid in (a, b)})
        if not ids:
            return {"labels": [], "datasets": []}
        span = max(1.0, (end - start).total_seconds())
        step = max(MIN_BUCKET_SECONDS, int(span // MAX_POINTS) + 1)
        bucket = self._epoch_bucket(step).label("bucket")
        stmt = (
            select(SensorDataHistory.sensor_id, bucket, func.avg(SensorDataHistory.value).label("value"))
            .where(SensorDataHistory.datatype_id == 1, SensorDataHistory.sensor_id.in_(ids),
                   SensorDataHistory.timestamp >= start, SensorDataHistory.timestamp <= end)
            .group_by(SensorDataHistory.sensor_id, bucket)
        )
        ordered, step, data = await self._bucketed(stmt, step)
        datasets = []
        for label, sup, ret in pairs:
            a, b = data.get(sup, {}), data.get(ret, {})
            values = [round(a[t] - b[t], 2) if t in a and t in b else None for t in ordered]
            if any(v is not None for v in values):
                datasets.append({"label": label, "data": values})
        return {"labels": self._labels(ordered, step), "datasets": datasets}

    async def get_history(
        self,
        datatype_id: int,
        start: datetime,
        end: datetime,
        sensor_ids: list[int] | None = None,
        system_id: int | None = None,
    ) -> dict:
        """Chart-ready {labels, datasets} averaged into at most MAX_POINTS time buckets.

        Aggregation happens in SQL: every series gets a value in every bucket it
        has data for, instead of the old approach (load all rows, then keep 500
        of the union of per-sensor timestamps), which left multi-series charts
        mostly empty because each sensor writes at its own second.
        Labels are ISO-8601 UTC with "Z".
        """
        span = max(1.0, (end - start).total_seconds())
        step = max(MIN_BUCKET_SECONDS, int(span // MAX_POINTS) + 1)
        bucket = self._epoch_bucket(step).label("bucket")

        stmt = (
            select(SensorDataHistory.sensor_id, bucket, func.avg(SensorDataHistory.value).label("value"))
            .where(
                SensorDataHistory.datatype_id == datatype_id,
                SensorDataHistory.timestamp >= start,
                SensorDataHistory.timestamp <= end,
            )
            .group_by(SensorDataHistory.sensor_id, bucket)
        )

        if sensor_ids:
            stmt = stmt.where(SensorDataHistory.sensor_id.in_(sensor_ids))

        if system_id is not None:
            system_sensor_ids = select(Sensor.id).join(
                MountPoint, Sensor.mount_point_id == MountPoint.id
            ).where(MountPoint.system_id == system_id)
            stmt = stmt.where(SensorDataHistory.sensor_id.in_(system_sensor_ids))

        ordered, step, sensor_data = await self._bucketed(stmt, step)
        labels = self._labels(ordered, step)

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
                "data": [values.get(b) for b in ordered],
            }
            for sid, values in sensor_data.items()
        ]

        return {"labels": labels, "datasets": datasets}
