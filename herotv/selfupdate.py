"""Updates with one press: HERO TV asks GitHub (the public HERO TV page) whether a newer version is out, shows what
is new, and on "Install now" downloads the release zip and installs it the same way Update-HERO-TV.bat does -
then starts again by itself. Your videos, favorites, resume points and settings are never touched.

Only GitHub's own addresses are used, over verified HTTPS, and the zip must say it is exactly the version that
was offered (and carry the ready-made application) before anything is installed."""
import ast
import json
import hashlib
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__, config, net, updater

REPO = "trentnick99/Hero-tv"
LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RAW = f"https://api.github.com/repos/{REPO}/contents/herotv/whatsnew.py?ref={{tag}}"
WEB_LATEST = f"https://github.com/{REPO}/releases/latest"          # no API limit: GitHub answers with the newest tag
RAW_WEB = f"https://raw.githubusercontent.com/{REPO}/{{tag}}/herotv/whatsnew.py"
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


def _latest_from_web(timeout=20):
    """The newest release without GitHub's API: the releases page sends you on to the newest tag. Used when the API
    says no - it allows only 60 questions an hour per Internet address, and home internet that shares one address
    between many homes (T-Mobile, Starlink and other mobile/satellite internet) often uses those up."""
    req = urllib.request.Request(WEB_LATEST, headers={"User-Agent": UA}, method="HEAD")
    with net.urlopen(req, timeout=timeout) as r:
        final = r.geturl()
    m = re.search(r"/releases/tag/([^/?#]+)$", final or "")
    if not m:
        raise ValueError("GitHub did not name a newest version")
    tag = urllib.parse.unquote(m.group(1))
    name = f"HERO-TV-{tag}-windows.zip"
    return {"tag_name": tag, "html_url": final, "assets": [
        {"name": name, "size": 0, "browser_download_url": f"https://github.com/{REPO}/releases/download/{tag}/{name}"}]}


def _why(e):
    """A short, plain reason for a failed check."""
    if isinstance(e, urllib.error.HTTPError):
        if e.code in (403, 429):
            return "GitHub is limiting update checks from your Internet address right now - try again in an hour"
        return f"GitHub answered with error {e.code}"
    if isinstance(e, urllib.error.URLError):
        r = str(getattr(e, "reason", "") or e)
        if "CERTIFICATE" in r.upper():
            return ("a security certificate was refused - antivirus 'HTTPS scanning' / 'web shield' is the usual cause; "
                    "allow HERO TV in it")
        return f"no connection ({r[:80]})"
    return f"{e.__class__.__name__}: {str(e)[:80]}"


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


def _digest(asset):
    """GitHub's own SHA-256 of a release file ("sha256:<64 hex>" in the API), or "" when it does not say (the releases-page
    fallback has none: then the download is checked for size and content only, as before)."""
    d = str((asset or {}).get("digest") or "").strip().lower()
    return d[7:] if re.fullmatch(r"sha256:[0-9a-f]{64}", d) else ""


def check(force=False, gj=None, gt=None, now=None):
    """What GitHub says. Remembered for a few hours. Never raises."""
    now = now or time.time()
    with _lock:
        if not force and _state["checked"] and now - _state["checked"] < CHECK_EVERY:
            return status()
    web = gj is None                                   # tests pass their own fake GitHub
    gj, gt = gj or _get_json, gt or _get_text
    try:
        try:
            d = gj(LATEST)
        except Exception as api_err:
            if not web:
                raise
            try:
                d = _latest_from_web()
            except Exception:
                raise api_err
        tag = str(d.get("tag_name") or "")
        latest = tag.lstrip("vV")
        asset = next((a for a in d.get("assets") or [] if str(a.get("name", "")).lower().endswith("-windows.zip")), None)
        info = {"latest": latest, "tag": tag, "page": d.get("html_url") or f"https://github.com/{REPO}/releases",
                "zip_url": asset.get("browser_download_url") if asset else "", "size": int(asset.get("size") or 0) if asset else 0,
                "sha256": _digest(asset),
                "published": d.get("published_at") or "", "notes": []}
        if updater.version_tuple(latest) > updater.version_tuple(__version__):
            for url in (RAW.format(tag=tag), RAW_WEB.format(tag=tag)):
                try:
                    info["notes"] = notes_from_source(gt(url), latest)
                    break
                except Exception:
                    continue
        err = ""
    except Exception as e:
        info, err = None, f"Could not check GitHub for updates: {_why(e)}."
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


def download(url, dest, size=0, opener=None, sha256=""):
    """Save the release zip. Only GitHub addresses; size checked while it streams, and its SHA-256 against the one GitHub
    published for the file when there is one (a damaged or swapped download is refused and deleted)."""
    if not url.startswith(DOWNLOAD_HOSTS):
        raise ValueError("refusing to download from an unexpected address")
    opener = opener or (lambda u: net.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60))
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    got = 0
    h = hashlib.sha256()
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
            h.update(chunk)
            _state["done"] = got
    if size and got != size:
        tmp.unlink(missing_ok=True)
        raise ValueError(f"the download was incomplete ({got} of {size} bytes) - try again")
    if sha256 and h.hexdigest() != sha256.lower():
        tmp.unlink(missing_ok=True)
        raise ValueError("the download does not match the checksum GitHub published for it, so it was not installed - try again")
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
            z = download(info["zip_url"], root / ".update-download" / f"HERO-TV-{info['tag']}-windows.zip", info["size"], opener, info.get("sha256", ""))
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
