"""Tests for DeviceGateway internal API."""

import pytest
from httpx import ASGITransport, AsyncClient

from device_gateway.api import create_gateway_api
from device_gateway.config import GatewaySettings
from device_gateway.dispatcher import AsyncCommandDispatcher


class FakePublisher:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []  # (device_id, params)

    async def publish_grouped(self, device_id: str, params: dict[str, str]) -> None:
        self.calls.append((device_id, dict(params)))


@pytest.fixture
def gateway_settings():
    return GatewaySettings(internal_api_secret="test-secret")


@pytest.fixture
def publisher():
    return FakePublisher()


@pytest.fixture
def dispatcher(publisher):
    return AsyncCommandDispatcher(publisher, debounce_seconds=0.1)


@pytest.fixture
def api_app(dispatcher, gateway_settings):
    return create_gateway_api(
        dispatcher=dispatcher,
        mqtt_connected_fn=lambda: True,
        settings=gateway_settings,
    )


@pytest.mark.asyncio
async def test_health_connected(api_app):
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mqtt_connected"] is True


@pytest.mark.asyncio
async def test_health_disconnected(dispatcher, gateway_settings):
    app = create_gateway_api(
        dispatcher=dispatcher,
        mqtt_connected_fn=lambda: False,
        settings=gateway_settings,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["mqtt_connected"] is False


@pytest.mark.asyncio
async def test_post_command(api_app, dispatcher, publisher):
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/commands",
            json={"device_id": "boiler", "params": {"tmp": "55", "prs": "1.5"}},
            headers={"X-Internal-Secret": "test-secret"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["queued"] is True
    assert data["device_id"] == "boiler"

    # Flush and verify params were sent as one grouped message
    await dispatcher.flush_all()
    assert len(publisher.calls) == 1
    device_id, params = publisher.calls[0]
    assert device_id == "boiler"
    assert set(params.keys()) == {"tmp", "prs"}


@pytest.mark.asyncio
async def test_post_command_bad_secret(api_app):
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/commands",
            json={"device_id": "boiler", "params": {"tmp": "55"}},
            headers={"X-Internal-Secret": "wrong-secret"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_command_no_secret(api_app):
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/commands",
            json={"device_id": "boiler", "params": {"tmp": "55"}},
        )
    assert resp.status_code == 422  # Missing required header


@pytest.mark.asyncio
async def test_health_reports_sync_lists(api_app, dispatcher):
    await dispatcher.add_param("boiler", "heating_boiler_temp", "60")
    await dispatcher.flush_all()
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        data = (await client.get("/health")).json()
    assert data["sync"] == {"boiler": {"pending": ["heating_boiler_temp"], "unsynced": []}}


class FakeTelemetryHandler:
    def __init__(self, connected: bool = True):
        self.connected = connected
        self.sent: list[tuple[str, dict]] = []

    async def publish_telemetry(self, device: str, params: dict) -> bool:
        if not self.connected:
            return False
        self.sent.append((device, params))
        return True


async def _post_telemetry(app, params: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/telemetry", json={"device_id": "boiler_unit", "params": params},
                                 headers={"X-Internal-Secret": "test-secret"})


@pytest.mark.asyncio
async def test_telemetry_is_published_at_once_not_queued(dispatcher, gateway_settings, publisher):
    handler = FakeTelemetryHandler()
    app = create_gateway_api(dispatcher=dispatcher, mqtt_connected_fn=lambda: True,
                             settings=gateway_settings, handler=handler)
    resp = await _post_telemetry(app, {"indoor_temp": "20.4"})
    assert resp.status_code == 200
    assert handler.sent == [("boiler_unit", {"indoor_temp": "20.4"})]
    await dispatcher.flush_all()
    assert publisher.calls == []          # not a setting: no dispatcher, no ack tracking


@pytest.mark.asyncio
async def test_settings_cannot_sneak_through_telemetry(dispatcher, gateway_settings):
    handler = FakeTelemetryHandler()
    app = create_gateway_api(dispatcher=dispatcher, mqtt_connected_fn=lambda: True,
                             settings=gateway_settings, handler=handler)
    resp = await _post_telemetry(app, {"indoor_temp": "20.4", "heating_boiler_max_temp": "90"})
    assert resp.status_code == 422
    assert handler.sent == []


@pytest.mark.asyncio
async def test_telemetry_without_mqtt_is_503(dispatcher, gateway_settings):
    app = create_gateway_api(dispatcher=dispatcher, mqtt_connected_fn=lambda: False,
                             settings=gateway_settings, handler=FakeTelemetryHandler(connected=False))
    assert (await _post_telemetry(app, {"indoor_temp": "20.4"})).status_code == 503
