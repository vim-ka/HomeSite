# Мониторинг ИБП (сервер, шлюз, сайт, имитация) — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ИБП в настройках (динамический список), опрос через apcupsd NIS и через MQTT от платы ESP32, тревоги и СМС об электричестве и здоровье ИБП, страница «ИБП» с графиками, напряжение сети на схеме и дашборде, имитация ИБП на стенде.

**Architecture:** `UpsMonitor` (вызывается HealthMonitor каждый опрос) раз в 60 с опрашивает ИБП с источником `apcupsd` по TCP (NIS) и берёт отчёты ИБП с источником `mqtt` из `/health` шлюза; приводит всё к одному `UpsStatus`, кэширует «живое» состояние, пишет историю, кладёт вид ИБП в `Snapshot` для правил тревог. Тревоги — правила в `alarm_rules.py`, дальше — существующие `AlarmTracker` и очередь СМС. Сайт читает кэш через `/api/v1/ups/state`, историю — через `/charts`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, aiomqtt (шлюз), pytest-asyncio; React 19 + TS, TanStack Query, recharts, vitest.

**Spec:** `docs/superpowers/specs/2026-11-14-ups-monitoring-design.md`

**Вне плана:** прошивка `firmware/esp32-ups/` и сборка железа — отдельный план после этого (порядок спеки). Здесь фиксируется формат MQTT-сообщения, который прошивка обязана выдавать (Task 2).

## Global Constraints

- Все времена UTC: `datetime.now(UTC)`, колонки `DateTime(timezone=True)`; на фронте серверные метки нормализовать (`Z`).
- Каждый новый ключ `PUT /settings` — в `setting_rules.py`; новая тревога — правило в `alarm_rules.py` + тест в `tests/test_alarm_rules.py`.
- Опрос ИБП: раз в 60 с, все ИБП параллельно, таймаут соединения и чтения 3 с; «не отвечает» — 3 опроса подряд без ответа или `COMMLOST`; для MQTT — нет сообщения дольше 3 минут или `COMMLOST`.
- Поля, которых ИБП не прислал, — `None` → на сайте «нет данных», в истории NULL, правило по полю молчит.
- Пороги по умолчанию: `ups_voltage_min` 200 В, `ups_voltage_max` 250 В (держится 120 с, гистерезис 5 В), `ups_low_battery_pct` 30 %, `ups_load_max_pct` 90 % (держится 5 мин).
- История ИБП не чистится (как показания датчиков, владелец); удаление ИБП удаляет его историю.
- Тексты интерфейса, тревог и СМС — по-русски, ключи интерфейса в `ru.json` и `en.json`.
- Мобильное приложение и фото ИБП — не трогаем (рисунок по типу корпуса).

## Review Focus

1. **ИБП без поля напряжения (ES 550)** — карточка «нет данных», нет тревоги `ups_voltage`, в графике разрыв, не ноль. Тесты: Task 3 (`test_voltage_rule_silent_without_linev`), Task 6 (`test_state_reports_missing_fields_as_null`).
2. **Адрес apcupsd молчит (пакеты теряются)** — опрос ждёт не дольше 3 с, остальные ИБП опрашиваются. Тест: Task 4 (`test_dead_host_does_not_stall_other_ups`).
3. **ИБП удалили или выключили, когда у него активна тревога** — тревога снимается, история удалена, в баннере не висит. Тест: Task 4 (`test_removed_ups_alarms_clear`).
4. **Две галочки «ИБП котельной»** — включение у одного снимает у другого; на схеме ровно один. Тест: Task 1 (`test_only_one_boiler_room_ups`).
5. **Плата ESP32 умерла (отчёты перестали приходить)** — через 3 минуты «не отвечает», старые значения не выдаются за текущие (`online: false`). Тест: Task 4 (`test_stale_mqtt_report_goes_unreachable`).

---

## File Structure

