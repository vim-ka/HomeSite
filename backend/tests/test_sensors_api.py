import pytest

from app.core.security import get_password_hash
from app.models.config import ConfigKV
from app.models.heating import HeatingCircuit
from app.models.sensor import (
    MountPoint,
    Place,
    Sensor,
    SensorData,
    SensorDataType,
    SensorType,
    SystemType,
)
from app.models.user import User, UserRole


@pytest.fixture
async def seeded_data(db_session):
    """Seed minimal data for sensor tests."""
    # System types
    db_session.add_all([
        SystemType(id=1, name="Отопление"),
        SystemType(id=2, name="Водоснабжение"),
        SystemType(id=3, name="Климат"),
    ])
    await db_session.flush()

    # Places
    db_session.add_all([
        Place(id=1, name="Котельная"),
        Place(id=2, name="Гостиная"),
        Place(id=7, name="Улица"),
    ])
    await db_session.flush()

    # Sensor types & data types
    db_session.add_all([
        SensorType(id=1, name="18B10"),
        SensorDataType(id=1, name="Temperature", code="tmp"),
        SensorDataType(id=2, name="Pressure", code="prs"),
        SensorDataType(id=3, name="Humidity", code="hmt"),
    ])
    await db_session.flush()

    # Mount points (create without sensor bindings first)
    mp1 = MountPoint(id=1, name="Котел, подача", system_id=1, place_id=1)
    mp2 = MountPoint(id=2, name="Котел, возврат", system_id=1, place_id=1)
    mp16 = MountPoint(id=16, name="У камина", system_id=3, place_id=2)
    db_session.add_all([mp1, mp2, mp16])
    await db_session.flush()

    # Sensors
    db_session.add_all([
        Sensor(id=1, name="tsboiler_s", sensor_type_id=1, mount_point_id=1),
        Sensor(id=2, name="tsboiler_b", sensor_type_id=1, mount_point_id=2),
        Sensor(id=16, name="clm_gost_th", sensor_type_id=1, mount_point_id=16),
    ])
    await db_session.flush()

    # Set explicit sensor bindings on mount points
    mp1.temperature_sensor_id = 1
    mp2.temperature_sensor_id = 2
    mp16.temperature_sensor_id = 16
    await db_session.flush()

    # Sensor data (current values)
    from datetime import datetime, UTC
    now = datetime.now(UTC)
    db_session.add_all([
        SensorData(sensor_id=1, datatype_id=1, value=55.2, timestamp=now),
        SensorData(sensor_id=2, datatype_id=1, value=42.1, timestamp=now),
        SensorData(sensor_id=16, datatype_id=1, value=22.5, timestamp=now),
        SensorData(sensor_id=16, datatype_id=3, value=45.0, timestamp=now),
    ])

    # Config
    db_session.add_all([
        ConfigKV(key="heating_boiler_temp", value="50"),
        ConfigKV(key="heating_boiler_power", value="1"),
    ])

    # Heating circuit
    db_session.add(HeatingCircuit(
        circuit_name="Котёл",
        supply_mount_point_id=1,
        return_mount_point_id=2,
        delta_threshold=5.0,
        config_temp_key="heating_boiler_temp",
        config_pump_key="heating_boiler_power",
        display_order=1,
    ))

    # User
    db_session.add(User(
        username="admin",
        password_hash=get_password_hash("admin123"),
        email="admin@test.com",
        role=UserRole.ADMIN.value,
    ))

    await db_session.commit()


async def _get_token(client) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_dashboard(client, seeded_data):
    token = await _get_token(client)
    response = await client.get(
        "/api/v1/sensors/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "climate" in data
    assert "heating" in data
    assert "water_supply" in data
    assert "stats" in data

    # Should have at least one heating circuit
    assert len(data["heating"]) >= 1
    boiler = data["heating"][0]
    assert boiler["circuit"] == "Котёл"
    assert boiler["temp_set"] == 50.0
    assert boiler["temp_supply"] == 55.2
    assert boiler["temp_return"] == 42.1


@pytest.mark.asyncio
async def test_list_sensors(client, seeded_data):
    token = await _get_token(client)
    response = await client.get(
        "/api/v1/sensors",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    sensors = response.json()
    assert len(sensors) >= 3
    names = {s["name"] for s in sensors}
    assert "tsboiler_s" in names
    assert "clm_gost_th" in names


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client):
    response = await client.get("/api/v1/sensors/dashboard")
    assert response.status_code in (401, 403)
