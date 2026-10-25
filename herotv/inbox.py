"""Hands-free Inbox: while HERO TV is running, anything you drop in the Inbox folder is filed onto the right channel
by its title (the same keywords as Sort-Movies.bat), fixed if its sound/format needs it, and shows up on its own.

Only the Inbox folder is watched. A file is touched only after it has stopped growing (so downloads in progress are left
alone), and files whose title matches no keyword stay in the Inbox - the Help screen counts them.
"""
import json
import os
import threading
import time
import traceback

from . import config, library

PARTIAL = (".part", ".crdownload", ".tmp", ".download", ".aria2", ".!ut")
MIN_AGE_S = 20


def enabled():
    try:
        v = json.loads(config.settings_file().read_text(encoding="utf-8-sig")).get("auto_inbox", True)
        return bool(v)
    except (OSError, ValueError, AttributeError):
        return True


def inbox_dir(cfg):
    return os.path.join(os.path.abspath(str(cfg.media_dir)), "Inbox")


def _convertible():
    from . import launcher
    return launcher.CONVERTIBLE


def candidates(cfg, seen, now=None):
    """Inbox videos that are finished arriving: same size on two passes in a row and not changed for MIN_AGE_S seconds."""
    now = now or time.time()
    d = inbox_dir(cfg)
    ok, sizes = [], {}
    if not os.path.isdir(d):
        return ok, sizes
    exts = library.EXTS | _convertible()
    for dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if not x.startswith(".")]
        for f in sorted(fn):
            p = os.path.join(dp, f)
            if f.startswith(".") or f.lower().endswith(PARTIAL) or os.path.splitext(f)[1].lower() not in exts:
                continue
            try:
                st = os.stat(p)
            except OSError:
                continue
            sizes[p] = st.st_size
            if seen.get(p) == st.st_size and now - st.st_mtime >= MIN_AGE_S and st.st_size > 0:
                ok.append(p)
    return ok, sizes


def waiting(cfg):
    """How many videos sit in the Inbox (for the Help screen)."""
    d = inbox_dir(cfg)
    n = 0
    if os.path.isdir(d):
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if not x.startswith(".")]
            n += sum(1 for f in fn if os.path.splitext(f)[1].lower() in library.EXTS | _convertible() and not f.lower().endswith(PARTIAL))
    return n


def facts_lookup(cfg):
    """A function stem -> TMDB facts (or None), using the library database as its memory."""
    from . import art
    from .db import connect

    def get(stem):
        c = connect(cfg.db_path)
        try:
            return art.facts_for(c, cfg, stem)
        finally:
            c.close()
    return get


def run_once(cfg, seen, now=None, place=None, facts=None):
    """One pass. Files are filed one at a time (converting can be slow). Returns {"filed": [...], "left": n}."""
    from . import launcher
    place = place or launcher._place
    ready, sizes = candidates(cfg, seen, now)
    seen.clear()
    seen.update(sizes)
    out = {"filed": [], "left": 0}
    if not ready:
        return out
    from . import sortrules
    rules, channels = sortrules.load(cfg)
    smart = sortrules.smart_rules(cfg)
    facts = facts or (facts_lookup(cfg) if smart else None)
    media = os.path.abspath(str(cfg.media_dir))
    for src in ready:
        stem = os.path.splitext(os.path.basename(src))[0]
        picked = sortrules.targets(stem, rules, channels, facts(stem) if facts else None, smart)
        if not picked:
            out["left"] += 1
            continue
        try:
            if place(src, picked, media, force_move=True):
                out["filed"].append(os.path.basename(src))
        except Exception:
            traceback.print_exc()
            out["left"] += 1
    return out


def watch_forever(cfg, every=30):
    def loop():
        seen = {}
        while True:
            try:
                if enabled():
                    run_once(cfg, seen)
            except Exception:
                traceback.print_exc()
            time.sleep(every)
    threading.Thread(target=loop, daemon=True, name="inbox").start()


# ---------- drag-and-drop onto the TV window ----------
MAX_UPLOAD = 80 * 1024 ** 3
SUBTITLE_EXTS = {".srt", ".vtt"}
_ILLEGAL = __import__("re").compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


def clean_name(name):
    """A safe file name for the Inbox, or None when the type is not something HERO TV uses."""
    base = os.path.basename(str(name or "").replace("\\", "/"))
    base = _ILLEGAL.sub(" ", base)
    base = " ".join(base.split()).strip(" .")
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext not in library.EXTS | _convertible() | SUBTITLE_EXTS:
        return None
    stem = stem.strip(" .")[:140] or "Untitled"
    if stem.lower() in _RESERVED:
        stem += "_"
    return stem + ext


def save_stream(cfg, name, rfile, length, reserve=2 * 1024 ** 3, chunk=1 << 20):
    """Write `length` bytes from rfile into the Inbox as <name> (via a .part file). Returns the final file name.
    Raises ValueError for anything not acceptable (wrong type, too big, no disk space)."""
    import shutil
    safe = clean_name(name)
    if not safe:
        raise ValueError("HERO TV can only take video files (mp4, mkv, avi, ...) and .srt/.vtt subtitles")
    if length <= 0 or length > MAX_UPLOAD:
        raise ValueError("file size is not acceptable")
    d = inbox_dir(cfg)
    os.makedirs(d, exist_ok=True)
    if shutil.disk_usage(d).free - length < reserve:
        raise ValueError("not enough free disk space for this file")
    stem, ext = os.path.splitext(safe)
    final, n = os.path.join(d, safe), 2
    while os.path.exists(final):
        final = os.path.join(d, f"{stem} {n}{ext}")
        n += 1
    part = final + ".part"
    left = length
    try:
        with open(part, "wb") as fh:
            while left > 0:
                b = rfile.read(min(chunk, left))
                if not b:
                    raise ConnectionError("upload was cut off")
                fh.write(b)
                left -= len(b)
        os.replace(part, final)
    except BaseException:
        try:
            os.remove(part)
        except OSError:
            pass
        raise
    return os.path.basename(final)
