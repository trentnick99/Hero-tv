"""Generates ORIGINAL synthetic demo clips (ffmpeg test pattern + tone) so HERO TV can be tried with no media.

Cross-platform replacement for scripts/make_sample_media.sh (which needs bash).
"""
import json
import os

from . import tools

# (path under target dir, seconds, tone Hz, sidecar metadata) - all fictional.
SAMPLES = [
    ("MCU/Captain Lumen (2008)", 31, 330, {"tags": ["action"], "plot": "A test pilot becomes a beacon (fictional sample)."}),
    ("MCU/Captain Lumen 2 (2011)", 27, 360, {"tags": ["action"], "plot": "The beacon returns."}),
    ("MCU/Lumen Rising (2014)", 36, 390, {"tags": ["action", "comedy"], "plot": "Sample film."}),
    ("Marvel Television/Night Watch/Night Watch S01E01 Pilot", 23, 420, {"title": "Pilot", "series": "Night Watch", "season": 1, "episode": 1, "year": 2016}),
    ("Marvel Television/Night Watch/Night Watch S01E02 Patrol", 25, 440, {"title": "Patrol", "series": "Night Watch", "season": 1, "episode": 2, "year": 2016}),
    ("Marvel Animation/Pocket Titans S01E01", 17, 470, {"title": "Small Heroes", "series": "Pocket Titans", "season": 1, "episode": 1, "year": 2021, "tags": ["comedy"]}),
    ("Spider-Verse/Webline (2018)", 33, 500, {"tags": ["spider-verse", "action"]}),
    ("X-Men/Mutant Academy (1999)", 29, 530, {"tags": ["classic"]}),
    ("DC/Dusk Knight (2005)", 35, 560, {"tags": ["action"]}),
    ("DC/Comet Boy (1978)", 21, 590, {"tags": ["classic", "comedy"]}),
    ("Classics/Flash Mercury Serial (1940)", 19, 620, {"franchise": "Classics", "tags": ["classic"]}),
]


def make(target, log=print):
    """Create the sample library under `target`. Returns the number of clips written."""
    ffmpeg = tools.find_tool("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg was not found")
    made = 0
    looks = ["gradients=size=640x360:rate=24:speed=0.03", "mandelbrot=size=640x360:rate=24", "testsrc2=size=640x360:rate=24"]
    for n, (rel, secs, hz, meta) in enumerate(SAMPLES):
        out = os.path.join(target, *rel.split("/")) + ".mp4"
        side = out[:-4] + ".hero.json"
        if os.path.isfile(out) and os.path.isfile(side):
            continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        for look in (looks[n % 2], looks[2]):          # varied pictures; plain test pattern as the safe fallback
            r = tools.run([ffmpeg, "-v", "error", "-y",
                           "-f", "lavfi", "-i", look,
                           "-f", "lavfi", "-i", f"sine=frequency={hz}:sample_rate=44100",
                           "-t", str(secs), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", out], timeout=300)
            if r.returncode == 0 and os.path.isfile(out):
                break
        if r.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError("ffmpeg could not create a sample clip: " + (r.stderr or "").strip()[-300:])
        with open(side, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
        made += 1
        log(f"  made {rel}.mp4")
    return made
