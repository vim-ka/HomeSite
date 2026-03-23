"""Rate limiting via slowapi.

Usage:
  - Global limit (60/minute) applied via SlowAPIMiddleware to all routes.
  - Stricter per-endpoint limits via @limiter.limit("N/minute") decorator.
    The decorated function must declare `request: Request` as a parameter.
"""

import os

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

# Limiter is disabled in test environment to avoid flaky tests caused by
# multiple requests from the same IP (127.0.0.1) exceeding per-endpoint limits.
_enabled = os.environ.get("APP_ENV") != "test"

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    enabled=_enabled,
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )
