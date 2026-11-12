# СМС-уведомления — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** тревоги HomeSite уходят СМС через Android-телефон с MacroDroid: первая — сразу, дальше итог, когда устаканится; склейка с лимитом длины; журнал; получатели в карточке пользователя; новая тревога «нет интернета».

**Architecture:** HealthMonitor после `AlarmTracker.update()` отдаёт активные тревоги в `SmsNotifier`, который по чистым правилам (`sms_policy.py`) для каждой пары (проблема, получатель) создаёт, заменяет или гасит записи очереди. Телефон забирает очередь через `/api/v1/sms/ping|next|done`; при `next` готовые записи одного номера склеиваются в неизменную `SmsMessage`. Журнал и управление — страница `/sms` (admin).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, pytest-asyncio; React 19 + TS, TanStack Query, vitest, i18n ru/en.

**Spec:** `docs/superpowers/specs/2026-11-12-sms-notifications-design.md`

## Global Constraints

- Все времена UTC: `datetime.now(UTC)`, колонки `DateTime(timezone=True)`; тихие часы в `config_kv` — `HH:MM` UTC, как `backup_time`, интерфейс показывает местное.
- Уровни: `ERROR` — сразу, круглосуточно; `WARNING` — не раньше конца тихих часов; `INFO`/советы — никогда.
- Изменение проблемы — только поднята / снята / сменился уровень; значение в тексте — не изменение.
- Лимит склеенной СМС — 134 символа; переполнение — `…и ещё N, подробнее на сайте`; порядок `ERROR` → `WARNING`, поднятые → снятые.
- Бронь 10 мин; повтор после неудачи 5, 15, 60 мин; после 3 неудач — «не ушла».
- Хранение журнала 90 дней.
- Ключ API — только заголовок `Authorization: Bearer` или `X-SMS-Key`; в базе SHA-256; сравнение `hmac.compare_digest`; лимит 60/мин на IP.
- Каждый новый ключ `PUT /settings` — в `backend/app/core/setting_rules.py` (admin-only).
- Новая тревога — правило в `alarm_rules.py` + тест в `tests/test_alarm_rules.py` (CLAUDE.md).
- Мобильное приложение не трогаем; электричество/ИБП не делаем.
- Тексты СМС, интерфейса и событий — по-русски; ключи интерфейса — в `ru.json` и `en.json`.

## Review Focus

1. **Перезапуск бэкенда с активными авариями** — ни одной СМС: трекер пуст, пока не истекут задержки подъёма (комнаты — 10 мин). Тест в Task 4 (`test_restart_sends_nothing`).
2. **Два пользователя с одним номером** — одна СМС, проблема в ней один раз. Тест в Task 5 (`test_shared_number_one_sms_problem_once`).
3. **Пользователь поменял номер или галочки посреди эпизода** — несформированные записи уходят на новый номер / гасятся, если категорию выключили. Тест в Task 4 (`test_recipient_changes_mid_episode`).
4. **Телефон пропал на час с занятой бронью** — по истечении брони та же СМС выдаётся снова, тем же текстом. Тест в Task 5 (`test_expired_lease_reissues_same_text`).
5. **Тихие часы через полночь** (22:00–08:00 местного, в UTC может быть 18:00–04:00 или переходить через 00:00) — `WARNING` в 23:30 ждёт до конца. Тест в Task 2 (`test_quiet_window_wraps_midnight`).

---

## File Structure

