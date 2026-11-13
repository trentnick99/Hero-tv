"""Streaming to phones: any video, any format, at a size that suits the connection.

An iPhone can only play some files as they are (.mp4 with H.264/H.265 and AAC or Dolby sound). Everything else - .mkv
files, DTS sound, a 30 Mbit/s Blu-ray copy on mobile data - is converted while you watch into HLS: the streaming
format iPhones, iPads and Android phones play natively (it is what Netflix and YouTube send to phones too).

How it works
  The video is cut into pieces of SEG seconds on a fixed grid (piece n starts at n*SEG). The phone first gets the list
  of every piece (index.m3u8), so it knows the whole length and can jump anywhere; then it asks for pieces one by one.
  A piece that is not ready yet starts an ffmpeg at exactly that point, which then makes the following pieces in order.
  Jumping far ahead or back starts a new ffmpeg there; the grid is the same every time, so pieces from different runs
  fit together. ffmpeg stops when it is LEAD pieces ahead of the phone (no point converting a whole film nobody is
  watching) and starts again when the phone gets within REFILL pieces of the end of what is ready.

  Pieces are kept in herotv-stream next to the database while a video is watched, and removed a few minutes after
  the phone stops asking. At most MAX_RUNNING conversions run at once; a new one stops the least recently used.
"""
import math
import os
import shutil
import subprocess
import threading
import time

from . import tools

SEG = 4.0                     # seconds per piece: short pieces start and jump quickly
LEAD = 45                     # pieces made ahead of the phone (3 minutes) before ffmpeg takes a break
REFILL = 15                   # ...and it starts again when the phone is within this many pieces (1 minute) of the end
AHEAD = 8                     # a piece this close ahead of the running conversion is waited for, not restarted for
KEEP_BEHIND = 150             # pieces kept behind the phone (10 minutes back) for a quick rewind
IDLE_STOP = 45                # seconds without a request before a conversion stops
IDLE_DROP = 600               # ...and before its pieces are deleted
MAX_RUNNING = 2
WAIT = 40                     # seconds a request waits for its piece (the first one of a run takes longest)

QUALITIES = {   # name, picture height, video kbit/s, sound kbit/s
    "high": {"name": "High (1080p)", "h": 1080, "v": 6000, "a": 160},
    "medium": {"name": "Medium (720p)", "h": 720, "v": 3000, "a": 128},
    "low": {"name": "Low (480p)", "h": 480, "v": 1200, "a": 96},
    "saver": {"name": "Data saver (360p)", "h": 360, "v": 600, "a": 64},
}
CHOICES = ["auto", "original"] + list(QUALITIES)
CHOICE_NAMES = dict({"auto": "Automatic", "original": "Original file"}, **{k: v["name"] for k, v in QUALITIES.items()})
AWAY_BUDGET = 3500            # kbit/s a phone away from home is sent as the file itself; above that it is converted

_sessions = {}
_lock = threading.Lock()
_janitor = {"started": False}
_HIDE_LOW = dict(tools.HIDE)
if tools.IS_WIN:
    _HIDE_LOW["creationflags"] = _HIDE_LOW.get("creationflags", 0) | 0x00004000       # below normal: the TV comes first


def folder(cfg):
    return os.path.splitext(cfg.db_path)[0] + "-stream"


# ---------------------------------------------------------------- which encoder

_enc = {}


def _enc_opts(name, v, a_max):
    """Bit-rate-limited H.264 settings for one encoder."""
    rate = ["-b:v", f"{v}k", "-maxrate", f"{int(v * 1.3)}k", "-bufsize", f"{v * 2}k"]
    if name == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-profile:v", "high", "-forced-idr", "1"] + rate
    if name == "h264_qsv":
        return ["-c:v", "h264_qsv", "-preset", "veryfast", "-profile:v", "high"] + rate
    if name == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "speed", "-rc", "vbr_peak", "-profile:v", "high"] + rate
    return ["-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high", "-level:v", "4.1"] + rate


def _pix(name):
    return "nv12" if name == "h264_qsv" else "yuv420p"