| Файл | Ответственность |
|---|---|
| `backend/app/models/ups.py` | `Ups` (настройки ИБП), `UpsReading` (история) |
| `backend/app/services/ups_catalog.py` | каталог моделей (мощность, сменная батарея, корпус) |
| `backend/app/services/ups_client.py` | `UpsStatus`, разбор NIS, запрос NIS, разбор MQTT-отчёта |
| `backend/app/services/ups_monitor.py` | `UpsMonitor`: опрос, кэш «живого» состояния, история, вид для правил |
| `backend/app/services/alarm_rules.py` (изм.) | `Snapshot.ups`, правила `ups_*`, удержание в `unknown()` |
| `backend/app/services/sms_policy.py`, `sms_text.py`, `sms_notifier.py` (изм.) | категория `power`, «ИБП не отвечает» без СМС, текст «Электричество вернулось» |
| `backend/app/services/health_monitor.py` (изм.) | вызов `UpsMonitor`, `state.ups` |
| `backend/app/services/chart_service.py` (изм.) | `ChartUpsVoltage`, `ChartUpsCharge` |
| `backend/app/api/v1/ups.py` | CRUD ИБП, каталог, проверка связи, живое состояние |
| `backend/app/api/v1/scheme.py` (изм.) | `power` в `/scheme/state` |
| `backend/app/core/setting_rules.py` (изм.) | пороги `ups_*` |
| `backend/device_gateway/handler.py`, `api.py` (изм.) | подтопик `ups`, `ups` в `/health` |
| `tools/ups_emulator/` | имитация apcupsd NIS и платы ESP32 (MQTT) |
| `tools/dev_stack.sh` (изм.) | сервис `ups`, ИБП в базе стенда |
| `frontend/src/components/SensorChart.tsx` | график из `StatisticsPage.tsx`, вынесенный без изменений поведения |
| `frontend/src/components/UpsSettingsSection.tsx` | раздел «ИБП» в настройках |
| `frontend/src/pages/UpsPage.tsx`, `components/UpsCard.tsx`, `components/UpsPicture.tsx` | страница «ИБП» |
| `frontend/src/components/PowerSection.tsx` | секция «Электропитание» на дашборде |
| `frontend/src/scheme/TopStrip.tsx` (изм.) | «Сеть 228 В» |
| `docs/ups-apcupsd.md` | инструкция подключения |

---

### Task 1: Модели, каталог, настройки ИБП (CRUD API)

**Files:**
- Create: `backend/app/models/ups.py`, `backend/app/services/ups_catalog.py`, `backend/app/api/v1/ups.py`, миграция `<rev>_ups.py` (down_revision `92f14ea2e26f`)
- Modify: `backend/app/models/__init__.py`, `backend/app/api/router.py` (`prefix="/ups"`), `backend/app/core/setting_rules.py`
- Test: `backend/tests/test_ups_api.py`

**Interfaces:**
- Produces:
  - `UpsModel(key: str, title: str, va: int | None, watts: int | None, battery: str | None, shape: Literal["tower", "tower_small"])` (frozen dataclass); `MODELS: dict[str, UpsModel]` — `"br1200g"`: «Back-UPS Pro 1200», 1200, 720, `"APCRBC124"`, `"tower"`; `"be550g"`: «Back-UPS ES 550», 550, 330, `"APCRBC110"`, `"tower_small"`; `"sua750i"`: «Smart-UPS 750», 750, 500, `"RBC48"`, `"tower"`; `"other"`: «Другая», None, None, None, `"tower"`.
  - `Ups`: `id`, `name String(64)`, `model String(16)` (ключ каталога), `watts int | None` (только для `other`), `powers String(200) default ""`, `source String(8)` (`"apcupsd"` | `"mqtt"`), `host String(128) | None`, `port int default 3551`, `device String(64) | None`, `enabled bool default True`, `boiler_room bool default False`, `created_at`.
  - `UpsReading`: `id`, `ups_id` FK `ups.id` `ondelete CASCADE`, `ts DateTime(tz)`, `linev`, `bcharge`, `loadpct`, `timeleft`, `battv` (float | None), `on_battery bool`; индекс `(ups_id, ts)`.
  - `effective_watts(ups: Ups) -> int | None` в `ups_catalog.py` (каталог, а для `other` — `ups.watts`).
  - API (admin, кроме `models`): `GET /api/v1/ups/models` (все роли) → `[{key, title, va, watts, battery, shape}]`; `GET /api/v1/ups` → список настроек; `POST /api/v1/ups`, `PUT /api/v1/ups/{id}`, `DELETE /api/v1/ups/{id}`. Тело: `name` (1–64), `model` (ключ каталога), `watts` (обязателен и 50–10000 только при `other`), `powers` (≤200), `source`, для `apcupsd` — `host` (обязателен) и `port` (1–65535), для `mqtt` — `device` (обязателен, `[a-z0-9_]+`), `enabled`, `boiler_room`. `boiler_room=true` снимает флаг у остальных в той же транзакции. Мутации — `EventLog` с `user_id` («ИБП добавлен: …», «ИБП изменён: …», «ИБП удалён: …»).
  - `setting_rules.py` (`_sys`): `ups_voltage_min` float 150–230, `ups_voltage_max` float 230–280, `ups_low_battery_pct` int 5–90, `ups_load_max_pct` int 50–100.