| Файл | Ответственность |
|---|---|
| `backend/app/models/user.py` (изм.) | `phone`, `sms_categories` |
| `backend/app/models/sms.py` | `SmsSubscription` (состояние пары проблема×получатель), `SmsItem` (запись очереди), `SmsMessage` (сформированная СМС) |
| `backend/app/services/sms_policy.py` | чистые правила: категория, эффективный уровень, тихие часы, решение по изменению |
| `backend/app/services/sms_text.py` | нормализация номера, тексты, склейка с лимитом |
| `backend/app/services/sms_notifier.py` | применяет решения к базе каждый опрос; стартовая пауза; чистка 90 дней |
| `backend/app/services/sms_queue.py` | ключи, выдача / склейка / бронь / `done` / повтор, статус телефона |
| `backend/app/services/internet_probe.py` | проба TCP-адресов, адрес роутера |
| `backend/app/services/alarm_rules.py` (изм.) | `Snapshot.net`, `Snapshot.sms`; правила `internet_down`, `lan_down`, `sms_phone_silent`, `sms_failed` |
| `backend/app/services/health_monitor.py` (изм.) | проба раз в 60 с, заполнение `Snapshot`, вызов `SmsNotifier` |
| `backend/app/api/v1/sms.py` | API телефона и admin-API журнала |
| `backend/app/api/v1/auth.py`, `schemas/auth.py` (изм.) | `PUT /auth/users/{id}/sms` |
| `backend/app/core/setting_rules.py` (изм.) | ключи `sms_*`, `internet_*` |
| `backend/app/db/migrations/versions/<rev>_user_sms.py`, `<rev>_sms_queue.py` | миграции Task 1 и Task 4 |
| `frontend/src/pages/SettingsPage.tsx` (изм.) | `UserSmsModal` в разделе пользователей |
| `frontend/src/pages/SmsPage.tsx`, `App.tsx`, `components/Layout.tsx` (изм.) | страница `/sms`, пункт меню только для admin |

---

### Task 1: Телефон и категории СМС у пользователя

**Files:**
- Modify: `backend/app/models/user.py`, `backend/app/schemas/auth.py`, `backend/app/api/v1/auth.py`
- Create: `backend/app/db/migrations/versions/<rev>_user_sms.py`
- Create: `backend/app/services/sms_text.py` (пока только `normalize_phone`)
- Test: `backend/tests/test_sms_users.py`

**Interfaces:**
- Produces: `User.phone: str | None`, `User.sms_categories: str` (через запятую, подмножество `SMS_CATEGORIES`); `SMS_CATEGORIES = ("critical", "warning", "link", "internet", "test")` в `sms_text.py`; `normalize_phone(raw: str) -> str` (`+7XXXXXXXXXX`, `ValueError` при мусоре; `8…` и `7…` → `+7…`); `UserResponse` получает `phone`, `sms_categories: list[str]`.

- [ ] **Step 1: Тесты** — `test_normalize_phone`: `"8 (900) 123-45-67"` → `"+79001234567"`, `"+7 900 1234567"` → то же, `"12345"` → `ValueError`. `test_admin_sets_phone_and_categories`: `PUT /api/v1/auth/users/{id}/sms` `{"phone": "89001234567", "categories": ["critical", "internet"]}` → 200, `GET /auth/users` отдаёт `"+79001234567"` и `["critical", "internet"]`. `test_operator_cannot_set_sms` → 403. `test_unknown_category_rejected` (`"power"`) → 422. `test_empty_phone_clears` (`"phone": ""` → `null`). Аудит: в `EventLog` строка «Изменены СМС-настройки пользователя: …».
- [ ] **Step 2:** `cd backend && pytest tests/test_sms_users.py -v` → FAIL.
- [ ] **Step 3:** Поля модели (`phone: String(16) nullable`, `sms_categories: String(64) default ""`), миграция (`alembic revision --autogenerate -m "user sms"`), схема `UpdateUserSmsRequest {phone: str | None, categories: list[Literal[...]]}`, эндпоинт по образцу `change_password` (`require_role([UserRole.ADMIN])`).
- [ ] **Step 4:** pytest файла → PASS; `pytest` целиком → PASS.
- [ ] **Step 5:** commit `SMS: phone and categories per user`.

### Task 2: Чистые правила (`sms_policy.py`)

**Files:**
- Create: `backend/app/services/sms_policy.py`
- Test: `backend/tests/test_sms_policy.py`

