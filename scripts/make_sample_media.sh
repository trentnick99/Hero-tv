#!/usr/bin/env bash
# Generates ORIGINAL synthetic clips (ffmpeg test patterns + tone) with sidecar metadata for fictional heroes.
# Usage: scripts/make_sample_media.sh [target_dir]   (needs ffmpeg with libx264 + aac)
set -euo pipefail
D="${1:-${HEROTV_MEDIA:-$HOME/hero-tv-media}}"
mk() { # path-under-D  seconds  freq  json
  local f="$D/$1.mp4"; mkdir -p "$(dirname "$f")"
  ffmpeg -v error -y -f lavfi -i "testsrc2=size=640x360:rate=24,drawtext=text='$(basename "$1")':fontcolor=white:fontsize=22:x=20:y=20" \
    -f lavfi -i "sine=frequency=$3:sample_rate=44100" -t "$2" -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 64k \
    -movflags +faststart "$f" 2>/dev/null || ffmpeg -v error -y -f lavfi -i "testsrc2=size=640x360:rate=24" \
    -f lavfi -i "sine=frequency=$3:sample_rate=44100" -t "$2" -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 64k "$f"
  echo "$4" > "${f%.mp4}.hero.json"
}
mk "MCU/Captain Lumen (2008)" 31 330 '{"tags":["action"],"plot":"A test pilot becomes a beacon (fictional sample)."}'
mk "MCU/Captain Lumen 2 (2011)" 27 360 '{"tags":["action"],"plot":"The beacon returns."}'
mk "MCU/Lumen Rising (2014)" 36 390 '{"tags":["action","comedy"],"plot":"Sample film."}'
mk "Marvel Television/Night Watch/Night Watch S01E01 Pilot" 23 420 '{"title":"Pilot","series":"Night Watch","season":1,"episode":1,"year":2016}'
mk "Marvel Television/Night Watch/Night Watch S01E02 Patrol" 25 440 '{"title":"Patrol","series":"Night Watch","season":1,"episode":2,"year":2016}'
mk "Marvel Animation/Pocket Titans S01E01" 17 470 '{"title":"Small Heroes","series":"Pocket Titans","season":1,"episode":1,"year":2021,"tags":["comedy"]}'
mk "Spider-Verse/Webline (2018)" 33 500 '{"tags":["spider-verse","action"]}'
mk "X-Men/Mutant Academy (1999)" 29 530 '{"tags":["classic"]}'
mk "DC/Dusk Knight (2005)" 35 560 '{"tags":["action"]}'
mk "DC/Comet Boy (1978)" 21 590 '{"tags":["classic","comedy"]}'
mk "Classics/Flash Mercury Serial (1940)" 19 620 '{"franchise":"Classics","tags":["classic"]}'
echo "Sample media written to $D"
