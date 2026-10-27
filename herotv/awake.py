"""Keep the PC awake for the TVs: a Roku TV or phone cannot wake a sleeping PC, so HERO TV tells Windows not to go
to sleep (the screen may still switch off) -
- always while a video is being sent to a TV, phone or this PC, and for 15 minutes after (a pause, a menu), and
- all the time if "Keep this PC awake" is on (on by default once a Roku TV is set up).
Elsewhere than Windows this does nothing."""
import contextlib
import json
import sys
import threading
import time

from . import config

GRACE = 15 * 60
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001

_lock = threading.Lock()
_state = {"active": 0, "last": 0.0, "thread": None, "held": False}
_wake = threading.Event()


def _settings():
    try:
        d = json.loads(config.settings_file().read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def always(d=None):
    """Keep the PC awake all the time? The setting, else on when a Roku TV is set up."""
    d = _settings() if d is None else d
    if isinstance(d.get("stay_awake"), bool):
        return d["stay_awake"]
    r, rs = d.get("roku"), d.get("rokus")
    return bool((isinstance(r, dict) and r.get("ip")) or (isinstance(rs, dict) and rs))


def set_always(on):
    from . import settings_api
    d = settings_api._load()
    d["stay_awake"] = bool(on)
    settings_api._save(d)
    _wake.set()


def wanted(now=None, always_on=None):
    now = time.time() if now is None else now
    with _lock:
        busy = _state["active"] > 0 or now - _state["last"] < GRACE
    return busy or (always() if always_on is None else always_on)


def _set(on, call=None):
    if call is None:
        if sys.platform != "win32":
            return False
        import ctypes
        call = ctypes.windll.kernel32.SetThreadExecutionState
    call(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    return True


def _loop():
    # Windows ties the "stay awake" request to the thread that made it, so one long-lived thread owns it
    while True:
        want = wanted()
        if want != _state["held"]:
            try:
                _set(want)
            except Exception:
                pass
            _state["held"] = want
        _wake.wait(30)
        _wake.clear()


def _ensure():
    if _state["thread"] is None:
        with _lock:
            if _state["thread"] is None:
                t = threading.Thread(target=_loop, name="herotv-awake", daemon=True)
                _state["thread"] = t
                t.start()


def start():
    _ensure()


@contextlib.contextmanager
def streaming():
    """Wrap sending a video: the PC stays awake while it runs and for a while after."""
    with _lock:
        _state["active"] += 1
        first = _state["active"] == 1 and not _state["held"]
    if first:
        _ensure()
        _wake.set()
    try:
        yield
    finally:
        with _lock:
            _state["active"] -= 1
            _state["last"] = time.time()


def status():
    return {"stay_awake": always(), "busy": wanted(always_on=False), "windows": sys.platform == "win32"}