**Interfaces:**
- Consumes: `Alarm`, `LEVEL_RANK` из `alarm_rules.py`.
- Produces:
  - `BANNER_ONLY = {"alarm_check_failed", "lan_down", "sms_phone_silent", "sms_failed"}`
  - `problem_key(a: Alarm) -> str` — `a.group or a.code`
  - `category(a: Alarm) -> str` — `"link"` для группы `link`, `"internet"` для `internet_down`, иначе `"critical"` (`ERROR`) / `"warning"` (`WARNING`); `INFO` → `""`
  - `current_problems(active: Iterable[Alarm]) -> dict[str, Alarm]` — без `BANNER_ONLY` и `INFO`, по проблеме самая серьёзная
  - `effective_level(a: Alarm | None, categories: set[str]) -> str | None` — уровень, если `category(a)` в `categories`, иначе `None`
  - `@dataclass Cfg: quiet_start: time | None, quiet_end: time | None, merge_s: int = 60, settle_s: int = 600`
  - `in_quiet(now: datetime, cfg: Cfg) -> bool`, `quiet_end_after(now: datetime, cfg: Cfg) -> datetime` (UTC, окно может переходить через полночь; `quiet_start == quiet_end` или `None` → тихих часов нет)
  - `@dataclass Sub: sent: str | None, seen: str | None, changes: int, episode_start: datetime | None` — `sent`/`seen` ∈ `{None, "WARNING", "ERROR"}`
  - `@dataclass Decision: kind: Literal["none", "first", "summary", "drop"], ready_at: datetime | None, sub: Sub` — `drop` = погасить ждущую запись со статусом «не нужна»; `first`/`summary` = заменить ждущую (если есть) и создать новую
  - `decide(sub: Sub, eff: str | None, now: datetime, cfg: Cfg) -> Decision`

Алгоритм `decide` (спека, «Логика по одной проблеме»):

```
if eff == sub.seen: return none
seen = eff
if eff is not None and (sub.sent is None or rank(eff) > rank(sub.sent)):
    kind = first; changes = 0; episode_start = episode_start or now
    ready = now + merge_s; quiet_level = eff                  # ухудшение — как первая
elif eff == sub.sent:
    kind = drop; changes += 1                                 # итог совпал с отправленным
else:                                                          # снятие или снижение
    kind = summary; changes += 1
    ready = now + settle_s; quiet_level = sub.sent            # тишина по отправленному уровню
if quiet_level == "WARNING" and (in_quiet(ready) ): ready = quiet_end_after(ready)
```

`sent` здесь не меняется — его ставит формирование СМС (Task 5) через `Sub` в базе.

- [ ] **Step 1: Тесты** (часы — фиксированные `datetime(..., tzinfo=UTC)`, `Cfg(time(18), time(4))`):
  - `test_first_error_immediate`: `Sub(None, None, 0, None)`, `eff="ERROR"` в 02:00 → `first`, `ready_at = now + 60 s`.
  - `test_first_warning_waits_quiet_end`: то же с `"WARNING"` в 02:00 → `ready_at` = 04:00 того же дня.
  - `test_quiet_window_wraps_midnight`: `"WARNING"` в 23:30 при `Cfg(time(22), time(8))` → 08:00 следующего дня; в 12:00 → `now + 60 s`.
  - `test_clear_after_error_settles_and_ignores_quiet`: `Sub("ERROR", "ERROR", 0, t0)`, `eff=None` в 02:00 → `summary`, `ready_at = now + 600 s`.
  - `test_clear_after_warning_waits_morning`: `Sub("WARNING", "WARNING", …)`, `eff=None` в 02:00 → `ready_at` = 04:00.
  - `test_back_to_sent_is_drop`: `Sub("ERROR", None, 1, t0)`, `eff="ERROR"` → `drop`, `changes == 2`.
  - `test_escalation_is_first`: `Sub("WARNING", "WARNING", 0, t0)`, `eff="ERROR"` → `first`, `episode_start == t0`.
  - `test_deescalation_is_summary`: `Sub("ERROR", "ERROR", …)`, `eff="WARNING"` → `summary`, тихие часы игнорируются.
  - `test_warning_raised_and_cleared_at_night_is_drop`: `Sub(None, "WARNING", 0, t0)`, `eff=None` → `drop`.
  - `test_no_change_is_none`.
  - `test_effective_level_filters_category`: `WARNING`-тревога при `{"critical"}` → `None`; `no_link` (группа `link`, `ERROR`) при `{"link"}` → `"ERROR"`, при `{"critical"}` → `None`.
  - `test_current_problems_group_and_banner_only`: `pressure_low` (`WARNING`, группа `p`) + `pressure_low_long` (`ERROR`, группа `p`) + `sms_failed` → `{"p": <ERROR>}`.
- [ ] **Step 2:** `pytest tests/test_sms_policy.py -v` → FAIL.
- [ ] **Step 3:** Реализовать по сигнатурам и псевдокоду.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** commit `SMS: per-problem policy (pure rules)`.

### Task 3: Тексты и склейка (`sms_text.py`)

