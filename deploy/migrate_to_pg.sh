#!/bin/bash
# HomeSite v2 — SQLite → PostgreSQL interactive migration runner.
# Usage: bash deploy/migrate_to_pg.sh
# See deploy/MigrateToPG.md for full context.

set -uo pipefail

INSTALL_DIR="/opt/homesite"
ENV_FILE="$INSTALL_DIR/.env"
PG_DB="homesite"
PG_USER="homesite"
PY="$INSTALL_DIR/venv/bin/python"

# Source DB = whatever the backend actually uses (was hardcoded ./sensors.db,
# while installs keep it in /opt/homesite/data/homesite.db)
SOURCE_URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- || true)"
if [[ "$SOURCE_URL" != sqlite* ]]; then
    echo "DATABASE_URL in $ENV_FILE is not SQLite ('$SOURCE_URL') — nothing to migrate."
    exit 1
fi
SOURCE_PATH="${SOURCE_URL#*:///}"

PG_PASS=""
TARGET_URL=""

prompt_pg_pass() {
    if [[ -n "$PG_PASS" ]]; then
        return
    fi
    read -r -s -p "Postgres password for role '$PG_USER': " PG_PASS
    echo
    if [[ -z "$PG_PASS" ]]; then
        echo "ERROR: password is empty."
        PG_PASS=""
        return 1
    fi
    # URL-encode the password: '@', ':' or '/' would otherwise break the URL
    local enc
    enc="$(PG_PASS="$PG_PASS" "$PY" -c 'import os, urllib.parse; print(urllib.parse.quote(os.environ["PG_PASS"], safe=""))')"
    TARGET_URL="postgresql+asyncpg://${PG_USER}:${enc}@localhost/${PG_DB}"
}

pause() {
    echo
    read -r -p "Press Enter to return to menu..."
}

step_1() {
    echo "=== [1/8] Install Postgres + create role/db + asyncpg ==="
    prompt_pg_pass || return
    sudo apt update
    sudo apt install -y postgresql postgresql-contrib
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$PG_USER'" | grep -q 1; then
        echo "Role $PG_USER already exists, skipping."
    else
        # Pass the password as a psql variable (:'pw' quotes it) — never splice it into SQL
        echo "CREATE ROLE $PG_USER WITH LOGIN PASSWORD :'pw';" | sudo -u postgres psql -v ON_ERROR_STOP=1 -v pw="$PG_PASS"
    fi
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$PG_DB'" | grep -q 1; then
        echo "Database $PG_DB already exists, skipping."
    else
        sudo -u postgres psql -c "CREATE DATABASE $PG_DB OWNER $PG_USER;"
    fi
    "$INSTALL_DIR/venv/bin/pip" install asyncpg
    echo "Done."
}

step_2() {
    echo "=== [2/8] Stop services and backup SQLite ==="
    sudo systemctl stop homesite-backend homesite-gateway
    echo "--- Service status:"
    sudo systemctl status homesite-backend homesite-gateway --no-pager | grep -E "Active:" || true
    BACKUP="${SOURCE_PATH}.pre-pg-$(date +%F)"
    # sqlite3 backup API: consistent copy including the WAL
    "$PY" -c 'import sqlite3, sys; s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()' "$SOURCE_PATH" "$BACKUP"
    echo "Backup: $BACKUP"
    echo "Done. Services stopped, SQLite backed up."
}

step_3() {
    echo "=== [3/8] Create schema in Postgres via Alembic ==="
    prompt_pg_pass || return
    (cd "$INSTALL_DIR/backend" && \
        DATABASE_URL="$TARGET_URL" "$INSTALL_DIR/venv/bin/alembic" upgrade head)
    echo "Done. Schema created in Postgres."
}

step_4() {
    echo "=== [4/8] Dry-run migration (row counts only) ==="
    prompt_pg_pass || return
    (cd "$INSTALL_DIR/backend" && \
        "$INSTALL_DIR/venv/bin/python" -m scripts.migrate_sqlite_to_pg \
            --source "$SOURCE_URL" --target "$TARGET_URL" --dry-run)
}

