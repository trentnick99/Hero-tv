"""Updates with one press: HERO TV asks GitHub (the public HERO TV page) whether a newer version is out, shows what
is new, and on "Install now" downloads the release zip and installs it the same way Update-HERO-TV.bat does -
then starts again by itself. Your videos, favorites, resume points and settings are never touched.

Only GitHub's own addresses are used, over verified HTTPS, and the zip must say it is exactly the version that
was offered (and carry the ready-made application) before anything is installed."""
import ast
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from . import __version__, config, net, updater

REPO = "trentnick99/Hero-tv"
LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RAW = f"https://api.github.com/repos/{REPO}/contents/herotv/whatsnew.py?ref={{tag}}"
DOWNLOAD_HOSTS = ("https://github.com/", "https://objects.githubusercontent.com/", "https://release-assets.githubusercontent.com/")
CHECK_EVERY = 6 * 3600
MAX_ZIP = 400 * 1024 ** 2
UA = f"HERO-TV/{__version__} (+https://github.com/{REPO})"

_lock = threading.Lock()
_state = {"checked": 0, "info": None, "error": "", "phase": "", "done": 0, "total": 0}


def enabled():
    try:
        d = json.loads(config.settings_file().read_text(encoding="utf-8-sig"))
        return d.get("auto_update", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with net.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _get_text(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github.raw"})
    with net.urlopen(req, timeout=timeout) as r:
        return r.read(512_000).decode("utf-8", "replace")


def notes_from_source(src, version):
    """The 'What's new' lines for one version, read from a whatsnew.py without running it."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "NOTES" for t in node.targets):
            try:
                notes = ast.literal_eval(node.value)
            except ValueError:
                return []
            lines = notes.get(version) if isinstance(notes, dict) else None
            return [str(x) for x in lines][:8] if isinstance(lines, list) else []
    return []


def check(force=False, gj=None, gt=None, now=None):
    """What GitHub says. Remembered for a few hours. Never raises."""
    now = now or time.time()
    with _lock:
        if not force and _state["checked"] and now - _state["checked"] < CHECK_EVERY:
            return status()
    gj, gt = gj or _get_json, gt or _get_text
    try:
        d = gj(LATEST)
        tag = str(d.get("tag_name") or "")
        latest = tag.lstrip("vV")
        asset = next((a for a in d.get("assets") or [] if str(a.get("name", "")).lower().endswith("-windows.zip")), None)
        info = {"latest": latest, "tag": tag, "page": d.get("html_url") or f"https://github.com/{REPO}/releases",
                "zip_url": asset.get("browser_download_url") if asset else "", "size": int(asset.get("size") or 0) if asset else 0,
                "published": d.get("published_at") or "", "notes": []}
        if updater.version_tuple(latest) > updater.version_tuple(__version__):
            try:
                info["notes"] = notes_from_source(gt(RAW.format(tag=tag)), latest)
            except Exception:
                pass
        err = ""
    except Exception as e:
        info, err = None, f"Could not reach GitHub ({e.__class__.__name__}). Check the Internet connection."
    with _lock:
        _state["checked"] = now
        if info is not None:
            _state["info"] = info
        _state["error"] = err
    return status()


def status():
    info = _state["info"] or {}
    latest = info.get("latest") or ""
    newer = bool(latest) and updater.version_tuple(latest) > updater.version_tuple(__version__) and bool(info.get("zip_url"))
    return {"current": __version__, "latest": latest, "available": newer, "notes": info.get("notes") or [] if newer else [],
            "size": info.get("size", 0), "page": info.get("page", ""), "checked": int(_state["checked"]), "error": _state["error"],
            "auto": enabled(), "phase": _state["phase"], "done": _state["done"], "total": _state["total"],
            "can_install": can_install()}


def can_install():
    """Only the ready-made application installs itself (a copy run from Python source updates with the .bat)."""
    return bool(getattr(sys, "frozen", False)) or os.environ.get("HEROTV_SELFUPDATE_TEST") == "1"


def download(url, dest, size=0, opener=None):
    """Save the release zip. Only GitHub addresses; size checked while it streams."""
    if not url.startswith(DOWNLOAD_HOSTS):
        raise ValueError("refusing to download from an unexpected address")
    opener = opener or (lambda u: net.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60))
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    got = 0
    with opener(url) as r, open(tmp, "wb") as fh:
        final = getattr(r, "geturl", lambda: url)()
        if not str(final).startswith(DOWNLOAD_HOSTS):
            raise ValueError("the download was sent to an unexpected address")
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            got += len(chunk)
            if got > MAX_ZIP:
                raise ValueError("the download is far bigger than expected")
            fh.write(chunk)
            _state["done"] = got
    if size and got != size:
        tmp.unlink(missing_ok=True)
        raise ValueError(f"the download was incomplete ({got} of {size} bytes) - try again")
    os.replace(tmp, dest)
    return dest


def install(root=None, opener=None, spawn=None):
    """Download the offered version and hand over to the updater (a separate process: it closes this HERO TV,
    swaps the files and starts the new one). Runs in the background; progress is in status()."""
    st = status()
    if not st["available"]:
        raise ValueError("You already have the newest HERO TV.")
    if not can_install():
        raise ValueError("This copy runs from Python source - update it with Update-HERO-TV.bat.")
    if _state["phase"] in ("downloading", "installing"):
        raise ValueError("The update is already on its way.")
    info = dict(_state["info"])
    root = Path(root or config.ROOT)

    def run():
        try:
            _state.update(phase="downloading", done=0, total=info["size"], error="")
            z = download(info["zip_url"], root / ".update-download" / f"HERO-TV-{info['tag']}-windows.zip", info["size"], opener)
            zi = updater.zip_info(z)
            if zi["version"] != info["latest"]:
                raise ValueError(f"the zip says it is version {zi['version']}, not {info['latest']}")
            if getattr(sys, "frozen", False) and not zi["app"]:
                raise ValueError("the zip does not contain the ready-made application")
            _state["phase"] = "installing"
            (spawn or _spawn)(z, root)
        except Exception as e:
            _state.update(phase="failed", error=f"The update did not install: {e}")
    threading.Thread(target=run, daemon=True, name="self-update").start()
    return status()


def _spawn(zip_path, root):
    """Start 'HERO-TV.exe self-update <zip>' on its own: it outlives this process, which it closes."""
    exe = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "herotv"]
    env = dict(os.environ, HEROTV_RESTART_NO_BROWSER="1")
    flags = (0x00000008 | 0x00000200) if os.name == "nt" else 0          # detached, own process group
    subprocess.Popen(exe + ["self-update", str(zip_path)], cwd=str(root), env=env, close_fds=True,
                     creationflags=flags, start_new_session=os.name != "nt")


def last_error_file():
    return config.settings_file().parent / "update-error.txt"


def take_last_error():
    """A message left by an update that failed after HERO TV was closed (shown once at the next start)."""
    f = last_error_file()
    try:
        text = f.read_text(encoding="utf-8").strip()
        f.unlink()
        return text
    except OSError:
        return ""


def watch_forever(every=CHECK_EVERY):
    """Look for a new version soon after start and every few hours (when switched on)."""
    def loop():
        time.sleep(20)
        while True:
            if enabled():
                check(force=True)
            time.sleep(every)
    threading.Thread(target=loop, daemon=True, name="update-check").start()
