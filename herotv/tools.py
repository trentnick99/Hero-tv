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


# ---------- converting video to standard H.264: the graphics card when it can, else the processor ----------
_ENC = {}
HW_ENCODERS = (
    ("h264_nvenc", ["-preset", "p5", "-rc", "vbr", "-cq", "21", "-b:v", "0"]),          # NVIDIA
    ("h264_qsv", ["-preset", "medium", "-global_quality", "22"]),                     # Intel
    ("h264_amf", ["-quality", "balanced", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22"]),  # AMD
)


CPU_H264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]


def use_processor(ffmpeg):
    """Stop using the graphics card for this ffmpeg (it made a broken copy). Returns the processor's arguments."""
    _ENC[ffmpeg] = list(CPU_H264)
    return list(CPU_H264)


def h264_encoder(ffmpeg, run=None):
    """ffmpeg arguments that make standard 8-bit H.264: with the PC's graphics card (NVIDIA / Intel / AMD) when one
    really works here - several times faster - else libx264 on the processor. Checked once per ffmpeg."""
    if ffmpeg in _ENC:
        return list(_ENC[ffmpeg])
    run = run or subprocess.run
    chosen = list(CPU_H264)
    for name, opts in HW_ENCODERS:
        try:
            r = run([ffmpeg, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25", "-frames:v", "10",
                     "-vf", "format=yuv420p", "-c:v", name] + opts + ["-f", "null", "-"],
                    capture_output=True, timeout=30, **HIDE)
        except (OSError, subprocess.SubprocessError):
            continue
        if getattr(r, "returncode", 1) == 0:
            chosen = ["-vf", "format=yuv420p", "-c:v", name] + opts
            break
    _ENC[ffmpeg] = chosen
    return list(chosen)
