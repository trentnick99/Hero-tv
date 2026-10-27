"""Always on: start with Windows, keep running when the TV window is closed, quit."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import alwayson, config, server as SV  # noqa: E402


class AlwaysOnTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.sf = Path(self.d) / "settings.json"
        p = mock.patch.object(config, "settings_file", return_value=self.sf)
        p.start(); self.addCleanup(p.stop)
        e = mock.patch.dict(os.environ, {"APPDATA": os.path.join(self.d, "Roaming")})
        e.start(); self.addCleanup(e.stop)

    def write(self, **kw):
        self.sf.write_text(json.dumps(kw))

    def test_background_follows_what_you_set_up(self):
        self.assertFalse(alwayson.background())                               # just the PC: quits with its window
        self.write(lan_share=True)
        self.assertTrue(alwayson.background())                                # phones need it
        self.write(roku={"ip": "192.168.1.40"})
        self.assertTrue(alwayson.background())                                # so does the Roku app
        self.write(roku={"ip": "192.168.1.40"}, background=False)
        self.assertFalse(alwayson.background())                               # unless you switch it off
        alwayson.set_background(True)
        self.assertTrue(json.loads(self.sf.read_text())["background"])

    def test_startup_shortcut(self):
        seen = []

        def fake(ps, env):
            seen.append(env)
            Path(env["HT_LINK"]).write_text("lnk")
            return env["HT_LINK"]
        link = alwayson.set_startup(True, run=fake)
        self.assertTrue(link.endswith(os.path.join("Startup", "HERO TV.lnk")))
        self.assertIn("--no-browser", seen[0]["HT_ARGS"])
        self.assertIn("--quiet", seen[0]["HT_ARGS"])
        self.assertTrue(alwayson.startup_on())
        self.write(background=False)
        self.assertTrue(alwayson.background())                                # starting with Windows keeps it running
        alwayson.set_startup(False)
        self.assertFalse(alwayson.startup_on())
        alwayson.set_startup(False)                                           # twice is fine

    def run_watch(self):
        """Run the heartbeat watcher for about 40 simulated minutes; returns how often it asked HERO TV to stop."""
        import threading
        app = SV.App.__new__(SV.App)
        app.last_hb = None
        stopped = []
        app.stop = lambda: stopped.append(1)
        clock, sleeps = [0], [0]

        def sleep(_s):
            sleeps[0] += 1
            if sleeps[0] > 500:
                raise SystemExit                           # end the simulated run
            clock[0] += 5
        started = []
        with mock.patch.object(threading.Thread, "start", lambda th: started.append(th)):
            SV.watch_heartbeat(app, idle_s=10, never_s=20)
        with mock.patch.object(SV.time, "sleep", sleep), mock.patch.object(SV.time, "monotonic", lambda: clock[0]):
            try:
                started[0]._target()
            except SystemExit:
                pass
        return stopped

    def test_closed_window_does_not_stop_it_when_always_on(self):
        self.write(background=True)
        self.assertEqual(self.run_watch(), [])
        self.write(background=False)
        self.assertEqual(self.run_watch(), [1])                                # not always on: turns off as before

if __name__ == "__main__":
    unittest.main()
