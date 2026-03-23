#!/bin/bash
# HomeSite v2 — Installation script for systemd deployment
# Usage: cd /srv/homesite && sudo bash deploy/install.sh

set -euo pipefail

INSTALL_DIR="/opt/homesite"
USER="homesite"

echo "=== HomeSite v2 Installation ==="

# Install Python 3.12 (Ubuntu 22.04 ships 3.10 — needs deadsnakes PPA)
if ! command -v python3.12 &>/dev/null; then
    echo "Installing Python 3.12..."
    add-apt-repository ppa:deadsnakes/ppa -y
    apt update -q
    apt install -y python3.12 python3.12-venv python3.12-distutils
fi

# Create user
if ! id "$USER" &>/dev/null; then
    useradd -r -m -d "$INSTALL_DIR" -s /bin/bash "$USER"
    echo "Created user: $USER"
fi

# Create directories
mkdir -p "$INSTALL_DIR"/{backend,frontend,data,logs}
chown "$USER:$USER" "$INSTALL_DIR/logs"

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
    cp backend/.env.example "$INSTALL_DIR/.env"
    # Enable log file rotation for production
    sed -i 's|^# LOG_FILE=.*|LOG_FILE=/opt/homesite/logs/backend.log|' "$INSTALL_DIR/.env"
    echo "IMPORTANT: Edit $INSTALL_DIR/.env with your settings!"
fi

# Set permissions
chown -R "$USER:$USER" "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"

# Install systemd units
cp deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload

# Generate self-signed TLS certificate (skip if already exists)
SSL_DIR="/etc/ssl/homesite"
if [ ! -f "$SSL_DIR/cert.pem" ]; then
    mkdir -p "$SSL_DIR"
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "$SSL_DIR/key.pem" \
        -out    "$SSL_DIR/cert.pem" \
        -subj "/CN=homesite.local/O=HomeSite/C=RU" \
        -addext "subjectAltName=DNS:homesite.local,IP:127.0.0.1"
    chmod 600 "$SSL_DIR/key.pem"
    echo "Self-signed certificate generated: $SSL_DIR/cert.pem (valid 10 years)"
    echo ""
    echo "To trust it on your device:"
    echo "  Linux:   sudo cp $SSL_DIR/cert.pem /usr/local/share/ca-certificates/homesite.crt && sudo update-ca-certificates"
    echo "  Windows: certlm.msc → Trusted Root Certification Authorities → Import $SSL_DIR/cert.pem"
    echo "  macOS:   sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $SSL_DIR/cert.pem"
    echo ""
else
    echo "TLS certificate already exists, skipping generation."
fi

# Install nginx config
cp deploy/nginx/homesite.conf /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/homesite.conf /etc/nginx/sites-enabled/
# Remove default site that conflicts on port 80
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# Enable and start services
systemctl enable --now homesite-backend homesite-gateway

echo ""
echo "=== Installation complete ==="
echo "Backend: http://127.0.0.1:8000/health"
echo "Frontend: https://homesite.local"
echo ""
echo "To switch to Let's Encrypt (public domain only):"
echo "  1. sudo apt install certbot python3-certbot-nginx"
echo "  2. sudo certbot --nginx -d <YOUR_DOMAIN>"
echo "  3. In deploy/nginx/homesite.conf replace ssl_certificate lines (see comments)"
echo ""
echo "Seed the database:"
echo "  sudo bash -c \"cd $INSTALL_DIR/backend && sudo -u $USER $INSTALL_DIR/venv/bin/python -m app.db.seed\""
echo ""
echo "Run Alembic migrations:"
echo "  sudo bash -c \"cd $INSTALL_DIR/backend && sudo -u $USER $INSTALL_DIR/venv/bin/alembic upgrade head\""
