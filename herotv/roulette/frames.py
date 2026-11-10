"""Choosing the moment of a film to show, and grabbing that picture with ffmpeg.

The window a scene may come from is always based on the file's measured length. Opening logos and end credits are left
out by a number of seconds (and by the credits point HERO TV found for the file, when it has one).

A picture is judged by a real measurement, not a guess: ffmpeg hands back a tiny grey copy (64x36) and its average
brightness and contrast are worked out here. Black, blown-out and flat pictures (fades, title cards on black) are thrown
back and another moment is tried. Nothing here can tell how *recognisable* a scene is; "clear" simply prefers the
most detailed of a few candidates and "plain" the least detailed."""
import os
import random

from .. import tools
from .store import Bad

_NT = os.name == "nt"
_FLAGS = {"creationflags": 0x08000000 | 0x00004000} if _NT else {}      # no console window, below-normal priority
W, H = 64, 36
DARK, BRIGHT, FLAT = 26.0, 232.0, 11.0
END_MARGIN = 2.0
_rng = random.SystemRandom()


def window(runtime, cfg, preset, credits=0.0):
    """(first, last) second a scene may start at."""
    if not runtime or runtime <= 0:
        raise Bad("This film's file has no measurable length.")
    lo = min(float(cfg["skip_open"]), runtime * 0.12)
    hi = runtime - min(float(cfg["skip_end"]), runtime * 0.15)
    if credits and runtime * 0.6 < credits < hi:
        hi = credits
    lo = max(lo, runtime * preset["from"] / 100.0)
    hi = min(hi, runtime * preset["to"] / 100.0)
    hi = min(hi, runtime - END_MARGIN)
    if hi <= lo:                                    # a very short file: use all of it rather than refuse the round
        lo, hi = 0.0, max(0.0, runtime - END_MARGIN)
    return round(lo, 2), round(hi, 2)


def valid(t, win, runtime):
    try:
        t = float(t)
    except (TypeError, ValueError):
        raise Bad("The time must be a number of seconds.") from None
    if t != t or t < 0 or t > runtime:
        raise Bad("That time is outside the film.")
    return round(min(max(t, win[0]), win[1]), 2)


def random_time(win, used=(), rng=None, gap=45.0):
    """A whole second inside the window, away from the moments already used for this film."""
    rng = rng or _rng
    lo, hi = int(win[0] + 0.999), int(win[1])
    if hi <= lo:
        return float(max(0, lo if lo <= win[1] else int(win[0])))
    for _ in range(40):
        t = float(rng.randint(lo, hi))
        if all(abs(t - u) >= gap for u in used):
            return t
    return float(rng.randint(lo, hi))


def measure(path, t, run=None):
    """(brightness 0-255, contrast) of the picture at t, or None when ffmpeg cannot read it."""
    exe = tools.find_tool("ffmpeg")
    if not exe:
        return None
    try:
        r = (run or tools.run)([exe, "-v", "error", "-threads", "1", "-ss", f"{t:.2f}", "-i", path, "-an", "-sn", "-frames:v", "1",
                                "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"], timeout=60, text=False, encoding=None, errors=None, **_FLAGS)
    except Exception:
        return None
    data = getattr(r, "stdout", b"") or b""
    if getattr(r, "returncode", 1) != 0 or len(data) < W * H:
        return None
    px = data[:W * H]
    mean = sum(px) / len(px)
    var = sum((p - mean) ** 2 for p in px) / len(px)
    return mean, var ** 0.5


def good(m):
    return m is not None and DARK <= m[0] <= BRIGHT and m[1] >= FLAT


def choose(path, win, how="any", used=(), rng=None, measure_fn=None, tries=6):
    """The second to show. how: any = the first usable picture, clear = the most detailed of a few, plain = the least.
    Returns (seconds, checked): checked is False when no usable picture was found (or ffmpeg is missing) and a
    plain random moment is used instead."""
    mf = measure_fn or measure
    want = 1 if how == "any" else 3
    found, seen = [], list(used)
    for _ in range(tries):
        t = random_time(win, seen, rng)
        seen.append(t)
        m = mf(path, t)
        if m is None:                       # unreadable at this point (or no ffmpeg): one more go, then give up measuring
            if not found and len(seen) - len(used) >= 2:
                break
            continue
        if good(m):
            found.append((m[1], t))
            if len(found) >= want:
                break
    if not found:
        return random_time(win, used, rng), False
    found.sort()
    return (found[-1] if how == "clear" else found[0])[1], True


def grab(path, t, out, width=1600, run=None):
    """Write the picture at t to out (a .jpg). True when the file is there afterwards."""
    if os.path.isfile(out) and os.path.getsize(out) > 0:
        return True
    exe = tools.find_tool("ffmpeg")
    if not exe or not os.path.isfile(path):
        return False
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".part.jpg"
    try:
        r = (run or tools.run)([exe, "-v", "error", "-y", "-threads", "2", "-ss", f"{t:.2f}", "-i", path, "-an", "-sn", "-frames:v", "1",
                                "-vf", f"scale='min({width},iw)':-2", "-q:v", "3", tmp], timeout=120, **_FLAGS)
    except Exception:
        r = None
    if r is not None and r.returncode == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
        os.replace(tmp, out)
        return True
    if os.path.isfile(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass
    return False


def folder(cfg):
    return os.path.splitext(cfg.db_path)[0] + "-roulette"


def file_for(cfg, token, n=0):
    safe = "".join(ch for ch in token if ch.isalnum() or ch in "-_")
    return os.path.join(folder(cfg), f"{safe}-{n}.jpg")


def tidy(cfg, keep):
    """Remove the pictures of rounds that are over (keep = tokens still in play)."""
    d = folder(cfg)
    if not os.path.isdir(d):
        return
    for f in os.listdir(d):
        if f.endswith(".jpg") and f.rsplit("-", 1)[0] not in keep:
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                pass
