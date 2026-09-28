from datetime import UTC, datetime, timedelta

from app.repositories.chart_repository import ChartRepository
from app.services.pza import get_pza_target


# PZA curve charts are generated from app.services.pza — the same curves the
# firmware and the heating page use (the old hardcoded copy had drifted)
PZA_CHART_OUTDOOR = list(range(20, -40, -5))  # 20, 15, ..., -35
DEFAULT_PZA_CURVE = 3
# Longest history a single chart request may cover
MAX_CHART_DAYS = 3660


def _pza_chart(circuit_type: str, label: str) -> dict:
    return {
        "labels": [str(t) for t in PZA_CHART_OUTDOOR],
        "datasets": [
            {
                "label": label,
                "data": [get_pza_target(circuit_type, DEFAULT_PZA_CURVE, t) for t in PZA_CHART_OUTDOOR],
            }
        ],
    }


PZA_RADIATORS = _pza_chart("radiator", "Кривая ПЗА (радиаторы)")
PZA_FLOOR = _pza_chart("floor", "Кривая ПЗА (тёплый пол)")

# Mapping: chart param → (SensorDataType.id, system_id or None)
CHART_CONFIG = {
    "ChartTemperature": {"datatype_id": 1, "system_id": 3},          # Climate temperatures
    "ChartPressureAtmo": {"datatype_id": 2, "system_id": 3},         # Atmospheric pressure (climate)
    "ChartPressureSystem": {"datatype_id": 2, "system_id": 1},       # Heating system pressure
    "ChartPressure": {"datatype_id": 2},                              # Legacy: all pressure (backwards compat)
    "ChartHumidity": {"datatype_id": 3, "system_id": 3},             # Humidity (climate)
    "ChartHeating": {"datatype_id": 1, "system_id": 1},               # Heating system temperatures
}


class ChartService:
    def __init__(self, chart_repo: ChartRepository):
        self.chart_repo = chart_repo

    async def get_chart_data(
        self,
        chart_type: str,
        start: datetime | None = None,
        end: datetime | None = None,
        default_days: int = 100,
    ) -> dict:
        """Return chart data. Static for PZA curves, dynamic for sensor history."""

        if chart_type == "ChartRadiators":
            return PZA_RADIATORS

        if chart_type == "ChartHeatFloor":
            return PZA_FLOOR

        config = CHART_CONFIG.get(chart_type)
        if config is None:
            return {"labels": [], "datasets": []}

        if end is None:
            end = datetime.now(UTC)
        if start is None:
            start = end - timedelta(days=default_days)
        if end < start:
            start, end = end, start
        if end - start > timedelta(days=MAX_CHART_DAYS):
            start = end - timedelta(days=MAX_CHART_DAYS)

        return await self.chart_repo.get_history(
            datatype_id=config["datatype_id"],
            start=start,
            end=end,
            sensor_ids=config.get("sensor_ids"),
            system_id=config.get("system_id"),
        )
