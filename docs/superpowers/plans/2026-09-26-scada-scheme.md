# Мнемосхема котельной («Схема») — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Страница-пульт в стиле SCADA: иллюстрированная схема котельной с живым состоянием оборудования и управлением по клику.

**Architecture:** Бэкенд собирает всё состояние схемы одним эндпоинтом `GET /api/v1/scheme/state` (датчики по ролям через привязки контуров, heartbeat и статус синхронизации из шлюза, настройки, аварии). Фронтенд рисует схему inline-SVG из чистых React-компонентов по одной из двух раскладок (горизонтальная/вертикальная) и открывает окно управления, которое отправляет изменённые ключи через существующий `PUT /settings`. Шлюз отдаёт списки ключей в синхронизации; контроллер (прошивка и эмулятор) шлёт heartbeat сразу после команд.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), aiomqtt gateway, React 19 + TypeScript + TanStack Query + Tailwind (frontend), Vitest + Testing Library (новые dev-зависимости), ESP32 Arduino (прошивка), Python-эмулятор (`tools/house_emulator`).

**Spec:** `docs/superpowers/specs/2026-09-26-scada-scheme-design.md`

## Global Constraints

- Все метки времени в ответах — ISO-8601 UTC с `Z` (правило CLAUDE.md «Timezone Rules»).
- Запись только через существующие API: `PUT /api/v1/settings`, `POST /api/v1/settings/retry-unsynced`, `POST /api/v1/catalog/devices/{name}/command`. Новых путей записи нет.
- Эндпоинт схемы требует вход (любая роль); `mqtt_pass` никогда не отдаётся.
- Права в UI зеркалят `backend/app/core/setting_rules.py`: admin-only — `heating_boiler_max_temp`, `heating_pressure_min`, `heating_pressure_max`; сброс блокировки подпитки — admin (эндпоинт команды admin-only). viewer ничего не меняет.
- Горизонтальная раскладка при ширине контейнера ≥ 900 px (viewBox 1000×560), иначе вертикальная (viewBox 360×640).
- Цвет трубы: ≤ 25 °C `#3b82f6` → ≥ 70 °C `#ef4444`, линейно; без значения — цвет по типу трубы.
- Анимации отключаются при `prefers-reduced-motion: reduce`.
- Схема работает в светлой и тёмной теме (`html.dark`), цвета — CSS-переменные.
- Имя устройства контроллера — `boiler_unit`; неотапливаемые датчики — `{"clm_garage_th"}`; датчик котельной — `clm_boiler_th`.
- Бэкенд-тесты: `cd backend && python3 -m pytest -q`; фронтенд: `cd frontend && npx vitest run` и `npx tsc -b --noEmit`; эмулятор: `cd tools && python3 -m pytest -q house_emulator`.

## Review Focus

- **Контроллер ни разу не присылал heartbeat** (шлюз жив, устройства нет) → схема рисуется, `controller.online=false`, реле все выкл, плашка «Нет связи», авария `no_link`; не 500. — тест в Task 3.
- **Шлюз недоступен** (connection refused / таймаут) → ответ 200, `controller.online=false`, `sync` пустой, авария `gateway_down`. — тест в Task 3.
- **SQLite-метки времени без зоны** (naive) → в ответе всё равно `…Z`, stale считается от UTC. — тест в Task 3.
- **Оператор открывает окно котла** → поле «Макс. температура» видно, но заблокировано; «Применить» не отправляет admin-ключи. — тест в Task 8.
- **Закрытие окна с несохранёнными изменениями** → подтверждение; «Применить» без изменений заблокирован и ничего не шлёт. — тест в Task 8.

---

## File Structure

| Файл | Ответственность |
|---|---|
| `backend/device_gateway/dispatcher.py` (mod) | `sync_status()` — списки pending/unsynced по устройствам |
| `backend/device_gateway/api.py` (mod) | поле `sync` в `/health` |
| `firmware/esp32-homesite/src/main.cpp` (mod) | heartbeat сразу после команд |
| `tools/house_emulator/__main__.py` (mod) | то же в эмуляторе |
| `backend/app/services/scheme_service.py` (new) | сборка состояния схемы: привязки, значения, контроллер, аварии |
| `backend/app/api/v1/scheme.py` (new) | `GET /scheme/state` |
| `backend/app/api/router.py` (mod) | подключение роутера |
| `frontend/vitest.config.ts`, `frontend/src/test/setup.ts` (new) | тестовая инфраструктура |
| `frontend/src/scheme/types.ts` (new) | типы ответа, роли, реле, виды элементов |
| `frontend/src/scheme/pipeColor.ts` (new) | цвет трубы по температуре |
| `frontend/src/scheme/permissions.ts` (new) | admin-only ключи (зеркало setting_rules) |
| `frontend/src/scheme/useSchemeState.ts` (new) | загрузка/обновление состояния |
| `frontend/src/scheme/elements/*.tsx` (new) | SVG-приборы |
| `frontend/src/scheme/layouts.ts` (new) | координаты двух раскладок |
| `frontend/src/scheme/SchemeCanvas.tsx` (new) | SVG: трубы + элементы + табло |
| `frontend/src/scheme/forms.ts` (new) | описания полей окон по виду элемента |
| `frontend/src/scheme/ControlDialog.tsx` (new) | окно управления |
| `frontend/src/scheme/AlarmPanel.tsx`, `TopStrip.tsx` (new) | сигнализация, верхняя полоса |
| `frontend/src/pages/SchemePage.tsx` (new) | страница |
| `frontend/src/App.tsx`, `components/Layout.tsx`, `i18n/*.json`, `index.css` (mod) | маршрут, меню, переводы, стили/переменные |

---

### Task 1: Шлюз — списки ключей синхронизации в `/health`

**Files:**
- Modify: `backend/device_gateway/dispatcher.py` (добавить метод после `unsynced_count`)
- Modify: `backend/device_gateway/api.py` (функция `health`)
- Test: `backend/tests/test_gateway_dispatcher.py`, `backend/tests/test_gateway_api.py`

**Interfaces:**
- Produces: `AsyncCommandDispatcher.sync_status() -> dict[str, dict[str, list[str]]]` вида `{"boiler_unit": {"pending": [...], "unsynced": [...]}}` (списки отсортированы); `GET /health` шлюза содержит `"sync"` с этим значением.

- [ ] **Step 1: Write the failing tests**

В конец `backend/tests/test_gateway_dispatcher.py`:

```python
@pytest.mark.asyncio
async def test_sync_status_lists_pending_and_unsynced(dispatcher, publisher):
    await dispatcher.add_param("boiler", "heating_boiler_temp", "60")
    await dispatcher.add_param("boiler", "heating_radiator_curve", "3")
    await dispatcher.flush_all()
    await dispatcher.handle_ack("boiler", {"heating_radiator_curve": "invalid_value"})

    assert dispatcher.sync_status() == {
        "boiler": {"pending": ["heating_boiler_temp"], "unsynced": ["heating_radiator_curve"]}
    }


@pytest.mark.asyncio
async def test_sync_status_empty(dispatcher):
    assert dispatcher.sync_status() == {}
```

В конец `backend/tests/test_gateway_api.py`:

```python
@pytest.mark.asyncio
async def test_health_reports_sync_lists(api_app, dispatcher):
    await dispatcher.add_param("boiler", "heating_boiler_temp", "60")
    await dispatcher.flush_all()
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        data = (await client.get("/health")).json()
    assert data["sync"] == {"boiler": {"pending": ["heating_boiler_temp"], "unsynced": []}}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest -q tests/test_gateway_dispatcher.py tests/test_gateway_api.py -k sync`
Expected: FAIL — `AttributeError: 'AsyncCommandDispatcher' object has no attribute 'sync_status'` / `KeyError: 'sync'`.

- [ ] **Step 3: Implement**

`dispatcher.py`, после свойства `unsynced_count`:

```python
    def sync_status(self) -> dict[str, dict[str, list[str]]]:
        """Keys awaiting ack and keys that failed, per device (for the UI)."""
        devices = set(self._pending_acks) | set(self.unsynced)
        return {
            device: {
                "pending": sorted(self._pending_acks.get(device, {})),
                "unsynced": sorted(self.unsynced.get(device, set())),
            }
            for device in sorted(devices)
        }
```

`api.py`, в возвращаемый словарь функции `health` добавить строку после `"unsynced_commands"`:

```python
            "sync": dispatcher.sync_status(),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest -q tests/test_gateway_dispatcher.py tests/test_gateway_api.py`
Expected: все PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/device_gateway/dispatcher.py backend/device_gateway/api.py backend/tests/test_gateway_dispatcher.py backend/tests/test_gateway_api.py
git commit -m "Gateway: expose pending/unsynced key lists in /health"
```

---

### Task 2: Контроллер — heartbeat сразу после команд (прошивка + эмулятор)

**Files:**
- Modify: `firmware/esp32-homesite/src/main.cpp` (`onCommand`, `loop`)
- Modify: `tools/house_emulator/__main__.py` (`heartbeat_loop`, `on_boiler_command`)
- Test: `tools/house_emulator/test_emulator.py`

**Interfaces:**
- Produces: `Emulator.publish_heartbeats() -> Awaitable[None]` (эмулятор); прошивка публикует `home/devices/<node>/heartbeat` в том же цикле `loop()`, где отправлен ack.

- [ ] **Step 1: Write the failing test (эмулятор)**

В конец `tools/house_emulator/test_emulator.py`:

```python
def test_heartbeat_sent_right_after_command(monkeypatch):
    import argparse

    from house_emulator.__main__ import Emulator

    args = argparse.Namespace(
        prefix="home/devices/", node="boiler_unit", rf_node="rf-gateway", speed=1, seed=1, outdoor=-12,
        leak=0.3, boiler_panel=75, prs_heating="prs_heating", prs_water="prs_water", local_outdoor=False,
        quiet=True,
    )
    emu = Emulator(args)
    topics = []

    async def fake_publish(topic, payload, qos=0):
        topics.append(topic)

    monkeypatch.setattr(emu, "publish", fake_publish)
    asyncio.run(emu.on_boiler_command({"heating_radiator_pump": "0"}))
    assert topics.index("boiler_unit/ack") < topics.index("boiler_unit/heartbeat")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd tools && python3 -m pytest -q house_emulator -k heartbeat_sent`
Expected: FAIL — `ValueError: 'boiler_unit/heartbeat' is not in list`.

- [ ] **Step 3: Implement (эмулятор)**

В `tools/house_emulator/__main__.py` заменить метод `heartbeat_loop` на два метода:

```python
    async def publish_heartbeats(self) -> None:
        hb = self.sim.controller.heartbeat(
            self.sim.heating_pressure_reading() if self.args.prs_heating else None,
            self.sim.water_pressure_reading() if self.args.prs_water else None,
        )
        await self.publish(f"{self.node}/heartbeat", hb)
        await self.publish(f"{self.rf_node}/heartbeat", {
            "uptime": int(self.rf_uptime), "free_heap": 151_000, "frames_ok": self.rf_frames,
            "frames_unknown": self.rf_frames // 40, "seen": len(CLIMATE), "raw_debug": False,
        })

    async def heartbeat_loop(self) -> None:
        while self.running:
            await self.publish_heartbeats()
            await asyncio.sleep(HEARTBEAT_S)
```

В `on_boiler_command` сразу после блока `if ack: await self.publish(f"{self.node}/ack", ack, qos=1)` добавить (до обработки `restart`):

```python
        # Like the firmware: report the new relay state right away, not in ≤30 s
        if not restart:
            self.sim.controller.update(
                self.sim.now, self.sim.boiler_readings(), self.sim.heating_pressure_reading() or 0.0
            )
            await self.publish_heartbeats()
```

- [ ] **Step 4: Implement (прошивка)**

`firmware/esp32-homesite/src/main.cpp`:
1. Рядом с `JsonDocument ackDoc;` объявить `bool heartbeatSoon = false;`
2. В начале `onCommand(...)` (после `ackDoc[key] = "ok";`) добавить `heartbeatSoon = true;`
3. В конце `loop()` заменить строку `sendAck();` на:

```cpp
    // Send ack for any pending commands (batched)
    sendAck();

    // After commands: apply them in a control cycle now and report the new
    // relay state immediately (the scheme page would otherwise lag up to 30 s)
    if (heartbeatSoon && mqtt.isConnected()) {
        heartbeatSoon = false;
        lastReadTime = 0;         // next loop runs a control cycle right away
        lastHeartbeat = millis() - HEARTBEAT_INTERVAL_MS + 1000;  // heartbeat ~1 s after it
    }
```

(Цикл управления выполняется в следующей итерации — `lastReadTime = 0`; heartbeat уходит через ≈1 с, уже с новыми реле.)

- [ ] **Step 5: Run tests and build**

Run: `cd tools && python3 -m pytest -q house_emulator` → все PASS.
Run: `cd firmware/esp32-homesite && pio run` → `[SUCCESS]`.

- [ ] **Step 6: Commit**

```bash
git add firmware/esp32-homesite/src/main.cpp tools/house_emulator/__main__.py tools/house_emulator/test_emulator.py
git commit -m "Controller: publish heartbeat right after processing commands"
```

---

### Task 3: Бэкенд — сервис состояния схемы

**Files:**
- Create: `backend/app/services/scheme_service.py`
- Test: `backend/tests/test_scheme_service.py`

**Interfaces:**
- Consumes: `SensorRepository.get_outdoor_sensor_id()` (существует), `SettingsRepository.get_all()`, `SECRET_KEYS` из `app.core.setting_rules`, gateway `/health` с полями `heartbeats`, `sync` (Task 1).
- Produces:
  - `RELAY_NAMES: list[str]` (16 имён в порядке `RelayChannel`)
  - `decode_relays(mask: int | None) -> dict[str, bool]`
  - `build_alarms(*, online: bool, gateway_ok: bool, flags: dict, pressure: float | None, p_min: float | None, p_max: float | None) -> list[dict]` — элементы `{"level", "code", "text"}`
  - `async fetch_gateway_health(url: str, timeout: float) -> dict | None`
  - `class SchemeService(db: AsyncSession, fetch_gateway: Callable[[], Awaitable[dict | None]])` с `async build_state(now: datetime | None = None) -> dict` (формат из спеки §5.1)

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_scheme_service.py`:

```python
"""SchemeService: role bindings, heartbeat fallback, staleness, alarms, gateway failures."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.config import ConfigKV
from app.models.heating import HeatingCircuit
from app.models.sensor import MountPoint, Place, Sensor, SensorData, SensorDataType, SensorType, SystemType
from app.services.scheme_service import SchemeService, build_alarms, decode_relays

NOW = datetime(2026, 1, 20, 12, 0, tzinfo=UTC)


async def seed(db, *, fresh: bool = True):
    db.add_all([
        SystemType(id=1, name="Отопление"), SystemType(id=2, name="Водоснабжение"), SystemType(id=3, name="Климат"),
        Place(id=1, name="Котельная"), Place(id=7, name="Улица"), Place(id=8, name="Гараж"), Place(id=2, name="Гостиная"),
        SensorType(id=1, name="DS18B20"), SensorDataType(id=1, name="Temperature", code="tmp"),
    ])
    await db.flush()
    mps = [
        (1, "Котел, подача", 1, 1), (2, "Котел, возврат", 1, 1), (3, "Радиаторы, подача", 1, 1),
        (4, "Радиаторы, возврат", 1, 1), (9, "ХВС", 2, 1), (10, "ГВС", 2, 1),
        (14, "Балкон", 3, 7), (18, "Гараж", 3, 8), (16, "Камин", 3, 2), (15, "У котла", 3, 1),
    ]
    db.add_all([MountPoint(id=i, name=n, system_id=s, place_id=p) for i, n, s, p in mps])
    await db.flush()
    names = {1: "tsboiler_s", 2: "tsboiler_b", 3: "tsrad_s", 4: "tsrad_b", 9: "tswatersupply_c",
             10: "tswatersupply_h", 14: "clm_street_th", 18: "clm_garage_th", 16: "clm_gost_th", 15: "clm_boiler_th"}
    db.add_all([Sensor(id=i, name=n, sensor_type_id=1, mount_point_id=i) for i, n in names.items()])
    await db.flush()
    for mp_id in names:
        mp = await db.get(MountPoint, mp_id)
        mp.temperature_sensor_id = mp_id
    db.add_all([
        HeatingCircuit(circuit_name="Котёл", config_prefix="heating_boiler", supply_mount_point_id=1, return_mount_point_id=2),
        HeatingCircuit(circuit_name="Радиаторы", config_prefix="heating_radiator", supply_mount_point_id=3, return_mount_point_id=4),
        ConfigKV(key="sensor_stale_minutes", value="5"), ConfigKV(key="heartbeat_timeout_seconds", value="60"),
        ConfigKV(key="heating_pressure_min", value="1.0"), ConfigKV(key="heating_pressure_max", value="2.0"),
        ConfigKV(key="mqtt_pass", value="secret"),
    ])
    ts = (NOW - timedelta(minutes=1 if fresh else 30)).replace(tzinfo=None)  # SQLite-style naive UTC
    values = {1: 75.1, 2: 64.4, 3: 54.1, 4: 43.0, 9: 7.1, 10: 61.8, 14: -7.4, 18: 2.3, 16: 22.7, 15: 23.0}
    db.add_all([SensorData(sensor_id=i, datatype_id=1, value=v, timestamp=ts) for i, v in values.items()])
    await db.commit()


def gateway(hb_age_s: float | None = 5, data: dict | None = None, sync: dict | None = None):
    async def fetch():
        heartbeats = {}
        if hb_age_s is not None:
            heartbeats["boiler_unit"] = {
                "timestamp": (NOW - timedelta(seconds=hb_age_s)).isoformat(),
                "data": data if data is not None else {"relays": 0b11, "prs_heat": 1.43, "prs_water": 3.05,
                                                       "rad_target": 54.0, "boiler_auto_target": 56.0},
            }
        return {"heartbeats": heartbeats, "sync": sync or {}}
    return fetch


def test_decode_relays():
    relays = decode_relays(0b1000000011)
    assert relays["boiler"] and relays["rad_pump"] and relays["rad_open"]
    assert not relays["floor_pump"]
    assert decode_relays(None)["boiler"] is False
    assert len(decode_relays(0)) == 16


def test_build_alarms_pressure_and_flags():
    alarms = build_alarms(online=True, gateway_ok=True, flags={"autofill_fault": True}, pressure=0.92, p_min=1.0, p_max=2.0)
    codes = {a["code"] for a in alarms}
    assert codes == {"autofill_fault", "pressure_low"}
    assert all(a["level"] == "ERROR" for a in alarms)


@pytest.mark.asyncio
async def test_state_values_by_role(db_session):
    await seed(db_session)
    state = await SchemeService(db_session, gateway()).build_state(NOW)
    v = state["values"]
    assert v["boiler_supply"]["value"] == 75.1 and v["rad_return"]["value"] == 43.0
    assert v["boiler_supply"]["ts"].endswith("Z") and v["boiler_supply"]["stale"] is False
    assert v["cold_water"]["value"] == 7.1 and v["hot_water"]["value"] == 61.8
    assert v["outdoor"]["value"] == -7.4
    assert v["indoor_avg"]["value"] == 22.7          # street and garage excluded, boiler room too
    assert v["boiler_room"]["value"] == 23.0
    assert v["heating_pressure"] == {"value": 1.43, "ts": state["controller"]["last_seen"], "stale": False, "source": "heartbeat"}
    assert v["floor_supply"]["value"] is None        # circuit not configured → empty, not an error
    assert state["controller"]["online"] is True
    assert state["controller"]["relays"]["rad_pump"] is True
    assert state["controller"]["targets"]["rad"] == 54.0
    assert "mqtt_pass" not in state["settings"]


@pytest.mark.asyncio
async def test_stale_values_flagged(db_session):
    await seed(db_session, fresh=False)
    state = await SchemeService(db_session, gateway()).build_state(NOW)
    assert state["values"]["boiler_supply"]["stale"] is True
    assert state["values"]["indoor_avg"]["value"] is None


@pytest.mark.asyncio
async def test_controller_never_seen(db_session):
    await seed(db_session)
    state = await SchemeService(db_session, gateway(hb_age_s=None)).build_state(NOW)
    assert state["controller"]["online"] is False
    assert state["controller"]["last_seen"] is None
    assert not any(state["controller"]["relays"].values())
    assert {a["code"] for a in state["alarms"]} == {"no_link"}


@pytest.mark.asyncio
async def test_heartbeat_too_old_is_offline(db_session):
    await seed(db_session)
    state = await SchemeService(db_session, gateway(hb_age_s=300)).build_state(NOW)
    assert state["controller"]["online"] is False
    assert state["values"]["heating_pressure"]["stale"] is True


@pytest.mark.asyncio
async def test_gateway_down(db_session):
    await seed(db_session)

    async def down():
        return None

    state = await SchemeService(db_session, down).build_state(NOW)
    assert state["controller"]["online"] is False
    assert state["sync"] == {"pending": [], "unsynced": []}
    assert {a["code"] for a in state["alarms"]} == {"gateway_down"}


@pytest.mark.asyncio
async def test_sync_lists_for_controller(db_session):
    await seed(db_session)
    sync = {"boiler_unit": {"pending": ["heating_radiator_curve"], "unsynced": ["heating_boiler_temp"]}}
    state = await SchemeService(db_session, gateway(sync=sync)).build_state(NOW)
    assert state["sync"] == sync["boiler_unit"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python3 -m pytest -q tests/test_scheme_service.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.scheme_service'`.

- [ ] **Step 3: Implement**

`backend/app/services/scheme_service.py`:

```python
"""State of the boiler room scheme page: sensors by role, controller, sync, alarms.

One place maps scheme roles to sensors:
- circuit supply/return — mount points of heating_circuits (by config_prefix),
  exactly like the dashboard;
- water — fixed sensor names; pressure — a bound "prs" sensor if the catalog has
  one, otherwise the value the controller reports in its heartbeat.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.setting_rules import SECRET_KEYS
from app.models.event import EventLog
from app.models.heating import HeatingCircuit
from app.models.sensor import MountPoint, Sensor, SensorData, SensorDataType
from app.repositories.sensor_repository import CLIMATE_SYSTEM_ID, SensorRepository
from app.repositories.settings_repository import SettingsRepository

CONTROLLER_DEVICE = "boiler_unit"
# Same order as firmware RelayChannel (relay_controller.h)
RELAY_NAMES = [
    "boiler", "rad_pump", "floor_pump", "ihb_pump", "water_pump", "water_hot_pump", "teh",
    "af_open", "af_close", "rad_open", "rad_close", "floor_open", "floor_close",
    "lamp_warning", "lamp_critical", "spare",
]
CIRCUIT_ROLES = {
    "heating_boiler": ("boiler_supply", "boiler_return"),
    "heating_radiator": ("rad_supply", "rad_return"),
    "heating_floorheating": ("floor_supply", "floor_return"),
    "watersupply_ihb": ("tank", "coil_return"),
}
WATER_SENSORS = {"cold_water": "tswatersupply_c", "hot_water": "tswatersupply_h"}
UNHEATED_SENSORS = {"clm_garage_th"}
BOILER_ROOM_SENSOR = "clm_boiler_th"
FLAG_KEYS = [
    "warning", "critical", "overtemp", "boiler_sensor_lost", "autofill_fault", "alm_active",
    "schedule_rad", "schedule_floor", "ihb_heating", "autofill_active", "autofill_closing",
    "boiler_auto",
]
ALL_ROLES = [r for pair in CIRCUIT_ROLES.values() for r in pair] + [
    "cold_water", "hot_water", "heating_pressure", "water_pressure", "outdoor", "indoor_avg", "boiler_room",
]

GatewayFetch = Callable[[], Awaitable[dict | None]]


def _utc(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)


def _iso(ts: datetime | None) -> str | None:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None


def _reading(value: float | None, ts: datetime | None, stale_before: datetime, source: str = "sensor") -> dict:
    ts = _utc(ts)
    stale = value is None or ts is None or ts < stale_before
    return {"value": value, "ts": _iso(ts), "stale": stale, "source": source}


def decode_relays(mask: int | None) -> dict[str, bool]:
    mask = mask or 0
    return {name: bool(mask & (1 << i)) for i, name in enumerate(RELAY_NAMES)}


def build_alarms(
    *, online: bool, gateway_ok: bool, flags: dict, pressure: float | None, p_min: float | None, p_max: float | None,
) -> list[dict]:
    if not gateway_ok:
        return [{"level": "ERROR", "code": "gateway_down", "text": "Шлюз устройств недоступен"}]
    if not online:
        return [{"level": "ERROR", "code": "no_link", "text": "Нет связи с контроллером котельной"}]
    alarms = []
    if flags.get("overtemp"):
        alarms.append({"level": "ERROR", "code": "overtemp", "text": "Перегрев котла — котёл отключён защитой"})
    if flags.get("boiler_sensor_lost"):
        alarms.append({"level": "ERROR", "code": "boiler_sensor_lost", "text": "Потерян датчик температуры котла"})
    if flags.get("autofill_fault"):
        alarms.append({"level": "ERROR", "code": "autofill_fault",
                       "text": "Автоподпитка заблокирована после аварийного таймаута (возможна утечка)"})
    if pressure is not None and p_min is not None and pressure < p_min:
        alarms.append({"level": "ERROR", "code": "pressure_low",
                       "text": f"Давление {pressure:.2f} бар ниже нормы {p_min:g}"})
    if pressure is not None and p_max is not None and pressure > p_max:
        alarms.append({"level": "ERROR", "code": "pressure_high",
                       "text": f"Давление {pressure:.2f} бар выше нормы {p_max:g}"})
    if flags.get("critical") and not alarms:
        alarms.append({"level": "ERROR", "code": "critical", "text": "Контроллер сообщает об аварии"})
    elif flags.get("warning") and not alarms:
        alarms.append({"level": "WARNING", "code": "warning", "text": "Контроллер сообщает о предупреждении"})
    return alarms


async def fetch_gateway_health(url: str, timeout: float) -> dict | None:
    try:
        async with httpx.AsyncClient(base_url=url, timeout=timeout) as client:
            resp = await client.get("/health")
            return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def _num(settings: dict[str, str], key: str, default: float | None = None) -> float | None:
    try:
        return float(settings[key])
    except (KeyError, ValueError):
        return default


class SchemeService:
    def __init__(self, db: AsyncSession, fetch_gateway: GatewayFetch):
        self.db = db
        self.fetch_gateway = fetch_gateway

    async def _latest_temps(self) -> dict[int, tuple[float, datetime]]:
        rows = await self.db.execute(
            select(SensorData.sensor_id, SensorData.value, SensorData.timestamp)
            .join(SensorDataType, SensorDataType.id == SensorData.datatype_id)
            .where(SensorDataType.code == "tmp")
        )
        return {sid: (value, ts) for sid, value, ts in rows}

    async def _latest_pressure(self, mount_point_name_hint: str) -> tuple[float, datetime] | None:
        """A pressure sensor bound in the catalog (mount point pressure_sensor_id)."""
        row = (await self.db.execute(
            select(SensorData.value, SensorData.timestamp)
            .join(SensorDataType, SensorDataType.id == SensorData.datatype_id)
            .join(MountPoint, MountPoint.pressure_sensor_id == SensorData.sensor_id)
            .where(SensorDataType.code == "prs", MountPoint.system_id == (1 if mount_point_name_hint == "heating" else 2))
            .order_by(desc(SensorData.timestamp)).limit(1)
        )).first()
        return (row[0], row[1]) if row else None

    async def build_state(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        settings_all = await SettingsRepository(self.db).get_all()
        settings = {k: v for k, v in settings_all.items() if k not in SECRET_KEYS}
        stale_minutes = int(_num(settings_all, "sensor_stale_minutes", 5) or 5)
        hb_timeout = int(_num(settings_all, "heartbeat_timeout_seconds", 60) or 60)
        stale_before = now - timedelta(minutes=stale_minutes)

        temps = await self._latest_temps()
        names = dict((await self.db.execute(select(Sensor.name, Sensor.id))).all())
        values: dict[str, dict] = {role: _reading(None, None, stale_before) for role in ALL_ROLES}

        def put(role: str, sensor_id: int | None) -> None:
            if sensor_id is not None and sensor_id in temps:
                value, ts = temps[sensor_id]
                values[role] = _reading(round(float(value), 2), ts, stale_before)

        circuits = (await self.db.execute(select(HeatingCircuit))).scalars().all()
        mp_sensor = dict((await self.db.execute(select(MountPoint.id, MountPoint.temperature_sensor_id))).all())
        for c in circuits:
            roles = CIRCUIT_ROLES.get(c.config_prefix or "")
            if roles:
                put(roles[0], mp_sensor.get(c.supply_mount_point_id))
                put(roles[1], mp_sensor.get(c.return_mount_point_id))
        for role, name in WATER_SENSORS.items():
            put(role, names.get(name))
        put("boiler_room", names.get(BOILER_ROOM_SENSOR))
        outdoor_id = await SensorRepository(self.db).get_outdoor_sensor_id()
        put("outdoor", outdoor_id)

        excluded = {outdoor_id, names.get(BOILER_ROOM_SENSOR)} | {names.get(n) for n in UNHEATED_SENSORS}
        climate_ids = (await self.db.execute(
            select(Sensor.id).join(MountPoint, MountPoint.id == Sensor.mount_point_id)
            .where(MountPoint.system_id == CLIMATE_SYSTEM_ID)
        )).scalars().all()
        fresh = [temps[i] for i in climate_ids if i not in excluded and i in temps
                 and _utc(temps[i][1]) >= stale_before]
        if fresh:
            values["indoor_avg"] = _reading(round(sum(v for v, _ in fresh) / len(fresh), 1),
                                            max(_utc(ts) for _, ts in fresh), stale_before)

        # Controller via gateway
        gw = await self.fetch_gateway()
        gateway_ok = gw is not None
        hb = (gw or {}).get("heartbeats", {}).get(CONTROLLER_DEVICE)
        last_seen = _utc(datetime.fromisoformat(hb["timestamp"])) if hb and hb.get("timestamp") else None
        online = last_seen is not None and (now - last_seen).total_seconds() < hb_timeout
        data = (hb or {}).get("data", {}) if online else {}
        flags = {k: bool(data.get(k, False)) for k in FLAG_KEYS}
        controller = {
            "online": online,
            "last_seen": _iso(last_seen),
            "relays": decode_relays(data.get("relays")),
            "flags": flags,
            "targets": {
                "boiler": data.get("boiler_auto_target"), "rad": data.get("rad_target"),
                "floor": data.get("floor_target"), "ihb": data.get("ihb_target"),
            },
        }

        # Pressure: catalog sensor first, heartbeat as fallback
        for role, system, hb_key in (("heating_pressure", "heating", "prs_heat"), ("water_pressure", "water", "prs_water")):
            bound = await self._latest_pressure(system)
            if bound:
                values[role] = _reading(round(float(bound[0]), 2), bound[1], stale_before)
            elif hb and hb.get("data", {}).get(hb_key) is not None:
                values[role] = _reading(float(hb["data"][hb_key]), last_seen, now - timedelta(seconds=hb_timeout), "heartbeat")
                if not online:
                    values[role]["stale"] = True

        sync = (gw or {}).get("sync", {}).get(CONTROLLER_DEVICE, {})
        pressure = values["heating_pressure"]["value"] if not values["heating_pressure"]["stale"] else None
        alarms = build_alarms(
            online=online, gateway_ok=gateway_ok, flags=flags, pressure=pressure,
            p_min=_num(settings_all, "heating_pressure_min"), p_max=_num(settings_all, "heating_pressure_max"),
        )
        events = (await self.db.execute(select(EventLog).order_by(desc(EventLog.timestamp)).limit(3))).scalars().all()

        return {
            "generated_at": _iso(now),
            "values": values,
            "controller": controller,
            "settings": settings,
            "sync": {"pending": list(sync.get("pending", [])), "unsynced": list(sync.get("unsynced", []))},
            "alarms": alarms,
            "events": [{"ts": _iso(_utc(e.timestamp)), "level": e.level, "text": e.message or ""} for e in events],
            "stale_minutes": stale_minutes,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest -q tests/test_scheme_service.py`
Expected: все PASS. Если `test_state_values_by_role` падает на `heating_pressure` из-за `ts`, сверить: `ts` = `controller.last_seen` (оба из heartbeat).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scheme_service.py backend/tests/test_scheme_service.py
git commit -m "Scheme: state service (roles, controller, sync, alarms)"
```

---

### Task 4: Бэкенд — эндпоинт `GET /api/v1/scheme/state`

**Files:**
- Create: `backend/app/api/v1/scheme.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_scheme_api.py`; существующий `tests/test_rbac.py` автоматически проверит, что маршрут закрыт.

**Interfaces:**
- Consumes: `SchemeService`, `fetch_gateway_health` (Task 3), `get_settings().device_gateway_url`.
- Produces: `GET /api/v1/scheme/state` → JSON из §5.1 спеки.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_scheme_api.py`:

```python
import pytest

from app.core.security import get_password_hash
from app.models.config import ConfigKV
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_scheme_state_requires_login(client):
    assert (await client.get("/api/v1/scheme/state")).status_code in (401, 403)


@pytest.mark.asyncio
async def test_scheme_state_for_viewer(client, db_session):
    db_session.add_all([
        User(username="viewer", password_hash=get_password_hash("viewer123"), email="v@test.com",
             role=UserRole.VIEWER.value),
        ConfigKV(key="mqtt_pass", value="secret"),
        ConfigKV(key="device_gateway_url", value="http://127.0.0.1:9"),
    ])
    await db_session.commit()
    token = (await client.post("/api/v1/auth/login", json={"username": "viewer", "password": "viewer123"})).json()["access_token"]
    resp = await client.get("/api/v1/scheme/state", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["controller"]["online"] is False          # no gateway in tests
    assert "mqtt_pass" not in body["settings"]
    assert set(body) >= {"values", "controller", "settings", "sync", "alarms", "events", "stale_minutes"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python3 -m pytest -q tests/test_scheme_api.py`
Expected: FAIL — 404.

- [ ] **Step 3: Implement**

`backend/app/api/v1/scheme.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.settings_repository import SettingsRepository
from app.services.scheme_service import SchemeService, fetch_gateway_health

router = APIRouter()


@router.get("/state")
async def scheme_state(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Everything the scheme page draws, in one response (any logged-in role)."""
    kv = await SettingsRepository(db).get_all()
    url = kv.get("device_gateway_url") or get_settings().device_gateway_url
    try:
        timeout = float(kv.get("gateway_timeout_seconds", "3"))
    except ValueError:
        timeout = 3.0

    async def fetch():
        return await fetch_gateway_health(url, timeout)

    return await SchemeService(db, fetch).build_state()
```

`backend/app/api/router.py`: импорт `from app.api.v1.scheme import router as scheme_router` и строка после подключения `sensor_router`:

```python
api_v1_router.include_router(scheme_router, prefix="/scheme", tags=["scheme"])
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest -q tests/test_scheme_api.py tests/test_rbac.py`
Expected: все PASS (в `test_rbac` появится параметр `GET /api/v1/scheme/state` → 401/403).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/scheme.py backend/app/api/router.py backend/tests/test_scheme_api.py
git commit -m "Scheme: GET /api/v1/scheme/state"
```

---

### Task 5: Фронтенд — тестовая инфраструктура, типы, цвет труб, права

**Files:**
- Modify: `frontend/package.json` (devDependencies, script `test`)
- Create: `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`
- Create: `frontend/src/scheme/types.ts`, `frontend/src/scheme/pipeColor.ts`, `frontend/src/scheme/permissions.ts`
- Test: `frontend/src/scheme/pipeColor.test.ts`, `backend/tests/test_scheme_permissions_mirror.py`

**Interfaces:**
- Produces (TS):
  - `types.ts`: `Reading`, `RoleKey`, `RelayName`, `ControllerState`, `SchemeAlarm`, `SchemeEvent`, `SchemeState`, `ElementKind`
  - `pipeColor(temp: number | null | undefined, kind: PipeKind): string`, `type PipeKind = "supply" | "return" | "cold" | "hot" | "fill"`
  - `ADMIN_ONLY_KEYS: readonly string[]`, `canEdit(role: string | undefined, key: string): boolean`

- [ ] **Step 1: Install dev dependencies and config**

```bash
cd frontend && npm install -D vitest@^3 @testing-library/react@^16 @testing-library/jest-dom@^6 @testing-library/user-event@^14 jsdom@^25
```

`package.json` → `"scripts"`: добавить `"test": "vitest run"`.

`frontend/vitest.config.ts`:

```ts
import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
    },
  }),
);
```

`frontend/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 2: Write the failing tests**

`frontend/src/scheme/pipeColor.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { pipeColor } from "./pipeColor";

describe("pipeColor", () => {
  it("is blue at or below 25 °C and red at or above 70 °C", () => {
    expect(pipeColor(10, "supply")).toBe("#3b82f6");
    expect(pipeColor(25, "supply")).toBe("#3b82f6");
    expect(pipeColor(70, "return")).toBe("#ef4444");
    expect(pipeColor(90, "return")).toBe("#ef4444");
  });
  it("interpolates in between", () => {
    const mid = pipeColor(47.5, "supply");
    expect(mid).not.toBe("#3b82f6");
    expect(mid).not.toBe("#ef4444");
    expect(mid).toMatch(/^#[0-9a-f]{6}$/);
  });
  it("falls back to the pipe kind colour without a value", () => {
    expect(pipeColor(null, "supply")).toBe("#ef4444");
    expect(pipeColor(undefined, "return")).toBe("#3b82f6");
    expect(pipeColor(null, "cold")).toBe("#0ea5e9");
    expect(pipeColor(null, "fill")).toBe("#0ea5e9");
    expect(pipeColor(null, "hot")).toBe("#f97316");
  });
});
```

`backend/tests/test_scheme_permissions_mirror.py`:

```python
"""The scheme UI mirrors admin-only settings — keep both lists identical."""

import re
from pathlib import Path

from app.core.setting_rules import RULES

TS = Path(__file__).resolve().parents[2] / "frontend/src/scheme/permissions.ts"


def test_admin_only_keys_mirror_backend():
    text = TS.read_text(encoding="utf-8")
    block = re.search(r"ADMIN_ONLY_KEYS = \[(.*?)\]", text, re.S).group(1)
    ui = set(re.findall(r'"([a-z_]+)"', block))
    backend = {k for k, r in RULES.items() if r.admin_only and r.device}
    assert ui == backend
```

- [ ] **Step 3: Run to verify they fail**

Run: `cd frontend && npx vitest run src/scheme` → FAIL (module not found).
Run: `cd backend && python3 -m pytest -q tests/test_scheme_permissions_mirror.py` → FAIL (`FileNotFoundError`).

- [ ] **Step 4: Implement**

`frontend/src/scheme/types.ts`:

```ts
export interface Reading {
  value: number | null;
  ts: string | null;
  stale: boolean;
  source?: "sensor" | "heartbeat";
}

export type RoleKey =
  | "boiler_supply" | "boiler_return" | "rad_supply" | "rad_return"
  | "floor_supply" | "floor_return" | "tank" | "coil_return"
  | "cold_water" | "hot_water" | "heating_pressure" | "water_pressure"
  | "outdoor" | "indoor_avg" | "boiler_room";

export type RelayName =
  | "boiler" | "rad_pump" | "floor_pump" | "ihb_pump" | "water_pump" | "water_hot_pump" | "teh"
  | "af_open" | "af_close" | "rad_open" | "rad_close" | "floor_open" | "floor_close"
  | "lamp_warning" | "lamp_critical" | "spare";

export interface ControllerState {
  online: boolean;
  last_seen: string | null;
  relays: Record<RelayName, boolean>;
  flags: Record<string, boolean>;
  targets: { boiler: number | null; rad: number | null; floor: number | null; ihb: number | null };
}

export interface SchemeAlarm { level: "ERROR" | "WARNING"; code: string; text: string }
export interface SchemeEvent { ts: string | null; level: string; text: string }

export interface SchemeState {
  generated_at: string;
  values: Record<RoleKey, Reading>;
  controller: ControllerState;
  settings: Record<string, string>;
  sync: { pending: string[]; unsynced: string[] };
  alarms: SchemeAlarm[];
  events: SchemeEvent[];
  stale_minutes: number;
}

export type ElementKind = "boiler" | "autofill" | "rad" | "floor" | "tank" | "cold" | "hot" | "sensor";
```

`frontend/src/scheme/pipeColor.ts`:

```ts
export type PipeKind = "supply" | "return" | "cold" | "hot" | "fill";

const COLD = [0x3b, 0x82, 0xf6]; // #3b82f6
const HOT = [0xef, 0x44, 0x44];  // #ef4444
const KIND_DEFAULT: Record<PipeKind, string> = {
  supply: "#ef4444", return: "#3b82f6", cold: "#0ea5e9", hot: "#f97316", fill: "#0ea5e9",
};

const hex = (rgb: number[]) => "#" + rgb.map((c) => Math.round(c).toString(16).padStart(2, "0")).join("");

/** Pipe colour by water temperature: ≤25 °C blue → ≥70 °C red. */
export function pipeColor(temp: number | null | undefined, kind: PipeKind): string {
  if (temp == null || kind === "cold" || kind === "fill") return KIND_DEFAULT[kind];
  const t = Math.min(1, Math.max(0, (temp - 25) / 45));
  return hex(COLD.map((c, i) => c + (HOT[i]! - c) * t));
}
```

`frontend/src/scheme/permissions.ts`:

```ts
/** Mirror of backend/app/core/setting_rules.py admin-only device keys
 *  (kept identical by backend/tests/test_scheme_permissions_mirror.py). */
export const ADMIN_ONLY_KEYS = [
  "heating_boiler_max_temp",
  "heating_pressure_min",
  "heating_pressure_max",
] as const;

export function canEdit(role: string | undefined, key: string): boolean {
  if (role === "admin") return true;
  if (role !== "operator") return false;
  return !(ADMIN_ONLY_KEYS as readonly string[]).includes(key);
}
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npx vitest run && npx tsc -b --noEmit` → PASS.
Run: `cd backend && python3 -m pytest -q tests/test_scheme_permissions_mirror.py` → PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/src/test frontend/src/scheme backend/tests/test_scheme_permissions_mirror.py
git commit -m "Scheme UI: vitest setup, types, pipe colour, permissions mirror"
```

---

### Task 6: Фронтенд — SVG-элементы приборов и стили схемы

**Files:**
- Create: `frontend/src/scheme/elements/Pipe.tsx`, `Pump.tsx`, `MixingValve.tsx`, `FillValve.tsx`, `Gauge.tsx`, `ValueTag.tsx`, `Boiler.tsx`, `Separator.tsx`, `Radiators.tsx`, `FloorLoops.tsx`, `Tank.tsx`, `Tap.tsx`, `index.ts`
- Modify: `frontend/src/index.css` (переменные темы и анимации)
- Test: `frontend/src/scheme/elements/elements.test.tsx`

**Interfaces:**
- Consumes: `pipeColor`, `PipeKind`, `Reading`.
- Produces (все — `<g>`-компоненты для вставки внутрь `<svg>`, координаты — центр/левый верх, как указано):
  - `Pipe({ points: [number, number][]; color: string; flowing: boolean; width?: number })`
  - `Pump({ x, y, running: boolean; r?: number })` — `data-state="running"|"stopped"`
  - `MixingValve({ x, y, direction: "open" | "close" | null })` — `data-state`
  - `FillValve({ x, y, state: "closed" | "opening" | "closing" | "fault" })` — `data-state`
  - `Gauge({ x, y, value: number | null; min?: number; max?: number; lo?: number | null; hi?: number | null })`
  - `ValueTag({ x, y, reading: Reading | undefined; unit: string; target?: number | null; digits?: number })` — текст `—` при `stale`
  - `Boiler({ x, y, on: boolean; auto: boolean; alarm: boolean })` — 120×170
  - `Separator({ x, y })` — гидрострелка 36×150 + коллектор 200×110 справа
  - `Radiators({ x, y, warmth: number })` — 260×46 (warmth 0..1)
  - `FloorLoops({ x, y, warmth: number })` — 160×46
  - `Tank({ x, y, fill: number; teh: boolean })` — 80×190 (fill 0..1 — «нагрев»)
  - `Tap({ x, y })` — душ 24×24

- [ ] **Step 1: Write the failing tests**

`frontend/src/scheme/elements/elements.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FillValve, MixingValve, Pump, ValueTag } from ".";

const svg = (el: React.ReactNode) => render(<svg>{el}</svg>);

