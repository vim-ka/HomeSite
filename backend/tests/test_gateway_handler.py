"""Tests for MQTTHandler — message parsing, DB upsert, device lookup."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.sensor import (
    MountPoint,
    Place,
    Sensor,
    SensorData,
    SensorDataHistory,
    SensorDataType,
    SensorType,
    SystemType,
)
from device_gateway.config import GatewaySettings
from device_gateway.handler import MQTTHandler


@pytest_asyncio.fixture
async def seeded_handler_data(db_session):
    """Seed minimal sensor data for handler tests."""
    db_session.add_all([
        SystemType(id=1, name="Отопление"),
        Place(id=1, name="Котельная"),
        SensorType(id=1, name="18B10"),
        SensorDataType(id=1, name="Temperature", code="tmp"),
        SensorDataType(id=2, name="Pressure", code="prs"),
    ])
    await db_session.flush()

    db_session.add(MountPoint(id=1, name="Котел, подача", system_id=1, place_id=1))
    await db_session.flush()

    db_session.add(Sensor(id=1, name="tsboiler_s", sensor_type_id=1, mount_point_id=1))
    await db_session.commit()


class FakeMessage:
    """Mimics aiomqtt.Message."""

    def __init__(self, topic: str, payload: dict):
        self.topic = topic
        self.payload = json.dumps(payload).encode()


@pytest.mark.asyncio
async def test_handle_known_device(engine, db_session, seeded_handler_data):
    """Handler should upsert SensorData and append SensorDataHistory for known device."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = GatewaySettings(
        mqtt_broker_host="127.0.0.1",
        backend_url="http://localhost:99999",  # won't actually connect
    )
    handler = MQTTHandler(settings, session_factory)

    msg = FakeMessage("home/devices/tsboiler_s", {"tmp": 55.5})
    await handler._handle_message(msg)

    # Check SensorData was upserted
    result = await db_session.execute(
        select(SensorData).where(SensorData.sensor_id == 1, SensorData.datatype_id == 1)
    )
    sd = result.scalar_one()
    assert sd.value == 55.5

    # Check history was appended
    result2 = await db_session.execute(
        select(SensorDataHistory).where(SensorDataHistory.sensor_id == 1)
    )
    history = result2.scalars().all()
    assert len(history) == 1
    assert history[0].value == 55.5


@pytest.mark.asyncio
async def test_handle_unknown_device(engine, db_session, seeded_handler_data):
    """Handler should skip unknown device names without error."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = GatewaySettings(backend_url="http://localhost:99999")
    handler = MQTTHandler(settings, session_factory)

    msg = FakeMessage("home/devices/unknown_sensor_xyz", {"tmp": 99.9})
    await handler._handle_message(msg)

    # No data should be written
    result = await db_session.execute(select(SensorData))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_handle_multiple_params(engine, db_session, seeded_handler_data):
    """Handler should process multiple params in a single message."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = GatewaySettings(backend_url="http://localhost:99999")
    handler = MQTTHandler(settings, session_factory)

    msg = FakeMessage("home/devices/tsboiler_s", {"tmp": 45.0, "prs": 1.2})
    await handler._handle_message(msg)

    result = await db_session.execute(select(SensorData))
    data = result.scalars().all()
    assert len(data) == 2

    values = {d.datatype_id: d.value for d in data}
    assert values[1] == 45.0
    assert values[2] == 1.2


@pytest.mark.asyncio
async def test_upsert_overwrites(engine, db_session, seeded_handler_data):
    """Second message for same sensor+datatype should update, not duplicate."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = GatewaySettings(backend_url="http://localhost:99999")
    handler = MQTTHandler(settings, session_factory)

    msg1 = FakeMessage("home/devices/tsboiler_s", {"tmp": 50.0})
    await handler._handle_message(msg1)

    msg2 = FakeMessage("home/devices/tsboiler_s", {"tmp": 55.5})
    await handler._handle_message(msg2)

    # SensorData should have 1 row with latest value
    result = await db_session.execute(
        select(SensorData).where(SensorData.sensor_id == 1, SensorData.datatype_id == 1)
    )
    sd = result.scalar_one()
    assert sd.value == 55.5

    # History should have 2 rows
    result2 = await db_session.execute(select(SensorDataHistory))
    assert len(result2.scalars().all()) == 2
