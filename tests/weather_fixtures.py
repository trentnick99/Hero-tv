"""Canned responses shaped like Open-Meteo (timeformat=unixtime) and api.weather.gov GeoJSON, for tests and screenshots."""
import time


def forecast(now=None):
    now = int(now or time.time())
    h0 = now - now % 3600
    day0 = now - now % 86400
    return {
        "latitude": 41.85, "longitude": -87.65, "utc_offset_seconds": -18000, "timezone": "America/Chicago",
        "current": {"time": now, "interval": 900, "temperature_2m": 61.3, "apparent_temperature": 58.9, "relative_humidity_2m": 72,
                    "is_day": 1, "weather_code": 2, "wind_speed_10m": 14.2, "wind_direction_10m": 225},
        "hourly": {"time": [h0 + i * 3600 for i in range(-2, 30)],
                   "temperature_2m": [55 + (i % 12) for i in range(32)],
                   "precipitation_probability": [0, 0, 5, 10, 20, 60, 80, 70, 40, 20, 10, 5] * 2 + [0] * 8,
                   "weather_code": [1, 2, 2, 3, 61, 63, 95, 80, 3, 2, 1, 0] * 2 + [0] * 8,
                   "is_day": [1] * 32},
        "daily": {"time": [day0 + i * 86400 for i in range(7)], "weather_code": [95, 63, 3, 2, 0, 71, 1],
                  "temperature_2m_max": [68.4, 64, 59, 62, 66, 41, 50], "temperature_2m_min": [51, 49, 44, 45, 47, 30, 33],
                  "precipitation_probability_max": [80, 60, 10, 5, 0, 70, 10],
                  "sunrise": [day0 + i * 86400 + 25000 for i in range(7)], "sunset": [day0 + i * 86400 + 65000 for i in range(7)]}}


def alerts(ends="2026-10-24T17:15:00-05:00"):
    def f(event, severity, headline, area, status="Actual", mtype="Alert"):
        return {"type": "Feature", "properties": {"event": event, "severity": severity, "urgency": "Immediate", "certainty": "Observed",
                "headline": headline, "areaDesc": area, "ends": ends, "expires": ends, "status": status, "messageType": mtype,
                "description": "At 4:05 PM CDT, a severe thunderstorm capable of producing a tornado was located near Oak Park.",
                "instruction": "TAKE COVER NOW! Move to a basement or an interior room on the lowest floor of a sturdy building.",
                "senderName": "NWS Chicago IL"}}
    return {"type": "FeatureCollection", "features": [
        f("Wind Advisory", "Moderate", "Wind Advisory issued October 24 by NWS Chicago IL", "Cook, IL; DuPage, IL"),
        f("Tornado Warning", "Extreme", "Tornado Warning issued October 24 at 4:05PM CDT by NWS Chicago IL", "Cook, IL"),
        f("Tornado Warning", "Extreme", "Tornado Warning issued October 24 at 4:05PM CDT by NWS Chicago IL", "Cook, IL"),   # duplicate zone copy
        f("Test Message", "Unknown", "Test", "Cook, IL", status="Test"),
    ]}


def fake_fetch(calls=None, offline=False):
    def fetch(url, params=None, headers=None):
        if calls is not None:
            calls.append(url)
        if offline:
            raise OSError("no internet")
        if "open-meteo" in url and "geocoding" not in url:
            return forecast()
        if "weather.gov" in url:
            return alerts()
        if "geocoding" in url:
            return {"results": [{"name": "Chicago", "latitude": 41.85, "longitude": -87.65, "country_code": "US", "admin1": "Illinois"}]}
        raise AssertionError(url)
    return fetch
