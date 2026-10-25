"""Weather channel data: forecast from Open-Meteo (free, no key, worldwide) and live alerts from the US National
Weather Service (free, no key, US only). Results are cached so the TV never hammers either service, and the last good
data is kept (marked "stale") when the internet drops.

The location is chosen once with Set-Weather-Location.bat and stored in settings.json:
  {"weather": {"name": "Chicago, Illinois", "lat": 41.85, "lon": -87.65, "country_code": "US", "units": "us"}}
"""
import json
import threading
import time
import urllib.parse
import urllib.request

from . import net
from .config import settings_file

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
ALERTS_URL = "https://api.weather.gov/alerts/active"
USER_AGENT = "HERO-TV/1.0 (personal home TV app; weather channel)"
FORECAST_TTL, ALERTS_TTL = 600, 120          # seconds
TIMEOUT = 8

_lock = threading.Lock()
_cache = {}            # key -> (fetched_at, data)


def _get_json(url, params=None, headers=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})})
    with net.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _cached(key, ttl, fetch):
    """(data, stale, error). Serves fresh cache, refreshes when old, falls back to old data when offline."""
    now = time.time()
    with _lock:
        hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1], False, None
    try:
        data = fetch()
    except Exception as exc:          # offline, DNS, HTTP 429/5xx, bad JSON ...
        if hit:
            return hit[1], True, str(exc)
        return None, True, str(exc)
    with _lock:
        _cache[key] = (now, data)
    return data, False, None


def clear_cache():
    with _lock:
        _cache.clear()


# ---------------------------------------------------------------- settings
def location():
    try:
        w = json.loads(settings_file().read_text(encoding="utf-8-sig")).get("weather") or {}
        if "lat" in w and "lon" in w:
            return w
    except (OSError, ValueError, AttributeError):
        pass
    return None


def save_location(loc):
    f = settings_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(f.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        data = {}
    data["weather"] = loc
    f.write_text(json.dumps(data, indent=1), encoding="utf-8")
    clear_cache()


def geocode(query, fetch=None):
    """Places matching a city name or postcode: list of dicts (name, lat, lon, country_code, label)."""
    fetch = fetch or _get_json
    j = fetch(GEOCODE_URL, {"name": query, "count": 8, "language": "en", "format": "json"})
    out = []
    for r in (j or {}).get("results") or []:
        parts = [r.get("name"), r.get("admin1"), r.get("country_code") or r.get("country")]
        out.append({"name": ", ".join(p for p in parts[:2] if p), "lat": r["latitude"], "lon": r["longitude"],
                    "country_code": (r.get("country_code") or "").upper(),
                    "label": ", ".join(p for p in parts if p)})
    return out


# ---------------------------------------------------------------- data
def _forecast(loc, fetch):
    us = loc.get("units", "us") == "us"
    return fetch(FORECAST_URL, {
        "latitude": loc["lat"], "longitude": loc["lon"], "timezone": "auto", "forecast_days": 7,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,is_day,weather_code,wind_speed_10m,wind_direction_10m",
        "hourly": "temperature_2m,precipitation_probability,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        "temperature_unit": "fahrenheit" if us else "celsius", "wind_speed_unit": "mph" if us else "kmh",
        "precipitation_unit": "inch" if us else "mm", "timeformat": "unixtime"})


def _alerts(loc, fetch):
    if (loc.get("country_code") or "").upper() != "US":
        return {"features": []}            # NWS covers the US only
    return fetch(ALERTS_URL, {"point": f"{float(loc['lat']):.4f},{float(loc['lon']):.4f}"},
                 {"Accept": "application/geo+json"})


def _num(v):
    return None if v is None else round(float(v))


def _pick(d, *names):
    for n in names:
        if n in d:
            return d[n]
    return None


def parse_forecast(j, now=None):
    now = now or time.time()
    cur = j.get("current") or j.get("current_weather") or {}
    out = {"current": {
        "temp": _num(_pick(cur, "temperature_2m", "temperature")),
        "feels": _num(cur.get("apparent_temperature")),
        "humidity": _num(cur.get("relative_humidity_2m")),
        "wind": _num(_pick(cur, "wind_speed_10m", "windspeed")),
        "wind_dir": _num(_pick(cur, "wind_direction_10m", "winddirection")),
        "code": _pick(cur, "weather_code", "weathercode"),
        "is_day": bool(_pick(cur, "is_day") if _pick(cur, "is_day") is not None else 1)}}
    h = j.get("hourly") or {}
    times = h.get("time") or []
    codes = _pick(h, "weather_code", "weathercode") or []
    hourly = []
    for i, t in enumerate(times):
        if t + 3600 <= now:
            continue
        hourly.append({"t": t, "temp": _num((h.get("temperature_2m") or [None] * len(times))[i]),
                       "pop": _num((h.get("precipitation_probability") or [None] * len(times))[i]),
                       "code": codes[i] if i < len(codes) else None,
                       "is_day": bool((h.get("is_day") or [1] * len(times))[i])})
        if len(hourly) == 12:
            break
    d = j.get("daily") or {}
    days = []
    for i, t in enumerate(d.get("time") or []):
        days.append({"t": t, "hi": _num((d.get("temperature_2m_max") or [None] * 99)[i]),
                     "lo": _num((d.get("temperature_2m_min") or [None] * 99)[i]),
                     "pop": _num((d.get("precipitation_probability_max") or [None] * 99)[i]),
                     "code": (_pick(d, "weather_code", "weathercode") or [None] * 99)[i],
                     "sunrise": (d.get("sunrise") or [None] * 99)[i], "sunset": (d.get("sunset") or [None] * 99)[i]})
    out.update(hourly=hourly, daily=days[:7], utc_offset=j.get("utc_offset_seconds", 0))
    return out


ALERT_RANK = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3, "Unknown": 4}