- [ ] **Step 1: Тесты** — `test_crud_roundtrip` (создать apcupsd-ИБП → в списке; изменить «что питает»; удалить → 404 при повторном удалении); `test_validation` (нет `host` у apcupsd → 422; нет `device` у mqtt → 422; неизвестная модель → 422; `other` без `watts` → 422); `test_only_one_boiler_room_ups` (два ИБП, у второго `boiler_room=true` → у первого `false`); `test_models_catalog` (4 модели, `br1200g.battery == "APCRBC124"`); `test_viewer_cannot_change` (403 на POST/PUT/DELETE, 200 на `/ups/models`); `test_delete_cascades_history` (строка `UpsReading` удаляется вместе с ИБП); `test_events_logged`.
- [ ] **Step 2:** `cd backend && python3 -m pytest tests/test_ups_api.py -v` → FAIL.
- [ ] **Step 3:** Модели, каталог, миграция (`alembic revision --autogenerate -m "ups"`, убрать посторонний шум; проверить upgrade/downgrade на копии базы), API, ключи порогов. `test_rbac.py`: новые маршруты должны проходить его проверку.
- [ ] **Step 4:** → PASS; полный `python3 -m pytest` → PASS.
- [ ] **Step 5:** commit `UPS: models, catalog, settings API`.

### Task 2: Источники данных — разбор apcupsd NIS и MQTT-отчёта; подтопик шлюза

**Files:**
- Create: `backend/app/services/ups_client.py`
- Modify: `backend/device_gateway/handler.py` (подтопик `ups`), `backend/device_gateway/api.py` (`ups` в `/health`)
- Test: `backend/tests/test_ups_client.py`, `backend/tests/test_gateway_handler.py` (дописать)

**Interfaces:**
- Produces:
  - `@dataclass UpsStatus`: `flags: frozenset[str]`, `linev`, `outputv`, `bcharge`, `timeleft` (мин), `loadpct`, `battv` (float | None), `nompower: int | None`, `selftest: str | None`, `battdate: str | None`, `lastxfer: str | None`, `numxfers: int | None`, `tonbatt_s: int | None`, `cumonbatt_s: int | None`, `model: str | None`, `serial: str | None`; свойства `on_battery` (`"ONBATT" in flags`), `comm_lost` (`"COMMLOST" in flags`).
  - `parse_nis(text: str) -> UpsStatus` — строки `KEY : value`, число берётся в начале значения («228.0 Volts» → 228.0), `STATUS` — флаги через пробел, «SHUTTING DOWN» — один флаг `SHUTTING_DOWN`; неизвестные ключи игнорируются.
  - `class UpsUnavailable(Exception)`; `async def fetch_nis(host: str, port: int, timeout: float = 3.0) -> UpsStatus` — запрос `status` в кадре NIS (2 байта длины big-endian + текст), чтение кадров до нулевой длины; весь обмен под `asyncio.wait_for(…, timeout)`; любая ошибка/обрыв/таймаут → `UpsUnavailable`.
  - `from_mqtt(data: dict) -> UpsStatus` — **контракт для прошивки**: ключи `status` (список флагов), `linev`, `outputv`, `bcharge`, `timeleft`, `loadpct`, `battv`, `selftest`, `battdate`, `model`, `serial`, `uptime` (с), `onbatt_since` (значение `uptime` в момент перехода на батарею или отсутствует); `tonbatt_s = uptime - onbatt_since` при работе от батареи; неверные типы → поле `None`.
  - Шлюз: подтопик `{prefix}{device}/ups` → `handler.ups_reports[device] = {"timestamp": datetime(UTC), "data": dict}` (неверный JSON — warning, пропуск; в heartbeats не попадает); `/health` → `"ups": {device: {"timestamp": iso, "data": {...}}}`.