describe("scheme elements", () => {
  it("pump shows running vs stopped", () => {
    const { container, rerender } = svg(<Pump x={10} y={10} running />);
    expect(container.querySelector("[data-state='running']")).not.toBeNull();
    rerender(<svg><Pump x={10} y={10} running={false} /></svg>);
    expect(container.querySelector("[data-state='stopped']")).not.toBeNull();
  });

  it("mixing valve shows the pulse direction", () => {
    const { container } = svg(<MixingValve x={0} y={0} direction="open" />);
    expect(container.querySelector("[data-state='open']")).not.toBeNull();
  });

  it("fill valve fault state", () => {
    const { container } = svg(<FillValve x={0} y={0} state="fault" />);
    expect(container.querySelector("[data-state='fault']")).not.toBeNull();
  });

  it("value tag shows the value, target and a dash when stale", () => {
    const { rerender } = svg(
      <ValueTag x={0} y={0} unit="°" reading={{ value: 54.12, ts: null, stale: false }} target={54} />,
    );
    expect(screen.getByText("54.1°")).toBeInTheDocument();
    expect(screen.getByText("/54")).toBeInTheDocument();
    rerender(<svg><ValueTag x={0} y={0} unit="°" reading={{ value: 54.12, ts: null, stale: true }} /></svg>);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npx vitest run src/scheme/elements`
Expected: FAIL — cannot resolve `.`.

- [ ] **Step 3: Implement the elements**

`frontend/src/scheme/elements/Pipe.tsx`:

```tsx
export function Pipe({ points, color, flowing, width = 6 }: {
  points: [number, number][]; color: string; flowing: boolean; width?: number;
}) {
  const d = points.map(([x, y], i) => `${i ? "L" : "M"}${x} ${y}`).join(" ");
  return (
    <g>
      <path d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" />
      {/* light highlight gives the pipe some volume */}
      <path d={d} fill="none" stroke="#fff" strokeOpacity={0.25} strokeWidth={width / 3}
            strokeLinecap="round" strokeLinejoin="round" transform={`translate(0 ${-width / 4})`} />
      {flowing && (
        <path d={d} fill="none" stroke="#fff" strokeOpacity={0.7} strokeWidth={width / 3}
              strokeDasharray="4 14" className="scheme-flow" />
      )}
    </g>
  );
}
```

`Pump.tsx`:

```tsx
export function Pump({ x, y, running, r = 13 }: { x: number; y: number; running: boolean; r?: number }) {
  return (
    <g transform={`translate(${x} ${y})`} data-state={running ? "running" : "stopped"}>
      <circle r={r} fill="var(--scheme-device)" stroke={running ? "#16a34a" : "var(--scheme-muted)"} strokeWidth={3} />
      <g className={running ? "scheme-spin" : undefined}>
        <path d={`M0 ${-r * 0.65} L${r * 0.3} 0 L0 ${r * 0.65} L${-r * 0.3} 0 Z`} fill={running ? "#16a34a" : "var(--scheme-muted)"} />
        <path d={`M${-r * 0.65} 0 L0 ${r * 0.3} L${r * 0.65} 0 L0 ${-r * 0.3} Z`} fill={running ? "#16a34a" : "var(--scheme-muted)"} opacity={0.6} />
      </g>
    </g>
  );
}
```

`MixingValve.tsx`:

```tsx
export function MixingValve({ x, y, direction }: { x: number; y: number; direction: "open" | "close" | null }) {
  const active = direction !== null;
  const fill = active ? "#f59e0b" : "var(--scheme-muted)";
  return (
    <g transform={`translate(${x} ${y})`} data-state={direction ?? "idle"}>
      <polygon points="-10,-8 0,0 -10,8" fill={fill} />
      <polygon points="10,-8 0,0 10,8" fill={fill} />
      <polygon points="-8,10 0,0 8,10" fill={fill} opacity={0.7} />
      {active && (
        <text x={14} y={4} fontSize={12} fill="#f59e0b" className="scheme-blink">
          {direction === "open" ? "↑" : "↓"}
        </text>
      )}
    </g>
  );
}
```

`FillValve.tsx`:

```tsx
const COLORS = { closed: "var(--scheme-muted)", opening: "#0ea5e9", closing: "#f59e0b", fault: "#dc2626" } as const;

export function FillValve({ x, y, state }: { x: number; y: number; state: keyof typeof COLORS }) {
  return (
    <g transform={`translate(${x} ${y})`} data-state={state} className={state === "fault" ? "scheme-blink" : undefined}>
      <polygon points="-10,-8 0,0 -10,8" fill={COLORS[state]} />
      <polygon points="10,-8 0,0 10,8" fill={COLORS[state]} />
      <rect x={-3} y={-18} width={6} height={10} fill={COLORS[state]} />
    </g>
  );
}
```

`Gauge.tsx`:

```tsx
/** Manometer; needle sweeps −120°..+120° over min..max; green arc = lo..hi. */
export function Gauge({ x, y, value, min = 0, max = 4, lo = null, hi = null }: {
  x: number; y: number; value: number | null; min?: number; max?: number; lo?: number | null; hi?: number | null;
}) {
  const angle = (v: number) => -120 + (240 * (Math.min(max, Math.max(min, v)) - min)) / (max - min);
  const polar = (deg: number, rad: number): [number, number] => {
    const a = ((deg - 90) * Math.PI) / 180;
    return [rad * Math.cos(a), rad * Math.sin(a)];
  };
  const arc = (from: number, to: number, rad: number) => {
    const [x1, y1] = polar(angle(from), rad);
    const [x2, y2] = polar(angle(to), rad);
    const large = angle(to) - angle(from) > 180 ? 1 : 0;
    return `M${x1} ${y1} A${rad} ${rad} 0 ${large} 1 ${x2} ${y2}`;
  };
  const [nx, ny] = polar(value == null ? -120 : angle(value), 13);
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle r={18} fill="var(--scheme-device)" stroke="var(--scheme-stroke)" strokeWidth={2} />
      {lo != null && hi != null && <path d={arc(lo, hi, 15)} stroke="#22c55e" strokeWidth={3} fill="none" />}
      <line x1={0} y1={0} x2={nx} y2={ny} stroke="#dc2626" strokeWidth={2} strokeLinecap="round" />
      <circle r={2.5} fill="var(--scheme-stroke)" />
    </g>
  );
}
```

`ValueTag.tsx`:

```tsx
import type { Reading } from "../types";

export function ValueTag({ x, y, reading, unit, target, digits = 1 }: {
  x: number; y: number; reading: Reading | undefined; unit: string; target?: number | null; digits?: number;
}) {
  const ok = reading && !reading.stale && reading.value != null;
  const text = ok ? `${reading!.value!.toFixed(digits)}${unit}` : "—";
  const width = 14 + text.length * 7 + (target != null ? 26 : 0);
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect width={width} height={20} rx={3} fill="var(--scheme-tag-bg)" />
      <text x={6} y={14} fontSize={12} fontWeight={600} fill={ok ? "var(--scheme-tag-fg)" : "var(--scheme-muted)"}
            style={{ fontVariantNumeric: "tabular-nums" }}>
        {text}
      </text>
      {target != null && (
        <text x={10 + text.length * 7} y={14} fontSize={10} fill="var(--scheme-muted)">{`/${Math.round(target)}`}</text>
      )}
    </g>
  );
}
```

`Boiler.tsx`:

```tsx
export function Boiler({ x, y, on, auto, alarm }: { x: number; y: number; on: boolean; auto: boolean; alarm: boolean }) {
  return (
    <g transform={`translate(${x} ${y})`} className={alarm ? "scheme-blink" : undefined}>
      <rect width={120} height={170} rx={12} fill="var(--scheme-device)" stroke={alarm ? "#dc2626" : "var(--scheme-stroke)"} strokeWidth={2} />
      <rect x={10} y={10} width={100} height={28} rx={5} fill="var(--scheme-panel)" />
      <circle cx={24} cy={24} r={5} fill={on ? "#22c55e" : "var(--scheme-muted)"} />
      <text x={36} y={29} fontSize={12} fontWeight={700} fill="var(--scheme-text)">Котёл</text>
      {/* flame window */}
      <rect x={35} y={70} width={50} height={60} rx={8} fill="var(--scheme-panel)" />
      {on && (
        <path d="M60 122 C45 108 52 92 60 80 C62 94 74 96 70 110 C68 118 64 121 60 122 Z" fill="#f97316" className="scheme-flicker" />
      )}
      <text x={60} y={155} fontSize={11} textAnchor="middle" fill="var(--scheme-muted)">{auto ? "авто" : "ручной"}</text>
      {/* vents */}
      {[0, 1, 2, 3, 4].map((i) => <rect key={i} x={20 + i * 18} y={160} width={10} height={3} fill="var(--scheme-muted)" />)}
    </g>
  );
}
```

`Separator.tsx`:

```tsx
/** Hydraulic separator (vertical) + distribution manifold (supply bar top, return bar bottom). */
export function Separator({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect width={36} height={150} rx={10} fill="var(--scheme-device)" stroke="var(--scheme-stroke)" strokeWidth={2} />
      <rect x={14} y={-14} width={8} height={14} fill="#d97706" /> {/* air vent */}
      <rect x={36} y={15} width={200} height={30} rx={8} fill="#fecaca" stroke="var(--scheme-stroke)" />
      <rect x={36} y={95} width={200} height={30} rx={8} fill="#bfdbfe" stroke="var(--scheme-stroke)" />
    </g>
  );
}
```

`Radiators.tsx`:

```tsx
/** Three sectional radiators; warmth 0..1 tints the fins. */
export function Radiators({ x, y, warmth }: { x: number; y: number; warmth: number }) {
  const tint = `rgba(239,68,68,${0.15 + 0.5 * Math.min(1, Math.max(0, warmth))})`;
  return (
    <g transform={`translate(${x} ${y})`}>
      {[0, 95, 190].map((dx) => (
        <g key={dx} transform={`translate(${dx} 0)`}>
          <rect width={70} height={46} rx={4} fill="var(--scheme-device)" stroke="var(--scheme-stroke)" />
          {Array.from({ length: 7 }, (_, i) => (
            <rect key={i} x={5 + i * 9.3} y={4} width={6} height={38} rx={2} fill={tint} />
          ))}
        </g>
      ))}
    </g>
  );
}
```

`FloorLoops.tsx`:

```tsx
/** Three spiral underfloor loops. */
export function FloorLoops({ x, y, warmth }: { x: number; y: number; warmth: number }) {
  const color = `rgba(239,68,68,${0.35 + 0.55 * Math.min(1, Math.max(0, warmth))})`;
  const spiral = "M4 4 H42 V42 H8 V10 H36 V36 H14 V16 H30 V30 H20 V22";
  return (
    <g transform={`translate(${x} ${y})`}>
      {[0, 56, 112].map((dx) => (
        <path key={dx} d={spiral} transform={`translate(${dx} 0)`} fill="none" stroke={color} strokeWidth={2.5} />
      ))}
    </g>
  );
}
```

`Tank.tsx`:

```tsx
/** DHW tank with coil; fill 0..1 = heat level (red top / blue bottom), TEH element at the bottom. */
export function Tank({ x, y, fill, teh }: { x: number; y: number; fill: number; teh: boolean }) {
  const hot = 190 * Math.min(1, Math.max(0.1, fill));
  return (
    <g transform={`translate(${x} ${y})`}>
      <defs>
        <linearGradient id="tank-heat" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ef4444" />
          <stop offset={hot / 190} stopColor="#f97316" />
          <stop offset="1" stopColor="#3b82f6" />
        </linearGradient>
      </defs>
      <rect width={80} height={190} rx={36} fill="url(#tank-heat)" opacity={0.25} />
      <rect width={80} height={190} rx={36} fill="none" stroke="var(--scheme-stroke)" strokeWidth={2} />
      <path d="M20 60 q20 10 40 0 q-20 10 -40 20 q20 10 40 0 q-20 10 -40 20" fill="none" stroke="var(--scheme-muted)" strokeWidth={2} />
      <rect x={22} y={160} width={36} height={6} rx={3} fill={teh ? "#f97316" : "var(--scheme-muted)"} className={teh ? "scheme-blink" : undefined} />
    </g>
  );
}
```

`Tap.tsx`:

```tsx
export function Tap({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`} stroke="var(--scheme-stroke)" fill="none" strokeWidth={2}>
      <path d="M0 24 V6 H14" />
      <path d="M8 6 h14 l-3 6 h-8 Z" fill="var(--scheme-device)" />
      <path d="M12 16 v4 M16 16 v5 M20 16 v4" stroke="#0ea5e9" />
    </g>
  );
}
```

`index.ts`:

```ts
export { Pipe } from "./Pipe";
export { Pump } from "./Pump";
export { MixingValve } from "./MixingValve";
export { FillValve } from "./FillValve";
export { Gauge } from "./Gauge";
export { ValueTag } from "./ValueTag";
export { Boiler } from "./Boiler";
export { Separator } from "./Separator";
export { Radiators } from "./Radiators";
export { FloorLoops } from "./FloorLoops";
export { Tank } from "./Tank";
export { Tap } from "./Tap";
```

- [ ] **Step 4: Add theme variables and animations to `frontend/src/index.css`** (в конец файла):

```css
/* ---- Scheme (SCADA page) ---- */
:root {
  --scheme-bg: #f1f5f9;
  --scheme-device: #ffffff;
  --scheme-panel: #e2e8f0;
  --scheme-stroke: #64748b;
  --scheme-muted: #94a3b8;
  --scheme-text: #0f172a;
  --scheme-tag-bg: #0f172a;
  --scheme-tag-fg: #fde68a;
}
html.dark {
  --scheme-bg: #111827;
  --scheme-device: #1f2937;
  --scheme-panel: #374151;
  --scheme-stroke: #94a3b8;
  --scheme-muted: #6b7280;
  --scheme-text: #f3f4f6;
  --scheme-tag-bg: #000000;
  --scheme-tag-fg: #fde68a;
}
@keyframes scheme-spin { to { transform: rotate(360deg); } }
@keyframes scheme-flow { to { stroke-dashoffset: -36; } }
@keyframes scheme-blink { 50% { opacity: 0.35; } }
@keyframes scheme-flicker { 50% { transform: scale(0.94); } }
.scheme-spin { animation: scheme-spin 1.2s linear infinite; transform-box: fill-box; transform-origin: center; }
.scheme-flow { animation: scheme-flow 1s linear infinite; }
.scheme-blink { animation: scheme-blink 1s step-end infinite; }
.scheme-flicker { animation: scheme-flicker 0.6s ease-in-out infinite; transform-box: fill-box; transform-origin: bottom; }
@media (prefers-reduced-motion: reduce) {
  .scheme-spin, .scheme-flow, .scheme-blink, .scheme-flicker { animation: none; }
}
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npx vitest run && npx tsc -b --noEmit`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/scheme/elements frontend/src/index.css
git commit -m "Scheme UI: illustrated SVG device elements and theme"
```

---

### Task 7: Фронтенд — раскладки, холст схемы и загрузка состояния

**Files:**
- Create: `frontend/src/scheme/layouts.ts`, `frontend/src/scheme/SchemeCanvas.tsx`, `frontend/src/scheme/useSchemeState.ts`
- Test: `frontend/src/scheme/SchemeCanvas.test.tsx`

**Interfaces:**
- Consumes: элементы (Task 6), `pipeColor`, типы (Task 5).
- Produces:
  - `type LayoutName = "wide" | "tall"`; `LAYOUTS: Record<LayoutName, LayoutDef>`; `chooseLayout(width: number): LayoutName` (≥ 900 → `"wide"`)
  - `SchemeCanvas({ state: SchemeState; layout: LayoutName; onOpen: (kind: ElementKind, role?: RoleKey) => void })`
  - `useSchemeState(opts?: { fast?: boolean }) -> { data: SchemeState | undefined; isLoading: boolean; refetch: () => void }` (queryKey `["scheme-state"]`)

- [ ] **Step 1: Write the failing tests**

`frontend/src/scheme/SchemeCanvas.test.tsx`:

```tsx
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { chooseLayout } from "./layouts";
import { SchemeCanvas } from "./SchemeCanvas";
import type { SchemeState } from "./types";

const reading = (value: number | null) => ({ value, ts: "2026-01-20T12:00:00Z", stale: false });

export function makeState(over: Partial<SchemeState["controller"]> = {}): SchemeState {
  const relays = Object.fromEntries(
    ["boiler", "rad_pump", "floor_pump", "ihb_pump", "water_pump", "water_hot_pump", "teh", "af_open", "af_close",
     "rad_open", "rad_close", "floor_open", "floor_close", "lamp_warning", "lamp_critical", "spare"].map((r) => [r, false]),
  ) as SchemeState["controller"]["relays"];
  return {
    generated_at: "2026-01-20T12:00:00Z",
    values: Object.fromEntries(
      ["boiler_supply", "boiler_return", "rad_supply", "rad_return", "floor_supply", "floor_return", "tank",
       "coil_return", "cold_water", "hot_water", "heating_pressure", "water_pressure", "outdoor", "indoor_avg",
       "boiler_room"].map((k) => [k, reading(40)]),
    ) as SchemeState["values"],
    controller: { online: true, last_seen: "2026-01-20T12:00:00Z", relays: { ...relays, rad_pump: true },
                  flags: {}, targets: { boiler: 56, rad: 54, floor: 29, ihb: 55 }, ...over },
    settings: { heating_boiler_automode: "1", heating_pressure_min: "1.0", heating_pressure_max: "2.0" },
    sync: { pending: [], unsynced: [] },
    alarms: [], events: [], stale_minutes: 5,
  };
}

describe("layouts", () => {
  it("picks the wide layout from 900 px", () => {
    expect(chooseLayout(1200)).toBe("wide");
    expect(chooseLayout(900)).toBe("wide");
    expect(chooseLayout(899)).toBe("tall");
  });
});

describe("SchemeCanvas", () => {
  for (const layout of ["wide", "tall"] as const) {
    it(`${layout}: radiator pump running, floor pump stopped`, () => {
      const { container } = render(<SchemeCanvas state={makeState()} layout={layout} onOpen={() => {}} />);
      expect(container.querySelector("[data-element='rad_pump'] [data-state='running']")).not.toBeNull();
      expect(container.querySelector("[data-element='floor_pump'] [data-state='stopped']")).not.toBeNull();
    });
  }

  it("opens the circuit dialog on click and keyboard", () => {
    const onOpen = vi.fn();
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={onOpen} />);
    const rad = container.querySelector("[data-element='radiators']")!;
    fireEvent.click(rad);
    fireEvent.keyDown(rad, { key: "Enter" });
    expect(onOpen).toHaveBeenNthCalledWith(1, "rad", undefined);
    expect(onOpen).toHaveBeenCalledTimes(2);
  });

  it("dims everything when the controller is offline", () => {
    const { container } = render(<SchemeCanvas state={makeState({ online: false })} layout="wide" onOpen={() => {}} />);
    expect(container.querySelector("[data-offline='true']")).not.toBeNull();
  });

  it("shows night and DHW priority badges", () => {
    const state = makeState({ flags: { schedule_rad: true, ihb_heating: true } });
    state.settings.heating_floorheating_pump = "1";   // floor pump commanded on, relay off → DHW priority
    const { container } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} />);
    expect(container.querySelector("[data-badges='rad']")?.textContent).toContain("Ночь");
    expect(container.querySelector("[data-badges='floor']")?.textContent).toContain("Приоритет ГВС");
  });

  it("shows autofill lockout", () => {
    const { container } = render(
      <SchemeCanvas state={makeState({ flags: { autofill_fault: true } })} layout="wide" onOpen={() => {}} />,
    );
    expect(container.querySelector("[data-element='autofill'] [data-state='fault']")).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npx vitest run src/scheme/SchemeCanvas.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement layouts**

`frontend/src/scheme/layouts.ts`:

```ts
import type { PipeKind } from "./pipeColor";
import type { RelayName, RoleKey } from "./types";

export type LayoutName = "wide" | "tall";
type Pt = [number, number];

export interface PipeDef {
  kind: PipeKind;
  role?: RoleKey;            // temperature that colours the pipe
  flow?: RelayName | "any";  // relay that makes it flow ("any" = any circulation pump)
  points: Pt[];
}

export interface LayoutDef {
  width: number;
  height: number;
  boiler: Pt; separator: Pt; gauge: Pt; autofill: Pt; radiators: Pt; floor: Pt; tank: Pt; tap: Pt;
  radPump: Pt; radValve: Pt; floorPump: Pt; floorValve: Pt; ihbPump: Pt; recircPump: Pt; coldPump: Pt;
  tags: Partial<Record<RoleKey, Pt>>;
  labels: { text: string; at: Pt }[];
  badges: { rad: Pt; floor: Pt; tank: Pt };
  pipes: PipeDef[];
}

export const LAYOUTS: Record<LayoutName, LayoutDef> = {
  wide: {
    width: 1000, height: 560,
    boiler: [40, 250], separator: [330, 270], gauge: [466, 340], autofill: [300, 470],
    radiators: [250, 50], floor: [360, 470], tank: [700, 250], tap: [888, 222],
    radPump: [440, 175], radValve: [440, 223], floorPump: [440, 432], floorValve: [440, 455],
    ihbPump: [630, 300], recircPump: [840, 280], coldPump: [880, 420],
    tags: {
      boiler_supply: [175, 270], boiler_return: [175, 390], rad_supply: [455, 130], rad_return: [330, 140],
      floor_supply: [455, 400], floor_return: [330, 420], tank: [708, 320], coil_return: [590, 395],
      cold_water: [830, 440], hot_water: [912, 250], heating_pressure: [488, 332], water_pressure: [830, 462],
    },
    labels: [
      { text: "К1 Радиаторы", at: [350, 114] }, { text: "К2 Тёплый пол", at: [530, 505] },
      { text: "К3 Бойлер ГВС", at: [700, 460] }, { text: "Подпитка", at: [246, 498] },
    ],
    badges: { rad: [250, 130], floor: [530, 522], tank: [700, 478] },
    pipes: [
      { kind: "supply", role: "boiler_supply", flow: "any", points: [[160, 300], [330, 300]] },
      { kind: "return", role: "boiler_return", flow: "any", points: [[330, 380], [160, 380]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[440, 285], [440, 110], [285, 110], [285, 96]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[380, 110], [380, 96]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[475, 110], [475, 96]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[520, 96], [520, 122], [400, 122], [400, 365]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[300, 96], [300, 122], [400, 122]] },
      { kind: "supply", role: "floor_supply", flow: "floor_pump", points: [[440, 315], [440, 470]] },
      { kind: "return", role: "floor_return", flow: "floor_pump", points: [[400, 470], [400, 395]] },
      { kind: "supply", role: "boiler_supply", flow: "ihb_pump", points: [[566, 300], [700, 300]] },
      { kind: "return", role: "coil_return", flow: "ihb_pump", points: [[700, 380], [566, 380]] },
      { kind: "hot", role: "hot_water", flow: "water_hot_pump", points: [[780, 280], [900, 280], [900, 248]] },
      { kind: "cold", role: "cold_water", flow: "water_pump", points: [[990, 420], [780, 420]] },
      { kind: "fill", flow: "af_open", points: [[990, 420], [990, 540], [230, 540], [230, 470], [348, 470], [348, 420]] },
    ],
  },
  tall: {
    width: 360, height: 640,
    boiler: [10, 250], separator: [130, 250], gauge: [180, 310], autofill: [150, 395],
    radiators: [55, 62], floor: [100, 470], tank: [285, 245], tap: [320, 205],
    radPump: [200, 170], radValve: [200, 215], floorPump: [200, 420], floorValve: [200, 445],
    ihbPump: [262, 280], recircPump: [330, 235], coldPump: [330, 395],
    tags: {
      boiler_supply: [12, 225], rad_supply: [215, 160], rad_return: [100, 160], floor_supply: [215, 470],
      tank: [282, 380], heating_pressure: [150, 355], cold_water: [20, 590], hot_water: [120, 590],
      water_pressure: [220, 590],
    },
    labels: [
      { text: "К1 Радиаторы", at: [130, 122] }, { text: "К2 Тёплый пол", at: [130, 540] },
      { text: "Бойлер", at: [288, 238] },
    ],
    badges: { rad: [130, 138], floor: [130, 556], tank: [282, 410] },
    pipes: [
      { kind: "supply", role: "boiler_supply", flow: "any", points: [[80, 280], [130, 280]] },
      { kind: "return", role: "boiler_return", flow: "any", points: [[130, 340], [80, 340]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[200, 265], [200, 105]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[165, 105], [165, 345]] },
      { kind: "supply", role: "floor_supply", flow: "floor_pump", points: [[200, 345], [200, 470]] },
      { kind: "return", role: "floor_return", flow: "floor_pump", points: [[165, 470], [165, 375]] },
      { kind: "supply", role: "boiler_supply", flow: "ihb_pump", points: [[230, 280], [285, 280]] },
      { kind: "return", role: "coil_return", flow: "ihb_pump", points: [[285, 340], [230, 340]] },
      { kind: "hot", role: "hot_water", flow: "water_hot_pump", points: [[340, 260], [340, 225]] },
      { kind: "cold", role: "cold_water", flow: "water_pump", points: [[350, 420], [330, 420], [330, 430]] },
      { kind: "fill", flow: "af_open", points: [[148, 400], [148, 380]] },
    ],
  },
};

export function chooseLayout(width: number): LayoutName {
  return width >= 900 ? "wide" : "tall";
}
```

- [ ] **Step 4: Implement the canvas**

`frontend/src/scheme/SchemeCanvas.tsx`:

```tsx
import type { KeyboardEvent, ReactNode } from "react";
import { Boiler, FillValve, FloorLoops, Gauge, MixingValve, Pipe, Pump, Radiators, Separator, Tank, Tap, ValueTag } from "./elements";
import { LAYOUTS, type LayoutName } from "./layouts";
import { pipeColor } from "./pipeColor";
import type { ElementKind, RoleKey, SchemeState } from "./types";

const CIRCULATION = ["rad_pump", "floor_pump", "ihb_pump"] as const;

function valveDirection(open: boolean, close: boolean): "open" | "close" | null {
  if (open && !close) return "open";
  if (close && !open) return "close";
  return null;
}

export function SchemeCanvas({ state, layout, onOpen }: {
  state: SchemeState; layout: LayoutName; onOpen: (kind: ElementKind, role?: RoleKey) => void;
}) {
  const L = LAYOUTS[layout];
  const { values: v, controller: c, settings: s } = state;
  const r = c.relays;
  const val = (role: RoleKey) => (v[role]?.stale ? null : v[role]?.value ?? null);
  const warmth = (role: RoleKey) => {
    const t = val(role);
    return t == null ? 0 : (t - 20) / 50;
  };
  const autofillState = c.flags.autofill_fault ? "fault" : r.af_open ? "opening" : r.af_close ? "closing" : "closed";

  const hit = (id: string, kind: ElementKind, child: ReactNode, role?: RoleKey) => (
    <g
      data-element={id}
      role="button"
      tabIndex={0}
      aria-label={id}
      style={{ cursor: "pointer" }}
      onClick={() => onOpen(kind, role)}
      onKeyDown={(e: KeyboardEvent) => (e.key === "Enter" || e.key === " ") && onOpen(kind, role)}
    >
      {child}
    </g>
  );

  return (
    <svg viewBox={`0 0 ${L.width} ${L.height}`} width="100%" role="img" aria-label="Схема котельной"
         style={{ background: "var(--scheme-bg)", display: "block", borderRadius: 8 }}>
      <g data-offline={String(!c.online)} opacity={c.online ? 1 : 0.45}>
        {L.pipes.map((p, i) => {
          const flowing = c.online && (p.flow === "any" ? CIRCULATION.some((k) => r[k]) : p.flow ? r[p.flow] : false);
          return <Pipe key={i} points={p.points} color={pipeColor(p.role ? val(p.role) : null, p.kind)} flowing={flowing} />;
        })}

        {hit("radiators", "rad", <Radiators x={L.radiators[0]} y={L.radiators[1]} warmth={warmth("rad_supply")} />)}
        {hit("rad_pump", "rad", <Pump x={L.radPump[0]} y={L.radPump[1]} running={r.rad_pump} />)}
        {hit("rad_valve", "rad", <MixingValve x={L.radValve[0]} y={L.radValve[1]} direction={valveDirection(r.rad_open, r.rad_close)} />)}
        {hit("floor", "floor", <FloorLoops x={L.floor[0]} y={L.floor[1]} warmth={warmth("floor_supply")} />)}
        {hit("floor_pump", "floor", <Pump x={L.floorPump[0]} y={L.floorPump[1]} running={r.floor_pump} r={11} />)}
        {hit("floor_valve", "floor", <MixingValve x={L.floorValve[0]} y={L.floorValve[1]} direction={valveDirection(r.floor_open, r.floor_close)} />)}
        {hit("boiler", "boiler", <Boiler x={L.boiler[0]} y={L.boiler[1]} on={r.boiler} auto={s.heating_boiler_automode === "1"}
                                         alarm={!!(c.flags.overtemp || c.flags.boiler_sensor_lost)} />)}
        {hit("separator", "autofill", <Separator x={L.separator[0]} y={L.separator[1]} />)}
        {hit("gauge", "autofill", <Gauge x={L.gauge[0]} y={L.gauge[1]} value={val("heating_pressure")}
                                         lo={Number(s.heating_pressure_min ?? NaN) || null} hi={Number(s.heating_pressure_max ?? NaN) || null} />)}
        {hit("autofill", "autofill", <FillValve x={L.autofill[0]} y={L.autofill[1]} state={autofillState} />)}
        {hit("tank", "tank", <Tank x={L.tank[0]} y={L.tank[1]} fill={warmth("tank")} teh={r.teh} />)}
        {hit("ihb_pump", "tank", <Pump x={L.ihbPump[0]} y={L.ihbPump[1]} running={r.ihb_pump} r={11} />)}
        {hit("recirc_pump", "hot", <Pump x={L.recircPump[0]} y={L.recircPump[1]} running={r.water_hot_pump} r={9} />)}
        {hit("cold_pump", "cold", <Pump x={L.coldPump[0]} y={L.coldPump[1]} running={r.water_pump} r={9} />)}
        {hit("tap", "hot", <Tap x={L.tap[0]} y={L.tap[1]} />)}

        {Object.entries(L.tags).map(([role, [x, y]]) => {
          const key = role as RoleKey;
          const target = key === "rad_supply" ? c.targets.rad : key === "floor_supply" ? c.targets.floor
            : key === "tank" ? c.targets.ihb : key === "boiler_supply" && s.heating_boiler_automode === "1" ? c.targets.boiler : null;
          const pressure = key === "heating_pressure" || key === "water_pressure";
          return (
            <g key={role}>
              {hit(`tag_${role}`, "sensor",
                <ValueTag x={x} y={y} reading={v[key]} unit={pressure ? " бар" : "°"} digits={pressure ? 2 : 1} target={target} />, key)}
            </g>
          );
        })}

        {L.labels.map((l) => (
          <text key={l.text} x={l.at[0]} y={l.at[1]} fontSize={12} fontWeight={700} fill="var(--scheme-text)">{l.text}</text>
        ))}

        {/* State badges: night setback, DHW priority (pump held off while the tank heats), anti-legionella */}
        {(["rad", "floor"] as const).map((k) => {
          const prefix = k === "rad" ? "heating_radiator" : "heating_floorheating";
          const pumpRelay = k === "rad" ? r.rad_pump : r.floor_pump;
          const badges = [
            c.flags[`schedule_${k}`] && "🌙 Ночь",
            s[`${prefix}_pump`] === "1" && !pumpRelay && c.flags.ihb_heating && "Приоритет ГВС",
          ].filter(Boolean) as string[];
          return badges.length ? (
            <text key={k} data-badges={k} x={L.badges[k][0]} y={L.badges[k][1]} fontSize={11} fill="#7c3aed">{badges.join(" · ")}</text>
          ) : null;
        })}
        {c.flags.alm_active && (
          <text data-badges="tank" x={L.badges.tank[0]} y={L.badges.tank[1]} fontSize={11} fill="#7c3aed">Анти-легионелла</text>
        )}
      </g>
    </svg>
  );
}
```

- [ ] **Step 5: Implement the state hook**

`frontend/src/scheme/useSchemeState.ts`:

```ts
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import type { SchemeState } from "./types";

export const SCHEME_QUERY_KEY = ["scheme-state"] as const;

/** Scheme state: 10 s polling (2 s while `fast`), plus refetch on WS updates (see useWebSocket). */
export function useSchemeState(opts: { fast?: boolean } = {}) {
  const query = useQuery<SchemeState>({
    queryKey: SCHEME_QUERY_KEY,
    queryFn: async () => (await api.get<SchemeState>("/scheme/state")).data,
    refetchInterval: opts.fast ? 2000 : 10000,
    staleTime: 1000,
  });
  return { data: query.data, isLoading: query.isLoading, refetch: query.refetch };
}

/** Throttled invalidation used by the WebSocket hook (≤ once per 2 s). */
export function useSchemeRefreshOnWs() {
  const qc = useQueryClient();
  useEffect(() => {
    let last = 0;
    const onUpdate = () => {
      const now = Date.now();
      if (now - last >= 2000) {
        last = now;
        qc.invalidateQueries({ queryKey: SCHEME_QUERY_KEY });
      }
    };
    window.addEventListener("scheme-refresh", onUpdate);
    return () => window.removeEventListener("scheme-refresh", onUpdate);
  }, [qc]);
}
```

В `frontend/src/hooks/useWebSocket.ts` в `socket.onmessage` после обработки `sensor_update` и после `settings_update` добавить:

```ts
            window.dispatchEvent(new Event("scheme-refresh"));
```

- [ ] **Step 6: Run tests**

Run: `cd frontend && npx vitest run && npx tsc -b --noEmit`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/scheme frontend/src/hooks/useWebSocket.ts
git commit -m "Scheme UI: two layouts, SVG canvas, live state hook"
```

---

### Task 8: Фронтенд — окно управления

**Files:**
- Create: `frontend/src/scheme/forms.ts`, `frontend/src/scheme/ControlDialog.tsx`
- Test: `frontend/src/scheme/ControlDialog.test.tsx`

**Interfaces:**
- Consumes: `SchemeState`, `ElementKind`, `RoleKey`, `canEdit` (Task 5), `api` (`@/api/client`).
- Produces:
  - `FieldDef = { key: string; label: string; type: "bool" | "number" | "curve"; min?: number; max?: number; step?: number; unit?: string; disabledWhen?: (v: Record<string,string>) => boolean }`
  - `FORMS: Record<Exclude<ElementKind,"sensor">, { title: string; fields: FieldDef[]; link?: { to: string; text: string } }>`
  - `ControlDialog({ kind, role, state, userRole, onClose, onApplied }: { kind: ElementKind; role?: RoleKey; state: SchemeState; userRole?: string; onClose: () => void; onApplied: (keys: string[]) => void })`

- [ ] **Step 1: Write the failing tests**

`frontend/src/scheme/ControlDialog.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/client";
import { ControlDialog } from "./ControlDialog";
import { makeState } from "./SchemeCanvas.test";

vi.mock("@/api/client", () => ({ default: { put: vi.fn(), post: vi.fn() } }));

const renderDialog = (props: Partial<Parameters<typeof ControlDialog>[0]> = {}) =>
  render(
    <MemoryRouter>
      <ControlDialog kind="boiler" state={makeState()} userRole="operator" onClose={() => {}} onApplied={() => {}} {...props} />
    </MemoryRouter>,
  );

describe("ControlDialog", () => {
  beforeEach(() => {
    vi.mocked(api.put).mockReset().mockResolvedValue({ data: { success: true, delivery: "queued", unrouted: [] } });
  });

  it("operator sees the max temperature field locked", () => {
    renderDialog();
    expect(screen.getByLabelText("Макс. температура котла")).toBeDisabled();
    expect(screen.getByLabelText("Уставка котла")).toBeEnabled();
  });

  it("Apply is disabled until something changes and sends only changed keys", async () => {
    const onApplied = vi.fn();
    renderDialog({ onApplied });
    const apply = screen.getByRole("button", { name: "Применить" });
    expect(apply).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Автоматический режим"));
    expect(apply).toBeEnabled();
    fireEvent.click(apply);
    await waitFor(() => expect(api.put).toHaveBeenCalledWith("/settings", { settings: { heating_boiler_automode: "0" } }));
    expect(onApplied).toHaveBeenCalledWith(["heating_boiler_automode"]);
  });

  it("viewer cannot apply anything", () => {
    renderDialog({ userRole: "viewer" });
    expect(screen.getByLabelText("Автоматический режим")).toBeDisabled();
  });

  it("asks before discarding unsaved changes", () => {
    const onClose = vi.fn();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderDialog({ onClose });
    fireEvent.click(screen.getByLabelText("Автоматический режим"));
    fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
    expect(confirm).toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("shows a 422 validation error under the field", async () => {
    vi.mocked(api.put).mockRejectedValue(Object.assign(new Error("422"), {
      isAxiosError: true, response: { status: 422, data: { detail: { errors: { heating_boiler_temp: "must be between 30 and 90" } } } },
    }));
    renderDialog();
    fireEvent.change(screen.getByLabelText("Уставка котла"), { target: { value: "95" } });
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(await screen.findByText("must be between 30 and 90")).toBeInTheDocument();
  });

  it("shows sync status next to a pending key", () => {
    const state = makeState();
    state.sync.pending = ["heating_boiler_temp"];
    renderDialog({ state });
    expect(screen.getByTitle("Ждём подтверждения устройства")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npx vitest run src/scheme/ControlDialog.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement forms**

`frontend/src/scheme/forms.ts`:

```ts
import type { ElementKind } from "./types";

export interface FieldDef {
  key: string;
  label: string;
  type: "bool" | "number" | "curve";
  min?: number; max?: number; step?: number; unit?: string;
  disabledWhen?: (v: Record<string, string>) => boolean;
}

export interface FormDef { title: string; fields: FieldDef[]; link?: { to: string; text: string } }

const circuit = (p: "heating_radiator" | "heating_floorheating", title: string, max: number): FormDef => ({
  title,
  fields: [
    { key: `${p}_pump`, label: "Насос", type: "bool" },
    { key: `${p}_wbm`, label: "ПЗА (погодозависимая)", type: "bool" },
    { key: `${p}_curve`, label: "Кривая ПЗА", type: "curve", disabledWhen: (v) => v[`${p}_wbm`] !== "1" },
    { key: `${p}_temp`, label: "Ручная уставка подачи", type: "number", min: 20, max, step: 1, unit: "°C",
      disabledWhen: (v) => v[`${p}_wbm`] === "1" },
    { key: `${p}_off_ihb`, label: "Отключать при нагреве БКН", type: "bool" },
  ],
  link: { to: "/heating", text: "Расписание и графики кривых → Отопление" },
});

export const FORMS: Record<Exclude<ElementKind, "sensor">, FormDef> = {
  boiler: {
    title: "Котёл",
    fields: [
      { key: "heating_boiler_automode", label: "Автоматический режим", type: "bool" },
      { key: "heating_boiler_power", label: "Питание котла", type: "bool", disabledWhen: (v) => v.heating_boiler_automode === "1" },
      { key: "heating_boiler_temp", label: "Уставка котла", type: "number", min: 30, max: 90, step: 1, unit: "°C" },
      { key: "heating_boiler_max_temp", label: "Макс. температура котла", type: "number", min: 60, max: 90, step: 1, unit: "°C" },
    ],
  },
  autofill: {
    title: "Давление и автоподпитка",
    fields: [
      { key: "heating_autofill_enabled", label: "Автоподпитка", type: "bool" },
      { key: "heating_pressure_min", label: "Давление min", type: "number", min: 0.5, max: 2.0, step: 0.1, unit: "бар" },
      { key: "heating_pressure_max", label: "Давление max", type: "number", min: 1.0, max: 2.8, step: 0.1, unit: "бар" },
    ],
  },
  rad: circuit("heating_radiator", "Контур №1 — Радиаторы", 90),
  floor: circuit("heating_floorheating", "Контур №2 — Тёплый пол", 50),
  tank: {
    title: "Контур №3 — Бойлер ГВС",
    fields: [
      { key: "watersupply_ihb_automode", label: "Авто-режим БКН", type: "bool" },
      { key: "watersupply_ihb_pump", label: "Насос загрузки", type: "bool", disabledWhen: (v) => v.watersupply_ihb_automode === "1" },
      { key: "watersupply_ihb_temp", label: "Уставка бойлера", type: "number", min: 30, max: 75, step: 1, unit: "°C" },
      { key: "watersupply_ihb_teh_automode", label: "ТЭН авто", type: "bool" },
      { key: "watersupply_ihb_teh_power", label: "ТЭН вкл", type: "bool", disabledWhen: (v) => v.watersupply_ihb_teh_automode === "1" },
      { key: "watersupply_ihb_teh_heating_delay", label: "Задержка ТЭН", type: "number", min: 0, max: 240, step: 5, unit: "мин" },
    ],
    link: { to: "/water-supply", text: "Анти-легионелла → Водоснабжение" },
  },
  cold: { title: "Холодная вода", fields: [{ key: "watersupply_pump", label: "Насос ХВС", type: "bool" }] },
  hot: { title: "Горячая вода", fields: [{ key: "watersupply_pump_hot", label: "Рециркуляция ГВС", type: "bool" }] },
};
```

- [ ] **Step 4: Implement the dialog**

`frontend/src/scheme/ControlDialog.tsx`:

```tsx
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { isAxiosError } from "axios";
import api from "@/api/client";
import { FORMS, type FieldDef } from "./forms";
import { canEdit } from "./permissions";
import type { ElementKind, RoleKey, SchemeState } from "./types";

const ROLE_LABELS: Partial<Record<RoleKey, string>> = {
  boiler_supply: "Подача котла", boiler_return: "Обратка котла", rad_supply: "Подача радиаторов",
  rad_return: "Обратка радиаторов", floor_supply: "Подача пола", floor_return: "Обратка пола",
  tank: "Бойлер", coil_return: "Обратка змеевика", cold_water: "Холодная вода", hot_water: "Горячая вода",
  heating_pressure: "Давление контура", water_pressure: "Давление ХВС",
};

function SyncMark({ k, state, sent }: { k: string; state: SchemeState; sent: string[] }) {
  if (state.sync.pending.includes(k)) return <span title="Ждём подтверждения устройства">⏳</span>;
  if (state.sync.unsynced.includes(k)) return <span title="Не синхронизировано" className="text-amber-600">⚠</span>;
  if (sent.includes(k)) return <span title="Подтверждено устройством" className="text-emerald-600">✓</span>;
  return null;
}

export function ControlDialog({ kind, role, state, userRole, onClose, onApplied }: {
  kind: ElementKind; role?: RoleKey; state: SchemeState; userRole?: string;
  onClose: () => void; onApplied: (keys: string[]) => void;
}) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [sent, setSent] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const values = useMemo(() => ({ ...state.settings, ...draft }), [state.settings, draft]);
  const dirty = Object.keys(draft).filter((k) => draft[k] !== state.settings[k]);

  const close = () => {
    if (dirty.length && !window.confirm("Есть несохранённые изменения. Закрыть без сохранения?")) return;
    onClose();
  };

  const apply = async () => {
    setBusy(true);
    setError(null);
    setFieldErrors({});
    const payload = Object.fromEntries(dirty.map((k) => [k, draft[k]!]));
    try {
      const { data } = await api.put("/settings", { settings: payload });
      if (data?.delivery === "failed") setError("Сохранено, но шлюз недоступен — отправится при переподключении");
      setSent(dirty);
      setDraft({});
      onApplied(dirty);
    } catch (e) {
      const status = isAxiosError(e) ? e.response?.status : undefined;
      const detail = isAxiosError(e) ? e.response?.data?.detail : null;
      if (detail?.errors) setFieldErrors(detail.errors as Record<string, string>);   // 422: shown under each field
      else setError(status === 403 ? "Недостаточно прав для этих параметров" : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  };

  const resetAutofill = async () => {
    await api.post("/catalog/devices/boiler_unit/command", { params: { autofill_reset: "1" } });
    onApplied([]);
  };

  const field = (f: FieldDef) => {
    const disabled = !canEdit(userRole, f.key) || !!f.disabledWhen?.(values);
    const set = (v: string) => setDraft((d) => ({ ...d, [f.key]: v }));
    const id = `f-${f.key}`;
    return (
      <div key={f.key} className="flex flex-wrap items-center justify-between gap-x-3 py-2 border-t border-gray-100">
        <label htmlFor={id} className="text-sm text-gray-700">{f.label}</label>
        <div className="flex items-center gap-2">
          {f.type === "bool" && (
            <input id={id} type="checkbox" role="switch" checked={values[f.key] === "1"} disabled={disabled}
                   onChange={(e) => set(e.target.checked ? "1" : "0")} className="h-5 w-9 accent-emerald-600" />
          )}
          {f.type === "number" && (
            <>
              <input id={id} type="number" min={f.min} max={f.max} step={f.step} value={values[f.key] ?? ""} disabled={disabled}
                     onChange={(e) => set(e.target.value)} className="w-20 rounded border border-gray-200 px-2 py-1 text-sm disabled:opacity-50" />
              <span className="text-xs text-gray-500">{f.unit}</span>
            </>
          )}
          {f.type === "curve" && (
            <div id={id} role="group" aria-label={f.label} className="flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} type="button" disabled={disabled} onClick={() => set(String(n))}
                        className={`px-2 py-0.5 text-xs rounded-full ${values[f.key] === String(n) ? "bg-primary-600 text-white" : "bg-gray-100 text-gray-600"} disabled:opacity-50`}>
                  {n}
                </button>
              ))}
            </div>
          )}
          <SyncMark k={f.key} state={state} sent={sent} />
        </div>
        {fieldErrors[f.key] && <div className="w-full text-right text-xs text-red-600">{fieldErrors[f.key]}</div>}
      </div>
    );
  };

  const form = kind === "sensor" ? null : FORMS[kind];
  const reading = role ? state.values[role] : undefined;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40" onClick={close}>
      <div role="dialog" aria-modal="true" aria-label={form?.title ?? ROLE_LABELS[role!] ?? "Датчик"}
           className="w-full sm:w-[440px] max-h-[85vh] overflow-y-auto rounded-t-2xl sm:rounded-xl bg-white p-4 shadow-xl"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold text-gray-900 mb-1">{form?.title ?? ROLE_LABELS[role!] ?? "Датчик"}</h3>

        {kind === "sensor" && (
          <div className="text-sm text-gray-700 space-y-1">
            <div>Значение: <b>{reading?.value ?? "—"}</b>{reading?.source === "heartbeat" ? " (по данным контроллера)" : ""}</div>
            <div className="text-gray-500">Обновлено: {reading?.ts ? new Date(reading.ts).toLocaleString("ru-RU") : "—"}</div>
            <Link to="/statistics" className="text-primary-600 text-sm">Графики → Статистика</Link>
          </div>
        )}

        {form && (
          <>
            {form.fields.map(field)}
            {kind === "autofill" && state.controller.flags.autofill_fault && (
              <div className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">
                Подпитка заблокирована после аварийного таймаута. Проверьте систему на утечку.
                <button type="button" onClick={resetAutofill} disabled={userRole !== "admin"}
                        className="ml-2 rounded bg-red-600 px-2 py-1 text-white disabled:opacity-50">Сбросить блокировку</button>
              </div>
            )}
            {form.link && <Link to={form.link.to} className="mt-3 block text-sm text-primary-600">{form.link.text}</Link>}
          </>
        )}

        {error && <div className="mt-3 text-sm text-red-600">{error}</div>}

        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={close} className="rounded bg-gray-100 px-3 py-1.5 text-sm text-gray-700">Отмена</button>
          {form && (
            <button type="button" onClick={apply} disabled={!dirty.length || busy}
                    className="rounded bg-primary-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Применить</button>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npx vitest run && npx tsc -b --noEmit`
Expected: PASS. (Если `getByLabelText` не находит чекбокс — проверить `htmlFor={id}` и `id` у `input`.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/scheme/forms.ts frontend/src/scheme/ControlDialog.tsx frontend/src/scheme/ControlDialog.test.tsx
git commit -m "Scheme UI: control dialog with draft, role locks and sync marks"
```

---

### Task 9: Фронтенд — страница, сигнализация, верхняя полоса, меню

**Files:**
- Create: `frontend/src/scheme/AlarmPanel.tsx`, `frontend/src/scheme/TopStrip.tsx`, `frontend/src/pages/SchemePage.tsx`
- Modify: `frontend/src/App.tsx` (маршрут `scheme`), `frontend/src/components/Layout.tsx` (пункт меню второй после «Панели», иконка `Workflow` из lucide-react), `frontend/src/i18n/ru.json` и `en.json` (`nav.scheme`: «Схема» / «Scheme»)
- Test: `frontend/src/pages/SchemePage.test.tsx`

**Interfaces:**
- Consumes: `useSchemeState`, `useSchemeRefreshOnWs`, `SchemeCanvas`, `chooseLayout`, `ControlDialog`, `useAuthStore` (`user?.role`).
- Produces: маршрут `/scheme`.

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/SchemePage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { makeState } from "@/scheme/SchemeCanvas.test";
import SchemePage from "./SchemePage";

vi.mock("@/scheme/useSchemeState", () => ({
  useSchemeState: () => ({ data: withAlarm(), isLoading: false, refetch: vi.fn() }),
  useSchemeRefreshOnWs: () => {},
}));

function withAlarm() {
  const s = makeState();
  s.alarms = [{ level: "ERROR", code: "pressure_low", text: "Давление 0.92 бар ниже нормы 1" }];
  s.sync.unsynced = ["heating_boiler_temp"];
  return s;
}

describe("SchemePage", () => {
  it("renders the scheme, alarms and unsynced counter", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter><SchemePage /></MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("img", { name: "Схема котельной" })).toBeInTheDocument();
    expect(screen.getByText("Давление 0.92 бар ниже нормы 1")).toBeInTheDocument();
    expect(screen.getByText(/Не синхронизировано: 1/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/pages/SchemePage.test.tsx` → FAIL (module not found).

- [ ] **Step 3: Implement**

`frontend/src/scheme/AlarmPanel.tsx`:

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import type { SchemeState } from "./types";
import { fmtTime } from "@/lib/utils";

export function AlarmPanel({ state, collapsible }: { state: SchemeState; collapsible: boolean }) {
  const [open, setOpen] = useState(!collapsible || state.alarms.length > 0);
  const bad = state.alarms.length > 0;
  return (
    <section className={`rounded-lg border p-3 text-sm ${bad ? "border-red-300 bg-red-50" : "border-gray-200 bg-white"}`}>
      <button type="button" className="flex w-full items-center gap-2 font-semibold text-gray-800"
              onClick={() => collapsible && setOpen(!open)} aria-expanded={open}>
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${bad ? "bg-red-500 scheme-blink" : "bg-emerald-500"}`} />
        Сигнализация {bad ? `(${state.alarms.length})` : "— аварий нет"}
        {collapsible && <span className="ml-auto text-gray-400">{open ? "▴" : "▾"}</span>}
      </button>
      {open && (
        <>
          {state.alarms.map((a) => (
            <div key={a.code} className={a.level === "ERROR" ? "mt-1 text-red-700" : "mt-1 text-amber-700"}>{a.text}</div>
          ))}
          <div className="mt-2 space-y-0.5 text-xs text-gray-500">
            {state.events.map((e, i) => <div key={i}>{e.ts ? fmtTime(e.ts) : ""} {e.text}</div>)}
          </div>
          <Link to="/events" className="mt-1 inline-block text-xs text-primary-600">→ Журнал</Link>
        </>
      )}
    </section>
  );
}
```

`frontend/src/scheme/TopStrip.tsx`:

```tsx
import api from "@/api/client";
import type { SchemeState } from "./types";

const fmt = (v: number | null | undefined) => (v == null ? "—" : `${v.toFixed(1)}°`);

export function TopStrip({ state, canRetry }: { state: SchemeState; canRetry: boolean }) {
  const { values: v, controller: c, sync } = state;
  const ago = c.last_seen ? Math.max(0, Math.round((Date.now() - new Date(c.last_seen).getTime()) / 1000)) : null;
  const val = (k: keyof SchemeState["values"]) => (v[k]?.stale ? null : v[k]?.value);
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-lg bg-white px-4 py-2 text-sm text-gray-700 shadow-sm">
      <span>Улица <b>{fmt(val("outdoor"))}</b></span>
      <span>Дом <b>{fmt(val("indoor_avg"))}</b></span>
      <span>Котельная <b>{fmt(val("boiler_room"))}</b></span>
      <span className="flex items-center gap-1.5">
        <span className={`h-2.5 w-2.5 rounded-full ${c.online ? "bg-emerald-500" : "bg-red-500"}`} />
        {c.online ? `Контроллер онлайн${ago != null ? `, ${ago} с назад` : ""}` : "Нет связи с контроллером"}
      </span>
      {sync.unsynced.length > 0 && (
        <span className="text-amber-700">
          Не синхронизировано: {sync.unsynced.length}
          {canRetry && (
            <button type="button" className="ml-2 underline" onClick={() => api.post("/settings/retry-unsynced")}>Повторить</button>
          )}
        </span>
      )}
    </div>
  );
}
```

`frontend/src/pages/SchemePage.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import LoadingSpinner from "@/components/LoadingSpinner";
import { AlarmPanel } from "@/scheme/AlarmPanel";
import { ControlDialog } from "@/scheme/ControlDialog";
import { chooseLayout, type LayoutName } from "@/scheme/layouts";
import { SchemeCanvas } from "@/scheme/SchemeCanvas";
import { TopStrip } from "@/scheme/TopStrip";
import type { ElementKind, RoleKey } from "@/scheme/types";
import { useSchemeRefreshOnWs, useSchemeState } from "@/scheme/useSchemeState";

export default function SchemePage() {
  const role = useAuthStore((s) => s.user?.role);
  const [dialog, setDialog] = useState<{ kind: ElementKind; role?: RoleKey } | null>(null);
  const [awaiting, setAwaiting] = useState(false);
  const { data, isLoading, refetch } = useSchemeState({ fast: awaiting });
  useSchemeRefreshOnWs();

  const box = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<LayoutName>("wide");
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setLayout(chooseLayout(entry!.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // stop fast polling once nothing is pending anymore
  useEffect(() => {
    if (awaiting && data && data.sync.pending.length === 0) setAwaiting(false);
  }, [awaiting, data]);

  if (isLoading || !data) return <LoadingSpinner />;

  return (
    <div className="space-y-3" ref={box}>
      <TopStrip state={data} canRetry={role === "admin" || role === "operator"} />
      <div className={layout === "wide" ? "relative" : "space-y-3"}>
        <SchemeCanvas state={data} layout={layout} onOpen={(kind, r) => setDialog({ kind, role: r })} />
        <div className={layout === "wide" ? "absolute bottom-3 right-3 w-72" : ""}>
          <AlarmPanel state={data} collapsible={layout === "tall"} />
        </div>
      </div>
      {dialog && (
        <ControlDialog kind={dialog.kind} role={dialog.role} state={data} userRole={role}
                       onClose={() => setDialog(null)}
                       onApplied={() => { setAwaiting(true); refetch(); }} />
      )}
    </div>
  );
}
```

Note: `ResizeObserver` отсутствует в jsdom — в `frontend/src/test/setup.ts` добавить заглушку:

```ts
class ResizeObserverStub { observe() {} unobserve() {} disconnect() {} }
(globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }).ResizeObserver ??= ResizeObserverStub;
```

`frontend/src/App.tsx`: импорт `import SchemePage from "@/pages/SchemePage";` и маршрут после `dashboard`:

```tsx
        <Route path="scheme" element={<SchemePage />} />
```

`frontend/src/components/Layout.tsx`: в импорт lucide-react добавить `Workflow`; в `NAV_ITEMS` второй строкой:

```ts
  { to: "/scheme", key: "scheme", icon: Workflow },
```

`i18n/ru.json` → `"nav"`: `"scheme": "Схема",`; `i18n/en.json` → `"nav"`: `"scheme": "Scheme",`.

- [ ] **Step 4: Run tests**

Run: `cd frontend && npx vitest run && npx tsc -b --noEmit && npm run build`
Expected: PASS, сборка успешна.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/scheme frontend/src/pages/SchemePage.tsx frontend/src/pages/SchemePage.test.tsx frontend/src/test/setup.ts frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/i18n
git commit -m "Scheme UI: page with alarm panel, status strip and navigation"
```

---

### Task 10: Сквозная проверка на стенде и документация

**Files:**
- Create: `tools/scheme_screenshots.py` (Playwright-скрипт проверки)
- Modify: `CLAUDE.md` (раздел «Scheme page» в Architecture), `docs/superpowers/specs/2026-09-26-scada-scheme-design.md` не меняется

**Interfaces:**
- Consumes: всё выше; локальный стенд `bash tools/dev_stack.sh start` (эмулятор, шлюз, бэкенд, фронтенд).

- [ ] **Step 1: Script the end-to-end check**

`tools/scheme_screenshots.py`:

```python
"""End-to-end check of the scheme page on the local dev stand.

Usage: python3 tools/scheme_screenshots.py <admin-password> [out_dir]
Needs: dev stand running (tools/dev_stack.sh start), Playwright + Chromium.
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"


def main() -> None:
    password = sys.argv[1]
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "scheme-shots")
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, viewport in (("wide", {"width": 1400, "height": 900}), ("tall", {"width": 390, "height": 844})):
            for theme in ("light", "dark"):
                page = browser.new_page(viewport=viewport)
                page.goto(f"{BASE}/login")
                page.fill("input:not([type=password])", "admin")
                page.fill("input[type=password]", password)
                page.keyboard.press("Enter")
                page.wait_for_url("**/dashboard")
                page.goto(f"{BASE}/scheme")
                page.wait_for_selector("svg[aria-label='Схема котельной']")
                if theme == "dark":
                    page.evaluate("document.documentElement.classList.add('dark')")
                page.wait_for_timeout(1500)
                page.screenshot(path=str(out / f"scheme-{name}-{theme}.png"), full_page=True)
                page.close()

        # Scenario: switch the radiator pump off → the pump stops on the scheme within 3 s
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{BASE}/login")
        page.fill("input:not([type=password])", "admin")
        page.fill("input[type=password]", password)
        page.keyboard.press("Enter")
        page.wait_for_url("**/dashboard")
        page.goto(f"{BASE}/scheme")
        page.click("[data-element='rad_pump']")
        page.click("label[for='f-heating_radiator_pump']")
        started = time.time()
        page.click("text=Применить")
        page.wait_for_selector("[data-element='rad_pump'] [data-state='stopped']", timeout=15000)
        print(f"rad pump stopped on the scheme after {time.time() - started:.1f} s")
        # restore
        page.click("[data-element='rad_pump']")
        page.click("label[for='f-heating_radiator_pump']")
        page.click("text=Применить")
        browser.close()
    print(f"screenshots in {out}/")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the stand and the check**

```bash
bash tools/dev_stack.sh start            # emulator + gateway + backend + frontend
python3 tools/scheme_screenshots.py <local-admin-password> /tmp/scheme-shots
```

Expected: вывод `rad pump stopped on the scheme after N s` с N ≤ 3; 4 скриншота. Просмотреть скриншоты: обе раскладки, обе темы, подписи не наезжают, табло читаются, насосы/трубы соответствуют состоянию.

- [ ] **Step 3: Leak scenario (вручную через консоль эмулятора)**

```bash
bash tools/dev_stack.sh      # пункт 6 — консоль эмулятора
leak 400
```

Expected в течение ~2 мин: на схеме кран подпитки красный мигающий (`fault`), в «Сигнализации» — «Автоподпитка заблокирована…». Затем `leak 0.3`, в окне подпитки (admin) «Сбросить блокировку» → кран серый.

- [ ] **Step 4: Document**

`CLAUDE.md`, в раздел `## Architecture` после абзаца «Health monitoring» добавить:

```markdown
**Scheme page** (`/scheme`): SCADA-style mnemonic of the boiler room. Backend `GET /api/v1/scheme/state`
(`app/services/scheme_service.py`) aggregates sensors by role (circuit mount points), controller heartbeat
(relays, flags, targets), gateway sync lists and alarms. Frontend `src/scheme/*`: pure SVG elements,
two layouts (`layouts.ts`, wide ≥ 900 px / tall), control dialog that applies changed keys via `PUT /settings`.
Admin-only keys in `scheme/permissions.ts` must mirror `setting_rules.py` (enforced by a test).
```

- [ ] **Step 5: Full test run and commit**

```bash
cd backend && python3 -m pytest -q && cd ../frontend && npx vitest run && npx tsc -b --noEmit && cd ../tools && python3 -m pytest -q house_emulator
git add tools/scheme_screenshots.py CLAUDE.md
git commit -m "Scheme: end-to-end check script and docs"
```
