"""Screengrab thumbnails: one JPEG per video, taken from the video itself with ffmpeg.

File names carry the media id, size and runtime, so a replaced video automatically gets a fresh grab and
nothing has to be deleted by hand. Generation runs in a background thread so the TV never waits for it.
"""
import os
import threading
import time

from . import tools

_NT = os.name == "nt"
# Windows: no popup window + below-normal priority, so grabbing frames never stutters the video you are watching.
_FLAGS = {"creationflags": 0x08000000 | 0x00004000} if _NT else {}
_failed = set()
_worker = None
_guard = threading.Lock()


def thumb_dir(cfg):
    stem = os.path.splitext(cfg.db_path)[0]
    return stem + "-thumbs"


def thumb_name(row):
    return f"{row['id']}-{int(row['size'] or 0)}-{int(row['runtime_s'] or 0)}.jpg"


def thumb_file(cfg, row):
    return os.path.join(thumb_dir(cfg), thumb_name(row))


def hero_name(row):
    return thumb_name(row)[:-4] + "-hero.jpg"


def hero_file(cfg, row):
    """A larger grab (1280 wide) for the big banner on Home. Made when first asked for, then kept."""
    return os.path.join(thumb_dir(cfg), hero_name(row))


_hero_lock = threading.Lock()


def make_hero(cfg, row):
    """The larger banner grab (one at a time, so two page loads never write the same file)."""
    with _hero_lock:
        return make_one(cfg, row, hero=True)


def _grab_time(runtime):
    # Skip studio logos and black intros: ~18% in for films, a bit later for short episodes.
    t = runtime * (0.18 if runtime > 600 else 0.3)
    return max(1.0, min(t, max(1.0, runtime - 2)))


def make_one(cfg, row, hero=False):
    """Create the thumbnail for one media row (hero=True: the larger banner grab). Returns True when a file exists afterwards."""
    ffmpeg = tools.find_tool("ffmpeg")
    out = hero_file(cfg, row) if hero else thumb_file(cfg, row)
    width = 1280 if hero else 640
    if os.path.isfile(out):
        return True
    if not ffmpeg or not os.path.isfile(row["path"]):
        return False
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".part.jpg"
    ss = f"{_grab_time(row['runtime_s'] or 0):.2f}"
    # "thumbnail" looks at ~48 frames and keeps the most representative one (avoids fades and black frames).
    for vf in (f"thumbnail=48,scale={width}:-2", f"scale={width}:-2"):
        try:
            r = tools.run([ffmpeg, "-v", "error", "-y", "-threads", "2", "-ss", ss, "-i", row["path"], "-an", "-sn",
                           "-vf", vf, "-frames:v", "1", "-q:v", "3" if hero else "5", tmp], timeout=180, **_FLAGS)
        except Exception:
            continue
        if r.returncode == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, out)
            return True
    if os.path.isfile(tmp):
        os.remove(tmp)
    return False


def generate_missing(cfg, connect, stop=None):
    """Make every missing thumbnail, programmes airing soonest first. Returns how many were created."""
    c = connect(cfg.db_path)
    try:
        rows = c.execute("SELECT id,path,size,runtime_s FROM media WHERE available=1 AND verified=1 AND playable=1").fetchall()
        soon = {r[0]: r[1] for r in c.execute(
            "SELECT media_id,MIN(start) FROM slots WHERE end>? GROUP BY media_id", (int(time.time()),))}
    finally:
        c.close()
    todo = [r for r in rows if not os.path.isfile(thumb_file(cfg, r)) and r["id"] not in _failed]
    todo.sort(key=lambda r: (r["id"] not in soon, soon.get(r["id"], 0)))
    made = 0
    for r in todo:
        if stop is not None and stop():
            break
        if make_one(cfg, r):
            made += 1
        else:
            _failed.add(r["id"])
    _prune(cfg, rows)
    return made


def _prune(cfg, rows):
    """Remove grabs of videos that were replaced (same id, different size/runtime)."""
    d = thumb_dir(cfg)
    if not os.path.isdir(d):
        return
    want = {thumb_name(r) for r in rows} | {hero_name(r) for r in rows}
    ids = {str(r["id"]) for r in rows}
    for f in os.listdir(d):
        if f.endswith(".jpg") and f not in want and f.split("-", 1)[0] in ids:
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                pass


def start_background(cfg, connect):
    """Kick off thumbnail generation unless it is already running."""
    global _worker
    with _guard:
        if _worker is not None and _worker.is_alive():
            return False
        _failed.clear()
        _worker = threading.Thread(target=lambda: generate_missing(cfg, connect), daemon=True, name="thumbnailer")
        _worker.start()
        return True
