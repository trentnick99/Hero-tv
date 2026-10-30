"""Runtime configuration (environment variables, sane defaults)."""
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

def _root():
    """The HERO TV folder: next to the source code, or - when built into HERO-TV.exe - the folder holding the exe
    (web/, config/ and your data stay there as normal files, so they remain easy to edit and back up)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT = _root()


IS_WIN = os.name == "nt"

# Bumped whenever the browser page needs something new from the server. A TV page talking to an older server (one that
# was still running from before an update) is detected and the old server is restarted. index.html carries the same number.
API_LEVEL = 17


def system_tz() -> str:
    if os.environ.get("TZ"):
        return os.environ["TZ"]
    if IS_WIN:   # Windows has no IANA zone name to read; "local" follows the PC's own clock settings (see tz.py)
        return "local"
    try:
        return Path("/etc/timezone").read_text().strip() or "UTC"
    except OSError:
        pass
    p = os.path.realpath("/etc/localtime")
    if "zoneinfo/" in p:
        return p.split("zoneinfo/", 1)[1]
    return "UTC"


def settings_file() -> Path:
    base = os.environ.get("LOCALAPPDATA") if IS_WIN else None
    return Path(base or Path.home() / ".local" / "share") / "HeroTV" / "settings.json"


DEFAULT_STATION = {"name": "HERO TV", "color": "#ffcf1f", "tagline": "What do you want to watch?"}


def station():
    """The personal touches: station name, brand colour and the line under it (set with Personalize.bat)."""
    import json
    import re
    out = dict(DEFAULT_STATION)
    try:
        d = json.loads(settings_file().read_text(encoding="utf-8-sig")).get("station") or {}
    except (OSError, ValueError, AttributeError):
        d = {}
    if isinstance(d.get("name"), str) and d["name"].strip():
        out["name"] = d["name"].strip()[:40]
    if isinstance(d.get("color"), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", d["color"]):
        out["color"] = d["color"]
    if isinstance(d.get("tagline"), str):
        out["tagline"] = d["tagline"].strip()[:80] or out["tagline"]
    return out


def saved_media_dir():
    """Media folder chosen with Choose-Media-Folder.bat (survives restarts; no Windows environment variable needed)."""
    try:
        import json
        d = json.loads(settings_file().read_text(encoding="utf-8-sig")).get("media_dir")
        return Path(d) if d else None
    except (OSError, ValueError, AttributeError):
        return None


def default_db_path() -> str:
    # On Windows keep the database out of the app folder: Desktop/Documents are often synced by OneDrive,
    # which locks SQLite files, and Program Files is read-only.
    if IS_WIN:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return str(Path(base) / "HeroTV" / "herotv.sqlite3")
    return str(ROOT / "data" / "herotv.sqlite3")


@dataclass
class Config:
    media_dir: Path = field(default_factory=lambda: Path(os.environ.get("HEROTV_MEDIA") or saved_media_dir() or Path.home() / "hero-tv-media"))
    db_path: str = field(default_factory=lambda: os.environ.get("HEROTV_DB", default_db_path()))
    channels_file: str = field(default_factory=lambda: os.environ.get("HEROTV_CHANNELS", str(ROOT / "config" / "channels.json")))
    tz: str = field(default_factory=lambda: os.environ.get("HEROTV_TZ") or system_tz())
    host: str = field(default_factory=lambda: os.environ.get("HEROTV_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("HEROTV_PORT", "8787")))
    horizon_h: int = field(default_factory=lambda: int(os.environ.get("HEROTV_HORIZON_H", "48")))
    web_dir: Path = ROOT / "web"