**Files:**
- Modify: `backend/app/services/sms_text.py`
- Test: `backend/tests/test_sms_text.py`

**Interfaces:**
- Produces:
  - `SMS_LIMIT = 134`
  - `@dataclass Part: problem: str, level: str, raised: bool, text: str`
  - `raised_text(a: Alarm) -> str` — `a.text`
  - `summary_text(a: Alarm | None, last_text: str, changes: int, episode_start: datetime, now: datetime) -> str` — снята: `"Снято: {last_text}"`, для `internet_down` — `"Интернет есть, не было {N} мин"`; иначе текст текущей тревоги; при `changes > 1` добавить `" (за {M} мин {changes} раз туда-обратно)"`
  - `merge(parts: list[Part], limit: int = SMS_LIMIT) -> tuple[str, list[Part]]` — текст и вошедшие части; дубли по `problem` удаляются (остаётся первая после сортировки); сортировка `ERROR` → `WARNING`, `raised` → нет; части через `"; "`; не влезающие → `"…и ещё N, подробнее на сайте"` (хвост тоже в лимите); одна часть длиннее лимита обрезается до `limit - 1` + `"…"`. Невошедшие части тоже считаются ушедшими (о них сказано «и ещё N») — возвращаются все, текст один.

- [ ] **Step 1: Тесты:** `test_merge_orders_error_first`; `test_merge_limit_134_with_tail` (5 частей по 40 символов → `len(text) <= 134`, оканчивается на `"…и ещё 3, подробнее на сайте"` или соответствующее N); `test_merge_single_too_long_truncated` (200 символов → 134, конец `"…"`); `test_merge_dedupes_problem`; `test_summary_internet` (`episode_start` = now − 47 мин → `"Интернет есть, не было 47 мин"`); `test_summary_counts_flaps` (`changes=5`, 40 мин → содержит `"за 40 мин 5 раз туда-обратно"`); `test_summary_single_change_no_counter`.
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать. **Step 4:** → PASS.
- [ ] **Step 5:** commit `SMS: texts and merging with the length limit`.

### Task 4: Модели очереди и `SmsNotifier`

**Files:**
- Create: `backend/app/models/sms.py`, `backend/app/db/migrations/versions/<rev>_sms_queue.py`
- Create: `backend/app/services/sms_notifier.py`
- Test: `backend/tests/test_sms_notifier.py`

**Interfaces:**
- Consumes: Task 2 (`current_problems`, `effective_level`, `decide`, `Sub`, `Cfg`), Task 3 (`raised_text`, `summary_text`), `User.phone`/`sms_categories`.
- Produces (модели; колонки времени `DateTime(timezone=True)`):
  - `SmsSubscription(id, problem: str, user_id: FK users ondelete CASCADE, sent: str|None, seen: str|None, changes: int, episode_start, last_text: str, unique(problem, user_id))`
  - `SmsItem(id, problem, code, level, raised: bool, kind: "first"|"summary"|"test", user_id, phone, text, is_test: bool, state: "pending"|"formed"|"superseded"|"not_needed", message_id: FK sms_message nullable, created_at, ready_at)`
  - `SmsMessage(id, phone, text, is_test, state: "ready"|"leased"|"sent"|"failed", items: int, attempts: int, error: str|None, created_at, ready_at, leased_until, sent_at)`
  - `class SmsNotifier: __init__(self, started_at: datetime)`; `async def apply(self, session, active: Iterable[Alarm], now: datetime, cfg: Cfg) -> None`; `async def cleanup(self, session, now) -> None` (раз в сутки, удаляет `SmsItem`/`SmsMessage` старше 90 дней)
  - `STARTUP_GRACE_S = 900`

Поведение `apply` (на каждый опрос):
1. Получатели: активные пользователи с `phone` и непустыми категориями (кроме одной `test`).
2. Для каждой пары (проблема из `current_problems(active)` ∪ проблемы с подпиской `seen` или `sent` не `None`) × получатель: `eff = effective_level(...)`. В первые `STARTUP_GRACE_S` после `started_at` снижения (`eff` ниже `seen`) **не применяются** — трекер после рестарта пуст, пока не истекут задержки.
3. `decide` → `first`/`summary`: ждущая (`pending`) запись пары → `superseded`; новая `SmsItem` с текстом (`raised_text` / `summary_text`); `drop`: ждущая → `not_needed`. Обновить `SmsSubscription`.
4. Ждущим записям активных проблем обновлять `text` (значение в тексте меняется), `phone` — текущим номером пользователя; записи пользователя, у которого категория выключена или номер удалён, → `not_needed`.
5. Один `commit` на вызов.

