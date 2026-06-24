#!/usr/bin/env bash
# WorkSearcher VPS setup — Ubuntu 22.04 LTS
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/worksearcher}
DB_DIR=/var/lib/worksearcher

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

echo "=== DB directory ==="
mkdir -p "$DB_DIR"
echo "Set DB_PATH=$DB_DIR/worksearcher.db in your .env"

echo "=== Log rotation ==="
cp deploy/logrotate.conf /etc/logrotate.d/worksearcher

echo ""
echo "=== Done. Next steps ==="
echo "1. cp .env.example .env && fill in META_* secrets"
echo "2. Set DB_PATH=$DB_DIR/worksearcher.db in .env"
echo "3. crontab -e  (see crontab.example)"
