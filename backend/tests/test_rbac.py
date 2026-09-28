"""Route-wide access control checks."""

import re

import pytest
from fastapi.routing import APIRoute

from app.core.security import get_password_hash
from app.main import app
from app.models.user import User, UserRole

# Endpoints that are intentionally reachable without a user token
PUBLIC = {
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("GET", "/health/status"),
    ("GET", "/health/sensors"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
}
# Protected by X-Internal-Secret instead of a user token
INTERNAL_PREFIX = "/api/v1/internal/"


def _routes():
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            if (method, route.path) in PUBLIC or route.path.startswith(INTERNAL_PREFIX):
                continue
            yield method, route.path


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", sorted(_routes()))
async def test_route_requires_auth(client, method, path):
    url = re.sub(r"\{[^}]+\}", "1", path)
    response = await client.request(method, url, json={})
    # 401 from our deps, 403 from HTTPBearer when the header is missing entirely
    assert response.status_code in (401, 403), f"{method} {path} -> {response.status_code}"


@pytest.mark.asyncio
async def test_internal_routes_require_secret(client):
    response = await client.post("/api/v1/internal/sensor-update", json={})
    assert response.status_code in (401, 403, 422)
    response = await client.post(
        "/api/v1/internal/sensor-update",
        json={"device_name": "x", "sensor_id": 1, "data": {}},
        headers={"X-Internal-Secret": "wrong"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_password_change_revokes_tokens(client, db_session):
    db_session.add(User(
        username="admin",
        password_hash=get_password_hash("admin123"),
        email="admin@test.com",
        role=UserRole.ADMIN.value,
    ))
    await db_session.commit()

    login = (await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
    )).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    user_id = me.json()["id"]

    changed = await client.put(
        f"/api/v1/auth/users/{user_id}/password",
        json={"new_password": "new-password-123"},
        headers=headers,
    )
    assert changed.status_code == 200

    # Old access and refresh tokens are no longer accepted
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401
    refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_cannot_delete_self_or_last_admin(client, db_session):
    from app.models.event import EventLog

    db_session.add_all([
        User(username="admin", password_hash=get_password_hash("admin123"),
             email="a@test.com", role=UserRole.ADMIN.value),
        User(username="viewer", password_hash=get_password_hash("viewer123"),
             email="v@test.com", role=UserRole.VIEWER.value),
    ])
    await db_session.commit()
    login = (await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
    )).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    users = {u["username"]: u["id"] for u in (await client.get("/api/v1/auth/users", headers=headers)).json()}

    assert (await client.delete(f"/api/v1/auth/users/{users['admin']}", headers=headers)).status_code == 400

    # Deleting a user with audit events keeps the events (user_id → NULL)
    db_session.add(EventLog(level="INFO", source="t", message="by viewer", user_id=users["viewer"]))
    await db_session.commit()
    assert (await client.delete(f"/api/v1/auth/users/{users['viewer']}", headers=headers)).status_code == 204


@pytest.mark.asyncio
async def test_create_user_rejects_unknown_role(client, db_session):
    db_session.add(User(username="admin", password_hash=get_password_hash("admin123"),
                        email="a@test.com", role=UserRole.ADMIN.value))
    await db_session.commit()
    login = (await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
    )).json()
    response = await client.post(
        "/api/v1/auth/users",
        json={"username": "x", "email": "x@test.com", "password": "password123", "role": "superadmin"},
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert response.status_code == 422
