"""Update HERO TV from a newer hero-tv-windows zip (the one you download from the chat).

Replaces the program files, but never touches your videos, your data (favorites, resume points...) or your own channel
settings: if a settings file in config/ was changed by you, the new version is saved beside it as <name>.new instead.
Everything that gets replaced is first copied to .update-backup/<date>/ so an update can be undone by hand.
"""
import glob
import os
import posixpath
import shutil
import time
import zipfile
from pathlib import Path

from . import backup

KEEP_AS_MINE = {"config/" + n for n in backup.CONFIG_FILES}
SKIP_TOP = ("data/", "build-app/", ".update-backup/", "_internal/")
SKIP_FILES = {"HERO-TV.exe"}
KEEP_BACKUPS = 3


def find_zip(arg=None, downloads=None):
    """The zip to install: the one given, else the newest hero-tv-windows*.zip in Downloads."""
    if arg:
        return Path(arg) if os.path.isfile(arg) else None
    d = Path(downloads) if downloads else Path.home() / "Downloads"
    found = [p for p in glob.glob(str(d / "*hero-tv-windows*.zip"))]
    found.sort(key=os.path.getmtime, reverse=True)
    return Path(found[0]) if found else None


def _prefix(names):
    """Folder inside the zip that holds herotv/__init__.py ('' or 'hero-tv/'), or None when this is not a HERO TV zip."""
    for n in names:
        if n.endswith("herotv/__init__.py") and n.count("/") <= 2:
            return n[: -len("herotv/__init__.py")]
    return None


def _safe(rel):
    p = posixpath.normpath(rel)
    return not (p.startswith("/") or p.startswith("..") or "/../" in "/" + p or ":" in p or p == ".")


def plan(zip_path, root):
    """[(member, relative path, action)] where action is 'new', 'same', 'replace', 'keep-mine' (saved as .new) ."""
    out = []
    with zipfile.ZipFile(zip_path) as z:
        pre = _prefix(z.namelist())
        if pre is None:
            raise ValueError("this zip does not look like HERO TV (no herotv folder inside)")
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(pre):
                continue
            rel = info.filename[len(pre):]
            if not rel or not _safe(rel) or rel.startswith(SKIP_TOP) or rel in SKIP_FILES or "__pycache__" in rel:
                continue
            dest = Path(root) / rel
            data = z.read(info)
            if not dest.exists():
                act = "new"
            elif dest.read_bytes() == data:
                act = "same"
            elif rel in KEEP_AS_MINE:
                act = "keep-mine"
            else:
                act = "replace"
            out.append((info.filename, rel, act))
    return out


def apply(zip_path, root, now=None):
    """Install the zip into root. Returns {"replaced": n, "new": n, "same": n, "kept": [config names saved as .new], "backup": path}."""
    root = Path(root)
    items = plan(zip_path, root)
    res = {"replaced": 0, "new": 0, "same": 0, "kept": [], "backup": None}
    if not any(a in ("new", "replace", "keep-mine") for _, _, a in items):
        res["same"] = len(items)
        return res
    stamp = time.strftime("%Y-%m-%d-%H%M%S", time.localtime(now or time.time()))
    bdir = root / ".update-backup" / stamp
    with zipfile.ZipFile(zip_path) as z:
        for member, rel, act in items:
            dest = root / rel
            if act == "same":
                res["same"] += 1
                continue
            if act == "keep-mine":
                dest = dest.with_name(dest.name + ".new")
                res["kept"].append(rel.split("/", 1)[1])
            elif act == "replace":
                (bdir / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, bdir / rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".tmp-update")
            tmp.write_bytes(z.read(member))
            os.replace(tmp, dest)
            if act != "keep-mine":
                res["replaced" if act == "replace" else "new"] += 1
    if bdir.exists():
        res["backup"] = str(bdir)
    old = sorted(p for p in (root / ".update-backup").glob("*") if p.is_dir())
    for p in old[:-KEEP_BACKUPS]:
        shutil.rmtree(p, ignore_errors=True)
    return res


# ---------- is the built application (HERO-TV.exe) older than the program files next to it? ----------
STAMP = "app-build.txt"


def source_hash(root):
    import hashlib
    h = hashlib.sha256()
    for p in sorted(Path(root, "herotv").rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def write_stamp(root=None):
    """Called by Build-App.bat right after a successful build."""
    from .config import ROOT
    root = Path(root or ROOT)
    (root / STAMP).write_text(source_hash(root), encoding="utf-8")
    return (root / STAMP).read_text()


def app_is_stale(root=None):
    """True when the program files on disk changed since HERO-TV.exe was built (or it was never stamped)."""
    from .config import ROOT
    root = Path(root or ROOT)
    if not (root / "herotv" / "__init__.py").is_file():
        return False
    try:
        return (root / STAMP).read_text(encoding="utf-8").strip() != source_hash(root)
    except OSError:
        return True
