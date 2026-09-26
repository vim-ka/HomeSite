import hashlib
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def password_fingerprint(password_hash: str) -> str:
    """Short digest of the stored hash, embedded in tokens as "pv".

    Changing the password changes the hash, which invalidates every token
    issued before — without a token blacklist or extra DB column.
    """
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
    pv: str | None = None,
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode = {"sub": subject, "role": role, "exp": expire, "type": "access"}
    if pv is not None:
        to_encode["pv"] = pv
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    subject: str, expires_delta: timedelta | None = None, pv: str | None = None
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    to_encode = {"sub": subject, "exp": expire, "type": "refresh"}
    if pv is not None:
        to_encode["pv"] = pv
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload dict or None if invalid."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
