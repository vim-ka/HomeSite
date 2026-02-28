#!/bin/bash
# HomeSite v2 — Installation script for systemd deployment
# Usage: sudo bash install.sh

set -euo pipefail

INSTALL_DIR="/opt/homesite"
USER="homesite"

echo "=== HomeSite v2 Installation ==="

# Create user
if ! id "$USER" &>/dev/null; then
    useradd -r -m -d "$INSTALL_DIR" -s /bin/bash "$USER"
    echo "Created user: $USER"
fi

# Create directories
mkdir -p "$INSTALL_DIR"/{backend,frontend,data,logs}

# Copy backend
cp -r backend/* "$INSTALL_DIR/backend/"

# Setup Python venv
python3.12 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --no-cache-dir "$INSTALL_DIR/backend"

# Build frontend
cd frontend
npm ci
npm run build
cp -r dist "$INSTALL_DIR/frontend/dist"
cd ..

# Copy .env (if not exists)
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp .env.example "$INSTALL_DIR/.env"
    echo "IMPORTANT: Edit $INSTALL_DIR/.env with your settings!"
fi

# Set permissions
chown -R "$USER:$USER" "$INSTALL_DIR"

# Install systemd units
cp deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload

# Install nginx config
cp deploy/nginx/homesite.conf /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/homesite.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Enable and start services
systemctl enable --now homesite-backend homesite-gateway

echo ""
echo "=== Installation complete ==="
echo "Backend: http://127.0.0.1:8000/health"
echo "Frontend: http://homesite.local"
echo ""
echo "Seed the database:"
echo "  sudo -u $USER $INSTALL_DIR/venv/bin/python -m app.db.seed"
echo ""
echo "Run Alembic migrations:"
echo "  cd $INSTALL_DIR/backend && sudo -u $USER $INSTALL_DIR/venv/bin/alembic upgrade head"
