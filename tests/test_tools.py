import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import config, jobs, launcher, server as SV  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402


def wait_job():
    for _ in range(100):
        j = jobs.current()
        if j and j["state"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


class JobTests(unittest.TestCase):
    def test_captures_say_and_result(self):
        def work():
            launcher.say("hello\nworld")
            return 0
        jobs.start("t", "Test", work, wait=True)
        j = jobs.current()
        self.assertEqual((j["state"], j["lines"]), ("done", ["hello", "world"]))
        launcher.say("not captured")                      # outside the job
        self.assertEqual(jobs.current()["lines"], ["hello", "world"])

    def test_failure_and_one_at_a_time(self):
        ev = threading.Event()
        jobs.start("slow", "Slow", lambda: ev.wait(5) and 0)
        with self.assertRaises(ValueError):
            jobs.start("other", "Other", lambda: 0)
        ev.set(); wait_job()
        jobs.start("bad", "Bad", lambda: 1 / 0, wait=True)
        self.assertEqual(jobs.current()["state"], "failed")
        self.assertTrue(any("division" in l for l in jobs.current()["lines"]))
        jobs.start("rc", "RC", lambda: 1, wait=True)
        self.assertEqual(jobs.current()["state"], "failed")


class ToolEndpointTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        shutil.copytree(Path(config.ROOT) / "config", Path(self.d) / "config")
        self.media = Path(self.d) / "media"; (self.media / "Inbox").mkdir(parents=True)
        self.cfg = Config(media_dir=self.media, db_path=os.path.join(self.d, "t.sqlite3"),
                          channels_file=str(Path(self.d) / "config" / "channels.json"))
        c = connect(self.cfg.db_path)
        c.execute("INSERT INTO media(path,title,verified,playable,available,runtime_s,vcodec,acodec) VALUES(?,?,1,0,1,60,'h264','dts')",
                  (str(self.media / "Bad.mkv"), "Bad Movie"))
        c.commit(); c.close()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(self.cfg)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        self.base = f"http://127.0.0.1:{srv.server_address[1]}"
        wait_job() if jobs.busy() else None

    def post(self, body):
        req = urllib.request.Request(self.base + "/api/job", json.dumps(body).encode(), {"Content-Type": "application/json"}, method="POST")
        try:
            r = urllib.request.urlopen(req)
            return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def test_tools_info(self):
        j = json.load(urllib.request.urlopen(self.base + "/api/tools"))
        self.assertTrue(j["free_sources"]); self.assertEqual(j["skipped"][0]["title"], "Bad Movie")
        self.assertIn("originals_bytes", j)

    def test_rejects_unknown_and_bad_input(self):
        self.assertEqual(self.post({"name": "rm -rf"})[0], 400)
        self.assertEqual(self.post({"name": "import", "path": os.path.join(self.d, "nope")})[0], 400)
        self.assertEqual(self.post({"name": "fix", "media_id": 999})[0], 400)
        self.assertEqual(self.post({"name": "fix", "media_id": "x"})[0], 400)       # file missing -> refused
        self.assertEqual(self.post({"name": "free", "count": 500})[0], 400)
        self.assertEqual(self.post({"name": "audio", "media_id": 1})[0], 400)

    def test_free_passes_choices(self):
        with mock.patch.object(launcher, "get_free_movies", return_value=0) as g:
            code, j = self.post({"name": "free", "count": 5, "lists": [0, 2]})
            self.assertEqual(code, 200); wait_job()
        self.assertEqual(g.call_args.args, (5, "1,3"))

    def test_import_runs(self):
        src = Path(self.d) / "usb"; src.mkdir()
        with mock.patch.object(launcher, "import_folder", return_value=0) as imp:
            self.assertEqual(self.post({"name": "import", "path": str(src)})[0], 200); wait_job()
        self.assertEqual(imp.call_args.args, ([str(src)],))
        j = json.load(urllib.request.urlopen(self.base + "/api/job"))["job"]
        self.assertEqual(j["state"], "done")


class FixAudioTrackTests(unittest.TestCase):
    def test_bad_track_number_refused(self):
        tr = [{"n": 0, "lang": "eng", "language": "English", "title": "", "codec": "aac", "channels": 2, "default": True},
              {"n": 1, "lang": "jpn", "language": "Japanese", "title": "", "codec": "aac", "channels": 2, "default": False}]
        with mock.patch.object(launcher.tools, "find_tool", return_value="/bin/true"), \
                mock.patch.object(launcher.library, "audio_tracks", return_value=tr), \
                mock.patch.object(launcher, "_after_change", return_value=0):
            self.assertEqual(launcher.fix_audio(["/x/a.mkv"], track=5), 1)
            self.assertEqual(launcher.fix_audio(["/x/a.mkv"], track=0), 0)      # already plays -> nothing to do


if __name__ == "__main__":
    unittest.main()
