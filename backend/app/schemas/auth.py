from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole
from app.services.sms_text import normalize_phone


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    phone: str | None = None
    sms_categories: list[str] = []

    model_config = {"from_attributes": True}

    @field_validator("sms_categories", mode="before")
    @classmethod
    def _split_categories(cls, v):
        if isinstance(v, str):
            return [c for c in v.split(",") if c]
        return v


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=120)
    password: str = Field(min_length=1, max_length=128)
    role: UserRole = UserRole.VIEWER


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=1, max_length=128)


class UpdateUserSmsRequest(BaseModel):
    phone: str | None = None
    categories: list[Literal["critical", "warning", "link", "internet", "test"]] = []

    @field_validator("phone")
    @classmethod
    def _normalize(cls, v):
        if v is None or not v.strip():
            return None
        return normalize_phone(v)
