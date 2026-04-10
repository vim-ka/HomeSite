from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.event import EventLog
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(UserRepository(db))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, service: AuthService = Depends(get_auth_service)):
    """Authenticate user and return JWT tokens."""
    return await service.authenticate(payload.username, payload.password)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
async def refresh_token(
    request: Request, payload: RefreshRequest, service: AuthService = Depends(get_auth_service)
):
    """Exchange refresh token for a new token pair."""
    return await service.refresh(payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return current user profile."""
    return user


# --- User management (admin only) ---


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    user: User = Depends(require_role([UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    return await repo.list_all()


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    payload: CreateUserRequest,
    user: User = Depends(require_role([UserRole.ADMIN])),
    service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    new_user = await service.create_user(
        payload.username, payload.email, payload.password, payload.role
    )
    db.add(EventLog(
        level="INFO", source="auth", method="POST", path="/api/v1/auth/users",
        message=f"Создан пользователь: {payload.username} (роль: {payload.role})",
        user_id=user.id,
    ))
    return new_user


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    user: User = Depends(require_role([UserRole.ADMIN])),
    service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    target = await repo.get_by_id(user_id)
    target_username = target.username if target else f"id={user_id}"
    await service.delete_user(user_id)
    db.add(EventLog(
        level="INFO", source="auth", method="DELETE", path=f"/api/v1/auth/users/{user_id}",
        message=f"Удалён пользователь: {target_username}",
        user_id=user.id,
    ))


@router.put("/users/{user_id}/password", status_code=200)
async def change_password(
    user_id: int,
    payload: ChangePasswordRequest,
    user: User = Depends(require_role([UserRole.ADMIN])),
    service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    target = await repo.get_by_id(user_id)
    target_username = target.username if target else f"id={user_id}"
    await service.change_password(user_id, payload.new_password)
    db.add(EventLog(
        level="INFO", source="auth", method="PUT", path=f"/api/v1/auth/users/{user_id}/password",
        message=f"Изменён пароль пользователя: {target_username}",
        user_id=user.id,
    ))
    return {"detail": "Пароль изменён"}
