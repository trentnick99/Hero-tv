"""Long-running tools started from the Settings screen (downloads, imports, conversions...), one at a time, in the
background. Their messages are the same ones the .bat files print; the screen shows the latest lines."""
import collections
import threading
import time
import traceback

_lock = threading.Lock()
_job = None
_n = 0


class Job:
    def __init__(self, name, title):
        global _n
        _n += 1
        self.id, self.name, self.title = _n, name, title
        self.lines = collections.deque(maxlen=300)
        self.state, self.rc, self.started, self.ended = "running", None, time.time(), None

    def add(self, text):
        for line in str(text).splitlines() or [""]:
            self.lines.append(line.rstrip())

    def as_dict(self):
        return {"id": self.id, "name": self.name, "title": self.title, "state": self.state, "rc": self.rc,
                "started": self.started, "ended": self.ended, "lines": list(self.lines)[-60:]}


def current():
    return _job.as_dict() if _job else None


def busy():
    return bool(_job and _job.state == "running")


def start(name, title, fn, wait=False):
    """Run fn() in the background with launcher.say() output captured. fn returns an exit code (0 = fine)."""
    global _job
    from . import launcher
    with _lock:
        if busy():
            raise ValueError(f"'{_job.title}' is still running. Wait for it to finish first.")
        job = _job = Job(name, title)

    def run():
        launcher._sink.fn = job.add
        try:
            rc = fn()
            job.rc = int(rc or 0)
            job.state = "done" if job.rc == 0 else "failed"
        except SystemExit as e:
            job.rc, job.state = int(e.code or 0) if str(e.code or "0").isdigit() else 1, "failed"
            if e.code and not str(e.code).isdigit():
                job.add(str(e.code))
        except Exception as e:
            traceback.print_exc()
            job.add(f"[FAIL] {e}")
            job.rc, job.state = 1, "failed"
        finally:
            launcher._sink.fn = None
            job.ended = time.time()

    t = threading.Thread(target=run, daemon=True, name="job-" + name)
    t.start()
    if wait:
        t.join()
    return job.as_dict()
