"""HERO TV's own window (no Edge around it), made with pywebview on the WebView2 engine that Windows already has.
Runs as its own small process: `HERO-TV.exe window <address>`. If it cannot open, the launcher falls back to Edge."""
import importlib.util
import os
import sys

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


def run(url, fullscreen=True, profile=None):
    if not IS_WIN:
        return FAILED
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)     # its own taskbar button, not Edge's
    except Exception:
        pass
    try:                                                       # one window only: starting HERO TV again must not open a second one
        import ctypes
        _h = ctypes.windll.kernel32.CreateMutexW(None, False, "HeroTV.App.Window")
        if ctypes.windll.kernel32.GetLastError() == 183:       # ERROR_ALREADY_EXISTS
            return 0
        globals()["_mutex"] = _h                               # keep it for as long as this window lives
    except Exception:
        pass
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--autoplay-policy=no-user-gesture-required --disable-features=Translate")
    try:
        import webview
        webview.create_window("HERO TV", url, fullscreen=fullscreen, width=1280, height=720, min_size=(800, 500),
                              background_color=NIGHT, text_select=False)
        webview.start(private_mode=False, storage_path=str(profile) if profile else None)
        return 0
    except Exception as e:
        print(f"HERO TV window could not open: {e}", file=sys.stderr)
        return FAILED
