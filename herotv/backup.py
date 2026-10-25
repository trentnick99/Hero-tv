"""Backup and restore of everything that is YOURS in HERO TV (not the videos themselves):
your channel settings and lists, station name and colour, favorites, resume points, what you have watched,
skip-intro settings and remembered choices. Videos keep their own rename/tag files (.hero.json) next to them."""
import json
import os
import time
import zipfile
from pathlib import Path

from . import config, library

CONFIG_FILES = ("channels.json", "auto-sort.json", "checklist.json", "free-sources.json")
MAX_JSON = 20 * 1024 * 1024


def default_dir():
    return Path.home() / "Documents" / "HERO TV Backups"


def _rel(path, media):
    try:
        rel = os.path.relpath(path, media)
        if not rel.startswith(".."):
            return rel.replace(os.sep, "/")
    except ValueError:
        pass
    return str(path)


def _abs(rel, media):
    return rel if os.path.isabs(rel) else os.path.join(media, *rel.split("/"))


def make(cfg, conn, dest_dir=None, now=None):
    """Write HERO-TV-backup-<date-time>.zip and return its path."""
    media = os.path.abspath(str(cfg.media_dir))
    dest_dir = Path(dest_dir or default_dir())
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / ("HERO-TV-backup-" + time.strftime("%Y-%m-%d-%H%M%S", time.localtime(now or time.time())) + ".zip")

    def rows(sql):
        return conn.execute(sql).fetchall()

    paths = {r["id"]: r["path"] for r in rows("SELECT id,path FROM media")}
    db = {
        "favorites": [_rel(paths[r["media_id"]], media) for r in rows("SELECT media_id FROM favorites") if r["media_id"] in paths],
        "progress": [{"file": _rel(paths[r["media_id"]], media), "position": r["position"], "completed": r["completed"], "updated": r["updated"]}
                     for r in rows("SELECT * FROM progress") if r["media_id"] in paths],
        "seen": [{"file": _rel(paths[r["media_id"]], media), "secs": r["secs"], "last": r["last"]}
                 for r in rows("SELECT * FROM seen") if r["media_id"] in paths],
        "skips": [dict(r) for r in rows("SELECT * FROM skips")],
        "prefs": {r["key"]: r["value"] for r in rows("SELECT * FROM prefs")},
    }
    cfg_dir = os.path.dirname(cfg.channels_file)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps({"app": "HERO TV", "version": 1, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                 "media_dir": media}, indent=1))
        z.writestr("data.json", json.dumps(db, indent=1))
        sf = config.settings_file()
        if sf.is_file():
            z.write(sf, "settings.json")
        for name in CONFIG_FILES:
            f = os.path.join(cfg_dir, name)
            if os.path.isfile(f):
                z.write(f, "config/" + name)
    return str(path)


def latest(dest_dir=None):
    d = Path(dest_dir or default_dir())
    files = sorted(d.glob("HERO-TV-backup-*.zip"), key=lambda p: p.stat().st_mtime) if d.is_dir() else []
    return str(files[-1]) if files else None


def _read_json(z, name):
    info = z.getinfo(name)
    if info.file_size > MAX_JSON:
        raise ValueError(f"{name} is unreasonably large")
    return json.loads(z.read(name).decode("utf-8-sig"))


