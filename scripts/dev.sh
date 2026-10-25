#!/usr/bin/env bash
# Try HERO TV on any computer: generates sample clips, then serves on http://127.0.0.1:8787
cd "$(dirname "$0")/.."
export HEROTV_MEDIA="${HEROTV_MEDIA:-$PWD/data/sample-media}" HEROTV_DB="${HEROTV_DB:-$PWD/data/dev.sqlite3}"
[ -d "$HEROTV_MEDIA" ] || scripts/make_sample_media.sh "$HEROTV_MEDIA"
exec python3 -m herotv serve --scan
