"""Locate ffmpeg/ffprobe (and run them quietly) on Linux, macOS and Windows."""
import glob
import os
import shutil
import subprocess
import sys

from .config import ROOT

IS_WIN = os.name == "nt"
# Stops a black console window from flashing every time ffprobe/ffmpeg is started on Windows.
HIDE = {"creationflags": 0x08000000} if IS_WIN else {}
_cache = {}


def _exe(name):
    return name + ".exe" if IS_WIN and not name.endswith(".exe") else name


def _candidate_dirs():
    env = os.environ.get("HEROTV_FFMPEG_DIR")
    if env:
        yield env
    for sub in ("ffmpeg/bin", "ffmpeg", "tools/ffmpeg/bin", "tools"):
        yield str(ROOT / sub)
    if IS_WIN:
        local = os.environ.get("LOCALAPPDATA", "")
        prog = os.environ.get("ProgramData", r"C:\ProgramData")
        home = os.path.expanduser("~")
        yield os.path.join(local, "Microsoft", "WinGet", "Links")          # winget shim folder
        for pat in (os.path.join(local, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "**", "bin"),
                    os.path.join(prog, "chocolatey", "lib", "ffmpeg", "tools", "**", "bin")):
            yield from glob.glob(pat, recursive=True)
        yield os.path.join(prog, "chocolatey", "bin")
        yield os.path.join(home, "scoop", "shims")
        yield r"C:\ffmpeg\bin"
        yield r"C:\Program Files\ffmpeg\bin"


def find_tool(name):
    """Full path to ffmpeg / ffprobe, or None. PATH first, then the usual Windows install places."""
    if name in _cache:
        return _cache[name]
    found = shutil.which(name)
    if not found:
        for d in _candidate_dirs():
            p = os.path.join(d, _exe(name))
            if os.path.isfile(p):
                found = p
                break
    _cache[name] = found
    return found


def forget():
    _cache.clear()


def run(cmd, **kw):
    """subprocess.run with UTF-8 decoding (Windows' default code page garbles non-English titles) and no popup window."""
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("encoding", "utf-8")
    kw.setdefault("errors", "replace")
    for k, v in HIDE.items():
        kw.setdefault(k, v)
    return subprocess.run(cmd, **kw)


def python_ok():
    return sys.version_info >= (3, 9)
