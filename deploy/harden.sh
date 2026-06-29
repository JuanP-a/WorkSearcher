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

echo "=== Deploy user (recovery account) ==="
# Create a sudoer account BEFORE locking down root SSH, so we never lose
# access if the root key is lost. The script copies root's authorized_keys
# — the operator must have at least one valid key on the server.
if ! id deploy &>/dev/null; then
  useradd -m -s /bin/bash deploy
  mkdir -p /home/deploy/.ssh
  if [ -f /root/.ssh/authorized_keys ]; then
    cp /root/.ssh/authorized_keys /home/deploy/.ssh/
  else
    echo "WARNING: /root/.ssh/authorized_keys not found." >&2
    echo "Add your public key to /home/deploy/.ssh/authorized_keys manually" >&2
    echo "before disconnecting the current root session." >&2
  fi
  chown -R deploy:deploy /home/deploy/.ssh
  chmod 700 /home/deploy/.ssh
  [ -f /home/deploy/.ssh/authorized_keys ] && chmod 600 /home/deploy/.ssh/authorized_keys
  echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy
  chmod 440 /etc/sudoers.d/deploy
  echo "deploy user created with NOPASSWD sudo"
else
  echo "deploy user already exists — skipping"
fi

echo "=== SSH server hardening ==="
# 00- prefix ensures this drop-in loads before 50-cloud-init.conf in
# /etc/ssh/sshd_config.d/. sshd uses "first occurrence wins" for directives,
# so without the prefix our PasswordAuthentication no is silently overridden
# by cloud-init's PasswordAuthentication yes.
install -m 644 "$SCRIPT_DIR/sshd_config.d/worksearcher.conf" \
  /etc/ssh/sshd_config.d/00-worksearcher.conf
# Remove the old (un-prefixed) drop-in if present from a previous deploy
rm -f /etc/ssh/sshd_config.d/worksearcher.conf
sshd -t && systemctl reload ssh
echo "sshd_config.d/00-worksearcher.conf installed and reloaded"

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