- [ ] **Step 1: Тесты** (база из `db_session`, пользователи с номерами, `Cfg(None, None)` если не сказано, `Alarm` как в `test_alarm_rules.py`; `started_at` = t0 − 1 ч, если тест не про рестарт):
  - `test_first_raise_creates_item_for_subscribed_only` — два пользователя, у одного `critical`, у другого `warning`; `ERROR` → одна запись.
  - `test_flapping_leaves_one_summary` — поднята (запись → вручную `formed`, `sub.sent="ERROR"` как сделала бы Task 5), затем 5 раз снята/поднята по минуте, в конце снята → ровно одна `pending` summary, остальные `superseded`/`not_needed`; `ready_at` = последнее изменение + 600 с.
  - `test_flapping_back_to_raised_needs_nothing` — то же, в конце поднята → нет `pending`.
  - `test_value_change_is_not_a_change` — та же тревога с другим числом в тексте → записей не прибавилось, текст ждущей обновился.
  - `test_restart_sends_nothing` — `sub(sent="ERROR", seen="ERROR")` в базе, новый `SmsNotifier(started_at=now)`, `apply` с пустым `active`, через 10 мин `active` с той же тревогой → нет новых записей.
  - `test_vanished_during_downtime_cleared_after_grace` — то же, но тревога не вернулась; через 16 мин → `pending` summary «Снято: …».
  - `test_recipient_changes_mid_episode` — ждущая запись; номер пользователя меняется → `phone` записи новый; категорию выключили → `not_needed`.
  - `test_cleanup_removes_older_than_90_days`.
- [ ] **Step 2:** `pytest tests/test_sms_notifier.py -v` → FAIL.
- [ ] **Step 3:** Модели, миграция (`alembic revision --autogenerate`, затем проверить `alembic upgrade head` на копии `homesite.db`), `SmsNotifier`.
- [ ] **Step 4:** → PASS; `pytest` целиком → PASS.
- [ ] **Step 5:** commit `SMS: queue models and notifier`.

### Task 5: Очередь и API телефона

**Files:**
- Create: `backend/app/services/sms_queue.py`, `backend/app/api/v1/sms.py`
- Modify: `backend/app/api/router.py` (`prefix="/sms"`)
- Test: `backend/tests/test_sms_queue.py`, `backend/tests/test_sms_phone_api.py`

**Interfaces:**
- Consumes: модели Task 4, `merge`/`Part` Task 3, `config_kv`.
- Produces (`sms_queue.py`):
  - `LEASE_S = 600`, `RETRY_S = (300, 900, 3600)`, `MAX_ATTEMPTS = 3`
  - `async def issue_key(session, mode: Literal["live", "test"]) -> str` — `secrets.token_urlsafe(32)`, в `config_kv` `sms_key_{mode}_hash` = SHA-256
  - `async def key_mode(session, key: str) -> Literal["live", "test"] | None`
  - `async def next_message(session, is_test: bool, now) -> SmsMessage | None` — 1) `leased` с истёкшей бронью → снова `leased_until = now + LEASE_S`, тот же текст; 2) `ready` с наступившим `ready_at` (повтор); 3) иначе самая старая `pending` `SmsItem` с наступившим `ready_at` → все такие же для её `phone` → `merge` → новая `SmsMessage` (`leased`), записи `formed` + `message_id`, у их `SmsSubscription` `sent` = `level` записи (`raised`) или `None` (снята), `changes = 0`; захват — `UPDATE … WHERE state = 'pending'` с проверкой `rowcount`
  - `async def mark_done(session, msg_id: int, is_test: bool, ok: bool, error: str | None, now) -> bool` — `False` если нет такого id для этого режима; `ok` → `sent`, `sent_at`; иначе `attempts += 1`, `< 3` → `ready`, `ready_at = now + RETRY_S[attempts-1]`, иначе `failed`; повтор для `sent` → `True` без изменений
  - `async def touch_poll(session, now)` — `config_kv` `sms_last_poll_at` (ISO UTC)
  - `async def phone_status(session, now, poll_s: int) -> dict` — `{"last_poll_at", "silent": bool, "pending": int, "failed": int}`; `silent` = есть боевой ключ, есть получатель и `now − last_poll > max(900, 3 × poll_s)` (нет опроса совсем → считать от момента выпуска ключа)