step_5() {
    echo "=== [5/8] Run real data migration ==="
    prompt_pg_pass || return
    (cd "$INSTALL_DIR/backend" && \
        "$INSTALL_DIR/venv/bin/python" -m scripts.migrate_sqlite_to_pg \
            --source "$SOURCE_URL" --target "$TARGET_URL")
    echo "Done. Data copied; row counts verified."
}

step_6() {
    echo "=== [6/8] Switch .env to Postgres ==="
    prompt_pg_pass || return
    echo "Will set DATABASE_URL in $ENV_FILE to postgresql+asyncpg://${PG_USER}:****@localhost/${PG_DB}"
    read -r -p "Proceed? [y/N] " ans
    if [[ "$ans" != "y" && "$ans" != "Y" ]]; then
        echo "Skipped."
        return
    fi
    sudo cp "$ENV_FILE" "${ENV_FILE}.pre-pg-$(date +%F)"
    TARGET_URL="$TARGET_URL" sudo --preserve-env=TARGET_URL "$PY" - "$ENV_FILE" <<'PY'
import os, sys
path, url = sys.argv[1], os.environ["TARGET_URL"]
lines = open(path, encoding="utf-8").read().splitlines()
out, found = [], False
for line in lines:
    if line.startswith("DATABASE_URL="):
        out.append(f"DATABASE_URL={url}"); found = True
    else:
        out.append(line)
if not found:
    out.append(f"DATABASE_URL={url}")
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY
    echo "Done. Previous .env saved as ${ENV_FILE}.pre-pg-$(date +%F). Run step 7."
}

step_7() {
    echo "=== [7/8] Start services and show status ==="
    sudo systemctl start homesite-backend homesite-gateway
    sleep 2
    sudo systemctl status homesite-backend homesite-gateway --no-pager | grep -E "Active:|Main PID:" || true
    echo
    echo "Smoke test in UI:"
    echo "  login → Dashboard → Stats → Events → save any Setting"
    echo
    echo "Tail logs: journalctl -u homesite-backend -f"
}

step_8() {
    echo "=== [8/8] Cleanup (run after 1-2 weeks of stable Postgres) ==="
    echo "This removes the dated pre-migration backup only."
    echo "$SOURCE_PATH itself is NOT deleted — remove it manually when fully confident."
    echo
    read -r -p "Delete pre-pg-* backups? [y/N] " ans
    if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
        rm -v "${SOURCE_PATH}.pre-pg-"* 2>/dev/null || echo "No backups to remove."
    else
        echo "Skipped."
    fi
}

step_rollback() {
    echo "=== Rollback to SQLite ==="
    echo "1. Stop services:"
    echo "     sudo systemctl stop homesite-backend homesite-gateway"
    echo "2. Edit $INSTALL_DIR/.env and set:"
    echo "     DATABASE_URL=$SOURCE_URL"
    echo "3. Start services:"
    echo "     sudo systemctl start homesite-backend homesite-gateway"
    echo
    echo "The source SQLite file was never modified by the migration script."
}

show_menu() {
    cat <<EOF

============================================================
 HomeSite v2 — SQLite → PostgreSQL migration
============================================================
  1)  Install Postgres + create role/db + asyncpg
  2)  Stop services + backup SQLite DB
  3)  Alembic upgrade head on empty Postgres
  4)  Dry-run migration (row counts)
  5)  Real data migration
  6)  Show how to switch .env (manual)
  7)  Start services + smoke status
  8)  Cleanup old backups (interactive)
  r)  Rollback instructions
  q)  Quit
------------------------------------------------------------
EOF
}

main() {
    while true; do
        show_menu
        read -r -p "Choose a step: " choice
        case "$choice" in
            1) step_1; pause ;;
            2) step_2; pause ;;
            3) step_3; pause ;;
            4) step_4; pause ;;
            5) step_5; pause ;;
            6) step_6; pause ;;
            7) step_7; pause ;;
            8) step_8; pause ;;
            r|R) step_rollback; pause ;;
            q|Q) echo "Bye."; exit 0 ;;
            *) echo "Unknown choice: $choice" ;;
        esac
    done
}

main
