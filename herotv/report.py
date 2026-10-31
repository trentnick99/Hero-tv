"""Report a problem: one plain-text report to paste into a Claude chat (Settings > Backup and about).

It holds what is needed to find a problem - version, system, settings, library and channel counts, the network check,
errors on the TV page and the last lines of the log - and is also saved under <app data>/reports. Nothing is sent
anywhere. Keys and tokens are hidden, and your home folder (with your Windows user name) is shown as <home>."""
import collections
import json
import os
import platform
import re
import sys
import time
from pathlib import Path

from . import __version__, config

PAGE_ERRORS = collections.deque(maxlen=20)        # script errors the TV page reported (newest last)
SECRET_KEYS = ("tmdb_key", "token", "media_key", "key", "code", "password")
SECRET = re.compile(r"((?:api_key|access_token|token|k)=|Bearer\s+)[A-Za-z0-9._\-]{8,}", re.I)
KEEP_REPORTS = 10


def page_error(msg, where=""):
    if msg:
        PAGE_ERRORS.append(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}" + (f"  ({where})" if where else ""))


def _hide(text):
    home = os.path.expanduser("~")
    if len(os.path.basename(home)) > 2:
        for h in {home, home.replace("\\", "/")}:
            text = text.replace(h, "<home>")
    return SECRET.sub(lambda m: m.group(1) + "<hidden>", text)


def _mask(v):
    """Hide passwords at any depth (the Roku TVs' developer passwords)."""
    if isinstance(v, dict):
        return {k: ("<set>" if k == "password" and x else _mask(x)) for k, x in v.items()}
    return v


def _settings():
    from . import settings_api
    d = settings_api._load()
    out = {}
    for k, v in sorted(d.items()):
        if any(k == s or k.endswith("_" + s) for s in SECRET_KEYS):
            out[k] = "<set>" if v else "<empty>"
        elif k in ("roku", "rokus") and isinstance(v, dict):
            out[k] = _mask(v)
        elif k == "weather" and isinstance(v, dict):
            out[k] = {"name": v.get("name", ""), "units": v.get("units", "")}       # not the exact coordinates
        else:
            out[k] = v
    return out


def _tail(path, n):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return [x.rstrip("\n") for x in fh.readlines()[-n:]]
    except OSError:
        return []


