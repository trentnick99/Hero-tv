#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo"; exit 1; }
systemctl disable --now hero-tv.service 2>/dev/null || true
rm -f /etc/systemd/system/hero-tv.service /etc/hero-tv.env && systemctl daemon-reload
U="${SUDO_USER:-}"; H=$(getent passwd "$U" | cut -d: -f6)
sed -i '\#scripts/kiosk.sh#d' "$H/.config/labwc/autostart" "$H/.config/lxsession/LXDE-pi/autostart" 2>/dev/null || true
echo "Removed service and autostart. Media and database were left in place."