- [ ] **Step 1: Тесты** — `test_parse_nis_full` (образец ответа Back-UPS Pro с `STATUS : ONLINE`, `LINEV : 228.0 Volts`, `BCHARGE : 100.0 Percent`, `TIMELEFT : 41.5 Minutes`, `LOADPCT : 12.0 Percent`, `SELFTEST : OK`, `BATTDATE : 2024-03-01`); `test_parse_nis_missing_linev` (ES без `LINEV` → `linev is None`); `test_parse_nis_flags` (`ONBATT LOWBATT` → `on_battery`, `"LOWBATT" in flags`; `COMMLOST` → `comm_lost`); `test_fetch_nis_roundtrip` (локальный `asyncio.start_server`, отвечающий кадрами NIS → поля разобраны); `test_fetch_nis_timeout` (сервер принимает и молчит → `UpsUnavailable` не позже `timeout + 0.5` с, `timeout=0.3`); `test_fetch_nis_refused` (закрытый порт → `UpsUnavailable`); `test_from_mqtt` (`{"status": ["ONBATT"], "bcharge": 80, "uptime": 1000, "onbatt_since": 700}` → `tonbatt_s == 300`); `test_from_mqtt_bad_types`; шлюз: `test_ups_report_stored_and_in_health`, `test_ups_report_bad_json_ignored`.
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать. **Step 4:** → PASS.
- [ ] **Step 5:** commit `UPS: apcupsd NIS client, MQTT report format, gateway ups subtopic`.

### Task 3: Правила тревог ИБП

**Files:**
- Modify: `backend/app/services/alarm_rules.py`
- Test: `backend/tests/test_alarm_rules.py`

**Interfaces:**
- Consumes: `UpsStatus` (Task 2).
- Produces:
  - `@dataclass UpsView`: `id: int`, `name: str`, `battery: str | None` (номер сменной), `watts: int | None`, `online: bool`, `status: UpsStatus | None`; `Snapshot.ups: list[UpsView] = field(default_factory=list)`.
  - Правила в `evaluate` (пороги из `s.settings` с умолчаниями Global Constraints), коды `…:{id}`, без `group`:
    - `ups_on_battery:{id}` ERROR, 30 с — `on_battery`; текст `Нет электричества: «{name}» работает от батареи, заряд {bcharge}%, осталось ~{timeleft} мин` (части без данных опускаются);
    - `ups_low_battery:{id}` ERROR, 0 — `LOWBATT` или (`on_battery` и `bcharge < ups_low_battery_pct`);
    - `ups_voltage:{id}` WARNING, 120 с — не `on_battery`, `linev` есть и вне `[min, max]`; гистерезис: уже активная держится, пока `linev < min + 5` или `> max − 5`; текст `Напряжение в сети {linev:.0f} В («{name}»)`;
    - `ups_replace_battery:{id}` WARNING, 0 — `REPLACEBATT`; текст с номером батареи, если есть;
    - `ups_selftest:{id}` WARNING, 0 — `selftest in ("BT", "NG")`;
    - `ups_overload:{id}` WARNING, 300 с — `OVERLOAD` или `loadpct > ups_load_max_pct`; текст с ваттами, если `watts` известна;
    - `ups_unreachable:{id}` WARNING, 0 — `not online`; текст `ИБП «{name}» не отвечает`.
  - `unknown()`: для ИБП с `online == False` — все его `ups_*:{id}`, кроме `ups_unreachable:{id}` (удерживаются).
- [ ] **Step 1: Тесты** (по строке таблицы спеки на каждый): `test_on_battery_raised` (delay 30, текст содержит «Нет электричества» и «заряд 95%»); `test_low_battery_by_flag_and_by_threshold`; `test_voltage_low_high_and_hysteresis` (190 → поднята; 203 при активной → держится; 206 → нет); `test_voltage_rule_silent_without_linev`; `test_voltage_not_checked_on_battery`; `test_replace_battery_mentions_part`; `test_selftest_bt_ng`; `test_overload_by_pct_and_flag` (delay 300); `test_unreachable_and_holds` (`online=False` → только `ups_unreachable:1` в `evaluate`, остальные коды ИБП 1 в `unknown`); `test_thresholds_from_settings`.
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать. **Step 4:** → PASS.
- [ ] **Step 5:** commit `Alarms: UPS rules (power, voltage, battery health, overload, unreachable)`.