- Produces (API, `Authorization: Bearer <key>` или `X-SMS-Key`; ключ в query игнорируется; `@limiter.limit("60/minute")`; ответ с `poll_after` из `sms_poll_seconds`, по умолчанию 60):
  - `GET /api/v1/sms/ping` → `{"mode", "queue", "quiet", "poll_after"}`
  - `GET /api/v1/sms/next` → 200 `{"id", "to", "text", "poll_after"}` / 204 + `X-Poll-After`
  - `POST /api/v1/sms/done` `{"id": int, "ok": bool, "error": str | None}` → 200 `{"ok": true, "poll_after"}` / 404
  - Для Swagger: `HTTPBearer(auto_error=False)` в зависимости, чтобы в `/docs` (стенд, `debug`) была кнопка Authorize.

- [ ] **Step 1: Тесты очереди:** `test_merge_same_phone_into_one_message` (две записи одного номера → одна `SmsMessage`, `items == 2`, обе `formed`); `test_shared_number_one_sms_problem_once` (два пользователя, один номер, одна проблема → в тексте один раз); `test_not_ready_not_issued`; `test_expired_lease_reissues_same_text` (после `LEASE_S + 1` — тот же `id` и текст); `test_failure_retries_then_failed` (`ok=False` → `ready_at` +300, +900, затем `failed`); `test_formed_message_is_immutable` (после формирования новая summary той же проблемы → отдельное сообщение, старое не тронуто); `test_formation_sets_sent` (`sub.sent` = `"ERROR"` после выдачи «поднята», `None` после «снята»); `test_test_and_live_isolated`; `test_phone_silent_threshold`.
- [ ] **Step 2: Тесты API:** `test_no_key_401`, `test_key_in_query_401`, `test_bearer_and_x_sms_key_both_work`, `test_next_204_has_x_poll_after`, `test_done_unknown_404`, `test_done_repeat_200`, `test_live_request_updates_last_poll`.
- [ ] **Step 3:** `pytest tests/test_sms_queue.py tests/test_sms_phone_api.py -v` → FAIL.
- [ ] **Step 4:** Реализовать.
- [ ] **Step 5:** → PASS; `pytest` → PASS.
- [ ] **Step 6:** commit `SMS: queue and phone API (ping/next/done)`.

### Task 6: Интернет, тревоги СМС и подключение к HealthMonitor

**Files:**
- Create: `backend/app/services/internet_probe.py`
- Modify: `backend/app/services/alarm_rules.py`, `backend/app/services/health_monitor.py`, `backend/app/core/setting_rules.py`
- Test: `backend/tests/test_alarm_rules.py`, `backend/tests/test_health_monitor.py`, `backend/tests/test_internet_probe.py`

**Interfaces:**
- Consumes: `SmsNotifier` (Task 4), `phone_status` (Task 5), `Cfg` (Task 2).
- Produces:
  - `internet_probe.py`: `async def reachable(targets: list[str], timeout: float = 3.0) -> bool` — `host:port`, хоть один открылся → `True`; `def default_router() -> str | None` — шлюз по умолчанию из `/proc/net/route` как `host:80`, `None` если нет; `internet_router_host` без порта — тоже `:80`
  - `Snapshot.net: dict = {}` — `{"internet": bool | None, "router": bool | None, "down_s": int}`; `Snapshot.sms: dict = {}` — `{"silent": bool, "failed": int}`
  - правила в `evaluate`: `router is False` → `Alarm("lan_down", "WARNING", "Нет локальной сети — сервер не видит роутер", 300)`; иначе `internet is False` → `Alarm("internet_down", "ERROR", "Нет интернета", down_s)`; `sms.silent` → `Alarm("sms_phone_silent", "ERROR", "Телефон СМС не на связи — СМС не уходят")`; `sms.failed > 0` → `Alarm("sms_failed", "WARNING", f"{n} СМС не отправлено — смотрите журнал СМС")`
  - `setting_rules.py` (все `_sys`): `sms_quiet_start`, `sms_quiet_end` (`time`), `sms_merge_seconds` (`int`, 0–600), `sms_settle_minutes` (`int`, 1–120), `sms_poll_seconds` (`int`, 30–900), `internet_check_hosts` (`str`, через запятую; пусто = проверка выключена), `internet_down_minutes` (`int`, 1–60), `internet_router_host` (`str`, пусто = шлюз ВМ). Значения по умолчанию — в коде, когда ключа нет в `config_kv` (прод уже засеян, сид не поможет): хосты `77.88.8.8:53,1.1.1.1:53,ya.ru:443,8.8.8.8:53`, 5 мин, тихие часы 18:00–04:00 UTC (22:00–08:00 у дома, +4), склейка 60 с, успокоение 10 мин, опрос 60 с.
  - `HealthMonitor`: проба не чаще раза в 60 с (кэш результата между опросами); `self.sms = SmsNotifier(started_at=now)` в `__init__`; после `self.alarms.update(...)` в `_check_alarms` — `await self.sms.apply(session, self.alarms.active.values(), now, cfg)` в своём `try` (ошибка СМС логируется, не ломает тревоги); `cleanup` раз в сутки.
