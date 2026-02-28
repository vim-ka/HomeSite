import pytest

from app.core.security import get_password_hash
from app.models.config import ConfigKV
from app.models.user import User, UserRole


@pytest.fixture
async def seeded_settings(db_session):
    """Seed settings and users for tests."""
    db_session.add_all([
        ConfigKV(key="heating_boiler_temp", value="50"),
        ConfigKV(key="heating_boiler_power", value="1"),
        ConfigKV(key="watersupply_ihb_temp", value="45"),
        ConfigKV(key="mqtt_host", value="127.0.0.1"),
        ConfigKV(key="mqtt_port", value="1883"),
        ConfigKV(key="mqtt_user", value=""),
        ConfigKV(key="mqtt_pass", value=""),
    ])
    db_session.add_all([
        User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            email="admin@test.com",
            role=UserRole.ADMIN.value,
        ),
        User(
            username="viewer",
            password_hash=get_password_hash("viewer123"),
            email="viewer@test.com",
            role=UserRole.VIEWER.value,
        ),
    ])
    await db_session.commit()


async def _get_token(client, username="admin", password="admin123") -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_get_all_settings(client, seeded_settings):
    token = await _get_token(client)
    response = await client.get(
        "/api/v1/settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    settings = response.json()
    assert len(settings) >= 3
    keys = {s["key"] for s in settings}
    assert "heating_boiler_temp" in keys


@pytest.mark.asyncio
async def test_update_settings_admin(client, seeded_settings):
    token = await _get_token(client)
    response = await client.put(
        "/api/v1/settings",
        json={"settings": {"heating_boiler_temp": "55"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    # Verify update persisted
    response2 = await client.get(
        "/api/v1/settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    settings = {s["key"]: s["value"] for s in response2.json()}
    assert settings["heating_boiler_temp"] == "55"


@pytest.mark.asyncio
async def test_update_settings_viewer_forbidden(client, seeded_settings):
    token = await _get_token(client, "viewer", "viewer123")
    response = await client.put(
        "/api/v1/settings",
        json={"settings": {"heating_boiler_temp": "99"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mqtt_settings(client, seeded_settings):
    token = await _get_token(client)

    # Get
    response = await client.get(
        "/api/v1/settings/mqtt",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["host"] == "127.0.0.1"

    # Update
    response2 = await client.put(
        "/api/v1/settings/mqtt",
        json={"host": "192.168.1.100", "port": "1884", "user": "mqttuser", "password": "secret"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response2.status_code == 200

    # Verify
    response3 = await client.get(
        "/api/v1/settings/mqtt",
        headers={"Authorization": f"Bearer {token}"},
    )
    data3 = response3.json()
    assert data3["host"] == "192.168.1.100"
    assert data3["port"] == "1884"


@pytest.mark.asyncio
async def test_toggle(client, seeded_settings):
    token = await _get_token(client)
    response = await client.post(
        "/api/v1/settings/toggle",
        json={"id": "heating_boiler_power", "toggle": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "heating_boiler_power"
    assert data["status"] == "OFF"


@pytest.mark.asyncio
async def test_chart_static_radiators(client, seeded_settings):
    token = await _get_token(client)
    response = await client.get(
        "/api/v1/charts/ChartRadiators",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["labels"]) == 12
    assert len(data["datasets"]) == 1


@pytest.mark.asyncio
async def test_chart_dynamic_empty(client, seeded_settings):
    token = await _get_token(client)
    response = await client.get(
        "/api/v1/charts/ChartTemperature",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "labels" in data
    assert "datasets" in data
