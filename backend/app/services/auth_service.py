from fastapi import HTTPException, status

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def authenticate(self, username: str, password: str) -> TokenResponse:
        """Verify credentials and return JWT tokens."""
        user = await self.user_repo.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт деактивирован",
            )

        access_token = create_access_token(subject=user.username, role=user.role)
        refresh_token = create_refresh_token(subject=user.username)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Exchange a refresh token for a new access token pair."""
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        username = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        user = await self.user_repo.get_by_username(username)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        access_token = create_access_token(subject=user.username, role=user.role)
        new_refresh_token = create_refresh_token(subject=user.username)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
        )

    async def create_user(
        self, username: str, email: str, password: str, role: str = "viewer"
    ):
        """Create a new user. Raises if username or email already taken."""
        existing = await self.user_repo.get_by_username(username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким именем уже существует",
            )

        existing_email = await self.user_repo.get_by_email(email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким email уже существует",
            )

        password_hash = get_password_hash(password)
        return await self.user_repo.create(username, email, password_hash, role)

    async def change_password(self, user_id: int, new_password: str) -> bool:
        password_hash = get_password_hash(new_password)
        result = await self.user_repo.update_password(user_id, password_hash)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )
        return True

    async def delete_user(self, user_id: int) -> bool:
        result = await self.user_repo.delete(user_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )
        return True
