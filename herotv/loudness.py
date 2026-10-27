"""Even volume: every video's loudness is measured once (the EBU R128 "integrated loudness" TV stations use) in the
background at low priority, and the TV screen and phones turn quiet videos up and loud ones down, so a film, a
cartoon short and the next episode all play at about the same volume. Night mode aims a little quieter and evens out
loud bangs too. (The Roku app cannot change a video's volume - Roku TVs have their own "volume leveling" setting.)"""
import os
import re
import subprocess
import threading
import time

TARGET_LUFS = -20.0
NIGHT_LUFS = -24.0
MAX_UP_DB, MAX_DOWN_DB = 9.0, 12.0
SAMPLE_S = 240                       # longer videos: four minutes from four places are enough
SCHEMA = "CREATE TABLE IF NOT EXISTS loudness(media_id INTEGER PRIMARY KEY, lufs REAL, checked INTEGER DEFAULT 0)"
_state = {"running": False}
_I = re.compile(r"^\s*I:\s*(-?[\d.]+)\s*LUFS", re.M)


def ensure(conn):
    conn.execute(SCHEMA)


def measure(exe, path, runtime=0, run=None):
    """Integrated loudness (LUFS) of a video, or None. Long videos are sampled at four places."""
    from . import tools
    flags = dict(tools.HIDE)
    if os.name == "nt":
        flags["creationflags"] = flags.get("creationflags", 0) | 0x00004000    # BELOW_NORMAL_PRIORITY_CLASS
    if runtime and runtime > 4 * SAMPLE_S:
        part = SAMPLE_S / 4
        ins, labels = [], []
        for k, f in enumerate((0.15, 0.4, 0.6, 0.85)):
            ins += ["-ss", f"{runtime * f:.1f}", "-t", f"{part:.1f}", "-i", path]
            labels.append(f"[{k}:a:0]")
        graph = "".join(labels) + f"concat=n=4:v=0:a=1,ebur128=framelog=quiet"
        cmd = [exe, "-hide_banner", "-nostdin", "-vn"] + ins + ["-filter_complex", graph, "-f", "null", "-"]
    else:
        cmd = [exe, "-hide_banner", "-nostdin", "-i", path, "-vn", "-map", "0:a:0", "-af", "ebur128=framelog=quiet",
               "-f", "null", "-"]
    try:
        r = (run or subprocess.run)(cmd, capture_output=True, text=True, timeout=900, **flags)
    except (OSError, subprocess.SubprocessError):
        return None
    found = _I.findall(r.stderr or "")
    if not found:
        return None
    v = float(found[-1])
    return v if -70 < v < 0 else None


def gain_db(lufs, night=False):
    """How much to turn a video up (+) or down (-)."""
    if lufs is None:
        return 0.0
    g = (NIGHT_LUFS if night else TARGET_LUFS) - lufs
    return round(max(-MAX_DOWN_DB, min(MAX_UP_DB, g)), 1)


def for_media(conn, mid):
    ensure(conn)
    r = conn.execute("SELECT lufs FROM loudness WHERE media_id=?", (mid,)).fetchone()
    return r["lufs"] if r and r["lufs"] is not None else None


def todo(conn, limit=4):
    ensure(conn)
    return conn.execute("SELECT m.* FROM media m LEFT JOIN loudness l ON l.media_id=m.id WHERE m.available=1 "
                        "AND m.verified=1 AND m.playable=1 AND l.media_id IS NULL ORDER BY m.added DESC, m.id LIMIT ?",
                        (limit,)).fetchall()


def run_once(conn, exe, limit=4, run=None, now=None):
    n = 0
    for m in todo(conn, limit):
        v = measure(exe, m["path"], m["runtime_s"] or 0, run) if os.path.isfile(m["path"] or "") else None
        conn.execute("INSERT OR REPLACE INTO loudness(media_id,lufs,checked) VALUES(?,?,?)", (m["id"], v, int(now or time.time())))
        conn.commit()
        n += 1
    return n


def status(conn):
    ensure(conn)
    total = conn.execute("SELECT COUNT(*) FROM media WHERE available=1 AND verified=1 AND playable=1").fetchone()[0]
    done = conn.execute("SELECT COUNT(*) FROM loudness l JOIN media m ON m.id=l.media_id WHERE m.available=1 "
                        "AND m.verified=1 AND m.playable=1").fetchone()[0]
    return {"videos": total, "measured": min(done, total), "running": _state["running"]}


def start_background(cfg, connect, every=5, idle=900):
    from . import tools

    def loop():
        time.sleep(180)
        while True:
            pause = idle
            try:
                exe = tools.find_tool("ffmpeg")
                if exe:
                    c = connect(cfg.db_path)
                    try:
                        _state["running"] = True
                        if run_once(c, exe):
                            pause = every
                    finally:
                        _state["running"] = False
                        c.close()
            except Exception:
                pass
            time.sleep(pause)
    threading.Thread(target=loop, name="herotv-loudness", daemon=True).start()
