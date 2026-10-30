"""Ready-to-play copies: videos the PC's TV screen cannot play as they are (Dolby/DTS sound, H.265 inside an .mkv, ...)
get a copy in a hidden '.prepared' folder inside your media folder, made by HERO TV by itself in the background.

- The picture is copied untouched (no quality loss, fast); only the sound is converted to AAC when it has to be.
- Your own files are never changed, moved or renamed. Deleting the .prepared folder is always safe: copies are made again.
- A video counts as playable on the PC once its copy is ready, so it joins the channels then.
- A Roku TV does not need the copy: it plays the original (Dolby, H.265 in .mkv ...) straight away, and uses the copy
  only as a fallback if it refuses the original (see delivery / alt).
- Pictures that need a real conversion (10-bit H.264 ...) are not touched here - that is what Fix is for."""
import os
import re
import shutil
import threading
import time
from pathlib import Path

from . import library, tools, work

FOLDER = ".prepared"
_OURS = re.compile(r"\d+-\d+\.(?:mp4|part)")             # the only file names this module ever makes (or deletes)
RETRY_FAILED_S = 7 * 86400
SPARE_BYTES = 2 * 1024 ** 3                  # always leave this much free on the drive
_state = {"folder": None, "running": False, "now": "", "done": 0, "blocked": False}
_lock = threading.Lock()
_busy = set()
WAKE = threading.Event()                     # set to look for work at once


def set_folder(media_dir):
    _state["folder"] = Path(media_dir) / FOLDER


def folder():
    return _state["folder"]


def _ext(path):
    return os.path.splitext(path or "")[1].lower()


# ---------- is there a copy, and which file does a player get ----------
def copy_path(conn, mid, size):
    """Path of the ready copy of a video (None when there is none or the original changed since)."""
    f = folder()
    if f is None:
        return None
    r = conn.execute("SELECT file,src_size,status FROM prepared WHERE media_id=?", (mid,)).fetchone()
    if not r or r["status"] != "ready" or (r["src_size"] or 0) != (size or 0):
        return None
    p = f / r["file"]
    return str(p) if p.is_file() else None


def has_copy(conn, mid, size):
    return copy_path(conn, mid, size) is not None


def delivery(conn, mid, client="browser"):
    """(path, extension) of the file a player should get. client: 'browser' (the PC's TV screen, phones), 'roku'
    (plays the original whenever Roku can) or 'safe' (a Roku that refused the original: the copy if there is one)."""
    r = conn.execute("SELECT path,vcodec,acodec,vfmt,size FROM media WHERE id=? AND available=1", (mid,)).fetchone()
    if r is None:
        return None
    ext = _ext(r["path"])
    args = (r["vcodec"], r["acodec"], r["vfmt"] or "", ext)
    if client == "safe":
        use = True
    elif client == "roku":
        use = not library.roku_ok(*args)
    else:
        use = library.pc_kind(*args) == "prepare"
    if use:
        cp = copy_path(conn, mid, r["size"])
        if cp:
            return cp, "mp4"
    return r["path"], ext.lstrip(".")


def alt(conn, mid):
    """File type of the fallback for a Roku that is given the original ('' when there is no copy to fall back to)."""
    first = delivery(conn, mid, "roku")
    r = conn.execute("SELECT path,size FROM media WHERE id=?", (mid,)).fetchone()
    if first is None or r is None or first[0] != r["path"]:
        return ""
    return "mp4" if has_copy(conn, mid, r["size"]) else ""


def why(conn, row):
    """Plain-English reason a video is not playable on the PC yet (for the lists in Settings > Tools)."""
    ext = _ext(row["path"])
    kind = library.pc_kind(row["vcodec"], row["acodec"], row["vfmt"] or "", ext)
    if kind != "prepare":
        return library.why_not_playable(row["vcodec"], row["acodec"], row["vfmt"] or "", ext)
    p = conn.execute("SELECT status,why FROM prepared WHERE media_id=?", (row["id"],)).fetchone()
    if p and p["status"] == "failed":
        return "HERO TV could not prepare a copy of it (" + (p["why"] or "unknown reason") + ") - Fix may still manage it"
    if not enabled():
        return "it needs a ready-to-play copy and automatic copies are switched off (Settings > Tools)"
    return "HERO TV is preparing a copy of it by itself (Dolby/DTS sound or H.265 in .mkv) - it joins the channels when that is done"


