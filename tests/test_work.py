"""The Settings progress display: what is being filed / converted / copied right now, and how far along it is."""
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from helpers import make_db, tmpdb
from herotv import inbox, launcher, library, prepare, tools, work
from herotv.config import Config
from herotv.server import App, make_handler
from test_prepare import FF, HAVE_FF, clip


def reset():
    with work._lock:
        work._active.clear()
        work._recent.clear()
    work.batch(0, 0)


class Tracker(unittest.TestCase):
    def setUp(self):
        reset()
        self.addCleanup(reset)

    def test_a_task_shows_while_it_runs_and_is_remembered_after(self):
        work.begin("inbox", "A.mkv")
        work.stage("Converting the sound to AAC")
        work.percent(work.current(), 0.426)
        t = work.snapshot()["active"][0]
        self.assertEqual((t["name"], t["stage"], t["pct"]), ("A.mkv", "Converting the sound to AAC", 42))
        work.end("filed")
        s = work.snapshot()
        self.assertEqual(s["active"], [])
        self.assertEqual([(r["name"], r["result"]) for r in s["recent"]], [("A.mkv", "filed")])

    def test_percent_is_kept_between_0_and_99_and_stage_resets_it(self):
        work.begin("copy", "B.mkv")
        k = work.current()
        work.percent(k, 7.0)
        self.assertEqual(work.snapshot()["active"][0]["pct"], 99)
        work.percent(k, -1)
        self.assertEqual(work.snapshot()["active"][0]["pct"], 0)
        work.stage("Sorting onto its channel")
        self.assertIsNone(work.snapshot()["active"][0]["pct"])
        work.end()

    def test_calls_without_a_task_do_nothing(self):
        work.stage("x")                              # a job started from Settings has no progress bar: no error
        work.percent(None, 0.5)
        work.end()
        self.assertEqual(work.snapshot()["active"], [])

    def test_quiet_end_and_repeats(self):
        work.begin("inbox", "C.mkv")
        work.end("left in the Inbox", quiet=True)
        self.assertEqual(work.snapshot()["recent"], [])
        for _ in range(3):                           # a retry replaces its old line instead of piling up
            work.begin("inbox", "D.mkv")
            work.end("left in the Inbox")
        self.assertEqual(len(work.snapshot()["recent"]), 1)
        for i in range(30):
            work.begin("inbox", f"E{i}.mkv")
            work.end("filed")
        self.assertEqual(len(work.snapshot()["recent"]), work.KEEP)
        self.assertEqual(work.snapshot()["recent"][0]["name"], "E29.mkv")      # newest first

    def test_tasks_on_two_threads_stay_apart(self):
        work.begin("inbox", "main.mkv")
        done = []

        def other():
            work.begin("copy", "other.mkv")
            work.stage("Making a ready-to-play copy")
            done.append(work.current())
            work.end("copy ready")
        t = threading.Thread(target=other)
        t.start()
        t.join()
        names = [x["name"] for x in work.snapshot()["active"]]
        self.assertEqual(names, ["main.mkv"])
        work.end("filed")


class Scan(unittest.TestCase):
    def setUp(self):
        reset()
        self.addCleanup(reset)
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(f"{self.root}/Movies")
        self.cfg = Config(media_dir=self.root, db_path=tmpdb(), channels_file=os.path.join(self.root, "ch.json"),
                          tz="America/New_York", port=0)
        Path(self.cfg.channels_file).write_text(json.dumps({"channels": []}))
        make_db(self.cfg.db_path).close()
        sf = mock.patch("herotv.config.settings_file", return_value=Path(self.root) / "settings.json")
        sf.start()
        self.addCleanup(sf.stop)

    def test_scan_says_which_new_video_it_is_reading(self):
        for n in ("A (2020).mp4", "B (2021).mp4"):
            Path(self.root, "Movies", n).write_bytes(b"x")
        c = make_db(self.cfg.db_path)
        self.addCleanup(c.close)
        stages = []
        orig = work.stage
        work.begin("scan", "Your library")
        with mock.patch.object(work, "stage", side_effect=lambda t, p=None: (stages.append(t), orig(t, p))):
            library.scan(c, self.root, probe_fn=lambda p: None)
        work.end()
        self.assertEqual(stages, ["Reading new video 1: A (2020).mp4", "Reading new video 2: B (2021).mp4"])

    def test_refresh_is_logged_only_when_something_changed(self):
        app = App(self.cfg)
        Path(self.root, "Movies", "A (2020).mp4").write_bytes(b"x")
        with mock.patch.object(library, "probe", return_value=None):
            app.refresh_library()
            self.assertEqual([r["result"] for r in work.snapshot()["recent"]], ["1 new"])
            app.refresh_library()                                   # nothing changed: no new line
        self.assertEqual(len(work.snapshot()["recent"]), 1)
        self.assertEqual(work.snapshot()["active"], [])