### Task 4: `UpsMonitor` и подключение к HealthMonitor

**Files:**
- Create: `backend/app/services/ups_monitor.py`
- Modify: `backend/app/services/health_monitor.py`
- Test: `backend/tests/test_ups_monitor.py`

**Interfaces:**
- Consumes: Task 1 (модели, `effective_watts`, каталог), Task 2 (`fetch_nis`, `from_mqtt`, `UpsUnavailable`), Task 3 (`UpsView`).
- Produces:
  - `POLL_EVERY_S = 60`, `MISSES_UNREACHABLE = 3`, `MQTT_STALE_S = 180`.
  - `@dataclass UpsLive`: `id`, `name`, `model`, `powers`, `source`, `boiler_room: bool`, `status: UpsStatus | None`, `online: bool`, `misses: int`, `last_ok: datetime | None`.
  - `class UpsMonitor: __init__(self, fetch=fetch_nis)`; `async def poll(self, session, now: datetime, gateway_ups: dict | None) -> None` — раз в `POLL_EVERY_S` (между вызовами возвращает кэш): читает включённые ИБП из базы, apcupsd-ИБП опрашивает параллельно (`asyncio.gather`), MQTT-ИБП берёт из `gateway_ups[device]` (отчёт старше `MQTT_STALE_S` или его нет → промах); `online = misses < MISSES_UNREACHABLE and not comm_lost`; на каждый ответивший ИБП пишет `UpsReading` и коммитит; ИБП, удалённые или выключенные, исчезают из кэша. `live: dict[int, UpsLive]`; `views() -> list[UpsView]`.
  - HealthMonitor: `self.ups = UpsMonitor()`; в `_check_alarms` до `Snapshot` — `await self.ups.poll(s, now, gateway_health.get("ups") if gateway_health else None)` в своей сессии и своём `try` (ошибка логируется, `Snapshot.ups` остаётся последним известным); `Snapshot(ups=self.ups.views())`; `HealthState.ups: list[dict]` — сериализованный `live` для API.
- [ ] **Step 1: Тесты** (подменённый `fetch`, подменённые часы): `test_polls_once_a_minute`; `test_reading_written_per_answer` (поля NULL, где их нет); `test_three_misses_then_unreachable`; `test_dead_host_does_not_stall_other_ups` (настоящий `fetch_nis`, один адрес — молчащий сервер, второй — отвечающий; `poll` укладывается в 4 с, второй онлайн); `test_mqtt_report_used` и `test_stale_mqtt_report_goes_unreachable` (отчёт 181 с назад → промах; через 3 опроса `online=False`); `test_removed_ups_alarms_clear` (HealthMonitor: ИБП на батарее → `ups_on_battery:1` активна; ИБП удалён → через `CLEAR_AFTER_S` тревога снята); `test_ups_error_does_not_break_alarms` (`poll` бросает → остальные тревоги работают).
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать. **Step 4:** → PASS; полный `pytest` → PASS.
- [ ] **Step 5:** commit `UPS: monitor (polling, cache, history) wired into the HealthMonitor`.

### Task 5: СМС — категория «Электричество», тексты

**Files:**
- Modify: `backend/app/services/sms_text.py` (`SMS_CATEGORIES`), `sms_policy.py`, `sms_notifier.py`, `backend/app/schemas/auth.py` (Literal категорий)
- Test: `backend/tests/test_sms_policy.py`, `test_sms_text.py`, `test_sms_notifier.py`, `test_sms_users.py`