# ---------- settings ----------
def enabled():
    from . import settings_api
    return settings_api._load().get("auto_prepare", True) is not False


def cap_gb():
    """Stop making NEW copies once the copies together use this many GB (0 = no limit). Nothing is ever deleted
    because of it: copies that exist stay, whatever the limit is set to."""
    from . import settings_api
    try:
        return max(0, int(settings_api._load().get("prepare_cap_gb") or 0))
    except (TypeError, ValueError):
        return 0


def used_bytes(conn):
    return conn.execute("SELECT COALESCE(SUM(bytes),0) FROM prepared WHERE status='ready'").fetchone()[0]


# ---------- making copies ----------
def command(ffmpeg, src, tmp, vcodec, acodec, amap="0:a:0?", tolerant=False, force_aac=False):
    """ffmpeg arguments: copy the picture into an .mp4; copy the sound when an .mp4 can hold it, else make AAC."""
    v = ["-c:v", "copy"] + (["-tag:v", "hvc1"] if vcodec == "hevc" else [])    # Apple devices only play HEVC tagged this way
    a = ["-c:a", "copy"] if library.mp4_audio_ok(acodec) and not force_aac else ["-c:a", "aac", "-b:a", "192k", "-ac", "2"]
    tol = ["-err_detect", "ignore_err", "-max_error_rate", "1"] if tolerant else []
    return [ffmpeg, "-v", "error", "-stats", "-y", "-fflags", "+genpts", *tol, "-i", src, "-map", "0:V:0", "-map", amap,
            *v, *a, "-sn", "-dn", "-max_muxing_queue_size", "9999", "-movflags", "+faststart", "-f", "mp4", str(tmp)]


def _same_length(path, runtime, probe=None):
    q = (probe or library.probe)(str(path))
    if not q:
        return False
    return not runtime or abs((q["runtime_s"] or 0) - runtime) <= max(5.0, runtime * 0.02)


def _record(conn, mid, status, size, file="", why_="", nbytes=0):
    conn.execute("INSERT OR REPLACE INTO prepared(media_id,file,src_size,status,why,made,bytes) VALUES(?,?,?,?,?,?,?)",
                 (mid, file, size, status, why_[:200], int(time.time()), nbytes))
    conn.commit()


def prepare_one(conn, row, ffmpeg, run=None, probe=None):
    """Make the ready copy of one video. Returns 'ready', 'failed' or 'busy'/'gone'. Never touches the original."""
    from .launcher import _Claim                           # one job per file: Fix, the Inbox and this must not overlap
    src, size, mid = row["path"], row["size"], row["id"]
    if not os.path.isfile(src):
        return "gone"
    run = run or (lambda cmd, rt: tools.run_ffmpeg(cmd, rt, None, low=True))
    with _Claim(src) as mine:
        if not mine:
            return "busy"
        f = folder()
        f.mkdir(parents=True, exist_ok=True)
        final, tmp = f / f"{mid}-{size}.mp4", f / f"{mid}-{size}.part"
        tracks = library.audio_tracks(src) or []
        n = library.playing_track(tracks)                  # the track a browser would play: default, else the first
        acodec = tracks[n]["codec"] if tracks else row["acodec"]
        rt = row["runtime_s"] or 0
        r = run(command(ffmpeg, src, tmp, row["vcodec"], acodec, f"0:a:{n}?"), rt)
        ok = r.returncode == 0 and tmp.is_file() and _same_length(tmp, rt, probe)
        if not ok and tools.sound_trouble(getattr(r, "errors", None)):
            ok, r = _rescue_sound(src, tmp, row, tracks, n, rt, run, ffmpeg, probe)
        if ok and os.path.getsize(src) != size:            # the original was replaced meanwhile: this copy is stale
            ok, r = False, tools.FFResult(1, ["the original changed while the copy was being made"])
        if not ok:
            why_ = ((getattr(r, "errors", None) or ["the copy came out shorter than the original"])[-1])
            _discard(tmp)
            _record(conn, mid, "failed", size, why_=why_)
            return "failed"
        os.replace(tmp, final)
        _record(conn, mid, "ready", size, final.name, nbytes=final.stat().st_size)
        conn.execute("UPDATE media SET playable=1 WHERE id=?", (mid,))
        conn.commit()
        return "ready"


