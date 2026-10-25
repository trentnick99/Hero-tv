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
SKIP_TOP = ("data/", "build-app/", ".update-backup/", ".update-stage/")
APP_TOP = ("_internal/",)                       # the built application: only installed from a zip that contains it
APP_FILES = {"HERO-TV.exe", "app-build.txt"}
STAGE = ".update-stage"
RUNNING = {"Update-HERO-TV.bat"}                  # in use while updating: saved as .new and swapped in at the next start
KEEP_BACKUPS = 3


def find_zip(arg=None, downloads=None):
    """The zip to install: the one given, else the newest HERO TV zip in Downloads
    (hero-tv-windows.zip from the chat, or HERO-TV-v1.2.0-windows.zip from GitHub)."""
    if arg:
        return Path(arg) if os.path.isfile(arg) else None
    d = Path(downloads) if downloads else Path.home() / "Downloads"
    try:
        found = [d / n for n in os.listdir(d) if n.lower().endswith(".zip") and "hero-tv" in n.lower()]
    except OSError:
        found = []
    found.sort(key=os.path.getmtime, reverse=True)
    return found[0] if found else None


def version_tuple(v):
    import re
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0"))[:3]) or (0,)


def zip_info(zip_path):
    """{"version": "1.2.0" or None, "app": True when the zip carries a built HERO-TV.exe}."""
    import re
    with zipfile.ZipFile(zip_path) as z:
        pre = _prefix(z.namelist())
        if pre is None:
            raise ValueError("this zip does not look like HERO TV (no herotv folder inside)")
        m = re.search(r'__version__\s*=\s*"([^"]+)"', z.read(pre + "herotv/__init__.py").decode("utf-8", "replace"))
        return {"version": m.group(1) if m else None, "app": (pre + "HERO-TV.exe") in z.namelist()}


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
    """[(member, relative path, action)] where action is 'new', 'same', 'replace', 'keep-mine' (saved as .new), or 'app'
    (a file of the built application, staged and swapped in once HERO TV has closed)."""
    out = []
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        pre = _prefix(names)
        if pre is None:
            raise ValueError("this zip does not look like HERO TV (no herotv folder inside)")
        has_app = (pre + "HERO-TV.exe") in names
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(pre):
                continue
            rel = info.filename[len(pre):]
            if not rel or not _safe(rel) or rel.startswith(SKIP_TOP) or "__pycache__" in rel:
                continue
            is_app = rel in APP_FILES or rel.startswith(APP_TOP)
            if is_app and not has_app:
                continue
            dest = Path(root) / rel
            data = z.read(info)
            if not dest.exists():
                act = "app" if is_app else "new"
            elif dest.read_bytes() == data:
                act = "same"
            elif is_app:
                act = "app"
            elif rel in KEEP_AS_MINE:
                act = "keep-mine"
            elif rel in RUNNING:
                act = "deferred"
            else:
                act = "replace"
            out.append((info.filename, rel, act))
    if any(a == "app" for _, _, a in out):        # the exe needs its whole _internal folder: stage the full set
        out = [(m, r, "app" if (r in APP_FILES or r.startswith(APP_TOP)) else a) for m, r, a in out]
    return out


def apply(zip_path, root, now=None):
    """Install the zip into root. Returns {"replaced": n, "new": n, "same": n, "kept": [config names saved as .new], "backup": path}."""
    root = Path(root)
    items = plan(zip_path, root)
    res = {"replaced": 0, "new": 0, "same": 0, "kept": [], "backup": None, "staged": 0}
    if not any(a in ("new", "replace", "keep-mine", "app", "deferred") for _, _, a in items):
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
            if act == "app":                       # the running program cannot be overwritten: stage it for finish_swap()
                dest = root / STAGE / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(member))
                res["staged"] += 1
                continue
            if act in ("keep-mine", "deferred"):
                dest = dest.with_name(dest.name + ".new")
                if act == "keep-mine":
                    res["kept"].append(rel.split("/", 1)[1])
            elif act == "replace":
                (bdir / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, bdir / rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".tmp-update")
            tmp.write_bytes(z.read(member))
            os.replace(tmp, dest)
            if act not in ("keep-mine", "deferred"):
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


# ---------- swapping in a new HERO-TV.exe once the old one has closed ----------
def staged(root):
    return (Path(root) / STAGE / "HERO-TV.exe").is_file() or any((Path(root) / STAGE).glob("*"))


def finish_swap(root, wait_pid=None, timeout=60, now=None):
    """Copy the staged application files over the old ones (the old exe and _internal are moved to .update-backup
    first). Waits for process wait_pid to end. Returns the number of files installed."""
    root = Path(root)
    stage = root / STAGE
    if not stage.is_dir():
        return 0
    if wait_pid:
        end = time.time() + timeout
        while time.time() < end and _alive(wait_pid):
            time.sleep(0.5)
    bdir = root / ".update-backup" / (time.strftime("%Y-%m-%d-%H%M%S", time.localtime(now or time.time())) + "-app")
    for name in ("HERO-TV.exe", "_internal"):
        if (stage / name).exists() and (root / name).exists():
            bdir.mkdir(parents=True, exist_ok=True)
            for _ in range(20):                     # antivirus may hold the file for a moment
                try:
                    shutil.move(str(root / name), str(bdir / name))
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                raise OSError(f"{name} is still in use - close HERO TV and run the update again")
    n = 0
    for f in sorted(stage.rglob("*")):
        if f.is_file():
            dest = root / f.relative_to(stage)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            n += 1
    return n


def clean_stage(root):
    """Remove a finished staging folder (called when HERO TV starts; ignored while files are still in use)."""
    st = Path(root) / STAGE
    if st.is_dir() and (Path(root) / "HERO-TV.exe").is_file():
        shutil.rmtree(st, ignore_errors=True)


def _alive(pid):
    if os.name == "nt":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))       # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259                                                 # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def apply_deferred(root):
    """Swap in program files that were in use during the update (Update-HERO-TV.bat). Called when HERO TV starts."""
    n = 0
    for name in RUNNING:
        new = Path(root) / (name + ".new")
        if new.is_file():
            try:
                os.replace(new, Path(root) / name)
                n += 1
            except OSError:
                pass
    return n
