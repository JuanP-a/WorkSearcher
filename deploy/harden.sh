#!/usr/bin/env bash
# WorkSearcher VPS hardening — Ubuntu 22.04 LTS
# Idempotent: safe to re-run.
# Run as root: sudo bash deploy/harden.sh

# Verify script is run as root
if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: must run as root (sudo bash deploy/harden.sh)" >&2
  exit 1
fi

set -euo pipefail

# ---------------------------------------------------------------------------
# Detect script dir (works when called from anywhere)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== SSH server hardening ==="
install -m 644 "$SCRIPT_DIR/sshd_config.d/worksearcher.conf" \
  /etc/ssh/sshd_config.d/worksearcher.conf
# sshd's Include requires *.conf suffix; idempotent (overwrites cleanly)
sshd -t && systemctl reload ssh
echo "sshd_config.d/worksearcher.conf installed and reloaded"

echo "=== UFW firewall ==="
if ! command -v ufw &>/dev/null; then
  apt-get install -y ufw
fi
# Default policy: deny inbound, allow outbound
ufw default deny incoming
ufw default allow outgoing
# Allow SSH on default port 22 (port change is a separate concern)
ufw allow OpenSSH
# Enable non-interactively (returns immediately if already active)
ufw --force enable
ufw status verbose

echo "=== fail2ban ==="
if ! command -v fail2ban-client &>/dev/null; then
  apt-get install -y fail2ban
fi
# Drop-in config: ban after 3 failed attempts for 1h
cat > /etc/fail2ban/jail.d/worksearcher.conf <<'JAIL'
[sshd]
enabled = true
port = ssh
maxretry = 3
findtime = 600
bantime = 3600
JAIL
systemctl enable --now fail2ban
systemctl restart fail2ban
echo "fail2ban active for sshd: 3 retries / 10 min → 1h ban"

echo "=== Unattended security upgrades ==="
if ! dpkg -s unattended-upgrades &>/dev/null; then
  apt-get install -y unattended-upgrades
fi
# Enable periodic + auto-apply security updates
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'APT'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
APT::Unattended-Upgrade::Allowed-Origins {
  "${distro_id}:${distro_codename}-security";
};
APT::Unattended-Upgrade::AutoFixInterruptedDpkg "true";
APT::Unattended-Upgrade::MinimalSteps "true";
APT::Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
APT::Unattended-Upgrade::Remove-Unused-Dependencies "true";
APT::Unattended-Upgrade::Automatic-Reboot "false";
APT
systemctl enable --now unattended-upgrades
echo "unattended-upgrades enabled (security patches auto-applied)"

echo ""
echo "=== Done. Verify ==="
echo "  - sshd config:  sshd -T | grep -E 'PermitRootLogin|PasswordAuth'"
echo "  - firewall:     ufw status"
echo "  - fail2ban:     fail2ban-client status sshd"
echo "  - cron already: sudo -u worksearcher crontab -l"
echo ""
echo "IMPORTANT: open a SECOND SSH session to confirm access before closing this one"
