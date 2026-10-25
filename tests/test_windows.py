import datetime as dt
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zoneinfo import ZoneInfo  # noqa: E402

from herotv import library, tools  # noqa: E402
from herotv.tz import LocalTZ, get_tz, js_zone  # noqa: E402
from helpers import make_db  # noqa: E402


class LocalTZTests(unittest.TestCase):
    """The 'local' zone (used on Windows) must agree with a real IANA zone across DST changes."""

    def setUp(self):
        if not hasattr(time, "tzset"):
            self.skipTest("needs time.tzset (Linux/macOS)")
        self.old = os.environ.get("TZ")
        os.environ["TZ"] = "America/Chicago"
        time.tzset()
        self.addCleanup(self._restore)

    def _restore(self):
        if self.old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self.old
        time.tzset()

    def test_matches_zoneinfo_every_30_minutes_across_a_year(self):
        z, loc = ZoneInfo("America/Chicago"), LocalTZ()
        t = int(dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc).timestamp())
        for ts in range(t, t + 365 * 86400, 1800):
            a, b = dt.datetime.fromtimestamp(ts, z), dt.datetime.fromtimestamp(ts, loc)
            self.assertEqual(a.replace(tzinfo=None), b.replace(tzinfo=None), ts)
            self.assertEqual(a.utcoffset(), b.utcoffset(), ts)
            self.assertEqual(b.timestamp(), ts)

    def test_day_bounds_are_23_and_25_hours_on_dst_days(self):
        from herotv import scheduler as S
        a, b = S.local_day_bounds("local", "2026-03-08")
        self.assertEqual(b - a, 23 * 3600)
        a, b = S.local_day_bounds("local", "2026-11-01")
        self.assertEqual(b - a, 25 * 3600)
        self.assertEqual((a, b), S.local_day_bounds("America/Chicago", "2026-11-01"))

    def test_js_zone_and_errors(self):
        self.assertIsNone(js_zone("local"))
        self.assertEqual(js_zone("Europe/Paris"), "Europe/Paris")
        with self.assertRaises(ValueError):
            get_tz("Not/AZone")


class LibraryWindowsTests(unittest.TestCase):
    def test_sidecar_with_utf8_bom_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "MCU"))
            open(os.path.join(d, "MCU", "Film (2008).mp4"), "wb").write(b"x")
            with open(os.path.join(d, "MCU", "Film (2008).hero.json"), "w", encoding="utf-8-sig") as f:   # what old Notepad writes
                json.dump({"tags": ["action"], "title": "Café Hero"}, f)
            c = make_db()
            library.scan(c, d, probe_fn=lambda p: {"runtime_s": 60, "vcodec": "h264", "acodec": "aac", "title": ""})
            row = c.execute("SELECT title,tags FROM media").fetchone()
            self.assertEqual(row["title"], "Café Hero")
            self.assertIn("action", row["tags"])

    def test_find_tool_uses_override_dir(self):
        with tempfile.TemporaryDirectory() as d:
            name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
            fake = os.path.join(d, name)
            open(fake, "w").write("")
            tools.forget()
            old = os.environ.get("HEROTV_FFMPEG_DIR"), os.environ.get("PATH")
            os.environ["HEROTV_FFMPEG_DIR"], os.environ["PATH"] = d, ""
            try:
                self.assertEqual(tools.find_tool("ffprobe"), fake)
            finally:
                tools.forget()
                os.environ["PATH"] = old[1]
                if old[0] is None:
                    os.environ.pop("HEROTV_FFMPEG_DIR")
                else:
                    os.environ["HEROTV_FFMPEG_DIR"] = old[0]


if __name__ == "__main__":
    unittest.main()
