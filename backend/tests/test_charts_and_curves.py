"""Chart aggregation and PZA curve consistency across backend / frontend / firmware."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.models.sensor import MountPoint, Place, Sensor, SensorDataHistory, SensorDataType, SensorType, SystemType
from app.repositories.chart_repository import ChartRepository
from app.services import pza

ROOT = Path(__file__).resolve().parents[2]


def _numbers(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", text)]


def test_pza_curves_match_frontend_and_firmware():
    """Four copies of the curves exist (backend, web, firmware, charts) — keep them identical."""
    ts = (ROOT / "frontend/src/lib/pzaCurves.ts").read_text(encoding="utf-8")
    cpp = (ROOT / "firmware/esp32-homesite/src/pza_controller.cpp").read_text(encoding="utf-8")
    for curves, ts_name, cpp_name in (
        (pza.RADIATOR_CURVES, "RADIATOR_CURVES", "_radiatorCurves"),
        (pza.FLOOR_CURVES, "FLOOR_CURVES", "_floorCurves"),
    ):
        flat = [float(v) for curve in curves for v in curve]
        ts_block = re.search(rf"{ts_name}: PZACurve\[\] = makeCurves\(\[(.*?)\]\);", ts, re.S)
        assert ts_block, f"{ts_name} not found in pzaCurves.ts"
        assert _numbers(ts_block.group(1)) == flat
        cpp_block = re.search(rf"{cpp_name}\[PZA_NUM_CURVES\]\s*=\s*\{{(.*?)\n\}};", cpp, re.S)
        assert cpp_block, f"{cpp_name} not found in firmware"
        assert _numbers(cpp_block.group(1)) == flat


@pytest.mark.asyncio
async def test_chart_buckets_align_series(db_session):
    db_session.add_all([
        SystemType(id=3, name="Климат"), Place(id=1, name="Дом"),
        SensorType(id=1, name="t"), SensorDataType(id=1, name="Temperature", code="tmp"),
    ])
    await db_session.flush()
    db_session.add_all([
        MountPoint(id=1, name="A", system_id=3, place_id=1),
        MountPoint(id=2, name="B", system_id=3, place_id=1),
    ])
    await db_session.flush()
    db_session.add_all([
        Sensor(id=1, name="s1", sensor_type_id=1, mount_point_id=1),
        Sensor(id=2, name="s2", sensor_type_id=1, mount_point_id=2),
    ])
    await db_session.flush()

    start = datetime(2026, 9, 1, tzinfo=UTC)
    # Two sensors writing at different seconds, one sample per 10 s for 2 hours
    for i in range(720):
        t = start + timedelta(seconds=10 * i)
        db_session.add(SensorDataHistory(sensor_id=1, datatype_id=1, value=20.0, timestamp=t + timedelta(seconds=1)))
        db_session.add(SensorDataHistory(sensor_id=2, datatype_id=1, value=22.0, timestamp=t + timedelta(seconds=6)))
    await db_session.commit()

    data = await ChartRepository(db_session).get_history(1, start, start + timedelta(hours=2), system_id=3)
    assert 1 < len(data["labels"]) <= 500
    assert data["labels"][0].endswith("Z")
    for ds in data["datasets"]:
        filled = [v for v in ds["data"] if v is not None]
        # every bucket has a value for every series (old downsampling left gaps)
        assert len(filled) >= len(data["labels"]) - 1


async def test_difference_charts_per_circuit_and_the_boiler_return(db_session):
    """ChartDeltas: supply − return of each circuit (the coil: its loading pipes); ChartBoilerReturn."""
    from app.models.heating import HeatingCircuit
    from app.services.chart_service import ChartService

    db_session.add_all([SystemType(id=1, name="Отопление"), Place(id=1, name="Котельная"),
                        SensorType(id=1, name="t"), SensorDataType(id=1, name="Temperature", code="tmp")])
    await db_session.flush()
    points = {1: "Котел, подача", 2: "Котел, возврат", 3: "Радиаторы, подача", 4: "Радиаторы, возврат",
              7: "БКН, подача", 8: "БКН, возврат"}
    db_session.add_all([MountPoint(id=i, name=n, system_id=1, place_id=1) for i, n in points.items()])
    await db_session.flush()
    db_session.add_all([Sensor(id=i, name=f"s{i}", sensor_type_id=1, mount_point_id=i) for i in points])
    await db_session.flush()
    for i in points:
        (await db_session.get(MountPoint, i)).temperature_sensor_id = i
    db_session.add_all([
        HeatingCircuit(circuit_name="Котёл", config_prefix="heating_boiler", supply_mount_point_id=1, return_mount_point_id=2),
        HeatingCircuit(circuit_name="Радиаторы", config_prefix="heating_radiator", supply_mount_point_id=3, return_mount_point_id=4),
        HeatingCircuit(circuit_name="БКН", config_prefix="watersupply_ihb", supply_mount_point_id=7, return_mount_point_id=8),
    ])
    start = datetime(2026, 9, 1, tzinfo=UTC)
    temps = {1: 70.0, 2: 58.0, 3: 55.0, 4: 43.5, 7: 65.0, 8: 52.0}   # 7/8: the loading pipes (tsihb_s / tsihb_b)
    for k in range(60):
        t = start + timedelta(minutes=k)
        db_session.add_all([SensorDataHistory(sensor_id=i, datatype_id=1, value=v, timestamp=t) for i, v in temps.items()])
    await db_session.commit()

    service = ChartService(ChartRepository(db_session))
    deltas = await service.get_chart_data("ChartDeltas", start, start + timedelta(hours=1))
    series = {d["label"]: {v for v in d["data"] if v is not None} for d in deltas["datasets"]}
    assert series == {"Котёл": {12.0}, "Радиаторы": {11.5}, "Змеевик бойлера": {13.0}}   # no floor circuit here
    ret = await service.get_chart_data("ChartBoilerReturn", start, start + timedelta(hours=1))
    assert [d["label"] for d in ret["datasets"]] == ["Обратка котла"]
    assert {v for v in ret["datasets"][0]["data"] if v is not None} == {58.0}