- [ ] **Step 1: Тесты правил** (`test_alarm_rules.py`): `test_internet_down_raised` (`net={"internet": False, "router": True, "down_s": 300}` → `internet_down`, `delay_s == 300`); `test_lan_down_instead_of_internet`; `test_partial_internet_no_alarm` (`internet: True`); `test_no_probe_no_alarm` (`net={}`); `test_sms_phone_silent`; `test_sms_failed_count_in_text`.
- [ ] **Step 2: Тест пробы:** `test_reachable_any_target` — локальный `asyncio.start_server` на свободном порту + закрытый порт → `True`; только закрытый → `False`.
- [ ] **Step 3: Тест монитора:** `test_alarm_reaches_sms_queue` — пользователь с номером и `critical`, `_monitor(engine)`, подменить `evaluate`/трекер так, чтобы активна `ERROR`-тревога, два `_check()` → в базе `pending` `SmsItem`; `test_sms_failure_does_not_break_alarms` (`apply` бросает → `state.active_alarms` заполнен).
- [ ] **Step 4:** → FAIL. **Step 5:** реализовать. **Step 6:** `pytest` (включая `test_setting_rules_firmware.py`) → PASS.
- [ ] **Step 7:** commit `SMS: internet loss alarm, SMS alarms, HealthMonitor hookup`.

### Task 7: Admin-API раздела СМС

**Files:**
- Modify: `backend/app/api/v1/sms.py`
- Test: `backend/tests/test_sms_admin_api.py`

**Interfaces:**
- Consumes: Task 5.
- Produces (все `require_role([UserRole.ADMIN])`):
  - `GET /api/v1/sms/log?state=&code=&user_id=&test=false&page=1` → `{"items": [{"id", "created_at", "code", "level", "kind", "text", "user": {"id", "username"}, "phone", "status", "message": {"id", "items", "attempts", "error", "sent_at"} | null}], "total", "page"}`; 50 на страницу, свежие сверху; `status` — `pending`→«ждёт», `superseded`→«заменена», `not_needed`→«не нужна», `formed` → статус сообщения (`leased`→«выдана», `sent`→«ушла», `failed`→«не ушла», `ready`→«ждёт повтора»)
  - `GET /api/v1/sms/status` → `phone_status(...)` + `{"has_live_key", "has_test_key"}`
  - `POST /api/v1/sms/messages/{id}/retry` — только `failed` → `ready`, `attempts = 0`; иначе 409
  - `POST /api/v1/sms/keys/{mode}` → `{"key"}` (показывается один раз)
  - `POST /api/v1/sms/test-me` — боевая `SmsItem(kind="test")` на номер текущего admin, текст «Тестовая СМС HomeSite»; 400, если у admin нет номера
  - `POST /api/v1/sms/test-queue` — то же, `is_test=True`
  - Все мутации пишут `EventLog` с `user_id`.
- [ ] **Step 1: Тесты:** `test_log_paginates_and_filters`; `test_log_shows_merged_count`; `test_retry_only_failed`; `test_issue_key_shown_once_and_works` (ключ из ответа проходит `/sms/ping`, в `config_kv` только хеш); `test_test_me_requires_phone`; `test_viewer_and_operator_forbidden`.
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать. **Step 4:** → PASS.
- [ ] **Step 5:** commit `SMS: admin API (log, retry, keys, test SMS)`.

