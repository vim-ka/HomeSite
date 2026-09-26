#!/bin/bash
# HomeSite v2 — Update script (run after git pull)
# Usage: sudo bash deploy/update.sh
# Assumes repo is at /srv/homesite and installation is at /opt/homesite
#
# Order: stop services → back up DB → sync code → deps → migrations → start →
# health check. Migrations never run against a live DB without a backup.

set -euo pipefail

REPO_DIR="/srv/homesite"
INSTALL_DIR="/opt/homesite"
USER="homesite"
BACKUP_DIR="$INSTALL_DIR/backups"

cd "$REPO_DIR"
source deploy/lib_secrets.sh

echo "=== HomeSite v2 Update ==="

# Pull latest code (as the repo owner, not root)
REPO_OWNER="$(stat -c %U "$REPO_DIR")"
sudo -u "$REPO_OWNER" git pull
echo "Code updated."

# Build frontend first (unprivileged — npm lifecycle scripts must not run as root)
sudo -u "$REPO_OWNER" bash -c "cd '$REPO_DIR/frontend' && npm ci && npm run build"
echo "Frontend built."

# Secrets: never run with the shipped placeholders
ensure_secrets "$INSTALL_DIR/.env"

# Stop services so nothing writes to the DB while we back up and migrate
systemctl stop homesite-backend homesite-gateway
echo "Services stopped."

# Consistent SQLite backup (sqlite3 backup API — includes the WAL)
DB_URL="$(grep -E '^DATABASE_URL=' "$INSTALL_DIR/.env" | cut -d= -f2- || true)"
if [[ "$DB_URL" == sqlite* ]]; then
    DB_PATH="${DB_URL#*:///}"
    if [ -f "$DB_PATH" ]; then
        mkdir -p "$BACKUP_DIR"
        BACKUP_FILE="$BACKUP_DIR/pre-update-$(date -u +%Y%m%d-%H%M%S).db"
        "$INSTALL_DIR/venv/bin/python" - "$DB_PATH" "$BACKUP_FILE" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close(); src.close()
PY
        chown "$USER:$USER" "$BACKUP_FILE"
        echo "DB backed up to $BACKUP_FILE"
        # Keep the 10 most recent pre-update backups
        ls -1t "$BACKUP_DIR"/pre-update-*.db 2>/dev/null | tail -n +11 | xargs -r rm -f
    fi
else
    echo "PostgreSQL detected — take a pg_dump before updating if you have not already."
fi

# Sync backend code (delete files removed from the repo; keep local data)
rsync -a --delete \
    --exclude '.env' --exclude '*.db' --exclude '*.db-*' --exclude '__pycache__' \
    --exclude '.venv' --exclude 'logs/' --exclude 'backups/' \
    backend/ "$INSTALL_DIR/backend/"

# Update Python dependencies
"$INSTALL_DIR/venv/bin/pip" install --no-cache-dir "$INSTALL_DIR/backend"
echo "Backend dependencies updated."

# Frontend assets
rsync -a --delete frontend/dist/ "$INSTALL_DIR/frontend/dist/"

# Fix permissions
chown -R "$USER:$USER" "$INSTALL_DIR"

# Apply DB migrations (services are stopped, backup taken)
cd "$INSTALL_DIR/backend"
sudo -u "$USER" "$INSTALL_DIR/venv/bin/alembic" upgrade head
echo "Migrations applied."
cd "$REPO_DIR"

# Update systemd units and nginx config (in case they changed)
cp deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
cp deploy/nginx/homesite.conf /etc/nginx/sites-available/
nginx -t && systemctl reload nginx

# Start services and verify
systemctl start homesite-backend homesite-gateway
echo "Services started, waiting for health check..."
for i in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/health/ready >/dev/null 2>&1; then
        echo "Backend is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: backend did not become ready. Check: journalctl -u homesite-backend -n 100"
        exit 1
    fi
    sleep 2
done
systemctl is-active --quiet homesite-gateway || {
    echo "ERROR: gateway is not running. Check: journalctl -u homesite-gateway -n 100"
    exit 1
}

echo ""
echo "=== Update complete. $(date) ==="
