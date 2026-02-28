"""Tests for DeviceGateway internal API."""

import pytest
from httpx import ASGITransport, AsyncClient

from device_gateway.api import create_gateway_api
from device_gateway.config import GatewaySettings
from device_gateway.dispatcher import AsyncCommandDispatcher


class FakePublisher:
    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []

    async def publish(self, device_id: str, parameter: str, value: str) -> str:
        self.calls.append((device_id, parameter, value))
        return f"topic/{device_id}"


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

    # Flush and verify params were queued
    await dispatcher.flush_all()
    assert len(publisher.calls) == 2


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
