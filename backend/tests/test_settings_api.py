import pytest

from app.core.security import get_password_hash
from app.core.setting_rules import RULES
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


@pytest.mark.asyncio
async def test_update_settings_out_of_range_rejected(client, seeded_settings):
    token = await _get_token(client)
    response = await client.put(
        "/api/v1/settings",
        json={"settings": {"heating_boiler_max_temp": "150"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "heating_boiler_max_temp" in response.json()["detail"]["errors"]


@pytest.mark.asyncio
async def test_update_settings_garbage_and_unknown_rejected(client, seeded_settings):
    token = await _get_token(client)
    for payload in ({"heating_boiler_temp": "abc"}, {"no_such_key": "1"}, {"mqtt_pass": "x"}):
        response = await client.put(
            "/api/v1/settings",
            json={"settings": payload},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422, payload


@pytest.mark.asyncio
async def test_update_settings_cross_field_pressure(client, seeded_settings):
    token = await _get_token(client)
    response = await client.put(
        "/api/v1/settings",
        json={"settings": {"heating_pressure_min": "1.8", "heating_pressure_max": "1.5"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_water_pressure_range_is_display_only(client, seeded_settings, db_session):
    """Well pressure range: saved for the scheme's manometer, min below max, operators may change it."""
    token = await _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    bad = await client.put("/api/v1/settings", headers=headers,
                           json={"settings": {"water_pressure_min": "3.0", "water_pressure_max": "2.0"}})
    assert bad.status_code == 422
    ok = await client.put("/api/v1/settings", headers=headers,
                          json={"settings": {"water_pressure_min": "1.6", "water_pressure_max": "3.2"}})
    assert ok.status_code == 200
    assert ok.json()["delivery"] == "none"   # nothing goes to the controller
    assert not RULES["water_pressure_min"].admin_only and not RULES["water_pressure_min"].device


@pytest.mark.asyncio
async def test_boiler_min_temp_must_stay_below_the_auto_target_cap(client, seeded_settings):
    """The auto target is capped at max - 7: a higher minimum would be silently ignored (review finding)."""
    token = await _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    bad = await client.put("/api/v1/settings", headers=headers,
                           json={"settings": {"heating_boiler_max_temp": "70", "heating_boiler_min_temp": "65"}})
    assert bad.status_code == 422
    ok = await client.put("/api/v1/settings", headers=headers,
                          json={"settings": {"heating_boiler_max_temp": "70", "heating_boiler_min_temp": "63"}})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_operator_cannot_change_safety_limits(client, seeded_settings, db_session):
    db_session.add(User(
        username="operator",
        password_hash=get_password_hash("operator123"),
        email="operator@test.com",
        role=UserRole.OPERATOR.value,
    ))
    await db_session.commit()
    token = await _get_token(client, "operator", "operator123")

    forbidden = await client.put(
        "/api/v1/settings",
        json={"settings": {"heating_boiler_max_temp": "80"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert forbidden.status_code == 403

    allowed = await client.put(
        "/api/v1/settings",
        json={"settings": {"heating_boiler_temp": "60"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_update_settings_reports_failed_delivery(client, seeded_settings):
    """Gateway is not running in tests — the API must say so instead of pretending success."""
    token = await _get_token(client)
    response = await client.put(
        "/api/v1/settings",
        json={"settings": {"heating_boiler_temp": "56"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["delivery"] == "failed"


@pytest.mark.asyncio
async def test_get_settings_hides_mqtt_password(client, seeded_settings):
    token = await _get_token(client, "viewer", "viewer123")
    response = await client.get(
        "/api/v1/settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    keys = {s["key"] for s in response.json()}
    assert "mqtt_pass" not in keys
    assert "mqtt_host" in keys


@pytest.mark.asyncio
async def test_toggle_only_bool_settings(client, seeded_settings):
    token = await _get_token(client)
    response = await client.post(
        "/api/v1/settings/toggle",
        json={"id": "mqtt_host", "toggle": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_anti_legionella_temperature_must_be_reachable_by_the_boiler():
    """The boiler's auto target is capped at max - 7: a higher disinfection temperature fails every time."""
    from app.core.setting_rules import SettingsValidationError, validate_settings

    current = {"heating_boiler_max_temp": "70", "watersupply_ihb_alm_mode": "1", "watersupply_alm_temp": "60"}
    with pytest.raises(SettingsValidationError) as e:
        validate_settings({"watersupply_alm_temp": "65"}, current, "admin")
    assert "watersupply_alm_temp" in e.value.errors
    with pytest.raises(SettingsValidationError):
        validate_settings({"heating_boiler_max_temp": "65"}, current, "admin")
    assert validate_settings({"watersupply_alm_temp": "63"}, current, "admin") == {"watersupply_alm_temp": "63"}
    # an unrelated change is never blocked by an old combination
    assert validate_settings({"heating_boiler_temp": "50"}, {**current, "watersupply_alm_temp": "75"}, "admin")