def restore(cfg, conn, zip_path):
    """Put a backup back. Returns a summary dict. Current config files are kept as <name>.before-restore."""
    media = os.path.abspath(str(cfg.media_dir))
    out = {"config": 0, "favorites": 0, "progress": 0, "seen": 0, "skips": 0, "prefs": 0, "not_found": 0}
    try:
        z = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile):
        raise ValueError("That is not a HERO TV backup file.")
    with z:
        names = set(z.namelist())
        if "manifest.json" not in names or "data.json" not in names:
            raise ValueError("That zip is not a HERO TV backup.")
        data = _read_json(z, "data.json")
        cfg_dir = os.path.dirname(cfg.channels_file)
        for name in CONFIG_FILES:
            member = "config/" + name
            if member in names:
                info = z.getinfo(member)
                if info.file_size > MAX_JSON:
                    continue
                raw = z.read(member)
                json.loads(raw.decode("utf-8-sig"))                   # never install a broken file
                target = os.path.join(cfg_dir, name)
                if os.path.isfile(target):
                    with open(target, "rb") as fh, open(target + ".before-restore", "wb") as bak:
                        bak.write(fh.read())
                with open(target, "wb") as fh:
                    fh.write(raw)
                out["config"] += 1
        if "settings.json" in names:
            saved = _read_json(z, "settings.json")
            sf = config.settings_file()
            try:
                cur = json.loads(sf.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                cur = {}
            if saved.get("media_dir") and not os.path.isdir(saved["media_dir"]):
                saved.pop("media_dir")                                  # that drive/folder is not on this PC
            cur.update(saved)
            sf.parent.mkdir(parents=True, exist_ok=True)
            sf.write_text(json.dumps(cur, indent=1), encoding="utf-8")
    library.scan(conn, media)
    ids = {r["path"]: r["id"] for r in conn.execute("SELECT id,path FROM media")}

    def mid(rel):
        return ids.get(_abs(rel, media)) or ids.get(os.path.normpath(_abs(rel, media)))

    for rel in data.get("favorites", []):
        m = mid(rel)
        if m:
            conn.execute("INSERT OR IGNORE INTO favorites(media_id,added) VALUES(?,?)", (m, int(time.time())))
            out["favorites"] += 1
        else:
            out["not_found"] += 1
    for r in data.get("progress", []):
        m = mid(r.get("file", ""))
        if m:
            conn.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(?,?,?,?) ON CONFLICT(media_id) DO UPDATE SET "
                         "position=excluded.position,completed=excluded.completed,updated=excluded.updated",
                         (m, float(r.get("position", 0)), int(r.get("completed", 0)), int(r.get("updated") or time.time())))
            out["progress"] += 1
    for r in data.get("seen", []):
        m = mid(r.get("file", ""))
        if m:
            conn.execute("INSERT INTO seen(media_id,secs,last) VALUES(?,?,?) ON CONFLICT(media_id) DO UPDATE SET secs=excluded.secs,last=excluded.last",
                         (m, float(r.get("secs", 0)), int(r.get("last") or time.time())))
            out["seen"] += 1
    for r in data.get("skips", []):
        if r.get("series"):
            conn.execute("INSERT INTO skips(series,intro,outro) VALUES(?,?,?) ON CONFLICT(series) DO UPDATE SET intro=excluded.intro,outro=excluded.outro",
                         (r["series"], float(r.get("intro", 0)), float(r.get("outro", 0))))
            out["skips"] += 1
    for k, val in (data.get("prefs") or {}).items():
        if k in ("channel", "volume", "muted", "bigtext", "subs"):
            conn.execute("INSERT INTO prefs(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(val)))
            out["prefs"] += 1
    conn.commit()
    return out


AUTO_EVERY_S = 7 * 86400
AUTO_KEEP = 8


def auto_enabled():
    try:
        return json.loads(config.settings_file().read_text(encoding="utf-8-sig")).get("auto_backup", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def auto(cfg, conn, dest_dir=None, now=None):
    """Weekly safety copy (Settings > Backup and about). Returns the new backup's path, or None when not due.
    Keeps the newest AUTO_KEEP backups and deletes older ones."""
    now = now or time.time()
    if not auto_enabled():
        return None
    last = latest(dest_dir)
    if last and now - os.path.getmtime(last) < AUTO_EVERY_S:
        return None
    path = make(cfg, conn, dest_dir, now=now)
    d = Path(dest_dir or default_dir())
    old = sorted(d.glob("HERO-TV-backup-*.zip"), key=lambda p: p.name)      # names carry the date and time
    for p in old[:-AUTO_KEEP]:
        try:
            p.unlink()
        except OSError:
            pass
    return path