def parse_alerts(j):
    out = []
    for f in (j or {}).get("features") or []:
        p = f.get("properties") or {}
        if p.get("status", "Actual") != "Actual" or p.get("messageType") == "Cancel":
            continue
        ev = p.get("event") or "Weather alert"
        out.append({"event": ev, "headline": p.get("headline") or ev, "severity": p.get("severity") or "Unknown",
                    "urgency": p.get("urgency") or "", "area": p.get("areaDesc") or "",
                    "ends": p.get("ends") or p.get("expires") or "", "description": (p.get("description") or "").strip(),
                    "instruction": (p.get("instruction") or "").strip(), "sender": p.get("senderName") or "",
                    # what interrupts every channel with the red crawl: warnings, watches, and anything Severe/Extreme
                    "crawl": p.get("severity") in ("Extreme", "Severe") or ev.endswith(("Warning", "Watch"))})
    out.sort(key=lambda a: (ALERT_RANK.get(a["severity"], 9), a["event"]))
    seen, uniq = set(), []
    for a in out:                         # NWS often repeats one alert per zone
        k = (a["event"], a["headline"])
        if k not in seen:
            seen.add(k)
            uniq.append(a)
    return uniq


def report(fetch=None, now=None):
    """Everything the weather channel shows. Never raises."""
    loc = location()
    if not loc:
        return {"configured": False}
    fetch = fetch or _get_json
    key = f"{loc['lat']},{loc['lon']},{loc.get('units', 'us')}"
    fj, f_stale, f_err = _cached("f:" + key, FORECAST_TTL, lambda: _forecast(loc, fetch))
    aj, a_stale, a_err = _cached("a:" + key, ALERTS_TTL, lambda: _alerts(loc, fetch))
    us = loc.get("units", "us") == "us"
    out = {"configured": True, "location": loc.get("name", ""), "units": {"temp": "°F" if us else "°C", "wind": "mph" if us else "km/h"},
           "alerts_supported": (loc.get("country_code") or "").upper() == "US",
           "stale": bool(f_stale or a_stale), "error": f_err or a_err, "updated": time.time()}
    try:
        out.update(parse_forecast(fj, now) if fj else {"current": None, "hourly": [], "daily": []})
    except Exception as exc:
        out.update(current=None, hourly=[], daily=[], error=f"forecast format: {exc}")
    try:
        out["alerts"] = parse_alerts(aj) if aj else []
    except Exception:
        out["alerts"] = []
    return out


def alerts_only(fetch=None):
    loc = location()
    if not loc:
        return {"configured": False, "alerts": []}
    fetch = fetch or _get_json
    key = f"{loc['lat']},{loc['lon']},{loc.get('units', 'us')}"
    aj, stale, err = _cached("a:" + key, ALERTS_TTL, lambda: _alerts(loc, fetch))
    try:
        alerts = parse_alerts(aj) if aj else []
    except Exception:
        alerts = []
    return {"configured": True, "alerts": alerts, "stale": stale}
