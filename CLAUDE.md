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

**Scheme page** (`/scheme`): SCADA-style mnemonic of the boiler room. Backend `GET /api/v1/scheme/state`
(`app/services/scheme_service.py`) aggregates sensors by role (circuit mount points), controller heartbeat
(relays, flags, targets), gateway sync lists and alarms. Frontend `src/scheme/*`: pure SVG elements,
two layouts (`layouts.ts`: wide ≥ 900 px / tall, both mirrored by `mirrorLayout` — boiler on the right),
left click on a pump/boiler/autofill toggles it (`toggles.ts`), right click / touch opens the control
dialog that applies changed keys via `PUT /settings`. Admin-only keys in `scheme/permissions.ts` must
mirror `setting_rules.py` (enforced by a test). E2E check: `python3 tools/scheme_screenshots.py <password>`
against the dev stand (`bash tools/dev_stack.sh`).

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
- Monitoring: `health_poll_seconds`, `frontend_poll_seconds`, `gateway_timeout_seconds`, `ack_timeout_seconds`, `heartbeat_timeout_seconds`
- Range alerts: `heating_pressure_min`, `heating_pressure_max`, `heating_boiler_max_temp`
- System: `access_token_expire_minutes`, `refresh_token_expire_days`, `log_level`, `device_gateway_url`
- Charts: `chart_history_days`
- PZA outdoor source: `pza_outdoor_sensor` (sensor name), `pza_outdoor_device` (controller that gets it forwarded as `outdoor_temp`)
- Backups: `backup_enabled`, `backup_interval`, `backup_time` (UTC), `backup_last_run` — set via `/settings/backup-schedule`

Every key writable via `PUT /settings` must be in the allowlist `backend/app/core/setting_rules.py`
(type, range, admin-only flag). Device ranges there mirror the firmware SETTINGS table in
`firmware/esp32-homesite/src/boiler_logic.cpp` — change both together.

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
1. Frontend `PUT /settings` → Backend validates (allowlist), saves to `config_kv` + calls Gateway `POST /settings`;
   response carries `delivery` (`queued`/`failed`/`none`) and `unrouted` keys
2. Gateway matches `config_key` to device via `config_prefix` in `heating_circuits` table (longest prefix wins)
3. Dispatcher accumulates params per device, deduplicates (last write wins), debounces 5s (max wait 15s);
   failed publishes are re-queued
4. Publishes single MQTT message: `home/devices/{mqtt_device_name}/cmd` → `{"key1": "val1", "key2": "val2"}`
   — **never retained** (a retained `restart` boot-loops the device)
5. ESP32 responds with ack: `home/devices/{name}/ack` → `{"key1": "ok"}`; non-`ok` values
   (`invalid_value`, `unknown_key`, `persist_failed`) mark the key unsynced + ERROR event
6. Watchdog checks for ack timeout (configurable `ack_timeout_seconds`, default 30s)

`config_kv` is the desired state: when a device reboots (heartbeat `uptime` decreases) or is first
seen after a gateway restart, the gateway re-sends all of its keys (`device_gateway/sync.py`).

ESP32 publishes a periodic heartbeat: `home/devices/{name}/heartbeat` (JSON with `uptime`, relays,
safety flags — `backend/app/services/controller_flags.py` maps each to an alarm level and text).
Controller safety rules (firmware `boiler_logic.cpp`, mirrored in `tools/house_emulator/controller.py` with tests):
frost protection (water < 7 °C → boiler and pumps forced on, beats manual OFF), zero pressure = alarm and no
blind autofill, boiler-doesn't-heat detection, well dry-run stop/retry/latch, TEH never heats without a tank
sensor, auto boiler target capped at max − 7 so regulation never hits the overtemp trip, lost boiler sensor
switches the boiler off only in mild weather (else it runs on its own thermostat).
Heartbeat loss detected after `heartbeat_timeout_seconds` (default 60s) → ERROR in event log.

## Deployment Target

Target: Windows 10 + Hyper-V → Ubuntu Server 22.04 VM (3GB RAM, 2 vCPU, 20GB disk).
No Docker — native systemd services + Nginx reverse proxy.
CI/CD planned via GitHub Actions self-hosted runner.

## TODO (Remaining Work)

### High Priority
- [x] **Deploy to VM**: Install script for Ubuntu (Python, Node, Mosquitto, Nginx, systemd units)
- [ ] **CI/CD**: GitHub Actions self-hosted runner on the VM
- [x] **ESP32 firmware**: Add `/ack` response and `/heartbeat` publishing to firmware
- [x] **Range monitoring**: Pressure outside min/max → ERROR, boiler overheating → ERROR

### Medium Priority
- [ ] **Data migration**: Transfer data from SQLite → PostgreSQL (not just schema + seed)
- [x] **SSL/HTTPS**: Nginx HTTPS + self-signed cert, Let's Encrypt ready
- [x] **Rate limiting**: SlowAPIMiddleware + strict limits on auth endpoints
- [x] **Log rotation**: RotatingFileHandler via LOG_FILE env var

### Low Priority
- [x] **Mobile app**: Паритет с десктопом — WS `/ws/sensors`, Events-фильтр по level, линейные графики Stats (react-native-svg), админ-раздел из 13 экранов в `mobile/app/admin/`, EN локализация + language picker
- [ ] **Notifications**: Push/Telegram on critical alerts
- [ ] **Real-time charts**: WebSocket for live chart updates (currently polling)
- [x] **Action audit**: EventLog джойнится с User — username отображается во всех мутирующих эндпоинтах
- [x] **Section tooltips**: TipLabel с иконкой "?" добавлен на Heating и Water Supply
- [x] **Statistics page rework**: Fixed — chart sections are collapsed + lazy by default, data loads only when section is expanded
- [x] **Settings page UX**: 4 вкладки (Оборудование / Устройства / Параметры системы / Инфраструктура)
- [x] **About page UX**: Архитектурная SVG-схема с тёмной темой и реальными портами из API
- [ ] **OpenTherm integration**: Подключить ESP32 к котлу по OpenTherm (проект [OTGateway](https://github.com/Laxilef/OTGateway), библиотека ihormelnyk/opentherm_library). Нужен OT-адаптер (~$15, Tindie/DIYLESS/DIY). Даёт: уставки CH/DHW, вкл/выкл, сброс ошибок, PID, погодозависимые кривые; мониторинг — коды ошибок, пламя, модуляция %, давление, температуры подачи/обратки, ГВС. Интеграция через MQTT. Совместимость Beretta: MyNute X, MySmart подтверждены; Ciao — только Green/X (конденсационные), обычная Ciao не поддерживает OT. Для Vaillant — протокол eBUS (не OT), нужен eBUS-адаптер + ebusd.
