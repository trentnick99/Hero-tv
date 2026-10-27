"""Always on: HERO TV as a quiet background service on the PC, so the Roku app and phones always find it.

- Start with Windows: a "HERO TV" shortcut in the Startup folder starts it in the background (no window) when you
  sign in. Clicking the HERO TV icon then just opens the TV window.
- Keep running when the TV window is closed (otherwise quiet mode turns HERO TV off a few minutes after the window
  closes). On by default once other devices or a Roku TV are set up.
- If HERO TV stops with an error while running in the background, it starts itself again (a few times).
- Quit HERO TV completely: Settings > Backup and about."""
import json
import os
import subprocess
import sys
from pathlib import Path

from . import config

LINK = "HERO TV.lnk"


def _settings():
    try:
        d = json.loads(config.settings_file().read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def startup_dir():
    base = os.environ.get("APPDATA")
    if not base:
        return None
    return Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_on():
    d = startup_dir()
    return bool(d and (d / LINK).is_file())


def background():
    """Keep the server running when no TV window is open?"""
    d = _settings()
    if isinstance(d.get("background"), bool):
        return d["background"] or startup_on()
    if startup_on():
        return True
    r = d.get("roku")
    return bool(d.get("lan_share") or (isinstance(r, dict) and r.get("ip")))


def set_background(on):
    from . import settings_api
    d = settings_api._load()
    d["background"] = bool(on)
    settings_api._save(d)


def _command():
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return str(exe), "launch --quiet --no-browser"
    pyw = exe.with_name("pythonw.exe")
    return str(pyw if pyw.is_file() else exe), "-m herotv launch --quiet --no-browser"


def set_startup(on, run=None):
    """Create or remove the Startup-folder shortcut. Returns its path (or None when removed)."""
    d = startup_dir()
    if d is None:
        raise ValueError("Starting with Windows only works on Windows.")
    link = d / LINK
    if not on:
        try:
            link.unlink()
        except FileNotFoundError:
            pass
        return None
    d.mkdir(parents=True, exist_ok=True)
    target, args = _command()
    ico = config.ROOT / "assets" / "hero-tv.ico"
    ps = ('$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:HT_LINK);$s.TargetPath=$env:HT_TARGET;'
          '$s.Arguments=$env:HT_ARGS;$s.WorkingDirectory=$env:HT_DIR;$s.WindowStyle=7;'
          'if(Test-Path $env:HT_ICON){$s.IconLocation=$env:HT_ICON};$s.Description="HERO TV (in the background)";$s.Save()')
    env = dict(os.environ, HT_LINK=str(link), HT_TARGET=target, HT_ARGS=args, HT_DIR=str(config.ROOT), HT_ICON=str(ico))
    if run is not None:
        return run(ps, env)
    from . import tools
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, text=True, env=env, **tools.HIDE)
    if r.returncode != 0 or not link.is_file():
        raise ValueError("Windows did not let HERO TV add itself to the Startup folder: " + (r.stderr or r.stdout).strip()[-200:])
    return str(link)


def status():
    return {"startup": startup_on(), "background": background(), "windows": startup_dir() is not None}