def encoder(exe, run=None, tmp=None):
    """The H.264 encoder used for streaming: the graphics card's when it really works here AND cuts pieces exactly on
    the grid (checked once with a 9-second test), else libx264 on the processor."""
    if exe in _enc:
        return _enc[exe]
    run = run or tools.run
    chosen = "libx264"
    base = tmp or os.path.join(os.path.expanduser("~"), ".herotv-enc-test")
    for name, _opts in tools.HW_ENCODERS:
        d = os.path.join(base, name)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
        try:
            r = run([exe, "-hide_banner", "-v", "error", "-nostdin", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=9",
                     "-vf", f"format={_pix(name)}"] + _enc_opts(name, 800, 64) +
                    ["-force_key_frames", f"expr:gte(t,n_forced*{SEG:g})", "-f", "hls", "-hls_time", f"{SEG:g}",
                     "-hls_list_size", "0", "-hls_segment_filename", os.path.join(d, "%d.ts"), os.path.join(d, "t.m3u8")],
                    timeout=40)
            ok = getattr(r, "returncode", 1) == 0 and _even_pieces(os.path.join(d, "t.m3u8"))
        except (OSError, subprocess.SubprocessError):
            ok = False
        shutil.rmtree(d, ignore_errors=True)
        if ok:
            chosen = name
            break
    shutil.rmtree(base, ignore_errors=True)
    _enc[exe] = chosen
    return chosen


def _even_pieces(m3u8):
    """True when a 9-second test came out as pieces of SEG, SEG and the rest (keyframes where they were asked for)."""
    try:
        lines = open(m3u8, encoding="utf-8").read().splitlines()
    except OSError:
        return False
    durs = [float(x[8:].split(",")[0]) for x in lines if x.startswith("#EXTINF:")]
    return len(durs) == 3 and all(abs(d - SEG) < 0.2 for d in durs[:2])


# ---------------------------------------------------------------- what to send

def source(conn, mid):
    """Everything a conversion needs about one video, or None when it is gone."""
    from . import library, prepare
    r = conn.execute("SELECT id,path,runtime_s,height,size,vcodec,acodec,vfmt,atracks FROM media WHERE id=? AND available=1", (mid,)).fetchone()
    if r is None:
        return None
    d = prepare.delivery(conn, mid, "browser")
    if d is None or not os.path.isfile(d[0]):
        return None
    path = d[0]
    audio = 0
    if os.path.normcase(path) == os.path.normcase(r["path"] or ""):       # the original: pick the sound in your language
        toks = [t for t in (r["atracks"] or "").split(",") if t and t != "-"]
        pref = library.pref_lang()
        codes = [t.rstrip("*") for t in toks]
        if pref and pref in codes:
            audio = codes.index(pref)
        elif any(t.endswith("*") for t in toks):
            audio = next(i for i, t in enumerate(toks) if t.endswith("*"))
    size = os.path.getsize(path)
    run_s = float(r["runtime_s"] or 0)
    kbps = int(size * 8 / run_s / 1000) if run_s > 0 else 0
    copy = os.path.normcase(path) != os.path.normcase(r["path"] or "")
    ext = os.path.splitext(path)[1].lower()
    vcodec = "h264" if copy else (r["vcodec"] or "")
    # H.265 plays on iPhones only when the file is tagged one particular way, which cannot be checked cheaply: convert it
    ok = vcodec == "h264" and library.phone_ok(path, vcodec, "aac" if copy else r["acodec"], "" if copy else (r["vfmt"] or ""))
    return {"id": r["id"], "path": path, "runtime": run_s, "height": int(r["height"] or 0), "kbps": kbps, "audio": audio,
            "phone_ok": ok, "ext": ext}


def plan(src, quality):
    """The picture height and bit rates for this video at this quality: never bigger or sharper than the file itself."""
    q = QUALITIES[quality]
    h = q["h"] if not src["height"] else min(q["h"], src["height"])
    h -= h % 2
    v = q["v"]
    if src["kbps"]:
        v = min(v, max(400, int((src["kbps"] - q["a"]) * 1.15)))       # converting never makes a small file bigger
    return {"h": max(144, h), "v": v, "a": q["a"]}


def choose(src, want="auto", hls=True, away=False):
    """('direct', why) to send the file as it is, or (quality, why) to convert it. hls=False: this player cannot take
    HLS (a PC browser), so it always gets the file as before."""
    if want not in CHOICES:
        want = "auto"
    if not hls:
        return "direct", "This player gets the file itself."
    if not src["phone_ok"]:
        if want in QUALITIES:
            return want, "Converted: this file's format does not play on phones."
        return ("medium" if away else "high"), "Converted: this file's format does not play on phones."
    if want == "original":
        return "direct", "The file itself."
    if want == "auto":
        if not away or src["kbps"] <= AWAY_BUDGET:
            return "direct", "The file itself (it plays on phones and suits this connection)."
        return "medium", "Converted to 720p: the file is too big for watching away from home."
    q = QUALITIES[want]
    if src["kbps"] and src["kbps"] <= q["v"] + q["a"] and (not src["height"] or src["height"] <= q["h"]):
        return "direct", f"The file itself: it is already no bigger than {q['name']}."
    return want, f"Converted to {q['name']}."


