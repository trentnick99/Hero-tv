"""Check everything: a quick health check in plain words (Settings > Backup and about, and once after an update).

Read-only. It looks, it never changes or deletes anything. Each check answers ok / warn / fail with a sentence a person can
read; `fail` means something HERO TV needs is broken, `warn` means worth a look."""
import json
import os
import shutil
import time
from pathlib import Path

from . import __version__

OK, WARN, FAIL = "ok", "warn", "fail"
LOW_GB, CRIT_GB = 10, 2


def _chk(name, level, text):
    return {"name": name, "level": level, "text": text}


def run(conn, cfg, now=None):
    """All checks as a list; never raises (a check that crashes is itself reported as a failure)."""
    out = []
    for fn in (_database, _tools, _media, _program, _data_folder, _channels, _guide, _log):
        try:
            out.extend(fn(conn, cfg, now or time.time()))
        except Exception as e:                      # a broken check must not hide the others
            out.append(_chk(getattr(fn, "__name__", "check").strip("_"), FAIL, f"This check could not run ({type(e).__name__}: {str(e)[:120]})"))
    return out


def summary(checks):
    f = sum(1 for c in checks if c["level"] == FAIL)
    w = sum(1 for c in checks if c["level"] == WARN)
    if f:
        return {"level": FAIL, "text": f"{f} problem{'s' if f != 1 else ''} found" + (f" and {w} to look at" if w else "")}
    if w:
        return {"level": WARN, "text": f"Working, with {w} thing{'s' if w != 1 else ''} to look at"}
    return {"level": OK, "text": "Everything checked is fine"}


def _database(c, cfg, now):
    n = c.execute("SELECT COUNT(*) FROM media WHERE available=1").fetchone()[0]
    r = [_chk("Library database", OK, f"Opens fine ({n} videos).")]
    if n == 0:
        r.append(_chk("Videos", WARN, "The library has no videos yet. Put some in the media folder or the Inbox."))
    return r


def _tools(c, cfg, now):
    from . import tools
    miss = [t for t in ("ffmpeg", "ffprobe") if not tools.find_tool(t)]
    if miss:
        return [_chk("Video tools", FAIL, f"{' and '.join(miss)} not found - needed to read, fix and convert videos.")]
    return [_chk("Video tools", OK, "ffmpeg and ffprobe are found.")]


def _media(c, cfg, now):
    d = Path(cfg.media_dir)
    if not d.is_dir():
        return [_chk("Media folder", FAIL, "The media folder cannot be found. Is the drive connected? (Settings > Media library)")]
    try:
        os.listdir(d)
    except OSError:
        return [_chk("Media folder", FAIL, "The media folder cannot be read.")]
    r = [_chk("Media folder", OK, "Found and readable.")]
    try:
        gb = shutil.disk_usage(d).free / 1e9
        lvl = FAIL if gb < CRIT_GB else WARN if gb < LOW_GB else OK
        r.append(_chk("Free space", lvl, f"{gb:.0f} GB free on the media drive." + ("" if lvl == OK else " Getting low - new copies and downloads may stop.")))
    except OSError:
        pass
    return r


def _program(c, cfg, now):
    missing = [f for f in ("index.html", "app.js", "app.css") if not (Path(cfg.web_dir) / f).is_file()]
    if missing:
        return [_chk("Program files", FAIL, f"Missing: {', '.join(missing)}. Reinstall HERO TV from the latest release.")]
    return [_chk("Program files", OK, f"The screens are in place (version {__version__}).")]


def _data_folder(c, cfg, now):
    from .launcher import app_data_dir
    d = app_data_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        t = d / ".selfcheck.tmp"
        t.write_text("ok", encoding="utf-8")
        t.unlink()
    except OSError:
        return [_chk("Settings folder", FAIL, "HERO TV cannot write to its own settings folder - settings and the log cannot be saved.")]
    return [_chk("Settings folder", OK, "Can be written to.")]


def _channels(c, cfg, now):
    try:
        with open(cfg.channels_file, encoding="utf-8-sig") as fh:
            ch = json.load(fh)["channels"]
    except Exception as e:
        return [_chk("Channels", FAIL, f"channels.json cannot be read ({type(e).__name__}).")]
    on = [x for x in ch if not x.get("off")]
    if not on:
        return [_chk("Channels", FAIL, "Every channel is switched off - there is nothing to watch live.")]
    return [_chk("Channels", OK, f"{len(on)} channels on ({len(ch) - len(on)} off).")]


def _guide(c, cfg, now):
    from . import scheduler
    try:
        with open(cfg.channels_file, encoding="utf-8-sig") as fh:
            ids = [x.get("id") for x in json.load(fh)["channels"] if not x.get("off")]
    except Exception:
        return []
    if not ids:
        return []
    empty = [i for i in ids if scheduler.current(c, i, now) is None]
    if len(empty) == len(ids):
        return [_chk("TV guide", FAIL, "No channel has anything on right now. The schedule may not have been filled yet - restart HERO TV or press Check again in a minute.")]
    if empty:
        return [_chk("TV guide", WARN, f"{len(empty)} of {len(ids)} channels have nothing on right now (channels with no videos assigned).")]
    return [_chk("TV guide", OK, f"All {len(ids)} channels have something on now.")]


def _log(c, cfg, now):
    from . import report
    from .launcher import app_data_dir
    lines = report._tail(app_data_dir() / "herotv.log", 400)
    bad = [x for x in lines if "Traceback (most recent call last)" in x]
    pages = [x for x in lines if "[page-error]" in x]
    r = []
    if bad:
        r.append(_chk("Errors in the log", WARN, f"{len(bad)} program error(s) in the recent log. Use Report a problem and send it to Claude."))
    if pages or report.PAGE_ERRORS:
        r.append(_chk("Screen errors", WARN, f"{max(len(pages), len(report.PAGE_ERRORS))} screen error(s) were noticed recently. Use Report a problem and send it to Claude."))
    if not r:
        r.append(_chk("Errors", OK, "No recent errors in the log."))
    return r


def new_version_started():
    """True once per new version: remembers which version last started in <app data>/lastversion.txt."""
    from .launcher import app_data_dir
    f = app_data_dir() / "lastversion.txt"
    try:
        old = f.read_text(encoding="utf-8").strip()
    except OSError:
        old = ""
    if old == __version__:
        return False
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(__version__, encoding="utf-8")
    except OSError:
        pass
    return bool(old)                    # a first-ever start is not "an update"


def backup_folder():
    """The newest folder of program files kept by the updater (for going back by hand), or None."""
    import sys
    if not getattr(sys, "frozen", False):
        return None
    try:
        b = sorted((Path(sys.executable).parent / ".update-backup").glob("*-app"))
    except OSError:
        return None
    return str(b[-1]) if b else None
