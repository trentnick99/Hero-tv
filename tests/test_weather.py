import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from herotv import scheduler as S, weather  # noqa: E402
from helpers import add, make_db  # noqa: E402
import weather_fixtures as fx  # noqa: E402


class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.old = {k: os.environ.get(k) for k in ("LOCALAPPDATA", "HOME")}
        os.environ["LOCALAPPDATA"] = self.d
        os.environ["HOME"] = self.d
        weather.clear_cache()
        self.addCleanup(self.restore)

    def restore(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        weather.clear_cache()

    def test_not_configured(self):
        self.assertEqual(weather.report(fetch=fx.fake_fetch()), {"configured": False})

    def test_report_and_alert_rules(self):
        weather.save_location({"name": "Chicago, Illinois", "lat": 41.85, "lon": -87.65, "country_code": "US", "units": "us"})
        r = weather.report(fetch=fx.fake_fetch())
        self.assertTrue(r["configured"])
        self.assertEqual((r["current"]["temp"], r["current"]["code"], r["units"]["temp"]), (61, 2, "°F"))
        self.assertEqual(len(r["daily"]), 7)
        self.assertTrue(1 <= len(r["hourly"]) <= 12)
        self.assertGreaterEqual(r["hourly"][0]["t"] + 3600, r["updated"] - 5)       # no hours from the past
        events = [a["event"] for a in r["alerts"]]
        self.assertEqual(events, ["Tornado Warning", "Wind Advisory"])           # worst first, duplicates and tests removed
        self.assertTrue(r["alerts"][0]["crawl"])
        self.assertFalse(r["alerts"][1]["crawl"])                                # advisories stay on the weather channel

    def test_cache_and_offline_fallback(self):
        weather.save_location({"name": "X", "lat": 1, "lon": 2, "country_code": "US", "units": "us"})
        calls = []
        weather.report(fetch=fx.fake_fetch(calls))
        weather.report(fetch=fx.fake_fetch(calls))
        self.assertEqual(len(calls), 2)                                          # second call served from cache
        weather._cache = {k: (0, v[1]) for k, v in weather._cache.items()}      # make it old
        r = weather.report(fetch=fx.fake_fetch(offline=True))
        self.assertTrue(r["stale"])
        self.assertEqual(r["current"]["temp"], 61)                              # last good data kept

    def test_no_alert_calls_outside_us(self):
        weather.save_location({"name": "Paris", "lat": 48.85, "lon": 2.35, "country_code": "FR", "units": "metric"})
        calls = []
        r = weather.report(fetch=fx.fake_fetch(calls))
        self.assertFalse(any("weather.gov" in c for c in calls))
        self.assertEqual((r["alerts"], r["alerts_supported"], r["units"]["temp"]), ([], False, "°C"))

    def test_offline_first_time(self):
        weather.save_location({"name": "X", "lat": 1, "lon": 2, "country_code": "US", "units": "us"})
        r = weather.report(fetch=fx.fake_fetch(offline=True))
        self.assertTrue(r["configured"] and r["stale"])
        self.assertIsNone(r["current"])

    def test_geocode(self):
        self.assertEqual(weather.geocode("Chicago", fetch=fx.fake_fetch())[0]["label"], "Chicago, Illinois, US")

    def test_weather_channel_is_never_scheduled(self):
        c = make_db()
        add(c, "A", 600)
        S.sync_channels(c, [{"id": "all", "number": 1, "name": "All", "match": {}},
                            {"id": "weather", "number": 13, "name": "Weather", "kind": "weather"}])
        S.extend_all(c, 1_800_000_000, 3600)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM slots WHERE channel_id='weather'").fetchone()[0], 0)
        self.assertGreater(c.execute("SELECT COUNT(*) FROM slots WHERE channel_id='all'").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT kind FROM channels WHERE id='weather'").fetchone()[0], "weather")


if __name__ == "__main__":
    unittest.main()
