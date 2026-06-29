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
    # Install to system-wide path so all users (including worksearcher in cron) can reach it
    install -m 755 "$HOME/.local/bin/uv" /usr/local/bin/uv
fi
# Ensure uv is reachable for the rest of this script
export PATH="/usr/local/bin:$PATH"

echo "=== Python dependencies ==="
cd "$APP_DIR"
uv venv
# PyPI packages: all hashes verified against requirements.hashes.lock
uv pip install --require-hashes -r requirements.hashes.lock
# jobspy from pinned git SHA — VCS URLs cannot carry pip hashes by design
uv pip install "git+https://github.com/Bunsly/JobSpy.git@fda080a373e8226f3fd60635323f5da9af9892b1#egg=python-jobspy"

echo "=== Permissions: app directory (before playwright) ==="
# Chown BEFORE playwright install so the venv is owned by the service user
# and the next step (playwright install) can run as that user. Playwright
# writes the browser binary to $HOME/.cache/ms-playwright/, which must be
# in the service user's writable home, not /root/.cache/.
chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"
chmod 750 "$APP_DIR"

echo "=== Playwright (browser + system libs) ==="
# Browser binary must be installed as the service user, NOT root. Otherwise
# the binary lands in /root/.cache/ms-playwright/ and the cron-launched
# pipeline fails at runtime with:
#   "Executable doesn't exist at /home/worksearcher/.cache/ms-playwright/..."
# The worksearcher user has /sbin/nologin as its shell, but `sudo -u` with
# an explicit command bypasses that.
sudo -u "$SERVICE_USER" bash -c "cd '$APP_DIR' && '$APP_DIR/.venv/bin/playwright' install chromium"
# install-deps needs root (it uses apt to install system libraries).
uv run playwright install-deps chromium

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
