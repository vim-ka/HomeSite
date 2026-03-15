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
                          (shared DB)                        |
                                                        [ESP32 devices]
```

**Backend layers**: API Router → Dependencies (auth, db) → Service Layer → Repository Layer → Database

**Health monitoring**: `HealthMonitor` background task (single source of truth) → cached state read by `/health/*` endpoints → frontend polls via `useServiceHealth` hook

**Settings**: All runtime config stored in `config_kv` table (single source of truth). `.env` only for infrastructure (JWT secret, DB URL, CORS). Gateway reads MQTT settings from `config_kv` at startup and on `/reload-mqtt`.

## Key Patterns

- **Auth**: JWT (access + refresh tokens), RBAC with roles (admin/operator/viewer)
- **Database**: SQLAlchemy 2.0 async, Alembic migrations, SQLite default / PostgreSQL optional
- **Config**: Runtime settings in `config_kv` DB table, infrastructure in `.env` (Pydantic Settings)
- **Logging**: structlog with JSON output
- **MQTT**: aiomqtt in DeviceGateway, topic prefix configurable (`config_kv: mqtt_topic_prefix`)
- **Real-time**: WebSocket at `/api/v1/ws/sensors`, DeviceGateway notifies via HTTP callback

## Timezone Rules (CRITICAL)

All timestamps are **UTC throughout the entire system**. Follow these rules strictly:

### Backend (Python)
- Always use `datetime.now(UTC)`, never `datetime.now()`
- Always use `datetime.fromtimestamp(ts, tz=UTC)`, never `datetime.fromtimestamp(ts)`
- All SQLAlchemy DateTime columns must use `DateTime(timezone=True)`
- All `server_default=func.now()` produce UTC timestamps

### Frontend (TypeScript)
- Server timestamps may arrive without `Z` suffix (SQLite limitation)
- When comparing server timestamps with `Date.now()`, always normalize: append `"Z"` if missing
- Pattern: `const ts = str.endsWith("Z") ? str : str + "Z"; new Date(ts).getTime()`
- `toLocaleString()` / `toLocaleDateString()` are OK for display only — they auto-convert to user's timezone

### Database
- SQLite stores UTC but returns naive strings (no timezone suffix)
- PostgreSQL stores and returns timezone-aware timestamps
- Both are handled by the normalization rules above

## Settings Architecture

Runtime settings stored in `config_kv` table (not in `.env`):
- MQTT: `mqtt_host`, `mqtt_port`, `mqtt_user`, `mqtt_pass`, `mqtt_topic_prefix`
- Sensors: `sensor_stale_minutes`
- Monitoring: `health_poll_seconds`, `frontend_poll_seconds`, `gateway_timeout_seconds`
- System: `access_token_expire_minutes`, `refresh_token_expire_days`, `log_level`, `device_gateway_url`
- Charts: `chart_history_days`

Infrastructure settings in `.env` only (not runtime-changeable):
- `DATABASE_URL`, `JWT_SECRET_KEY`, `INTERNAL_API_SECRET`, `CORS_ORIGINS`

## Environment Variables

See `.env.example` for all available settings.

## Testing

```bash
cd backend && pytest                          # all tests
cd backend && pytest tests/test_auth.py -v    # single file
cd backend && pytest -k "test_login" -v       # single test
```

Tests use pytest-asyncio, httpx AsyncClient, isolated SQLite DB per session.

## Command Dispatch

Settings changes → Gateway → grouped MQTT message per device:
1. Frontend `PUT /settings` → Backend saves to `config_kv` + calls Gateway `POST /settings`
2. Gateway matches `config_key` to device via `config_prefix` in `heating_circuits` table (longest prefix wins)
3. Dispatcher accumulates params per device, deduplicates (last write wins), debounces 5s
4. Publishes single MQTT message: `home/devices/{mqtt_device_name}/cmd` → `{"key1": "val1", "key2": "val2"}`
5. ESP32 should respond with ack: `home/devices/{name}/ack` → `{"key1": "ok"}`
6. Watchdog checks for ack timeout (configurable `ack_timeout_seconds`, default 30s)

ESP32 should also publish periodic heartbeat: `home/devices/{name}/heartbeat` (any payload).
Heartbeat loss detected after `heartbeat_timeout_seconds` (default 60s) → ERROR in event log.

## Deployment Target

Target: Windows 10 + Hyper-V → Ubuntu Server 22.04 VM (3GB RAM, 2 vCPU, 20GB disk).
No Docker — native systemd services + Nginx reverse proxy.
CI/CD planned via GitHub Actions self-hosted runner.

## TODO (Remaining Work)

### High Priority
- [ ] **Deploy to VM**: Install script for Ubuntu (Python, Node, Mosquitto, Nginx, systemd units)
- [ ] **CI/CD**: GitHub Actions self-hosted runner on the VM
- [ ] **ESP32 firmware**: Add `/ack` response and `/heartbeat` publishing to firmware
- [ ] **Range monitoring**: Pressure outside min/max → ERROR, boiler overheating → ERROR

### Medium Priority
- [ ] **Data migration**: Transfer data from SQLite → PostgreSQL (not just schema + seed)
- [ ] **SSL/HTTPS**: Let's Encrypt or self-signed for production
- [ ] **Rate limiting**: Middleware implementation (setting exists, middleware not wired)
- [ ] **Log rotation**: structlog → file with rotation

### Low Priority
- [ ] **Mobile app**: Update React Native app for new endpoints
- [ ] **Notifications**: Push/Telegram on critical alerts
- [ ] **Real-time charts**: WebSocket for live chart updates (currently polling)
- [ ] **Action audit**: Expand EventLog with who-changed-what details
