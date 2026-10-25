import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import add, make_db  # noqa: E402
from herotv import scheduler as S, server as SV  # noqa: E402
from herotv.config import Config  # noqa: E402


class SmartServerTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.media = os.path.join(self.d, "media")
        os.makedirs(self.media)
        cfg = Config(); cfg.db_path = os.path.join(self.d, "t.sqlite3"); cfg.tz = "UTC"; cfg.media_dir = self.media
        self.c = make_db(cfg.db_path)
        self.mid = add(self.c, "A", 600)
        self.app = SV.App(cfg)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(self.app))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        self.base = f"http://127.0.0.1:{srv.server_address[1]}"

    def get(self, path):
        return json.load(urllib.request.urlopen(self.base + path))

    def post(self, path, body):
        r = urllib.request.Request(self.base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(r))

    def test_seen_accumulates_and_marks_watched(self):
        for _ in range(10):
            self.post("/api/seen", {"media_id": self.mid, "secs": 30})
        self.assertEqual(self.c.execute("SELECT secs FROM seen").fetchone()[0], 300)
        self.assertIn(self.mid, S.seen_ids(self.c))             # 300 s of 600 s = half

    def test_seen_validation(self):
        for body, code in (({"media_id": self.mid, "secs": 9999}, 400), ({"media_id": self.mid, "secs": -1}, 400),
                           ({"media_id": 12345, "secs": 30}, 404), ({"secs": 30}, 400)):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.post("/api/seen", body)
            self.assertEqual(cm.exception.code, code, body)

    def test_prefs_round_trip_and_validation(self):
        self.assertEqual(self.get("/api/prefs"), {})
        self.post("/api/prefs", {"channel": 7, "volume": 0.4, "muted": False})
        self.assertEqual(self.get("/api/prefs"), {"channel": 7, "volume": 0.4, "muted": False})
        self.post("/api/prefs", {"muted": True})
        self.assertEqual(self.get("/api/prefs")["muted"], True)
        self.assertEqual(self.get("/api/prefs")["channel"], 7)
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/prefs", {"volume": 5})
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/prefs", {"channel": "abc"})

    def test_heartbeat_reports_library_version(self):
        j = self.get("/api/hb")
        self.assertEqual((j["ok"], j["lib"]), (True, 0))

    def test_library_signature_changes_with_files_and_sidecars_only(self):
        a = self.app.library_signature()
        open(os.path.join(self.media, "notes.txt"), "w").close()
        self.assertEqual(self.app.library_signature(), a)
        open(os.path.join(self.media, "x.mp4"), "wb").close()
        b = self.app.library_signature()
        self.assertNotEqual(a, b)
        open(os.path.join(self.media, "x.hero.json"), "w").write("{}")
        self.assertNotEqual(self.app.library_signature(), b)

    def test_unplugged_drive_is_not_treated_as_a_change(self):
        self.app.cfg.media_dir = os.path.join(self.d, "nope")
        self.assertIsNone(self.app.library_signature())

    def test_watcher_notices_new_video_after_it_settles(self):
        self.app.watch_library_forever(every=0.15)
        time.sleep(0.4)
        with open(os.path.join(self.media, "New Movie (2020).mp4"), "wb") as fh:
            fh.write(b"not really a video")
        deadline = time.time() + 6
        while time.time() < deadline and self.app.lib_version == 0:
            time.sleep(0.1)
        self.assertEqual(self.app.lib_version, 1)
        self.assertIn("new", self.app.lib_note)
        self.assertEqual(self.get("/api/hb")["lib"], 1)
        time.sleep(0.6)
        self.assertEqual(self.app.lib_version, 1, "no repeated refresh when nothing changed")


if __name__ == "__main__":
    unittest.main()
