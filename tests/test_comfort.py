"""Even volume, night mode, screensaver, TV edge margin settings."""
import datetime as dt
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import make_db
from herotv import config, loudness as L, settings_api as SA, tools


class Comfort(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        sf = Path(self.d) / "settings.json"
        p = mock.patch.object(config, "settings_file", return_value=sf)
        p.start(); self.addCleanup(p.stop)

    def test_gain(self):
        self.assertEqual(L.gain_db(-30), 9.0)                 # quiet: up, at most 9 dB
        self.assertEqual(L.gain_db(-14), -6.0)                # loud: down
        self.assertEqual(L.gain_db(-14, night=True), -10.0)   # quieter at night
        self.assertEqual(L.gain_db(None), 0.0)

    def test_settings_and_night_window(self):
        c = SA.comfort({})
        self.assertEqual((c["level"], c["screensaver"], c["safe_margin"], c["theme"], c["night"]["active"]),
                         (True, True, 0, "classic", False))
        SA.update({"night": {"on": True, "from": "22:00", "to": "07:00"}, "safe_margin": 2.5, "level_volume": False,
                   "theme": "black"})
        d = SA._load()
        z = dt.timezone.utc
        late = dt.datetime(2026, 10, 27, 23, 30, tzinfo=z).timestamp()
        noon = dt.datetime(2026, 10, 27, 12, 0, tzinfo=z).timestamp()
        early = dt.datetime(2026, 10, 27, 6, 59, tzinfo=z).timestamp()
        self.assertTrue(SA.comfort(d, late, z)["night"]["active"])
        self.assertTrue(SA.comfort(d, early, z)["night"]["active"])
        self.assertFalse(SA.comfort(d, noon, z)["night"]["active"])
        self.assertEqual((SA.comfort(d)["safe_margin"], SA.comfort(d)["level"], SA.comfort(d)["theme"]), (2.5, False, "black"))
        for bad in ({"safe_margin": 7}, {"theme": "pink"}, {"night": {"on": True, "from": "10pm", "to": "07:00"}}):
            with self.assertRaises(ValueError):
                SA.update(bad)


class Measure(unittest.TestCase):
    def test_todo_and_store(self):
        c = make_db()
        c.execute("INSERT INTO media(path,title,verified,playable,available,runtime_s) VALUES('/nope.mp4','X',1,1,1,60)")
        c.commit()
        self.assertEqual(len(L.todo(c)), 1)
        L.run_once(c, "ffmpeg")
        self.assertEqual(L.todo(c), [])
        self.assertIsNone(L.for_media(c, 1))                  # missing file: nothing measured, not tried again

    @unittest.skipUnless(tools.find_tool("ffmpeg"), "needs ffmpeg")
    def test_measure_real_sound(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        ff = tools.find_tool("ffmpeg")
        for name, vol in (("quiet", "-30dB"), ("loud", "-3dB")):
            subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=20", "-af", f"volume={vol}",
                            os.path.join(d, name + ".m4a")], check=True)
        q, lo = L.measure(ff, os.path.join(d, "quiet.m4a"), 20), L.measure(ff, os.path.join(d, "loud.m4a"), 20)
        self.assertAlmostEqual(lo - q, 27, delta=2)
        self.assertGreater(L.gain_db(q), L.gain_db(lo))


if __name__ == "__main__":
    unittest.main()
