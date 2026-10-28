"""Hands-free Inbox: while HERO TV is running, anything you drop in the Inbox folder is filed onto the right channel
by its title (the same keywords as Sort-Movies.bat), fixed if its sound/format needs it, and shows up on its own.

The Inbox folder is watched, and so are videos loose in the media folder itself (not in any folder). A file is touched
only after it has stopped growing (so downloads in progress are left alone). Files whose title matches nothing stay in
the Inbox (loose ones are moved into it), where Settings > Tools lists them with a channel picker.
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


def _walk(cfg):
    """(folder, files) of the Inbox (all its folders) and of the media folder's top level (loose videos)."""
    d = inbox_dir(cfg)
    if os.path.isdir(d):
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if not x.startswith(".")]
            yield dp, fn
    media = os.path.abspath(str(cfg.media_dir))
    try:
        yield media, [e.name for e in os.scandir(media) if e.is_file()]
    except OSError:
        pass


def candidates(cfg, seen, now=None):
    """Videos that are finished arriving: same size on two passes in a row and not changed for MIN_AGE_S seconds."""
    now = now or time.time()
    ok, sizes = [], {}
    exts = library.EXTS | _convertible()
    for dp, fn in _walk(cfg):
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


def series_lookup(cfg, channels):
    """A function stem -> channels the show's earlier episodes are on (a new episode follows its show)."""
    from . import insights
    from .db import connect

    def get(stem):
        try:
            c = connect(cfg.db_path)
        except Exception:
            return []
        try:
            return insights.series_channels(c, channels, stem)
        except Exception:
            return []
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
    from . import fixes as F
    mine = F.load(cfg)
    follow = series_lookup(cfg, channels)
    media = os.path.abspath(str(cfg.media_dir))
    for src in ready:
        stem = os.path.splitext(os.path.basename(src))[0]
        picked = sortrules.targets(stem, rules, channels, None if F.lookup(mine, stem) else (facts(stem) if facts else None), smart, mine)
        if not picked:
            picked = follow(stem)                         # a new episode of a show you already have
        if not picked:
            out["left"] += 1
            if os.path.normcase(os.path.dirname(os.path.abspath(src))) == os.path.normcase(media):
                move_in([src], cfg)                       # a loose video nothing matched: into the Inbox list
            continue
        try:
            if place(src, picked, media, force_move=True):
                out["filed"].append(os.path.basename(src))
        except Exception:
            traceback.print_exc()
            out["left"] += 1
    return out


SIDECARS = (".hero.json", ".srt", ".vtt", ".ass", ".ssa", ".nfo", ".jpg", ".png")


def move_in(paths, cfg, keep_folder_of=None):
    """Move videos (with their subtitle / note files) into the Inbox. keep_folder_of: the media folder - a video in
    a folder keeps that folder name inside the Inbox, so a show's episodes stay together. Returns how many moved."""
    import shutil
    d = inbox_dir(cfg)
    n = 0
    for src in paths:
        src = os.path.abspath(src)
        if not os.path.isfile(src):
            continue
        sub = ""
        if keep_folder_of:
            rel = os.path.relpath(os.path.dirname(src), keep_folder_of)
            if not rel.startswith("..") and rel != ".":
                sub = rel
        target = os.path.join(d, sub)
        dest = os.path.join(target, os.path.basename(src))
        if os.path.normcase(dest) == os.path.normcase(src) or os.path.exists(dest):
            continue
        os.makedirs(target, exist_ok=True)
        stem = os.path.splitext(os.path.basename(src))[0]
        folder = os.path.dirname(src)
        try:
            shutil.move(src, dest)
        except OSError:
            continue
        n += 1
        try:
            for f in os.listdir(folder):
                if f.startswith(stem) and f[len(stem):].lower().endswith(SIDECARS) and f[len(stem):len(stem) + 1] in (".", ""):
                    if not os.path.exists(os.path.join(target, f)):
                        shutil.move(os.path.join(folder, f), os.path.join(target, f))
        except OSError:
            pass
    return n


def not_on_channels(conn, cfg):
    """Library videos (outside the Inbox) that no channel shows - e.g. in a folder no channel uses. Shorts are left out
    (they are filler between shows), and so are videos already set aside."""
    from . import scheduler as S, sortrules
    try:
        _r, chans = sortrules.load(cfg, write=False)
    except (OSError, ValueError, KeyError):
        return []
    rules = [S.config_rules(ch) for ch in chans if ch.get("kind", "tv") == "tv" and not ch.get("off")
             and (ch.get("match") or ch.get("also"))]
    d = os.path.normcase(inbox_dir(cfg)) + os.sep
    out = []
    for m in conn.execute("SELECT * FROM media WHERE available=1 AND verified=1 ORDER BY franchise,series,ord,title"):
        p = os.path.normcase(os.path.abspath(m["path"] or ""))
        if p.startswith(d) or os.sep + ".originals" + os.sep in p or S.is_short(m) or \
                str(m["franchise"] or "").lower() == S.SHORTS_FOLDER:
            continue
        if not any(S.matches(r, m) for r in rules):
            out.append(m)
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
