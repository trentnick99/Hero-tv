"""What HERO TV is busy with right now (new videos from the Inbox, ready-to-play copies), for the Settings progress bars.
Only remembers things in memory; nothing here touches your files."""
import threading
import time

_lock = threading.Lock()
_tl = threading.local()
_active = {}            # key -> task
_recent = []            # newest last: {"name","result","at"}
_batch = {"total": 0, "done": 0}
_next = [0]
KEEP = 12
FIRST = "Working out where it belongs"


def begin(kind, name):
    """Start a task on this thread (later stage()/percent() calls from this thread update it)."""
    with _lock:
        _next[0] += 1
        key = _next[0]
        _active[key] = {"id": key, "kind": kind, "name": name, "stage": "Starting", "pct": None, "started": time.time()}
    _tl.key = key
    return key


def current():
    return getattr(_tl, "key", None)


def stage(text, pct=None):
    with _lock:
        t = _active.get(current())
        if t:
            t["stage"], t["pct"] = text, pct


def percent(key, frac):
    """Progress of a task from another thread (ffmpeg's output reader)."""
    if key is None:
        return
    with _lock:
        t = _active.get(key)
        if t:
            t["pct"] = max(0, min(99, int(frac * 100)))


def waiting_stage():
    """True while this thread's task has not got past the first look (nothing was done to the file)."""
    with _lock:
        t = _active.get(current())
        return bool(t) and t["stage"] == FIRST


def end(result="done", quiet=False):
    key = current()
    _tl.key = None
    with _lock:
        t = _active.pop(key, None)
        if t and not quiet:
            _recent[:] = [r for r in _recent if not (r["name"] == t["name"] and r["kind"] == t["kind"])]   # a retry replaces the old line
            _recent.append({"name": t["name"], "result": result, "at": time.time(), "kind": t["kind"]})
            del _recent[:-KEEP]


def batch(total=0, done=0):
    with _lock:
        _batch["total"], _batch["done"] = total, done


def batch_step():
    with _lock:
        _batch["done"] = min(_batch["total"], _batch["done"] + 1)


def snapshot():
    with _lock:
        return {"active": [dict(t) for t in _active.values()], "recent": [dict(r) for r in reversed(_recent)],
                "batch": dict(_batch), "now": time.time()}
