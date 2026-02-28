from pydantic import BaseModel


class ChartDataset(BaseModel):
    label: str
    data: list[float | None]


class ChartDataResponse(BaseModel):
    labels: list[str]
    datasets: list[ChartDataset]