def pieces(runtime):
    return max(1, int(math.ceil(max(0.1, runtime) / SEG - 1e-6)))


def playlist(runtime, query=""):
    """The list of every piece, so the phone knows the length and can jump anywhere."""
    n = pieces(runtime)
    tail = f"?{query}" if query else ""
    out = ["#EXTM3U", "#EXT-X-VERSION:3", f"#EXT-X-TARGETDURATION:{int(math.ceil(SEG))}", "#EXT-X-MEDIA-SEQUENCE:0",
           "#EXT-X-PLAYLIST-TYPE:VOD", "#EXT-X-INDEPENDENT-SEGMENTS"]
    for i in range(n):
        d = SEG if i < n - 1 else max(0.1, runtime - SEG * (n - 1))
        out += [f"#EXTINF:{d:.3f},", f"{i}.ts{tail}"]
    out.append("#EXT-X-ENDLIST")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- one video at one quality

class Session:
    def __init__(self, cfg, src, quality, exe, gain_db=0.0, popen=None, enc=None):
        self.cfg = cfg
        self.key = f"{src['id']}-{quality}"
        self.src, self.quality, self.exe, self.gain = src, quality, exe, gain_db
        self.dir = os.path.join(folder(cfg), self.key)
        os.makedirs(self.dir, exist_ok=True)
        self.total = pieces(src["runtime"])
        self.proc = None
        self.run_start = self.run_end = 0
        self.want = 0                       # the piece the phone asked for last (its place in the film, roughly)
        self.touched = time.monotonic()
        self.lock = threading.RLock()
        self.popen = popen or subprocess.Popen
        self.enc = enc
        self.fails = 0

    # -- pieces on disk
    def file(self, n):
        return os.path.join(self.dir, f"{int(n)}.ts")

    def have(self, n):
        return os.path.isfile(self.file(n))

    def next_missing(self, n):
        while n < self.total and self.have(n):
            n += 1
        return n

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    # -- ffmpeg
    def command(self, start, end):
        p = plan(self.src, self.quality)
        enc = self.enc or encoder(self.exe, tmp=os.path.join(folder(self.cfg), "_enc"))
        t0 = start * SEG
        af = ["-af", f"volume={self.gain:.1f}dB,alimiter=limit=0.9:level=disabled"] if abs(self.gain) >= 0.5 else []
        head = [self.exe, "-hide_banner", "-loglevel", "error", "-nostdin"]
        if t0 > 0:
            head += ["-ss", f"{t0:.3f}"]
        cmd = head + ["-i", self.src["path"]]
        if end < self.total:                # stop right before a piece that is already there
            cmd += ["-t", f"{(end - start) * SEG:.3f}"]
        cmd += ["-map", "0:v:0", "-map", f"0:a:{self.src['audio']}?", "-sn", "-dn", "-max_muxing_queue_size", "2048",
                "-vf", f"scale=-2:{p['h']}:flags=bicubic,format={_pix(enc)}"] + _enc_opts(enc, p["v"], p["a"])
        cmd += ["-force_key_frames", f"expr:gte(t,n_forced*{SEG:g})",
                "-c:a", "aac", "-ac", "2", "-ar", "48000", "-b:a", f"{p['a']}k"] + af
        cmd += ["-f", "hls", "-hls_time", f"{SEG:g}", "-hls_list_size", "0", "-hls_segment_type", "mpegts",
                "-hls_flags", "temp_file+independent_segments", "-start_number", str(start),
                "-hls_segment_filename", os.path.join(self.dir, "%d.ts"), "-output_ts_offset", f"{t0:.3f}",
                os.path.join(self.dir, f"run{start}.m3u8")]
        return cmd

    def start(self, n):
        """Convert from piece n up to the next piece that is already there (or the end)."""
        with self.lock:
            self.stop()
            end = n + 1
            while end < self.total and not self.have(end):
                end += 1
            _make_room(self)
            self.run_start, self.run_end = n, end
            try:
                self.proc = self.popen(self.command(n, end), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, **_HIDE_LOW)
            except OSError:
                self.proc = None
                self.fails += 1

    def stop(self):
        with self.lock:
            p, self.proc = self.proc, None
        if p is not None and p.poll() is None:
            try:
                p.kill()
                p.wait(timeout=5)
            except Exception:
                pass

    # -- a request
    def get(self, n, wait=WAIT):
        """The file of piece n once it is ready, or None (out of range, or it could not be made in time)."""
        if not 0 <= n < self.total:
            return None
        with self.lock:
            self.touched = time.monotonic()
            self.want = n
            if self.have(n):
                return self.file(n)
            ahead_ok = self.running() and self.run_start <= n < self.run_end and n <= self.next_missing(self.run_start) + AHEAD
            if not ahead_ok:
                self.start(n)               # nothing is making it soon: start there (the phone jumped)
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if self.have(n):
                with self.lock:
                    self.touched = time.monotonic()
                    self.fails = 0
                return self.file(n)
            with self.lock:
                if not self.running():
                    if self.have(n):
                        return self.file(n)
                    if self.fails > 3:
                        return None
                    self.fails += 1          # ffmpeg ended without this piece: one more go from here
                    self.start(n)
            time.sleep(0.1)
        return None

    def tidy(self, now):
        """Called every second: pause, resume, forget."""
        with self.lock:
            idle = now - self.touched
            if idle > IDLE_STOP:
                self.stop()
                return idle > IDLE_DROP
            ready_to = self.next_missing(self.want)
            if self.running() and ready_to - self.want > LEAD:
                self.stop()                 # far enough ahead: take a break
            elif not self.running() and ready_to < self.total and ready_to - self.want <= REFILL and self.fails <= 3:
                self.start(ready_to)        # the phone is catching up: make more
            if self.want > KEEP_BEHIND:
                for n in range(max(0, self.want - KEEP_BEHIND - 40), self.want - KEEP_BEHIND):
                    try:
                        os.remove(self.file(n))
                    except OSError:
                        pass
        return False

    def drop(self):
        self.stop()
        shutil.rmtree(self.dir, ignore_errors=True)


