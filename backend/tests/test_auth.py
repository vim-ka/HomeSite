import pytest

from app.core.security import get_password_hash
from app.models.user import User, UserRole


@pytest.fixture
async def seeded_users(db_session):
    """Create test users for auth tests."""
    admin = User(
        username="admin",
        password_hash=get_password_hash("admin123"),
        email="admin@test.com",
        role=UserRole.ADMIN.value,
    )
    viewer = User(
        username="viewer",
        password_hash=get_password_hash("viewer123"),
        email="viewer@test.com",
        role=UserRole.VIEWER.value,
    )
    db_session.add_all([admin, viewer])
    await db_session.commit()
    return {"admin": admin, "viewer": viewer}


@pytest.mark.asyncio
async def test_login_success(client, seeded_users):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, seeded_users):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "pass"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client, seeded_users):
    # Login first
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    # Get profile
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_get_me_no_token(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code in (401, 403)  # No credentials


@pytest.mark.asyncio
async def test_refresh_token(client, seeded_users):
    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Refresh
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_rbac_admin_only(client, seeded_users):
    """Viewer should not be able to list users (admin-only endpoint)."""
    # Login as viewer
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "viewer123"},
    )
    token = login_resp.json()["access_token"]

    # Try to list users
    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rbac_admin_can_list_users(client, seeded_users):
    """Admin should be able to list users."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 2


@pytest.mark.asyncio
async def test_create_user(client, seeded_users):
    """Admin creates a new user."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/users",
        json={
            "username": "newuser",
            "email": "new@test.com",
            "password": "newpass",
            "role": "operator",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["role"] == "operator"


@pytest.mark.asyncio
async def test_change_password(client, seeded_users):
    """Admin changes another user's password."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    # Get viewer's ID
    users_resp = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    viewer = next(u for u in users_resp.json() if u["username"] == "viewer")

    # Change password
    response = await client.put(
        f"/api/v1/auth/users/{viewer['id']}/password",
        json={"new_password": "newpass"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    # Verify new password works
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "newpass"},
    )
    assert login2.status_code == 200
