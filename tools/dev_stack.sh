#!/bin/bash
# HomeSite v2 — local dev stand: site + gateway + MQTT broker + house emulator
# on a copy of the production database.
#
# Usage: bash tools/dev_stack.sh            (interactive menu)
#        bash tools/dev_stack.sh start|stop|status
#
# Everything lives in tools/.dev_stack/ (gitignored). Production is only read:
# a consistent DB snapshot is copied over SSH (host alias "homesite").
# Ports: broker 18830 (does not touch a system mosquitto on 1883),
#        backend 8000, gateway 8001, site 5173.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/tools/.dev_stack"
DB="$DIR/homesite.db"
PROD_HOST="${PROD_HOST:-homesite}"
PROD_DB="/opt/homesite/data/homesite.db"
BROKER_PORT=18830
SERVICES=(mosquitto backend gateway frontend emulator)

mkdir -p "$DIR"

export APP_ENV=dev
export DATABASE_URL="sqlite+aiosqlite:///$DB"
export JWT_SECRET_KEY=local-dev-jwt-secret-0123456789
export INTERNAL_API_SECRET=local-dev-internal-secret-0123
export DEVICE_GATEWAY_URL=http://127.0.0.1:8001
export BACKEND_URL=http://127.0.0.1:8000
export GATEWAY_API_PORT=8001
export CORS_ORIGINS=http://localhost:5173
export LOG_FORMAT=console

is_up() { [[ -f "$DIR/$1.pid" ]] && kill -0 "$(cat "$DIR/$1.pid")" 2>/dev/null; }

copy_prod_db() {
    echo "=== Copy production DB snapshot ($PROD_HOST) ==="
    if is_up backend || is_up gateway; then
        echo "Stop the stand first (the DB file is in use)."; return 1
    fi
    local remote
    # sqlite3 backup API on the server → consistent copy including the WAL
    remote="$(ssh "$PROD_HOST" "F=\$(mktemp /tmp/hs-copy-XXXX.db) && /opt/homesite/venv/bin/python -c 'import sqlite3,sys; s=sqlite3.connect(\"file:$PROD_DB?mode=ro\", uri=True); d=sqlite3.connect(sys.argv[1]); s.backup(d); d.close()' \$F && echo \$F")" || return 1
    scp -q "$PROD_HOST:$remote" "$DB.new" && ssh "$PROD_HOST" "rm -f $remote"
    mv "$DB.new" "$DB"
    prepare_db
    echo "Done: $(du -h "$DB" | cut -f1)"
}

prepare_db() {
    # Point the copy at the local broker/gateway, feed the outdoor sensor to the controller
    (cd "$ROOT/backend" && python3 -m alembic upgrade head >/dev/null)
    python3 - "$DB" "$BROKER_PORT" <<'PY'
import sqlite3, sys
db, port = sys.argv[1], sys.argv[2]
c = sqlite3.connect(db)
kv = {"mqtt_host": "127.0.0.1", "mqtt_port": port, "mqtt_user": "", "mqtt_pass": "",
      "device_gateway_url": "http://127.0.0.1:8001",
      "pza_outdoor_sensor": "clm_street_th", "pza_outdoor_device": "boiler_unit"}
for k, v in kv.items():
    c.execute("INSERT INTO config_kv(key, value) VALUES(?, ?) "
              "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
c.commit()
PY
}

set_local_password() {
    local pw="local-$(python3 -c 'import secrets; print(secrets.token_hex(4))')"
    python3 - "$DB" "$pw" <<'PY'
import sqlite3, sys, bcrypt
c = sqlite3.connect(sys.argv[1], timeout=10)
c.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'",
          (bcrypt.hashpw(sys.argv[2].encode(), bcrypt.gensalt()).decode(),))
c.commit()
PY
    echo "Local login: admin / $pw   (only in the local copy)"
}

start_one() {
    local name="$1"; shift
    if is_up "$name"; then echo "  $name already running"; return; fi
    nohup "$@" > "$DIR/$name.log" 2>&1 &
    echo $! > "$DIR/$name.pid"
    echo "  $name started (pid $!)"
}

start() {
    echo "=== Start stand ==="
    [[ -f "$DB" ]] || { echo "No database yet — copying from production first."; copy_prod_db || return 1; }
    printf 'listener %s 127.0.0.1\nallow_anonymous true\n' "$BROKER_PORT" > "$DIR/mosquitto.conf"
    start_one mosquitto mosquitto -c "$DIR/mosquitto.conf"
    sleep 1
    (cd "$ROOT/backend" && start_one backend python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000)
    (cd "$ROOT/backend" && start_one gateway python3 -m device_gateway)
    (cd "$ROOT/frontend" && start_one frontend npm run dev -- --host 127.0.0.1)
    (cd "$ROOT/tools" && start_one emulator python3 -m house_emulator --port "$BROKER_PORT" --no-console)
    echo "Waiting for the site..."
    for _ in $(seq 1 60); do
        curl -fs -o /dev/null http://127.0.0.1:5173/ && break
        sleep 2
    done
    status
    echo "Site: http://localhost:5173"
}

stop() {
    echo "=== Stop stand ==="
    for name in "${SERVICES[@]}"; do
        if is_up "$name"; then
            kill "$(cat "$DIR/$name.pid")" && echo "  $name stopped"
        fi
        rm -f "$DIR/$name.pid"
    done
}

status() {
    for name in "${SERVICES[@]}"; do
        printf "  %-10s %s\n" "$name" "$(is_up "$name" && echo up || echo down)"
    done
    curl -fs http://127.0.0.1:8000/health/status 2>/dev/null && echo
}

emulator_console() {
    echo "Stopping the background emulator and starting it here with a console (Ctrl+C / quit to leave)."
    if is_up emulator; then kill "$(cat "$DIR/emulator.pid")"; rm -f "$DIR/emulator.pid"; sleep 1; fi
    (cd "$ROOT/tools" && python3 -m house_emulator --port "$BROKER_PORT")
    echo "Console closed. Restart the background emulator with 'start'."
}

logs() {
    read -r -p "Service (${SERVICES[*]}): " name
    [[ -f "$DIR/$name.log" ]] && tail -n 40 "$DIR/$name.log" || echo "No log for '$name'"
}

menu() {
    while true; do
        echo
        echo "HomeSite dev stand ($DIR)"
        echo "  1) Start everything"
        echo "  2) Stop everything"
        echo "  3) Status"
        echo "  4) Copy fresh production DB snapshot"
        echo "  5) Set local admin password"
        echo "  6) Emulator console (interactive)"
        echo "  7) Show a log"
        echo "  0) Exit"
        read -r -p "> " choice
        case "$choice" in
            1) start ;;
            2) stop ;;
            3) status ;;
            4) copy_prod_db ;;
            5) set_local_password ;;
            6) emulator_console ;;
            7) logs ;;
            0) break ;;
            *) echo "?" ;;
        esac
    done
}

case "${1:-menu}" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    menu) menu ;;
    *) echo "Usage: $0 [start|stop|status]"; exit 1 ;;
esac