def build(c, cfg, note="", lan=False, dlna_on=False, page=""):
    """The report as plain text."""
    from . import art, inbox, tools
    from .launcher import app_data_dir
    L = []
    add = L.append
    add("=== HERO TV problem report ===")
    add("Paste this into the Claude chat and say what happened.")
    add(f"Made: {time.strftime('%Y-%m-%d %H:%M:%S %z')}")
    add(f"HERO TV {__version__} (build {config.API_LEVEL}), {'ready-made app' if getattr(sys, 'frozen', False) else 'run from Python source'}")
    add(f"System: {platform.platform()}, Python {platform.python_version()}")
    add(f"Video tools: ffmpeg {'found' if tools.find_tool('ffmpeg') else 'MISSING'}, ffprobe {'found' if tools.find_tool('ffprobe') else 'MISSING'}")
    if page:
        add(f"Screen: {page}")
    add("")
    add("What happened (in your words):")
    add("  " + (note.strip().replace("\n", "\n  ") if note and note.strip() else "(nothing typed)"))
    add("")
    add("Settings: " + json.dumps(_settings(), ensure_ascii=False))
    try:
        m = c.execute("SELECT COUNT(*), COALESCE(SUM(available),0), COALESCE(SUM(available AND verified AND playable),0), "
                      "COUNT(DISTINCT CASE WHEN series<>'' THEN series END) FROM media").fetchone()
        add(f"Library: {m[1]} videos ({m[2]} playable), {m[3]} shows; Inbox waiting: {inbox.waiting(cfg)}; cover art: {art.stats(c)}")
    except Exception as e:
        add(f"Library: could not be read ({e})")
    try:
        with open(cfg.channels_file, encoding="utf-8-sig") as fh:
            ch = json.load(fh)["channels"]
        add(f"channels.json: {len(ch)} channels - " + ", ".join(f"{x.get('number')} {x.get('name')}{' (off)' if x.get('off') else ''}"
                                                              for x in sorted(ch, key=lambda x: x.get("number", 0))))
    except Exception as e:
        add(f"channels.json: cannot be read ({e})")
    from . import remote as R
    try:
        paired = len(R.devices(c))
    except Exception:
        paired = "?"
    add(f"Other devices: listener {'on' if lan else 'off'} (setting {'on' if R.enabled() else 'off'}), "
        f"addresses {R.lan_addresses()}, paired devices: {paired}")
    add(f"TV media server (DLNA): {'on' if dlna_on else 'off'}")
    if R.enabled():
        try:
            from . import netcheck
            chk = netcheck.diagnose(lan, R.lan_addresses(), netcheck.snapshot())
            add("Connection check: " + ("all clear" if not chk["problems"] else "; ".join(p["title"] for p in chk["problems"]))
                + (f" (card {chk['alias']}, network type {chk['category']})" if chk.get("alias") else ""))
        except Exception as e:
            add(f"Connection check: could not run ({e})")
    try:
        from . import selfupdate
        u = selfupdate.status()
        add(f"Updates: newest seen {u['latest'] or '?'}, automatic checks {'on' if u['auto'] else 'off'}"
            + (f", last problem: {u['error']}" if u["error"] else ""))
    except Exception:
        pass
    add("")
    add("Videos played last (sound details):")
    try:
        from . import library, prepare
        rows = c.execute("SELECT m.id,m.path,m.vcodec,m.acodec,m.atracks FROM progress p JOIN media m ON m.id=p.media_id "
                         "WHERE p.updated IS NOT NULL ORDER BY p.updated DESC LIMIT 3").fetchall()
        if not rows:
            add("  (none yet)")
        for r in rows:
            add(f"  {os.path.basename(r['path'])}: video {r['vcodec']}, first sound {r['acodec']}, languages {r['atracks'] or 'not read yet'}")
            for t in library.audio_tracks(r["path"]) or []:
                add(f"    track {t['n'] + 1}: {t['lang']} {t['codec']} {t['channels']} ch{' default' if t['default'] else ''}"
                    + (f" \"{t['title']}\"" if t["title"] else ""))
            pr = c.execute("SELECT file,status,alang,mix,why FROM prepared WHERE media_id=?", (r["id"],)).fetchone()
            if pr:
                add(f"    ready copy: {pr['status']}, language {pr['alang'] or 'default'}, surround mixed down: {'yes' if pr['mix'] else 'no (older copy)'}"
                    + (f", note: {pr['why']}" if pr["why"] else ""))
            else:
                add("    ready copy: none")
            for client in ("browser", "roku"):
                d = prepare.delivery(c, r["id"], client)
                add(f"    {client} gets: " + (("the ready copy" if d[0] != r["path"] else "the original file") if d else "?"))
    except Exception as e:
        add(f"  could not be read ({e})")
    add("")
    add("Errors on the TV page (newest last):" if PAGE_ERRORS else "Errors on the TV page: none")
    L.extend("  " + e for e in PAGE_ERRORS)
    for name, n in (("herotv.log", 60), ("update.log", 25)):
        lines = _tail(app_data_dir() / name, n)
        if lines:
            add("")
            add(f"Last lines of {name}:")
            L.extend("  " + x for x in lines)
    return _hide("\n".join(L)) + "\n"


def save(text):
    """Keep a copy under <app data>/reports (the newest few). Returns the file path."""
    from .launcher import app_data_dir
    d = Path(app_data_dir()) / "reports"
    d.mkdir(parents=True, exist_ok=True)
    f = d / time.strftime("HERO-TV-report-%Y-%m-%d-%H%M%S.txt")
    f.write_text(text, encoding="utf-8")
    for old in sorted(d.glob("HERO-TV-report-*.txt"))[:-KEEP_REPORTS]:
        try:
            old.unlink()
        except OSError:
            pass
    return str(f)
