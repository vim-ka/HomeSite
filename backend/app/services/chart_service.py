from datetime import datetime, timedelta

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

# Mapping: chart param → SensorDataType.id
CHART_DATATYPE_MAP = {
    "ChartTemperature": 1,
    "ChartPressure": 2,
    "ChartHumidity": 3,
    "ChartHeating": 1,  # temperature, but filtered to heating sensors
}

# Heating sensor IDs (supply sensors for 4 circuits)
HEATING_SENSOR_IDS = [1, 3, 5, 7]


class ChartService:
    def __init__(self, chart_repo: ChartRepository):
        self.chart_repo = chart_repo

    async def get_chart_data(
        self,
        chart_type: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict:
        """Return chart data. Static for PZA curves, dynamic for sensor history."""

        if chart_type == "ChartRadiators":
            return PZA_RADIATORS

        if chart_type == "ChartHeatFloor":
            return PZA_FLOOR

        datatype_id = CHART_DATATYPE_MAP.get(chart_type)
        if datatype_id is None:
            return {"labels": [], "datasets": []}

        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=100)

        sensor_ids = HEATING_SENSOR_IDS if chart_type == "ChartHeating" else None
        return await self.chart_repo.get_history(datatype_id, start, end, sensor_ids)
