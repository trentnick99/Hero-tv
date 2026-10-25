#!/usr/bin/env bash
# HERO TV installer for Raspberry Pi OS Bookworm 64-bit.  Usage: sudo scripts/install.sh [media_dir]
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo: sudo scripts/install.sh"; exit 1; }
U="${SUDO_USER:-}"; [ -n "$U" ] && [ "$U" != root ] || { echo "Run via sudo from your normal user account"; exit 1; }
H=$(getent passwd "$U" | cut -d: -f6); APP=$(cd "$(dirname "$0")/.." && pwd); MEDIA="${1:-$H/hero-tv-media}"

apt-get update
apt-get install -y python3 ffmpeg tzdata curl
apt-get install -y chromium || apt-get install -y chromium-browser

sudo -u "$U" mkdir -p "$MEDIA" "$APP/data"
chmod +x "$APP"/scripts/*.sh

cat > /etc/hero-tv.env <<ENV
HEROTV_MEDIA=$MEDIA
HEROTV_DB=$APP/data/herotv.sqlite3
HEROTV_TZ=$(cat /etc/timezone 2>/dev/null || echo UTC)
HEROTV_PORT=8787
ENV

cat > /etc/systemd/system/hero-tv.service <<UNIT
[Unit]
Description=HERO TV server
After=local-fs.target time-sync.target
RequiresMountsFor=$MEDIA
[Service]
NoNewPrivileges=true
PrivateTmp=true
User=$U
WorkingDirectory=$APP
EnvironmentFile=/etc/hero-tv.env
ExecStart=/usr/bin/python3 -m herotv serve --scan
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now hero-tv.service

# Kiosk autostart for the desktop session (Bookworm uses labwc; older images use LXDE on X11).
add_line() { # file line
  sudo -u "$U" mkdir -p "$(dirname "$1")"
  grep -qsF "$2" "$1" || printf '%s\n' "$2" | sudo -u "$U" tee -a "$1" >/dev/null
}
LAB="$H/.config/labwc/autostart"
# a user autostart file replaces the system one, so seed it with the stock desktop entries first
if [ ! -f "$LAB" ] && [ -f /etc/xdg/labwc/autostart ]; then
  sudo -u "$U" mkdir -p "$(dirname "$LAB")"; sudo -u "$U" cp /etc/xdg/labwc/autostart "$LAB"
fi
add_line "$LAB" "$APP/scripts/kiosk.sh &"
add_line "$H/.config/lxsession/LXDE-pi/autostart" "@$APP/scripts/kiosk.sh"
raspi-config nonint do_blanking 1 2>/dev/null || true   # keep the screen awake

echo
echo "HERO TV installed. Media folder: $MEDIA   (see README: one folder per franchise)"
echo "Add media, then: sudo systemctl restart hero-tv     Reboot to start the fullscreen kiosk."
echo "Make sure the Pi boots to the desktop with auto-login (raspi-config > System Options > Boot / Auto Login)."
