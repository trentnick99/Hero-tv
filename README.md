# HERO TV

A personal superhero TV network for Raspberry Pi 4/5 (Raspberry Pi OS 64-bit). Your own legally obtained media is
organised into virtual channels with a live guide, channel surfing, a searchable library and resume.
**No streams are included; HERO TV does not fetch, pirate or decrypt anything (no DRM bypass).**

**Windows 10/11:** extract the zip and double-click `HERO-TV.bat` - see `README_WINDOWS.txt`.

## Quick start (on the Pi)
```
unzip hero-tv.zip && cd hero-tv
sudo scripts/install.sh            # installs python3, ffmpeg, chromium; service + kiosk autostart
# copy your media into ~/hero-tv-media (see "Organising media"), then:
sudo systemctl restart hero-tv     # rescans; then reboot for the fullscreen kiosk
```
Set the Pi to boot to the desktop with auto-login (`sudo raspi-config` → System Options → Boot / Auto Login).
Try it first with fake clips: `scripts/make_sample_media.sh && sudo systemctl restart hero-tv`, or on any computer run `scripts/dev.sh`
and open http://127.0.0.1:8787.

## Using it
| Key | Action |
|---|---|
| ↑ / ↓, Page Up/Down | next / previous channel |
| 0-9 | type a channel number |
| Enter or G | guide (arrows move, Enter tunes, G/Esc closes) |
| L or / | library: type to search, Enter plays on demand and resumes where you stopped |
| I | info banner · M mute · F fullscreen · ←/→ volume · Esc leaves on-demand |

A TV remote works through HDMI-CEC (it arrives as arrow/Enter keys; channel buttons depend on your TV).

## Organising media
```
hero-tv-media/
  MCU/Some Movie (2008).mp4              <- top folder = franchise (matches channel rules)
  Marvel Television/Show Name/Show Name S01E02 Title.mp4   <- subfolder = series
  DC/Another Movie (1978).mp4
  DC/Another Movie (1978).hero.json      <- optional sidecar
```
Sidecar (`<same name>.hero.json`): `{"title":"","year":2008,"franchise":"","series":"","season":1,"episode":2,"tags":["action","comedy","classic","spider-verse"],"plot":"","order":10}`.
Without a sidecar, title/year/season/episode come from the filename. Play order is `order` if given, otherwise year, season, episode
(set `order` to get an in-universe chronological order). After changing files: `sudo systemctl restart hero-tv` or `python3 -m herotv scan`.

## Channels
Edit `config/channels.json` (id, number, name, `mode` = `sequential` or `shuffle`, `match`). `match` keys are AND-ed, values within a key are OR-ed:
`franchise`, `tags`, `series`, `year_min`, `year_max`; an empty `match` takes everything (Hero Marathon).
Add `"tags":["action"]` to sidecars to feed Action/Comedy/Classics/Spider-Verse.

## How showtimes work (and what they are not)
- Showtimes are **generated** by your Pi for your virtual channels; they are **not official broadcast listings**, and the UI says so.
- A file is only schedulable once ffprobe has measured its runtime (`verified`) and its codecs are browser-playable. A slot lasts
  `ceil(runtime)` seconds, and slots are back-to-back with no gaps.
- Schedules are stored in SQLite and extended 48 h ahead (every 5 min, and at start). Stored slots never change on restart; after downtime the
  channel is caught up exactly as if it had kept running (outages over 7 days resume at "now").
- Times are UTC epochs; the guide displays them in `HEROTV_TZ` (default: system timezone), so DST changes never alter a program's real length.
- Library changes rebuild only the not-yet-started part of the schedule; the airing program is kept unless its file is missing or fails.
- Playback errors are reported to the server: a missing file is dropped immediately, a file failing 3 times in 10 min is marked unplayable
  (re-evaluated at the next scan) and the channel moves on.

## Architecture
```
herotv/config.py     env config            herotv/scheduler.py  slots, rules, DST-safe queries
herotv/db.py         SQLite (WAL) schema   herotv/library.py    scan, ffprobe, sidecars
herotv/server.py     API + range streaming + static UI           web/index.html  fullscreen UI (no build step)
```
Python 3.9+ standard library only (zoneinfo, sqlite3, http.server): no pip packages. Playback is HTML5 video in Chromium kiosk mode, so the guide
and info overlays sit directly over the picture. Chromium decodes H.264 (MP4/MKV/MOV), VP9, AV1 and, on Pi 4/5, HEVC where hardware support exists;
audio must be AAC, MP3, Opus, Vorbis or FLAC. **AC-3/E-AC-3/DTS audio is not supported and those files are skipped.** Fix with:
`ffmpeg -i in.mkv -map 0:v -map 0:a:0 -c:v copy -c:a aac -b:a 192k out.mp4`.

Environment (`/etc/hero-tv.env`): `HEROTV_MEDIA`, `HEROTV_DB`, `HEROTV_TZ`, `HEROTV_HOST` (default `127.0.0.1`), `HEROTV_PORT`, `HEROTV_HORIZON_H`, `HEROTV_CHANNELS`.

**Library safety:** if the media folder is missing or empty at scan time (for example a USB/NAS drive that is not mounted yet), HERO TV keeps the existing library instead of wiping your channels, and the service waits for the media path's mount (`RequiresMountsFor`). Files that fail to play three times in 10 minutes are skipped until the next scan, which re-evaluates them.

**Network safety:** HERO TV's API is designed for a trusted, local kiosk and does not include user authentication. The server now refuses to bind to a non-loopback address unless `HEROTV_ALLOW_LAN=1` is explicitly set. Do not enable LAN binding on an untrusted network or forward port 8787 to the internet; other devices able to reach it could control playback and change saved progress. For remote access, use a properly authenticated VPN or reverse proxy rather than exposing this port directly. The API also validates request sizes and inputs, sends baseline browser security headers, accepts POSTs only as `application/json` (so other websites in your browser cannot trigger them) and rejects unexpected `Host` headers (DNS rebinding).

## Tests
`cd tests && python3 -m unittest -v` (35 tests: schedule continuity/boundaries, DST spring-forward/fall-back, half-hour zones, midnight crossing,
restart persistence, outage catch-up, rebuilds, shuffle determinism, library scan safety, API validation, range requests, CSRF/Host guards,
keep-alive framing, error recovery; the ffmpeg-based server tests are skipped if ffmpeg is missing).

## Verification status
Verified on a Linux x86-64 sandbox (Python 3.12 and 3.13, ffmpeg): all 35 tests, the scan → schedule → serve flow, and JS syntax. The guide layout fixes were made without a browser to render them.
**Not tested:** Raspberry Pi hardware (1080p decode on Pi 4 vs 5, thermals), Chromium rendering/key handling and autoplay with sound in kiosk,
HDMI-CEC remote, `install.sh`/systemd/labwc autostart on a real Pi OS image, long soak runs, very large libraries (thousands of files).

## Roadmap (phase 2)
Optional TMDB posters/plots (needs your own API key), mpv playback backend for formats Chromium can't play, auto-transcode of AC-3 audio, remote-friendly settings screen.

Troubleshooting: `journalctl -u hero-tv -f`; `python3 -m herotv schedule --hours 3` prints the generated lineup; "No programming" means no verified, playable file matches that channel.
