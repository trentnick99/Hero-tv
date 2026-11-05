"""HERO TV's own window (no Edge around it), made with pywebview on the WebView2 engine that Windows already has.
Runs as its own small process: `HERO-TV.exe window <address>`. If it cannot open, the launcher falls back to Edge."""
import importlib.util
import os
import sys
import time

IS_WIN = sys.platform.startswith("win")
NIGHT = "#090b13"
APP_ID = "HeroTV.App"
FAILED = 4          # exit code: the window could not be opened


def available():
    """pywebview is part of the built app; on a plain Python install it may be missing."""
    return IS_WIN and importlib.util.find_spec("webview") is not None


def selftest():
    """For the build: the window library and its Windows bridge are inside the app."""
    import clr_loader  # noqa: F401
    import webview  # noqa: F401
    import clr  # noqa: F401
    return 0


def stay_home(win, url):
    """A video dropped on the window can make the web view open that file by itself (a black window with the movie in it,
    and HERO TV gone). Whenever the window is not showing HERO TV, put HERO TV back. Also tell the page's own drop
    handler to keep the browser's default (opening the file) out of it."""
    try:
        cur = (win.get_current_url() or "").lower()
        base = url.lower().rstrip("/")
        if cur and not cur.startswith(base):
            win.load_url(url)
            return
    except Exception:
        return
    watch_drops(win)


class Gentle:
    """A file that is read a little slower than the disk allows, so a big copy does not freeze the movie that is playing."""
    PAUSE = 0.012                    # seconds after each megabyte: about 60-80 MB/s at most

    def __init__(self, fh):
        self.fh = fh

    def read(self, n):
        b = self.fh.read(n)
        if b:
            time.sleep(self.PAUSE * max(1, len(b) // (1 << 20)))
        return b


def add_dropped(paths, say, cfg=None):
    """Copy dropped video files into the Inbox (the same safe copy the page's own drop uses). Returns how many went in."""
    from . import inbox
    from .config import Config
    cfg = cfg or Config()
    done = bad = 0
    for p in paths:
        try:
            if not os.path.isfile(p):
                raise ValueError("not a file")
            with open(p, "rb") as fh:
                inbox.save_stream(cfg, os.path.basename(p), Gentle(fh), os.path.getsize(p))
            done += 1
        except (OSError, ValueError, ConnectionError):
            bad += 1
    say(f"{done} video{'' if done == 1 else 's'} added to your Inbox. HERO TV will file {'it' if done == 1 else 'them'} in about a minute."
        + (f" ({bad} could not be added)" if bad else "") if done else "Nothing could be added. Only videos (mp4, mkv, avi...) work.")
    return done


def watch_drops(win):
    """Files dropped on the window are taken by the window itself (it knows their real place on the disk), so the web view
    never opens them and the page never has to receive them."""
    if getattr(win, "_hero_drops", False):
        return
    try:
        import json
        import threading
        from webview.dom import DOMEventHandler

        def say(msg):
            try:
                win.evaluate_js("toast(%s)" % json.dumps(msg))
            except Exception:
                pass

        def on_drop(e):
            files = ((e or {}).get("dataTransfer") or {}).get("files") or []
            paths = [f.get("pywebviewFullPath") for f in files if isinstance(f, dict) and f.get("pywebviewFullPath")]
            if not paths:
                return say("This window could not read where that file is. Copy the video into your Inbox folder instead.")
            say("Adding %d file%s..." % (len(paths), "" if len(paths) == 1 else "s"))
            threading.Thread(target=add_dropped, args=(paths, say), daemon=True).start()
        win.dom.document.events.drop += DOMEventHandler(on_drop, prevent_default=True, stop_propagation=True)
        win.dom.document.events.dragover += DOMEventHandler(lambda e: None, prevent_default=True)
        win._hero_drops = True
    except Exception:
        pass


def run(url, fullscreen=True, profile=None):
    if not IS_WIN:
        return FAILED
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)     # its own taskbar button, not Edge's
    except Exception:
        pass
    try:                                                       # one window only: starting HERO TV again must not open a second one
        import ctypes
        import time as _t
        for _try in range(10):                                 # after an update the old window needs a moment to go
            _h = ctypes.windll.kernel32.CreateMutexW(None, False, "HeroTV.App.Window")
            if ctypes.windll.kernel32.GetLastError() != 183:   # not ERROR_ALREADY_EXISTS: ours
                break
            ctypes.windll.kernel32.CloseHandle(_h)
            _t.sleep(1)
        else:
            return 0                                           # a window is open already
        globals()["_mutex"] = _h                               # keep it for as long as this window lives
    except Exception:
        pass
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--autoplay-policy=no-user-gesture-required --disable-features=Translate "
                                                         "--enable-blink-features=AudioVideoTracks")
    import threading
    import time

    def leave_if_moved():                                      # an update moved this old exe into .update-backup: the window must not outlive it
        while True:
            time.sleep(3)
            try:
                buf = ctypes.create_unicode_buffer(1024)
                ctypes.windll.kernel32.GetModuleFileNameW(None, buf, 1024)
                if ".update-backup" in buf.value.replace("\\", "/"):
                    os._exit(0)
            except Exception:
                return
    threading.Thread(target=leave_if_moved, daemon=True).start()

    def leave_if_server_gone():                                # HERO TV was closed or is being updated: nothing left to show
        import urllib.request
        misses = 0
        while True:
            time.sleep(3)
            try:
                urllib.request.urlopen(url.rstrip("/") + "/api/health", timeout=2).close()
                misses = 0
            except Exception:
                misses += 1
                if misses >= 5:
                    os._exit(0)
    threading.Thread(target=leave_if_server_gone, daemon=True).start()
    try:
        import webview
        win = webview.create_window("HERO TV", url, fullscreen=fullscreen, width=1280, height=720, min_size=(800, 500),
                                    background_color=NIGHT, text_select=False)
        win.events.loaded += lambda *a: stay_home(win, url)
        webview.start(private_mode=False, storage_path=str(profile) if profile else None)
        return 0
    except Exception as e:
        print(f"HERO TV window could not open: {e}", file=sys.stderr)
        return FAILED
