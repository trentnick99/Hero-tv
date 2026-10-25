#!/usr/bin/env bash
# Waits for the HERO TV server, then launches Chromium fullscreen (kiosk).
[ -f /etc/hero-tv.env ] && set -a && . /etc/hero-tv.env && set +a
URL="http://127.0.0.1:${HEROTV_PORT:-8787}/"
until curl -fs "${URL}api/health" >/dev/null; do sleep 1; done
BIN=$(command -v chromium || command -v chromium-browser)
exec "$BIN" --kiosk --noerrdialogs --disable-infobars --no-first-run --autoplay-policy=no-user-gesture-required \
  --disable-session-crashed-bubble --disable-features=Translate --check-for-update-interval=31536000 \
  --user-data-dir="$HOME/.cache/hero-tv-chromium" "$URL"
