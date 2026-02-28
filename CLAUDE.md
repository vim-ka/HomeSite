# CLAUDE.md

## Project Overview

HomeSite v2 — home automation system with three components:
- **Backend**: FastAPI async API (`backend/`)
- **DeviceGateway**: Standalone MQTT microservice (`backend/device_gateway/`)
- **Frontend**: React 19 + TypeScript SPA (`frontend/`)

## Commands

```bash
# Backend — run API server
cd backend && uvicorn app.main:app --reload --port 8000

# Backend — run tests
cd backend && pytest

# Backend — create Alembic migration
cd backend && alembic revision --autogenerate -m "description"

# Backend — apply migrations
cd backend && alembic upgrade head

# Backend — seed initial data
cd backend && python -m app.db.seed

# DeviceGateway — run MQTT service
cd backend && python -m device_gateway

# Frontend — dev server
cd frontend && npm run dev

# Docker — start all services
docker compose up -d
```

## Architecture

```
[React SPA] <--REST/WS--> [FastAPI Backend] <--HTTP--> [DeviceGateway]
                                |                            |
                           [SQLite/PG]                  [Mosquitto MQTT]
```

**Backend layers**: API Router → Dependencies (auth, db, rate limit) → Service Layer → Repository Layer → Database

## Key Patterns

- **Auth**: JWT (access + refresh tokens), RBAC with roles (admin/operator/viewer)
- **Database**: SQLAlchemy 2.0 async, Alembic migrations, SQLite default / PostgreSQL optional
- **Config**: Pydantic Settings from .env file
- **Logging**: structlog with JSON output
- **MQTT**: aiomqtt in DeviceGateway, topic format `home/devices/{device_name}/...`
- **Real-time**: WebSocket at `/api/v1/ws/sensors`, DeviceGateway notifies via HTTP callback

## Environment Variables

See `.env.example` for all available settings.

## Testing

```bash
cd backend && pytest                          # all tests
cd backend && pytest tests/test_auth.py -v    # single file
cd backend && pytest -k "test_login" -v       # single test
```

Tests use pytest-asyncio, httpx AsyncClient, isolated SQLite DB per session.
