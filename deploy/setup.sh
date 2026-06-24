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
    UV_VERSION="0.11.24"
    UV_INSTALLER_SHA256="b3c113bcb8b5f361805bc2283cb1bcc8f3e07b5f0387a12e4f6e71281f7ec120"
    curl -LsSf "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-installer.sh" \
        -o /tmp/uv-installer.sh
    echo "${UV_INSTALLER_SHA256}  /tmp/uv-installer.sh" | sha256sum -c -
    sh /tmp/uv-installer.sh
    rm /tmp/uv-installer.sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "=== Python dependencies ==="
cd "$APP_DIR"
uv venv
# PyPI packages: all hashes verified against requirements.hashes.lock
uv pip install --require-hashes -r requirements.hashes.lock
# jobspy from pinned git SHA — VCS URLs cannot carry pip hashes by design
uv pip install "git+https://github.com/Bunsly/JobSpy.git@fda080a373e8226f3fd60635323f5da9af9892b1#egg=python-jobspy"

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
