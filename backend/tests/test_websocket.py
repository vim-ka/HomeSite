"""Tests for WebSocket endpoint and internal sensor-update broadcast."""

import pytest
import pytest_asyncio
from starlette.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.user import User, UserRole


@pytest_asyncio.fixture
async def seeded_ws_user(db_session):
    """Create a user for WebSocket auth tests."""
    db_session.add(User(
        username="wsuser",
        password_hash=get_password_hash("pass123"),
        email="ws@test.com",
        role=UserRole.ADMIN.value,
    ))
    await db_session.commit()


@pytest.fixture
def valid_token(seeded_ws_user) -> str:
    return create_access_token(subject="wsuser", role=UserRole.ADMIN.value)


@pytest.fixture
def sync_client(engine):
    """Sync TestClient for WebSocket tests (Starlette's WS test support)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.session import get_db

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# --- WebSocket tests ---


def test_ws_connect_with_valid_token(sync_client, valid_token):
    """WebSocket connects successfully with a valid JWT token."""
    with sync_client.websocket_connect(
        f"/api/v1/ws/sensors?token={valid_token}"
    ) as ws:
        ws.send_text("ping")


def test_ws_reject_no_token(sync_client, seeded_ws_user):
    """WebSocket should reject connection without a token."""
    with pytest.raises(Exception):
        with sync_client.websocket_connect("/api/v1/ws/sensors") as ws:
            ws.receive_text()


def test_ws_reject_invalid_token(sync_client, seeded_ws_user):
    """WebSocket should reject connection with an invalid token."""
    with pytest.raises(Exception):
        with sync_client.websocket_connect(
            "/api/v1/ws/sensors?token=invalid-jwt-token"
        ) as ws:
            ws.receive_text()


# --- Internal sensor-update endpoint tests ---


@pytest.mark.asyncio
async def test_internal_sensor_update(client, seeded_ws_user):
    """POST /internal/sensor-update should accept valid secret and return broadcast info."""
    response = await client.post(
        "/api/v1/internal/sensor-update",
        json={
            "device_name": "tsboiler_s",
            "sensor_id": 1,
            "data": {"tmp": 55.5},
        },
        headers={"X-Internal-Secret": "test-internal-secret"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["broadcast"] is True
    assert "clients" in data


@pytest.mark.asyncio
async def test_internal_sensor_update_bad_secret(client, seeded_ws_user):
    """POST /internal/sensor-update should reject wrong secret."""
    response = await client.post(
        "/api/v1/internal/sensor-update",
        json={
            "device_name": "tsboiler_s",
            "sensor_id": 1,
            "data": {"tmp": 55.5},
        },
        headers={"X-Internal-Secret": "wrong-secret"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_internal_sensor_update_no_secret(client, seeded_ws_user):
    """POST /internal/sensor-update should reject missing secret."""
    response = await client.post(
        "/api/v1/internal/sensor-update",
        json={
            "device_name": "tsboiler_s",
            "sensor_id": 1,
            "data": {"tmp": 55.5},
        },
    )
    assert response.status_code == 422
