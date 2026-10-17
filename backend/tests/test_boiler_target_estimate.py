"""Dashboard estimate of the boiler auto target follows the firmware rules (boiler_logic.cpp updateBoiler)."""

import pytest

from app.models.config import ConfigKV
from app.repositories.sensor_repository import SensorRepository

BASE = {"heating_boiler_automode": "1", "heating_radiator_pump": "1", "heating_radiator_wbm": "0",
        "heating_radiator_temp": "45", "heating_floorheating_pump": "0", "watersupply_ihb_automode": "1",
        "watersupply_ihb_pump": "0", "watersupply_ihb_temp": "50", "heating_boiler_max_temp": "85"}


async def estimate(db, tank: float | None, **kv: str) -> float:
    db.add_all([ConfigKV(key=k, value=v) for k, v in {**BASE, **kv}.items()])
    await db.commit()
    return await SensorRepository(db)._compute_boiler_auto_target(None, tank)


@pytest.mark.asyncio
async def test_a_satisfied_tank_leaves_the_boiler_at_the_minimum(db_session):
    assert await estimate(db_session, 55.0) == 55            # radiators 45 → non-condensing minimum 55


@pytest.mark.asyncio
async def test_a_loading_tank_gets_15_above_its_target(db_session):
    assert await estimate(db_session, 40.0) == 65


@pytest.mark.asyncio
async def test_capped_below_the_overtemp_trip(db_session):
    assert await estimate(db_session, 40.0, heating_boiler_max_temp="70") == 63


@pytest.mark.asyncio
async def test_the_controllers_own_target_wins_over_the_estimate(db_session):
    from app.models.heating import HeatingCircuit

    db_session.add_all([ConfigKV(key=k, value=v) for k, v in BASE.items()])
    db_session.add_all([HeatingCircuit(circuit_name="Котёл", config_prefix="heating_boiler"),
                        HeatingCircuit(circuit_name="Радиаторы", config_prefix="heating_radiator")])
    await db_session.commit()
    repo = SensorRepository(db_session)
    rows = {r["config_prefix"]: r for r in
            await repo.get_heating_status(controller_targets={"boiler": 78.0, "rad": 52.3, "floor": None})}
    assert rows["heating_boiler"]["TempSet"] == 78.0
    assert rows["heating_radiator"]["TempSet"] == 52.3     # PZA on the smoothed street temperature, by the controller
    boiler = [rows["heating_boiler"]]
    estimate = [r for r in await repo.get_heating_status() if r["config_prefix"] == "heating_boiler"]
    assert [r["TempSet"] for r in estimate] == [55.0]     # offline: the estimate (radiators 45 → minimum 55)


@pytest.mark.asyncio
async def test_a_pressure_sensor_on_a_water_point_does_not_double_its_card(db_session):
    """«Холодное водоснабжение» with tswatersupply_c and prs_water bound to it: one card, the temperature's."""
    from datetime import UTC, datetime

    from app.models.sensor import MountPoint, Place, Sensor, SensorData, SensorDataType, SensorType, SystemType

    db_session.add_all([SystemType(id=2, name="Водоснабжение"), Place(id=1, name="Котельная"),
                        SensorType(id=1, name="t"), SensorType(id=2, name="A2"),
                        SensorDataType(id=1, name="Temperature", code="tmp"), SensorDataType(id=2, name="Pressure", code="prs")])
    await db_session.flush()
    db_session.add_all([MountPoint(id=9, name="Холодное водоснабжение", system_id=2, place_id=1),
                        MountPoint(id=10, name="Горячее водоснабжение", system_id=2, place_id=1)])
    await db_session.flush()
    db_session.add_all([Sensor(id=9, name="tswatersupply_c", sensor_type_id=1, mount_point_id=9),
                        Sensor(id=10, name="tswatersupply_h", sensor_type_id=1, mount_point_id=10),
                        Sensor(id=18, name="prs_water", sensor_type_id=2, mount_point_id=9)])
    await db_session.flush()
    for mp, t, p in ((9, 9, 18), (10, 10, None)):
        point = await db_session.get(MountPoint, mp)
        point.temperature_sensor_id, point.pressure_sensor_id = t, p
    now = datetime.now(UTC)
    db_session.add_all([SensorData(sensor_id=9, datatype_id=1, value=7.1, timestamp=now),
                        SensorData(sensor_id=10, datatype_id=1, value=55.0, timestamp=now),
                        SensorData(sensor_id=18, datatype_id=2, value=3.0, timestamp=now),
                        ConfigKV(key="watersupply_ihb_temp", value="55")])
    await db_session.commit()
    rows = await SensorRepository(db_session).get_water_supply_status()
    assert sorted((r["type"], r["tempFact"], r["is_tank"]) for r in rows) == [
        ("Горячее водоснабжение", 55.0, True), ("Холодное водоснабжение", 7.1, False)]
