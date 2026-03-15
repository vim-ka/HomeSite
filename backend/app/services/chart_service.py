from datetime import UTC, datetime, timedelta

from app.repositories.chart_repository import ChartRepository


# Static PZA curve data (default curve 3)
PZA_RADIATORS = {
    "labels": ["20", "15", "10", "5", "0", "-5", "-10", "-15", "-20", "-25", "-30", "-35"],
    "datasets": [
        {
            "label": "Кривая ПЗА (радиаторы)",
            "data": [20, 31, 38, 44, 48, 52, 56, 60, 64, 67, 69, 70],
        }
    ],
}

PZA_FLOOR = {
    "labels": ["20", "15", "10", "5", "0", "-5", "-10", "-15", "-20", "-25", "-30", "-35"],
    "datasets": [
        {
            "label": "Кривая ПЗА (тёплый пол)",
            "data": [20, 22, 24, 25.5, 27, 28.5, 30, 31.5, 33, 34, 35, 36],
        }
    ],
}

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

        return await self.chart_repo.get_history(
            datatype_id=config["datatype_id"],
            start=start,
            end=end,
            sensor_ids=config.get("sensor_ids"),
            system_id=config.get("system_id"),
        )