**Interfaces:**
- Produces:
  - `SMS_CATEGORIES` + `"power"`.
  - `category(a)`: коды с префиксами `ups_on_battery:`, `ups_low_battery:`, `ups_voltage:` → `"power"`; остальные `ups_*` — по уровню (как сейчас).
  - `effective_level(a, cats)`: тревога категории `power` уровня ERROR доходит и при `"critical" in cats` (спека: «Аварии» получают «Нет электричества»).
  - `is_banner_only(code: str) -> bool` — `BANNER_ONLY` плюс префикс `ups_unreachable:`; `current_problems` использует его.
  - `summary_text`: снятие `ups_on_battery:{id}` → `Электричество вернулось («{name}»), не было {N} мин` (имя — из `last_text` между «»); начало эпизода сдвигается на 30 с (`UPS_ONBATT_DELAY_S`, задержка подъёма) — как сейчас для `internet_down`.
- [ ] **Step 1: Тесты:** `test_power_category`; `test_critical_gets_power_errors_but_not_voltage`; `test_power_only_gets_voltage_warning`; `test_ups_unreachable_never_sms`; `test_power_restored_text` («Электричество вернулось («Серверный»), не было 12 мин» для эпизода 12 мин + 30 с задержки); `test_user_can_select_power` (`PUT /auth/users/{id}/sms` с `"power"` → 200).
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать. **Step 4:** → PASS.
- [ ] **Step 5:** commit `SMS: «Электричество» category, power restored text, unreachable UPS banner-only`.

### Task 6: API для сайта — живое состояние, проверка связи, графики, схема

**Files:**
- Modify: `backend/app/api/v1/ups.py`, `backend/app/services/chart_service.py` (+ репозиторий истории по необходимости), `backend/app/api/v1/scheme.py`
- Test: `backend/tests/test_ups_api.py`, `backend/tests/test_charts_and_curves.py`, `backend/tests/test_scheme_api.py`

**Interfaces:**
- Consumes: `HealthState.ups` (Task 4), `fetch_nis`/`from_mqtt` (Task 2), каталог (Task 1).
- Produces:
  - `GET /api/v1/ups/state` (все роли) → `[{id, name, model, model_title, battery, watts, powers, source, boiler_room, online, last_ok, status: {flags: [..], linev, outputv, bcharge, timeleft, loadpct, load_watts, battv, selftest, battdate, lastxfer, numxfers, tonbatt_s, cumonbatt_s} | null}]` — отсутствующее = `null`, `load_watts = loadpct × watts / 100` при известных обоих.
  - `POST /api/v1/ups/check` (admin), тело `{source, host, port, device}` → `{ok: bool, error: str | null, model, flags, fields: [имена пришедших полей]}`; apcupsd — разовый `fetch_nis`; mqtt — последний отчёт шлюза и его возраст в `age_s`.
  - `chart_service`: `ChartUpsVoltage` (dataset на ИБП, `linev`) и `ChartUpsCharge` (`bcharge`) за период — формат `{labels, datasets: [{label, data}]}` как у остальных графиков, NULL → `null` (разрыв).
  - `/scheme/state` → `power: {name, online, on_battery, linev, bcharge, timeleft} | null` — ИБП с `boiler_room`.
- [ ] **Step 1: Тесты:** `test_state_reports_missing_fields_as_null`; `test_state_load_watts`; `test_check_apcupsd_ok_and_refused` (локальный сервер NIS / закрытый порт); `test_check_mqtt_age`; `test_check_admin_only`; `test_chart_ups_voltage_gaps` (NULL в середине → `None` в `data`); `test_scheme_power_from_boiler_room_ups` и `test_scheme_power_null_without_one`.
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать. **Step 4:** → PASS.
- [ ] **Step 5:** commit `UPS: live state, connection check, charts, power on the scheme state`.

### Task 7: Имитация ИБП и стенд

**Files:**
- Create: `tools/ups_emulator/__init__.py`, `__main__.py`, `nis.py`, `mqtt_board.py`, `scenarios.py`, `test_ups_emulator.py`
- Modify: `tools/dev_stack.sh`

