# HERO TV revision notes

This revision preserves the original architecture and channel configuration while adding defensive server-side handling.

## Changes
- Refuses non-loopback server binding unless `HEROTV_ALLOW_LAN=1` is explicitly set. This is an opt-in warning barrier, not authentication; do not expose port 8787 to the internet.
- Adds baseline browser security headers and `nosniff` on JSON responses.
- Caps JSON request bodies at 64 KiB and rejects malformed JSON, non-object bodies, and invalid content lengths with HTTP 400.
- Validates guide time ranges, dates, media IDs, and playback-progress values; unknown media progress updates return 404.
- Tightens HTTP byte-range handling, including invalid and multi-range requests.
- Adds regression tests for malformed inputs and security headers.

## Validation
- `python3 -m compileall -q herotv` passed.
- `python3 -m unittest -q` passed: 27 tests.
- Some pre-existing tests/scheduler paths emit `ResourceWarning` for unclosed SQLite connections or test fixture files. These warnings did not fail the suite and are still worth cleaning up in a future maintenance pass.
- Raspberry Pi hardware, Chromium kiosk playback, HDMI-CEC, and long-duration playback remain unverified in this environment.