def _discard(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _rescue_sound(src, tmp, row, tracks, n, rt, run, ffmpeg, probe):
    """The sound track is damaged: try the file's other tracks, else keep this one and let ffmpeg skip the damaged bits
    (those moments are silent). Same approach as Fix (see launcher._rescue_sound)."""
    good = lambda res: res.returncode == 0 and tmp.is_file() and _same_length(tmp, rt, probe)
    last = None
    for t in tracks:
        if t["n"] == n:
            continue
        _discard(tmp)
        last = run(command(ffmpeg, src, tmp, row["vcodec"], t["codec"], f"0:a:{t['n']}?", force_aac=True), rt)
        if good(last):
            return True, last
    _discard(tmp)
    last = run(command(ffmpeg, src, tmp, row["vcodec"], row["acodec"], f"0:a:{n}?", tolerant=True, force_aac=True), rt)
    return good(last), last


# ---------- what to make, and housekeeping ----------
def _skip_dirs(media_dir):
    return (os.path.normcase(os.path.join(os.path.abspath(str(media_dir)), "Inbox")) + os.sep,)   # the Inbox is converted and filed


def todo(conn, media_dir="", now=None):
    """Videos that need a copy and have none, newest first. Failed ones wait a week."""
    now = now or time.time()
    skip = _skip_dirs(media_dir) if media_dir else ()
    out = []
    for r in conn.execute("SELECT id,path,vcodec,acodec,vfmt,size,runtime_s,added FROM media WHERE available=1 AND verified=1 "
                          "AND playable=0 ORDER BY added DESC, id").fetchall():
        if library.pc_kind(r["vcodec"], r["acodec"], r["vfmt"] or "", _ext(r["path"])) != "prepare":
            continue
        if skip and os.path.normcase(os.path.abspath(r["path"])).startswith(skip):
            continue
        p = conn.execute("SELECT status,src_size,made FROM prepared WHERE media_id=?", (r["id"],)).fetchone()
        if p and (p["src_size"] or 0) == (r["size"] or 0):
            if p["status"] == "failed" and now - (p["made"] or 0) < RETRY_FAILED_S:
                continue
            if p["status"] == "ready" and has_copy(conn, r["id"], r["size"]):
                continue
        out.append(r)
    return out


def tidy(conn):
    """Remove copies nobody needs: the video is gone from the library, was replaced, or plays as it is now."""
    f = folder()
    if f is None or not f.is_dir():
        return 0
    keep, n = set(), 0
    for p in conn.execute("SELECT media_id,file,src_size,status FROM prepared").fetchall():
        m = conn.execute("SELECT id,path,vcodec,acodec,vfmt,size FROM media WHERE id=?", (p["media_id"],)).fetchone()
        useful = (m is not None and p["status"] == "ready" and (m["size"] or 0) == (p["src_size"] or 0)
                  and library.pc_kind(m["vcodec"], m["acodec"], m["vfmt"] or "", _ext(m["path"])) == "prepare")
        if p["status"] == "failed" and m is not None and (m["size"] or 0) == (p["src_size"] or 0):
            continue                                       # remembered failure: keeps it from being retried at once
        if useful and (f / p["file"]).is_file():
            keep.add(p["file"])
            continue
        conn.execute("DELETE FROM prepared WHERE media_id=?", (p["media_id"],))
        if p["file"]:
            _discard(f / p["file"])
        if m is not None:
            ok = library.pc_ok(conn, m["id"], m["size"], m["vcodec"], m["acodec"], m["vfmt"], _ext(m["path"]))
            conn.execute("UPDATE media SET playable=? WHERE id=?", (1 if ok else 0, m["id"]))
        n += 1
    for x in f.iterdir():                                  # half-made copies and copies no row knows about (our own names only)
        if x.is_file() and _OURS.fullmatch(x.name) and (x.suffix == ".part" or x.name not in keep):
            _discard(x)
    conn.commit()
    return n


def run_once(conn, ffmpeg, media_dir="", run=None, probe=None):
    """Make one copy. Returns True when it did something (so the loop carries on soon), False when nothing is left."""
    if folder() is None:
        set_folder(media_dir)
    tidy(conn)
    cap, used = cap_gb() * 1024 ** 3, used_bytes(conn)
    _state["blocked"] = False
    for r in todo(conn, media_dir):
        if cap and used + int((r["size"] or 0) * 1.05) > cap:
            _state["blocked"] = True                       # the limit you chose: no new copy (an existing copy is never removed)
            continue
        need = int((r["size"] or 0) * 1.05) + SPARE_BYTES
        try:
            os.makedirs(folder(), exist_ok=True)
            free = shutil.disk_usage(folder()).free
        except OSError:
            free = need
        if free < need:
            with _lock:
                _state["now"] = ""
            continue                                       # not enough room for this one: maybe a smaller one fits
        with _lock:
            _state["now"] = os.path.basename(r["path"])
        work.begin("copy", os.path.basename(r["path"]))
        work.stage("Making a ready-to-play copy")
        res = ""
        try:
            res = prepare_one(conn, r, ffmpeg, run, probe)
        finally:
            work.end({"ready": "copy ready", "failed": "could not make a copy"}.get(res, "stopped"), quiet=res not in ("ready", "failed"))
            with _lock:
                _state["now"] = ""
        if res == "ready":
            with _lock:
                _state["done"] += 1
        if res in ("ready", "failed"):
            return True
    return False


def retry(conn):
    """Forget earlier failures and look for work now."""
    conn.execute("DELETE FROM prepared WHERE status='failed'")
    conn.commit()
    WAKE.set()


def clear(conn):
    """Delete every copy (the originals are untouched). Videos that needed one stop being playable on the PC."""
    f = folder()
    for p in conn.execute("SELECT media_id,file FROM prepared").fetchall():
        if f is not None and p["file"]:
            _discard(f / p["file"])
    conn.execute("DELETE FROM prepared")
    for r in conn.execute("SELECT id,path,vcodec,acodec,vfmt,size FROM media WHERE playable=1").fetchall():
        if library.pc_kind(r["vcodec"], r["acodec"], r["vfmt"] or "", _ext(r["path"])) == "prepare":
            conn.execute("UPDATE media SET playable=0 WHERE id=?", (r["id"],))
    conn.commit()


def status(conn):
    need = ready = convert = 0
    for r in conn.execute("SELECT id,path,vcodec,acodec,vfmt,size FROM media WHERE available=1 AND verified=1").fetchall():
        k = library.pc_kind(r["vcodec"], r["acodec"], r["vfmt"] or "", _ext(r["path"]))
        if k == "prepare":
            need += 1
            ready += 1 if has_copy(conn, r["id"], r["size"]) else 0
        elif k == "convert":
            convert += 1
    row = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(bytes),0) AS b FROM prepared WHERE status='ready'").fetchone()
    failed = conn.execute("SELECT COUNT(*) FROM prepared WHERE status='failed'").fetchone()[0]
    free = None
    try:
        if folder() is not None and folder().parent.is_dir():
            free = shutil.disk_usage(folder().parent).free
    except OSError:
        free = None
    return {"on": enabled(), "need": need, "ready": ready, "failed": failed, "convert": convert, "bytes": row["b"],
            "cap_gb": cap_gb(), "blocked": _state["blocked"], "free": free, "working": _state["now"], "running": _state["running"]}


def start_background(cfg, connect, every=3, idle=600):
    """Make the copies one at a time while HERO TV runs (low priority; a few minutes per movie)."""
    set_folder(cfg.media_dir)

    def loop():
        time.sleep(90)                                     # let HERO TV start up first
        while True:
            pause = idle
            try:
                exe = tools.find_tool("ffmpeg")
                if exe and enabled():
                    c = connect(cfg.db_path)
                    try:
                        _state["running"] = True
                        if run_once(c, exe, cfg.media_dir):
                            pause = every
                    finally:
                        _state["running"] = False
                        c.close()
            except Exception:
                pass
            WAKE.wait(pause)
            WAKE.clear()
    threading.Thread(target=loop, name="herotv-prepare", daemon=True).start()
