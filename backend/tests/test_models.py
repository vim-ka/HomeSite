import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.config import ConfigKV, Schedule, ScheduleDetail
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


@pytest.mark.asyncio
async def test_create_user(db_session):
    user = User(
        username="testuser",
        password_hash=get_password_hash("pass123"),
        email="test@example.com",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.username == "testuser"))
    fetched = result.scalar_one()
    assert fetched.username == "testuser"
    assert fetched.role == "viewer"
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_sensor_chain(db_session):
    """Test creating the full sensor reference chain: SystemType → Place → MountPoint → Sensor."""
    sys_type = SystemType(id=100, name="TestSystem")
    place = Place(id=100, name="TestPlace")
    sensor_type = SensorType(id=100, name="TestType")
    data_type = SensorDataType(id=100, name="TestData", code="tst")

    db_session.add_all([sys_type, place, sensor_type, data_type])
    await db_session.flush()

    mp = MountPoint(id=100, name="TestMount", system_id=100, place_id=100)
    db_session.add(mp)
    await db_session.flush()

    sensor = Sensor(id=100, name="test_sensor", sensor_type_id=100, mount_point_id=100)
    db_session.add(sensor)
    await db_session.flush()

    # Verify relationships
    result = await db_session.execute(
        select(Sensor).where(Sensor.id == 100)
    )
    fetched = result.scalar_one()
    assert fetched.name == "test_sensor"


@pytest.mark.asyncio
async def test_config_kv(db_session):
    kv = ConfigKV(key="test_key", value="test_value")
    db_session.add(kv)
    await db_session.commit()

    result = await db_session.execute(select(ConfigKV).where(ConfigKV.key == "test_key"))
    fetched = result.scalar_one()
    assert fetched.value == "test_value"


@pytest.mark.asyncio
async def test_heating_circuit_with_sensors(db_session):
    """Test HeatingCircuit with sensor bindings."""
    sys_type = SystemType(id=200, name="Heating")
    place = Place(id=200, name="Boiler Room")
    sensor_type = SensorType(id=200, name="18B10")
    db_session.add_all([sys_type, place, sensor_type])
    await db_session.flush()

    mp1 = MountPoint(id=200, name="Supply", system_id=200, place_id=200)
    mp2 = MountPoint(id=201, name="Return", system_id=200, place_id=200)
    db_session.add_all([mp1, mp2])
    await db_session.flush()

    s1 = Sensor(id=200, name="supply_sensor", sensor_type_id=200, mount_point_id=200)
    s2 = Sensor(id=201, name="return_sensor", sensor_type_id=200, mount_point_id=201)
    db_session.add_all([s1, s2])
    await db_session.flush()

    circuit = HeatingCircuit(
        circuit_name="Test Circuit",
        supply_mount_point_id=200,
        return_mount_point_id=201,
        delta_threshold=5.0,
        config_temp_key="heating_test_temp",
        config_pump_key="heating_test_pump",
    )
    db_session.add(circuit)
    await db_session.commit()

    result = await db_session.execute(
        select(HeatingCircuit).where(HeatingCircuit.circuit_name == "Test Circuit")
    )
    fetched = result.scalar_one()
    assert fetched.supply_mount_point_id == 200
    assert fetched.return_mount_point_id == 201
    assert fetched.delta_threshold == 5.0