def _make_room(keep):
    """At most MAX_RUNNING conversions at once: the one used least recently stops for the new one."""
    with _lock:
        busy = [s for s in _sessions.values() if s is not keep and s.running()]
    busy.sort(key=lambda s: s.touched)
    while len(busy) >= MAX_RUNNING:
        busy.pop(0).stop()


def session(cfg, src, quality, exe, gain_db=0.0):
    key = f"{src['id']}-{quality}"
    with _lock:
        s = _sessions.get(key)
        if s is None or s.src["path"] != src["path"] or abs(s.src["runtime"] - src["runtime"]) > 1:
            if s is not None:
                s.drop()
            s = _sessions[key] = Session(cfg, src, quality, exe, gain_db)
    _start_janitor()
    return s


def find(key):
    with _lock:
        return _sessions.get(key)


def active():
    """How many conversions are running (keeps the PC awake, shows in Settings)."""
    with _lock:
        return sum(1 for s in _sessions.values() if s.running())


def stop_all(cfg=None):
    with _lock:
        ss = list(_sessions.values())
        _sessions.clear()
    for s in ss:
        s.drop()
    if cfg is not None:
        shutil.rmtree(folder(cfg), ignore_errors=True)


def _start_janitor():
    with _lock:
        if _janitor["started"]:
            return
        _janitor["started"] = True

    def loop():
        while True:
            time.sleep(1)
            now = time.monotonic()
            with _lock:
                ss = list(_sessions.items())
            for k, s in ss:
                try:
                    if s.tidy(now):
                        s.drop()
                        with _lock:
                            if _sessions.get(k) is s:
                                del _sessions[k]
                except Exception:
                    pass
    threading.Thread(target=loop, daemon=True, name="stream-janitor").start()


def clear_leftovers(cfg):
    """Pieces left by a HERO TV that was closed mid-stream."""
    shutil.rmtree(folder(cfg), ignore_errors=True)


def warm(cfg):
    """Pick the encoder in the background at start, so the first phone does not wait for the test."""
    exe = tools.find_tool("ffmpeg")
    if exe:
        threading.Thread(target=lambda: encoder(exe, tmp=os.path.join(folder(cfg), "_enc")), daemon=True, name="stream-encoder-test").start()
