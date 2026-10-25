"""The Settings screen's backend: read, validate and save the choices kept in settings.json.

Everything is validated here (never trust the page), written atomically, and a copy of the previous file is kept as
settings.json.bak so a bad change can always be undone. Keys this module does not know about (media_dir, weather,
tmdb_key, ...) are left exactly as they were.
"""
import json
import os
import re
from pathlib import Path

from . import __version__, config, inbox

COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def _load():
    f = config.settings_file()
    try:
        d = json.loads(f.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    f = config.settings_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.is_file():
        try:
            (f.with_name(f.name + ".bak")).write_bytes(f.read_bytes())
        except OSError:
            pass
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, f)


def _seasonal_list():
    try:
        d = json.loads((config.ROOT / "config" / "seasonal.json").read_text(encoding="utf-8-sig"))
        return [{"name": b.get("name", ""), "dates": b.get("dates", ""), "from": b.get("from", ""), "to": b.get("to", "")}
                for b in d.get("blocks", []) if isinstance(b, dict)]
    except (OSError, ValueError):
        return []


def _last_backup():
    from . import backup
    p = backup.latest()
    return {"file": p, "when": int(os.path.getmtime(p))} if p else None


SUB_SIZES, SUB_BGS, SUB_COLORS = ("normal", "large", "xl"), ("box", "none"), ("white", "yellow")


def subs_style(d=None):
    """How subtitles look on every screen: size, black box or outline only, white or yellow."""
    d = _load() if d is None else d
    st = d.get("subs_style") if isinstance(d.get("subs_style"), dict) else {}
    return {"size": st.get("size") if st.get("size") in SUB_SIZES else "normal",
            "bg": st.get("bg") if st.get("bg") in SUB_BGS else "box",
            "color": st.get("color") if st.get("color") in SUB_COLORS else "white"}


def mask(key):
    return ("…" + key[-4:]) if key and len(key) > 8 else ("set" if key else "")


def read(cfg):
    """Everything the Settings screen shows."""
    from . import tools, weather
    d = _load()
    loc = weather.location()
    key = d.get("tmdb_key") if isinstance(d.get("tmdb_key"), str) else ""
    return {
        "station": config.station(),
        "default_station": config.DEFAULT_STATION,
        "auto_inbox": inbox.enabled(),
        "windowed": bool(d.get("windowed")),
        "subs_style": subs_style(d),
        "auto_backup": d.get("auto_backup", True) is not False,
        "seasonal": d.get("seasonal", True) is not False,
        "seasonal_list": _seasonal_list(),
        "last_backup": _last_backup(),
        "media_dir": str(cfg.media_dir),
        "weather": loc.get("name") if loc else "",
        "art": {"has_key": bool(key.strip()), "key_hint": mask(key.strip())},
        "about": {"version": __version__, "api": config.API_LEVEL, "ffmpeg": bool(tools.find_tool("ffmpeg")),
                  "ffprobe": bool(tools.find_tool("ffprobe")), "settings_file": str(config.settings_file()),
                  "log_file": str(config.settings_file().parent / "herotv.log"), "config_dir": str(Path(cfg.channels_file).parent)},
    }


def update(changes, geocode=None):
    """Apply a dict of changes. Returns {"saved": [...], "restart": bool}. Raises ValueError with a plain-English reason."""
    if not isinstance(changes, dict) or not changes:
        raise ValueError("nothing to save")
    data = _load()
    saved, restart = [], False
    st = changes.get("station")
    if st is not None:
        if not isinstance(st, dict):
            raise ValueError("station must be an object")
        cur = data.get("station") if isinstance(data.get("station"), dict) else {}
        if "name" in st:
            name = str(st["name"]).strip()
            if not name:
                raise ValueError("The station name cannot be empty.")
            cur["name"] = name[:40]
        if "color" in st:
            if not isinstance(st["color"], str) or not COLOR.fullmatch(st["color"]):
                raise ValueError("The colour must look like #ff3b3b.")
            cur["color"] = st["color"]
        if "tagline" in st:
            cur["tagline"] = str(st["tagline"]).strip()[:80]
        data["station"] = cur
        saved.append("station")
    if "reset_station" in changes and changes["reset_station"]:
        data.pop("station", None)
        saved.append("station")
    if "auto_inbox" in changes:
        if not isinstance(changes["auto_inbox"], bool):
            raise ValueError("auto_inbox must be on or off")
        data["auto_inbox"] = changes["auto_inbox"]
        saved.append("auto_inbox")
    if "seasonal" in changes:
        if not isinstance(changes["seasonal"], bool):
            raise ValueError("seasonal must be on or off")
        data["seasonal"] = changes["seasonal"]
        saved.append("seasonal")
    if "auto_backup" in changes:
        if not isinstance(changes["auto_backup"], bool):
            raise ValueError("auto_backup must be on or off")
        data["auto_backup"] = changes["auto_backup"]
        saved.append("auto_backup")
    if "subs_style" in changes:
        st = changes["subs_style"]
        if not isinstance(st, dict) or st.get("size") not in SUB_SIZES or st.get("bg") not in SUB_BGS or st.get("color") not in SUB_COLORS:
            raise ValueError("Choose a subtitle size, background and colour from the lists.")
        data["subs_style"] = {k: st[k] for k in ("size", "bg", "color")}
        saved.append("subs_style")
    if "windowed" in changes:
        if not isinstance(changes["windowed"], bool):
            raise ValueError("windowed must be on or off")
        data["windowed"] = changes["windowed"]
        saved.append("windowed")
    if "tmdb_key" in changes:
        k = str(changes["tmdb_key"]).strip().strip('"')
        if k and not re.fullmatch(r"[A-Za-z0-9._\-]{16,}", k):
            raise ValueError("That does not look like a TMDB key (letters and numbers, at least 16 characters).")
        if k:
            data["tmdb_key"] = k
        else:
            data.pop("tmdb_key", None)
        saved.append("tmdb_key")
    if "media_dir" in changes:
        p = str(changes["media_dir"]).strip().strip('"')
        if not p or not os.path.isdir(p):
            raise ValueError("That folder does not exist. Type the full path of an existing folder.")
        data["media_dir"] = os.path.abspath(p)
        saved.append("media_dir")
        restart = True
    if "weather" in changes:
        q = str(changes["weather"]).strip()
        if not q:
            data.pop("weather", None)
        else:
            from . import weather
            try:
                found = (geocode or weather.geocode)(q)
            except Exception as e:
                raise ValueError(f"Could not look that place up ({e}). Check the Internet connection.")
            if not found:
                raise ValueError("No place found with that name. Try a city name or a postcode.")
            w = found[0]
            data["weather"] = {"name": w["name"], "lat": w["lat"], "lon": w["lon"], "country_code": w.get("country_code", ""),
                               "units": "us" if w.get("country_code") in ("US", "LR", "MM") else "metric"}
            weather.clear_cache()
        saved.append("weather")
    if not saved:
        raise ValueError("nothing to save")
    _save(data)
    return {"saved": saved, "restart": restart}
