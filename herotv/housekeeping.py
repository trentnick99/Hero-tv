"""Tidy HERO TV's OWN leftovers. It never touches a video, a folder of yours or a ready copy that is in use:
  - old rows of the channel schedule (days that are over; the newest row of each channel and block stays, so the order goes on)
  - the subtitle cache (made again when a video is played)
  - update files already installed (.update-download)
  - the old log file (herotv.old.log)
The database is then compacted so the freed room is really given back."""
import os
import shutil
import time
from pathlib import Path

KEEP_DAYS = 14                      # past schedule rows younger than this stay (Recently-played style lookups, reminders)
UPDATE_QUIET_S = 3600               # an update downloaded in the last hour may still be in use

SLOTS_OLD = ("FROM slots WHERE end < :cut "
             "AND EXISTS (SELECT 1 FROM slots n WHERE n.channel_id=slots.channel_id AND n.start>slots.start) "
             "AND EXISTS (SELECT 1 FROM slots n WHERE n.channel_id=slots.channel_id AND COALESCE(n.pl,'')=COALESCE(slots.pl,'') AND n.start>slots.start)")


def _size(path):
    total = 0
    p = Path(path)
    if p.is_file():
        return p.stat().st_size
    for x in p.rglob("*"):
        try:
            if x.is_file():
                total += x.stat().st_size
        except OSError:
            pass
    return total


def _targets(cfg, root, data_dir):
    subs = Path(os.path.splitext(str(cfg.db_path))[0] + "-subs")
    upd = Path(root) / ".update-download"
    oldlog = Path(data_dir) / "herotv.old.log"
    return subs, upd, oldlog


def _update_idle(upd):
    try:
        return all(time.time() - x.stat().st_mtime > UPDATE_QUIET_S for x in upd.rglob("*") if x.is_file())
    except OSError:
        return False


def report(conn, cfg, root, data_dir, now=None):
    now = now or time.time()
    subs, upd, oldlog = _targets(cfg, root, data_dir)
    cut = int(now - KEEP_DAYS * 86400)
    n = conn.execute("SELECT COUNT(*) " + SLOTS_OLD, {"cut": cut}).fetchone()[0]
    items = [{"id": "slots", "title": "Old schedule", "count": n, "bytes": n * 60,
              "text": f"{n:,} rows of channel schedule from days that are over." if n else "No old schedule to remove."},
             {"id": "subs", "title": "Subtitle cache", "count": len(list(subs.glob("*"))) if subs.is_dir() else 0,
              "bytes": _size(subs) if subs.is_dir() else 0, "text": "Subtitles made for playback; they are made again when needed."},
             {"id": "updates", "title": "Installed update files", "count": 1 if upd.is_dir() else 0,
              "bytes": _size(upd) if upd.is_dir() and _update_idle(upd) else 0, "text": "The downloaded update files, after the update is in."},
             {"id": "log", "title": "Old log", "count": 1 if oldlog.is_file() else 0, "bytes": _size(oldlog) if oldlog.is_file() else 0,
              "text": "The previous log file."}]
    for i in items:
        i["can"] = bool(i["count"]) and (i["id"] != "updates" or i["bytes"] > 0 or not upd.is_dir())
    return {"items": items, "bytes": sum(i["bytes"] for i in items), "keeps": "Your videos, favorites, resume points and settings are never touched."}


def clean(conn, cfg, root, data_dir, what, now=None):
    """Remove the chosen kinds. Returns {"freed": bytes, "done": [ids]}."""
    now = now or time.time()
    subs, upd, oldlog = _targets(cfg, root, data_dir)
    freed, done = 0, []
    if "slots" in what:
        cut = int(now - KEEP_DAYS * 86400)
        cur = conn.execute("DELETE " + SLOTS_OLD, {"cut": cut})
        conn.commit()
        freed += (cur.rowcount or 0) * 60
        done.append("slots")
        try:
            conn.execute("VACUUM")                       # give the room back to the disk (skipped when the database is busy)
        except Exception:
            pass
    if "subs" in what and subs.is_dir():
        freed += _size(subs)
        shutil.rmtree(subs, ignore_errors=True)
        done.append("subs")
    if "updates" in what and upd.is_dir() and _update_idle(upd):
        freed += _size(upd)
        shutil.rmtree(upd, ignore_errors=True)
        done.append("updates")
    if "log" in what and oldlog.is_file():
        freed += _size(oldlog)
        try:
            oldlog.unlink()
            done.append("log")
        except OSError:
            pass
    return {"freed": freed, "done": done}
