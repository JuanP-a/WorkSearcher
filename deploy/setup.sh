#!/usr/bin/env bash
# WorkSearcher VPS setup — Ubuntu 22.04 LTS
# Run as root: sudo bash deploy/setup.sh
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/worksearcher}
DB_DIR=/var/lib/worksearcher
SERVICE_USER=worksearcher

echo "=== Service user ==="
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /sbin/nologin "$SERVICE_USER"
    echo "Created user: $SERVICE_USER"
else
    echo "User $SERVICE_USER already exists"
fi

echo "=== System dependencies ==="
apt-get update -qq
apt-get install -y curl python3-pip

echo "=== uv ==="
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "=== Python dependencies ==="
cd "$APP_DIR"
uv venv
uv pip install -r requirements.lock

echo "=== Playwright (browser + system libs) ==="
uv run playwright install chromium
uv run playwright install-deps chromium

echo "=== Permissions: app directory ==="
chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"
chmod 750 "$APP_DIR"

echo "=== Permissions: .env (secrets) ==="
if [[ -f "$APP_DIR/.env" ]]; then
    chown "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo ".env locked to $SERVICE_USER only"
else
    echo "WARNING: $APP_DIR/.env not found — create it before running the pipeline"
    echo "  cp $APP_DIR/.env.example $APP_DIR/.env"
    echo "  fill in META_* secrets, set DB_PATH=$DB_DIR/worksearcher.db"
    echo "  chown $SERVICE_USER:$SERVICE_USER $APP_DIR/.env && chmod 600 $APP_DIR/.env"
fi

echo "=== DB directory ==="
mkdir -p "$DB_DIR"
chown "$SERVICE_USER":"$SERVICE_USER" "$DB_DIR"
chmod 750 "$DB_DIR"

echo "=== Log rotation ==="
cp deploy/logrotate.conf /etc/logrotate.d/worksearcher

echo ""
echo "=== Done. Next steps ==="
echo "1. If .env not created yet:"
echo "     cp $APP_DIR/.env.example $APP_DIR/.env"
echo "     \$EDITOR $APP_DIR/.env   # fill META_* + set DB_PATH=$DB_DIR/worksearcher.db"
echo "     chown $SERVICE_USER:$SERVICE_USER $APP_DIR/.env && chmod 600 $APP_DIR/.env"
echo "2. Install cron job as $SERVICE_USER:"
echo "     sudo -u $SERVICE_USER crontab -e   # paste line from crontab.example"