@unittest.skipUnless(HAVE_FF, "ffmpeg/ffprobe not installed")
class Real(unittest.TestCase):
    def setUp(self):
        reset()
        self.addCleanup(reset)
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(f"{self.root}/Movies")
        os.makedirs(f"{self.root}/Inbox")
        self.cfg = Config(media_dir=self.root, db_path=tmpdb(), channels_file=os.path.join(self.root, "ch.json"),
                          tz="America/New_York", port=0)
        Path(self.cfg.channels_file).write_text(json.dumps({"channels": [{"id": "m", "number": 1, "name": "Movies", "match": {"franchise": ["Movies"]}}]}))
        Path(self.root, "auto-sort.json").write_text(json.dumps({"rules": []}))
        self.c = make_db(self.cfg.db_path)
        self.addCleanup(self.c.close)
        sf = mock.patch("herotv.config.settings_file", return_value=Path(self.root) / "settings.json")
        sf.start()
        self.addCleanup(sf.stop)
        prepare.set_folder(self.root)

    def test_ffmpeg_reports_how_far_along_it_is(self):
        src = f"{self.root}/in.mkv"
        clip(src, 4, "ac3")
        work.begin("inbox", "in.mkv")
        seen = []
        orig = work.percent
        with mock.patch.object(work, "percent", side_effect=lambda k, f: (seen.append(f), orig(k, f))):
            r = tools.run_ffmpeg([FF, "-v", "error", "-stats", "-y", "-i", src, "-c:v", "copy", "-c:a", "aac", f"{self.root}/out.mp4"], 4)
        work.end()
        self.assertEqual(r.returncode, 0)
        self.assertTrue(seen, "no progress was reported")
        self.assertTrue(all(0 <= f <= 1.5 for f in seen))

    def test_inbox_file_is_followed_from_check_to_sorted(self):
        src = f"{self.root}/Inbox/Dolby Film (2020).mkv"
        clip(src, 3, "ac3")
        old = time.time() - 600
        os.utime(src, (old, old))
        stages, active = [], []
        orig = work.stage
        real_place = launcher._place

        def place(*a, **k):
            active.append([t["name"] for t in work.snapshot()["active"]])
            return real_place(*a, **k)
        with mock.patch.object(work, "stage", side_effect=lambda t, p=None: (stages.append(t), orig(t, p))), \
                mock.patch.object(launcher, "say", lambda *a, **k: None):
            picked = [{"name": "Movies", "match": {"franchise": ["Movies"]}}]
            with mock.patch("herotv.sortrules.targets", return_value=picked):
                seen = {}
                inbox.run_once(self.cfg, seen, place=place, facts=lambda s: None)
                r = inbox.run_once(self.cfg, seen, place=place, facts=lambda s: None)
        self.assertEqual(r["filed"], ["Dolby Film (2020).mkv"])
        self.assertEqual(active, [["Dolby Film (2020).mkv"]])
        for want in (work.FIRST, "Checking the file", "Converting the sound to AAC", "Sorting onto its channel"):
            self.assertIn(want, stages)
        s = work.snapshot()
        self.assertEqual(s["active"], [])
        self.assertEqual(s["recent"][0]["result"], "filed")
        self.assertEqual(s["batch"], {"total": 0, "done": 0})
        self.assertTrue(os.path.isfile(f"{self.root}/Movies/Dolby Film (2020).mp4"))

    def test_nothing_matched_is_not_logged_as_work(self):
        src = f"{self.root}/Inbox/Unknown thing.mkv"
        clip(src, 2, "ac3")
        old = time.time() - 600
        os.utime(src, (old, old))
        with mock.patch("herotv.sortrules.targets", return_value=[]):
            seen = {}
            inbox.run_once(self.cfg, seen, place=lambda *a, **k: True, facts=lambda s: None)
            inbox.run_once(self.cfg, seen, place=lambda *a, **k: True, facts=lambda s: None)
        self.assertEqual(work.snapshot()["recent"], [])
        self.assertTrue(os.path.isfile(src))                       # untouched

    def test_copy_making_is_tracked_and_http_shows_it(self):
        dolby = f"{self.root}/Movies/Dolby Film (2020).mkv"
        clip(dolby, 3, "ac3")
        library.scan(self.c, self.root)
        inside = []
        real = prepare.prepare_one

        def spy(*a, **k):
            inside.append([(t["kind"], t["name"]) for t in work.snapshot()["active"]])
            return real(*a, **k)
        with mock.patch.object(prepare, "prepare_one", spy):
            self.assertTrue(prepare.run_once(self.c, FF, self.root))
        self.assertEqual(inside, [[("copy", "Dolby Film (2020).mkv")]])
        self.assertEqual(work.snapshot()["recent"][0]["result"], "copy ready")
        app = App(self.cfg)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        shutil.copy(dolby, f"{self.root}/Inbox/Waiting one.mkv")
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/work") as r:
            j = json.load(r)
        self.assertEqual(j["inbox"]["waiting"], 1)
        self.assertEqual(j["inbox"]["names"], ["Waiting one.mkv"])
        self.assertEqual((j["copies"]["need"], j["copies"]["ready"]), (1, 1))
        self.assertEqual(j["recent"][0]["name"], "Dolby Film (2020).mkv")


if __name__ == "__main__":
    unittest.main()
