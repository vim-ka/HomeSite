#!/bin/bash
# HomeSite v2 — Update script (run after git pull)
# Usage: sudo bash deploy/update.sh
# Assumes repo is at /srv/homesite and installation is at /opt/homesite

set -euo pipefail

REPO_DIR="/srv/homesite"
INSTALL_DIR="/opt/homesite"
USER="homesite"

echo "=== HomeSite v2 Update ==="

# Pull latest code
cd "$REPO_DIR"
git pull
echo "Code updated."

# Update backend files
cp -r backend/* "$INSTALL_DIR/backend/"

# Update Python dependencies
"$INSTALL_DIR/venv/bin/pip" install --no-cache-dir "$INSTALL_DIR/backend"
echo "Backend dependencies updated."

# Apply DB migrations
cd "$INSTALL_DIR/backend"
sudo -u "$USER" "$INSTALL_DIR/venv/bin/alembic" upgrade head
echo "Migrations applied."
cd "$REPO_DIR"

# Rebuild frontend
cd frontend
npm ci
npm run build
rm -rf "$INSTALL_DIR/frontend/dist"
cp -r dist "$INSTALL_DIR/frontend/dist"
cd ..
echo "Frontend rebuilt."

# Fix permissions
chown -R "$USER:$USER" "$INSTALL_DIR"

# Update systemd units and nginx config (in case they changed)
cp deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
cp deploy/nginx/homesite.conf /etc/nginx/sites-available/
nginx -t && systemctl reload nginx

# Restart services
systemctl restart homesite-backend homesite-gateway
echo "Services restarted."

echo ""
echo "=== Update complete. $(date) ==="
echo "Backend: http://127.0.0.1:8000/health"
echo "Frontend: https://homesite.local"
