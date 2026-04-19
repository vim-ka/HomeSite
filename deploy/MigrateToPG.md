# Migration SQLite → PostgreSQL

Перенос рантайм-данных HomeSite v2 с SQLite на Postgres без потерь. Инструмент — `backend/scripts/migrate_sqlite_to_pg.py` (только копирование данных; схему создаёт Alembic).

Предполагается, что пути стандартные (`install.sh`): код в `/opt/homesite`, venv в `/opt/homesite/venv`, systemd-юниты `homesite-backend` и `homesite-gateway`. Если переход делается на живом инстансе — сначала прогони всё на копии VM.

**Быстрый путь:** шаги ниже обёрнуты в интерактивный скрипт `deploy/migrate_to_pg.sh` — запусти без аргументов и выбирай пункт из меню:

```bash
bash deploy/migrate_to_pg.sh
```

Пароль Postgres запросится один раз (на первом же шаге, где он нужен) и сохранится на сессию. Подробное описание каждого шага — ниже.

---

## 1. Установить Postgres и клиентские зависимости

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres psql -c "CREATE ROLE homesite WITH LOGIN PASSWORD 'СГЕНЕРИРУЙ';"
sudo -u postgres psql -c "CREATE DATABASE homesite OWNER homesite;"

# asyncpg в том же venv, где крутится бэкенд
/opt/homesite/venv/bin/pip install asyncpg
```

## 2. Остановить сервисы и сделать бэкап SQLite

Бэкенд и gateway должны стоять на всё время копирования — иначе gateway продолжит писать в SQLite, и часть строк потеряется после миграции.

```bash
# Остановить оба юнита (порядок не важен)
sudo systemctl stop homesite-backend homesite-gateway

# Убедиться, что процессы действительно завершились
sudo systemctl status homesite-backend homesite-gateway | grep Active
# Ожидаемое: "Active: inactive (dead)"

# (опционально) disable, чтобы не стартовали после перезагрузки
sudo systemctl disable homesite-backend homesite-gateway

# Бэкап SQLite
cp /opt/homesite/backend/sensors.db \
   /opt/homesite/backend/sensors.db.pre-pg-$(date +%F)
```

## 3. Создать схему в пустом Postgres через Alembic

```bash
cd /opt/homesite/backend
DATABASE_URL="postgresql+asyncpg://homesite:ПАРОЛЬ@localhost/homesite" \
  /opt/homesite/venv/bin/alembic upgrade head
```

Создаст все 17 таблиц + индексы + constraints + пустые sequences.

## 4. Dry-run миграционного скрипта

```bash
cd /opt/homesite/backend
/opt/homesite/venv/bin/python -m scripts.migrate_sqlite_to_pg \
  --source "sqlite+aiosqlite:///./sensors.db" \
  --target "postgresql+asyncpg://homesite:ПАРОЛЬ@localhost/homesite" \
  --dry-run
```

Выведет row counts по каждой таблице. Проверь, что `sensor_data_history` и `event_logs` выглядят разумно.

## 5. Реальная миграция

```bash
cd /opt/homesite/backend
/opt/homesite/venv/bin/python -m scripts.migrate_sqlite_to_pg \
  --source "sqlite+aiosqlite:///./sensors.db" \
  --target "postgresql+asyncpg://homesite:ПАРОЛЬ@localhost/homesite"
```

Что делает:
- Копирует 17 таблиц в FK-порядке, батчами по 1000 строк.
- Заполняет `mount_points` с `NULL` в `*_sensor_id`, после `sensors` делает второй проход с UPDATE (решает круговой FK).
- Приводит naive datetime из SQLite к UTC-aware.
- Сбрасывает sequences через `setval` на всех 15 таблицах с autoincrement PK.
- В конце сверяет row counts source vs target и падает с `SystemExit` при расхождении.

На ~900k строк истории — несколько минут.

Повторный запуск: добавить `--truncate` (очистит target через `TRUNCATE ... RESTART IDENTITY CASCADE` и зальёт заново).

## 6. Переключить `.env` на Postgres

```bash
sudo nano /opt/homesite/.env
# DATABASE_URL=postgresql+asyncpg://homesite:ПАРОЛЬ@localhost/homesite
```

`JWT_SECRET_KEY`, `INTERNAL_API_SECRET`, `CORS_ORIGINS` не трогаем.

## 7. Запустить сервисы и проверить

```bash
# Если на шаге 2 делал disable
sudo systemctl enable homesite-backend homesite-gateway

sudo systemctl start homesite-backend homesite-gateway
sudo systemctl status homesite-backend homesite-gateway
journalctl -u homesite-backend -f   # смотреть на ошибки коннекта/FK
```

Смок-тест через UI:
- **Логин** — `users` таблица переехала корректно.
- **Dashboard** — данные грузятся, `sensor_data` читается.
- **Stats** — графики отрисовываются (`sensor_data_history`).
- **Events** — лог виден (`event_logs`).
- **Settings** — сохранить любую настройку и убедиться, что она применилась (проверяет, что sequence на `config_kv` корректно сдвинут).

## 8. Откат

Если что-то пошло не так — старая `sensors.db` не тронута (скрипт только читает из неё):

```bash
sudo systemctl stop homesite-backend homesite-gateway
sudo nano /opt/homesite/.env
# DATABASE_URL=sqlite+aiosqlite:///./sensors.db
sudo systemctl start homesite-backend homesite-gateway
```

## 9. Чистка через 1-2 недели

Когда убедишься, что Postgres стабилен:

```bash
rm /opt/homesite/backend/sensors.db.pre-pg-*
# Сам sensors.db лучше оставить ещё неделю на всякий случай.
```

---

## Нюансы

- **Таймзоны**: SQLite возвращал naive-строки, Postgres возвращает tz-aware. Фронт уже нормализует через `endsWith("Z")` (см. CLAUDE.md), так что ничего дополнительно менять не нужно.
- **Gateway**: читает MQTT-настройки из `config_kv` при старте — они переедут вместе с остальными данными.
- **Бэкапы PG**: теперь вместо копирования `.db` файла используем `pg_dump`:
  ```bash
  PGPASSWORD=ПАРОЛЬ pg_dump -U homesite homesite > homesite-$(date +%F).sql
  ```
  Стоит добавить в cron (отдельный TODO).
- **Флаги скрипта**:
  - `--truncate` — очистить target перед копированием (для перезапуска).
  - `--dry-run` — только вывести row counts источника.
  - `--batch-size N` — размер батча для INSERT (default 1000).
  - `--tables a,b,c` — скопировать только перечисленные таблицы (в своём порядке; используй с осторожностью — FK не проверяются).
