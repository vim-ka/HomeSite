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


@pytest.mark.asyncio
async def test_heartbeat_detects_boot_and_reboot(engine):
    """First heartbeat after gateway start and any uptime decrease trigger a resync."""
    import asyncio
    from sqlalchemy.ext.asyncio import async_sessionmaker

    booted: list[str] = []

    async def on_boot(name: str) -> None:
        booted.append(name)

    handler = MQTTHandler(
        GatewaySettings(mqtt_broker_host="127.0.0.1"),
        async_sessionmaker(engine, expire_on_commit=False),
        on_device_boot=on_boot,
    )
    for uptime in (100, 110, 120):
        await handler._handle_message(FakeMessage("home/devices/boiler_unit/heartbeat", {"uptime": uptime}))
    await asyncio.sleep(0)
    assert booted == ["boiler_unit"]  # first seen only

    await handler._handle_message(FakeMessage("home/devices/boiler_unit/heartbeat", {"uptime": 3}))
    await asyncio.sleep(0)
    assert booted == ["boiler_unit", "boiler_unit"]  # reboot detected
    await handler.close()


@pytest.mark.asyncio
async def test_resync_routes_only_device_keys(engine, db_session):
    """resync_device queues exactly the config_kv keys routed to the device."""
    from device_gateway.dispatcher import AsyncCommandDispatcher
    from device_gateway.sync import resync_device

    from app.models.config import ConfigKV
    from app.models.heating import HeatingCircuit

    db_session.add_all([
        HeatingCircuit(circuit_name="Котёл", config_prefix="heating_boiler", mqtt_device_name="boiler_unit"),
        HeatingCircuit(circuit_name="ВС", config_prefix="watersupply", mqtt_device_name="water_unit"),
        ConfigKV(key="heating_boiler_temp", value="60"),
        ConfigKV(key="heating_boiler_power", value="0"),
        ConfigKV(key="watersupply_pump", value="1"),
        ConfigKV(key="mqtt_pass", value="secret"),
    ])
    await db_session.commit()

    class Pub:
        async def publish_grouped(self, *a):
            pass

    d = AsyncCommandDispatcher(Pub(), debounce_seconds=10)
    url = str(engine.url)
    n = await resync_device(d, url, "boiler_unit")
    assert n == 2
    assert await d.pending_for("boiler_unit") == {"heating_boiler_temp": "60", "heating_boiler_power": "0"}
    assert await d.pending_for("water_unit") == {}
    await d.shutdown()


@pytest.mark.asyncio
async def test_outdoor_temp_forwarded_to_controller(engine):
    import asyncio
    from sqlalchemy.ext.asyncio import async_sessionmaker

    class Client:
        def __init__(self):
            self.sent = []

        async def publish(self, topic, payload, qos=0, retain=False):
            self.sent.append((topic, json.loads(payload), retain))

    handler = MQTTHandler(GatewaySettings(), async_sessionmaker(engine, expire_on_commit=False))
    handler._connected = True
    handler._active_client = Client()
    handler.outdoor_forward = ("clm_street_th", "boiler_unit")

    handler._forward_outdoor("clm_kitchen_th", {"tmp": "21.0"})
    handler._forward_outdoor("clm_street_th", {"tmp": "-7.5", "hmt": "80"})
    await asyncio.sleep(0)
    assert handler._active_client.sent == [
        ("home/devices/boiler_unit/cmd", {"outdoor_temp": "-7.5"}, False)
    ]
    await handler.close()


async def _gateway_events(db_session) -> list[tuple[str, str]]:
    from app.models.event import EventLog
    db_session.expire_all()
    return [(e.level, e.message) for e in (await db_session.execute(select(EventLog).order_by(EventLog.id))).scalars()]


@pytest.mark.asyncio
async def test_reboot_is_logged_with_its_reason_and_a_reboot_loop_is_an_error(engine, db_session):
    import asyncio
    from sqlalchemy.ext.asyncio import async_sessionmaker

    handler = MQTTHandler(GatewaySettings(mqtt_broker_host="127.0.0.1"), async_sessionmaker(engine, expire_on_commit=False))
    topic = "home/devices/boiler_unit/heartbeat"
    await handler._handle_message(FakeMessage(topic, {"uptime": 500}))
    await handler._handle_message(FakeMessage(topic, {"uptime": 5, "reset_reason": "watchdog"}))
    for _ in range(100):
        events = await _gateway_events(db_session)
        if events:
            break
        await asyncio.sleep(0.02)
    assert events == [("INFO", "Устройство «boiler_unit» перезагрузилось (причина: сторожевой таймер)")]

    for _ in range(3):   # three more quick reboots: 4 within 30 minutes
        await handler._handle_message(FakeMessage(topic, {"uptime": 400}))
        await handler._handle_message(FakeMessage(topic, {"uptime": 2, "reset_reason": "brownout"}))
    for _ in range(100):   # events are written by background tasks
        events = await _gateway_events(db_session)
        if len(events) >= 5:
            break
        await asyncio.sleep(0.02)
    assert ("ERROR", "Устройство «boiler_unit» постоянно перезагружается: 4 раза за 30 мин "
                     "(последняя причина: просадка питания)") in events
    await handler.close()


@pytest.mark.asyncio
async def test_heartbeat_loss_and_return_in_russian_controller_left_to_the_backend(engine):
    from datetime import timedelta
    from sqlalchemy.ext.asyncio import async_sessionmaker

    handler = MQTTHandler(GatewaySettings(mqtt_broker_host="127.0.0.1"), async_sessionmaker(engine, expire_on_commit=False))
    for dev in ("rf-gateway", "boiler_unit"):
        await handler._handle_message(FakeMessage(f"home/devices/{dev}/heartbeat", {"uptime": 10}))
    later = datetime.now(UTC) + timedelta(seconds=120)
    events = handler.check_heartbeats(later, timeout_s=60, quiet={"boiler_unit"})
    assert events == [{"level": "WARNING", "source": "gateway_watchdog",
                       "message": "Устройство «rf-gateway» не на связи — нет сигнала 60 с"}]
    assert handler.heartbeats == {}   # both records dropped, the controller silently (backend alarm covers it)

    restored: list[tuple[str, str]] = []

    async def capture(level: str, message: str) -> None:
        restored.append((level, message))

    handler._log_event = capture  # type: ignore[method-assign]
    await handler._handle_message(FakeMessage("home/devices/rf-gateway/heartbeat", {"uptime": 200}))
    await handler._handle_message(FakeMessage("home/devices/boiler_unit/heartbeat", {"uptime": 200}))
    import asyncio
    for _ in range(10):
        await asyncio.sleep(0)
    assert restored == [("INFO", "Устройство «rf-gateway» снова на связи")]
    await handler.close()


@pytest.mark.asyncio
async def test_telemetry_publish_failure_is_a_clean_false(engine):
    """A broker dropping mid-publish must not escape as an exception (the API answers 503, not 500)."""
    import aiomqtt
    from sqlalchemy.ext.asyncio import async_sessionmaker

    class Client:
        async def publish(self, topic, payload, qos=0, retain=False):
            raise aiomqtt.MqttError("connection lost")

    handler = MQTTHandler(GatewaySettings(), async_sessionmaker(engine, expire_on_commit=False))
    handler._connected = True
    handler._active_client = Client()
    assert await handler.publish_telemetry("boiler_unit", {"indoor_temp": "20.4"}) is False
    await handler.close()
