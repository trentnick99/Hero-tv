"""Locate ffmpeg/ffprobe (and run them quietly) on Linux, macOS and Windows."""
import glob
import os
import re
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


class FFResult:
    def __init__(self, returncode, errors):
        self.returncode, self.errors = returncode, errors


def run_ffmpeg(cmd, runtime=0, report=None, low=False):
    """Run an ffmpeg conversion. Keeps ffmpeg's last error lines (so a failure can say why), and calls
    report("  40% done") every 10% for long videos. Progress still shows in a console window.
    low=True runs it at low priority (background work while someone may be watching)."""
    import re as _re
    import sys as _sys
    import threading as _th
    kw = dict(HIDE)
    if low:
        if IS_WIN:
            kw["creationflags"] = kw.get("creationflags", 0) | 0x00004000      # BELOW_NORMAL_PRIORITY_CLASS
        elif shutil.which("nice"):
            cmd = ["nice", "-n", "10"] + list(cmd)
    try:
        pr = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **kw)
    except OSError as e:
        return FFResult(1, [str(e)])
    errors, state = [], {"step": 0}
    from . import work
    task = work.current()                                   # the Settings progress bar for this job, if it has one

    def line(t):
        t = t.strip()
        if not t:
            return
        m = _re.search(r"time=(\d+):(\d+):([\d.]+)", t)
        if m and t.startswith(("frame=", "size=")):
            if runtime > 0:
                work.percent(task, (int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])) / runtime)
            if report and runtime > 300:
                done = (int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])) / runtime
                step = int(done * 10)
                if 1 <= step <= 9 and step > state["step"]:
                    state["step"] = step
                    report(f"  {step * 10}% done")
            return
        errors.append(t[:300])
        del errors[:-12]

    def pump():
        buf = b""
        con = getattr(_sys, "__stderr__", None)
        while True:
            ch = pr.stderr.read(4096)
            if not ch:
                break
            try:
                if con:
                    con.write(ch.decode("utf-8", "replace"))
                    con.flush()
            except (OSError, ValueError, AttributeError):
                pass
            buf += ch
            parts = _re.split(rb"[\r\n]", buf)
            buf = parts.pop()
            for x in parts:
                line(x.decode("utf-8", "replace"))
        line(buf.decode("utf-8", "replace"))
    t = _th.Thread(target=pump, daemon=True)
    t.start()
    rc = pr.wait()
    t.join(10)
    try:
        pr.stderr.close()
    except OSError:
        pass
    return FFResult(rc, errors)


SOUND_ERR = re.compile(r"\[aist#|\[dec:(?:ac3|eac3|dts|dca|truehd|aac|mp3|mp2|opus|vorbis|flac|pcm\w*)\b")


def sound_trouble(errors):
    """Do ffmpeg's error lines say the sound track (not the picture) is damaged?"""
    return any(SOUND_ERR.search(e) for e in errors or [])


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