**Interfaces:**
- Consumes: формат кадров NIS и MQTT-отчёта (Task 2).
- Produces:
  - `python3 -m ups_emulator --nis 13551:serverny --nis 13552:es550 --mqtt ups_kotelnaya --broker-port 18830 --scenarios <file>` (из каталога `tools/`); сценарии: `normal`, `outage` (от батареи, заряд падает 1 %/мин, время пропорционально, при < 10 % — `LOWBATT`), `low_voltage` (190 В), `replace_battery`, `no_linev` (ES без `LINEV`), `comm_lost`; текущий сценарий каждого ИБП читается из JSON-файла `--scenarios` на каждом ответе (`{"serverny": "outage"}`), меняется правкой файла без перезапуска.
  - `dev_stack.sh`: сервис `ups` в `SERVICES`, файл сценариев `tools/.dev_stack/ups_scenarios.json` (по умолчанию все `normal`); при старте, если таблица `ups` пуста, — три ИБП: «Серверный» (`br1200g`, apcupsd `127.0.0.1:13551`), «Кабинет» (`be550g`, `127.0.0.1:13552`), «Котельная» (`sua750i`, mqtt `ups_kotelnaya`, `boiler_room`); пункт меню «сценарий ИБП».
- [ ] **Step 1: Тесты** (`cd tools && python3 -m pytest ups_emulator -v`): NIS-ответ разбирается `parse_nis` из бэкенда (импорт через `sys.path`, как это делают тесты `house_emulator`, если делают; иначе — проверка кадров и ключей); `outage` уменьшает заряд со временем; смена файла сценариев меняет ответ; MQTT-отчёт соответствует контракту `from_mqtt`.
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать. **Step 4:** → PASS; стенд `bash tools/dev_stack.sh start` поднимает `ups`, `/api/v1/ups/state` показывает три ИБП онлайн.
- [ ] **Step 5:** commit `Tools: UPS emulator (apcupsd NIS + ESP32 MQTT) on the dev stand`.

### Task 8: Фронтенд — раздел «ИБП» в настройках и галочка «Электричество»

**Files:**
- Create: `frontend/src/components/UpsSettingsSection.tsx`, `frontend/src/components/UpsSettingsSection.test.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx` (вкладка «Оборудование»), `frontend/src/components/UserSmsModal.tsx` (+ `power`), i18n

**Interfaces:**
- Consumes: Task 1 API, Task 6 `POST /ups/check`, пороги `ups_*` через `useSettingUpdate`.
- Содержимое: таблица (название, модель, что питает, источник: адрес:порт или устройство, связь из `/ups/state`), «Добавить»; форма в `Modal`: название, модель (список из `/ups/models`), мощность — только для «Другая», что питает, источник (переключатель «apcupsd по сети» / «ESP32 по MQTT») и его поля, «Включён», «ИБП котельной (показывать на схеме)», «Проверить связь» (результат в форме: модель, режим, какие поля пришли или ошибка), «Сохранить», «Удалить» с подтверждением; ниже — пороги (4 поля). В `UserSmsModal` — галочка «Электричество» (`power`).
- [ ] **Step 1: Тест:** добавление apcupsd-ИБП шлёт `POST /ups` с телом формы; при «ESP32» вместо адреса — поле устройства; «Проверить связь» показывает «Модель: Back-UPS Pro 1200»; `UserSmsModal` содержит «Электричество».
- [ ] **Step 2:** `cd frontend && npx vitest run src/components/UpsSettingsSection.test.tsx` → FAIL. **Step 3:** реализовать. **Step 4:** → PASS; `npm run build`.
- [ ] **Step 5:** commit `UPS: settings section, «Электричество» SMS category in the user card`.

### Task 9: Фронтенд — страница «ИБП»

**Files:**
- Create: `frontend/src/components/SensorChart.tsx` (вынести `SensorChart`, `Period`, `PERIODS` и помощники из `StatisticsPage.tsx` без изменения поведения), `frontend/src/pages/UpsPage.tsx`, `frontend/src/components/UpsCard.tsx`, `frontend/src/components/UpsPicture.tsx`, `frontend/src/pages/UpsPage.test.tsx`
- Modify: `frontend/src/pages/StatisticsPage.tsx` (импорт вынесенного), `frontend/src/App.tsx` (маршрут `ups`), `frontend/src/components/Layout.tsx` (пункт `{ to: "/ups", key: "ups", icon: BatteryCharging }` для всех ролей), i18n