### Task 8: Фронтенд — СМС в карточке пользователя

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx` (раздел Users, около строки 2495; новый `UserSmsModal` рядом с `ChangePasswordModal`), `frontend/src/i18n/ru.json`, `frontend/src/i18n/en.json`
- Test: `frontend/src/pages/UserSmsModal.test.tsx` (компонент вынести в `frontend/src/components/UserSmsModal.tsx`)

**Interfaces:**
- Consumes: `PUT /auth/users/{id}/sms`, `UserResponse.phone`, `sms_categories`.
- [ ] **Step 1: Тест:** модалка показывает пять галочек (аварии, предупреждения, связь с контроллером, интернет, тестовые) и номер; сохранение шлёт `{"phone": "...", "categories": [...]}`; ошибка 422 показывается под полем номера.
- [ ] **Step 2:** `cd frontend && npx vitest run src/components/UserSmsModal.test.tsx` → FAIL.
- [ ] **Step 3:** Реализовать; в строке пользователя — номер и значок СМС, кнопка «СМС» открывает модалку.
- [ ] **Step 4:** → PASS; `npm run build` без ошибок типов.
- [ ] **Step 5:** скриншоты десктоп + телефон (стенд `bash tools/dev_stack.sh`), commit `SMS: phone and SMS categories in the user card`.

### Task 9: Фронтенд — страница `/sms`

**Files:**
- Create: `frontend/src/pages/SmsPage.tsx`, `frontend/src/pages/SmsPage.test.tsx`
- Modify: `frontend/src/App.tsx` (маршрут `sms`), `frontend/src/components/Layout.tsx` (пункт `{ to: "/sms", key: "sms", icon: MessageSquare }` только для `role === "admin"`), i18n

**Interfaces:**
- Consumes: Task 7.
- Содержимое (спека, «Раздел СМС»): над журналом — последний опрос телефона, ждёт / не ушло, предупреждение «телефон молчит»; журнал с фильтрами (статус, тип, получатель, тестовые) и листанием, «Повторить» у «не ушла», склеенные — «в одной СМС с N»; блок настроек через существующий `useSettingUpdate` (тихие часы в местном времени ↔ UTC, как у расписания бэкапов; окно склейки, успокоение, опрос, интернет); ключи — «Создать/перевыпустить» с показом один раз и копированием; кнопки тестовых СМС; инструкция MacroDroid (интервал 1 мин; переменная из `poll_after` / `X-Poll-After`; цикл next → отправить СМС → done → next до 204; отключить оптимизацию батареи; сначала тестовый ключ).
- [ ] **Step 1: Тест:** страница рендерит журнал из замоканного `/sms/log`, статус «не ушла» показывает кнопку «Повторить», клик шлёт `POST /sms/messages/{id}/retry`; не-admin пункт меню не видит.
- [ ] **Step 2:** → FAIL. **Step 3:** реализовать. **Step 4:** → PASS; `npm run build`.
- [ ] **Step 5:** скриншоты десктоп + телефон, commit `SMS: SMS page (log, status, keys, settings, MacroDroid guide)`.

### Task 10: Документация и проверка на стенде

**Files:**
- Modify: `CLAUDE.md` (раздел про СМС в Architecture, новые ключи в Settings Architecture, TODO: СМС — частично, ИБП — осталось), `deploy/nginx/` (заготовка LAN-only HTTP `location /api/v1/sms/` с `allow 192.168.0.0/16; deny all;`, закомментированная, с пояснением)

- [ ] **Step 1:** Обновить `CLAUDE.md` и nginx-заготовку.
- [ ] **Step 2:** Стенд: `bash tools/dev_stack.sh`, выпустить тестовый ключ, `curl -H "Authorization: Bearer …" /api/v1/sms/ping|next|done` — цикл до 204; «Создать тестовую СМС» → видна в журнале как «ушла».
- [ ] **Step 3:** `cd backend && pytest` и `cd frontend && npm test` → всё зелёное.
- [ ] **Step 4:** commit `Docs: SMS notifications`.
- [ ] **Step 5 (после деплоя, вручную с владельцем):** MacroDroid на телефоне с самоподписанным сертификатом; если не принимает — включить LAN-only HTTP из заготовки.