**Interfaces:**
- Consumes: `GET /ups/state` (Task 6), `/charts` с `ChartUpsVoltage` / `ChartUpsCharge`, пороги `ups_voltage_min/max` для пунктирных линий.
- Содержимое (спека «Страница «ИБП»»): карточка — `UpsPicture` (SVG по `shape`, светлая и тёмная тема), название, модель, что питает; режим крупно («От сети» / «От батареи N мин» / «Батарея разряжена» / «Нет связи»); заряд, время, нагрузка % и Вт, напряжения сети и батареи; «Здоровье»: батарея (норма / пора менять + номер), самотест, дата батареи, переходов на батарею и время от батареи, причина последнего перехода; `null` → «нет данных». Ниже — переключатель периода и два графика. Обновление — раз в `frontend_poll_seconds`. Телефон: карточки друг под другом.
- [ ] **Step 1: Тест:** карточка с полным статусом показывает «От сети» и «228 В»; ИБП без `linev` — «нет данных»; `online=false` — «Нет связи»; `REPLACEBATT` — «пора менять (APCRBC124)»; пункт меню «ИБП» виден viewer.
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать; `StatisticsPage.test`/существующие тесты зелёные. **Step 4:** → PASS; `npm run build`.
- [ ] **Step 5:** commit `UPS: monitoring page with cards and charts`.

### Task 10: Фронтенд — напряжение сети на схеме и дашборде

**Files:**
- Create: `frontend/src/components/PowerSection.tsx`, `frontend/src/components/PowerSection.test.tsx`
- Modify: `frontend/src/scheme/TopStrip.tsx`, `frontend/src/scheme/types.ts` (`power`), `frontend/src/scheme/TopStrip.test.tsx`, `frontend/src/pages/DashboardPage.tsx`, i18n

**Interfaces:**
- Consumes: `/scheme/state.power` (Task 6), `GET /ups/state`.
- Содержимое (спека «Дашборд и схема»): `TopStrip` — «Сеть 228 В»; на батарее — красным «От батареи · 85% · ~30 мин»; `online=false` — «Сеть —»; нет `linev` — только режим; `power == null` — элемента нет. Дашборд — секция «Электропитание» после «Водоснабжения»: компактная карточка на ИБП (название, режим, напряжение, заряд, время), ссылка на `/ups`; ИБП нет — секции нет.
- [ ] **Step 1: Тесты:** `TopStrip` с `power` онлайн / на батарее / без связи / `null`; `PowerSection` — две карточки, ссылка на `/ups`; пустой список — ничего.
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать. **Step 4:** → PASS; `npm test`, `npm run build`.
- [ ] **Step 5:** commit `UPS: mains voltage on the scheme top strip and a power section on the dashboard`.

### Task 11: Инструкция, документация, проверка на стенде

**Files:**
- Create: `docs/ups-apcupsd.md`
- Modify: `CLAUDE.md` (абзац «UPS monitoring» в Architecture, ключи `ups_*` в Settings Architecture, TODO: пункт «пропало электричество» — сделано на сервере, осталось: прошивка ESP32 котельной, подключение железа, роутер/Wi-Fi/сервер на ИБП)

- [ ] **Step 1:** `docs/ups-apcupsd.md` по спеке («Инструкция»): кабель USB; apcupsd для Windows (`UPSCABLE usb`, `UPSTYPE usb`, `NETSERVER on`, `NISIP 0.0.0.0`, `NISPORT 3551`), правило брандмауэра только для подсети ВМ, не ставить PowerChute; второй ИБП — второй экземпляр на другом порту (пометка «проверить при подключении») или Raspberry Pi; Raspberry Pi Zero 2 W с apcupsd; как добавить ИБП в настройках и проверить связь; условие «роутер, Wi-Fi и сервер на ИБП, иначе СМС о свете не уйдёт».
- [ ] **Step 2:** `CLAUDE.md`.
- [ ] **Step 3:** `cd backend && python3 -m pytest`, `cd frontend && npm test && npm run build` — всё зелёное.
- [ ] **Step 4:** commit `Docs: UPS monitoring`.
- [ ] **Step 5 (контроллер, стенд):** сценарий `outage` у «Серверного» → баннер «Нет электричества», СМС в журнале (при включённой отправке), график заряда, схема «От батареи»; затем `normal` → «Электричество вернулось». Скриншоты страницы «ИБП», дашборда, схемы — десктоп и телефон, тёмная тема.
