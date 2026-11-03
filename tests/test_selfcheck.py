"""Check everything: plain-language results, nothing changed, and the once-per-update startup check."""
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
from herotv import selfcheck, tools, __version__
from herotv.config import Config
from herotv.server import App, make_handler


class SelfCheck(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(f"{self.root}/Inbox")
        self.web = Path(self.root) / "web"
        self.web.mkdir()
        for f in ("index.html", "app.js", "app.css"):
            (self.web / f).write_text("x")
        self.chf = os.path.join(self.root, "ch.json")
        Path(self.chf).write_text(json.dumps({"channels": [{"id": "a", "number": 1, "name": "A"}]}))
        self.cfg = Config(media_dir=self.root, db_path=tmpdb(), channels_file=self.chf, tz="America/New_York", port=0, web_dir=self.web)
        self.c = make_db(self.cfg.db_path)
        self.addCleanup(self.c.close)
        self.data = Path(self.root) / "data"
        for target in ("herotv.launcher.app_data_dir",):
            m = mock.patch(target, return_value=self.data)
            m.start()
            self.addCleanup(m.stop)
        sf = mock.patch("herotv.config.settings_file", return_value=self.data / "settings.json")
        sf.start()
        self.addCleanup(sf.stop)

    def levels(self):
        with mock.patch.object(tools, "find_tool", return_value="/usr/bin/x"):
            return {x["name"]: x["level"] for x in selfcheck.run(self.c, self.cfg)}

    def test_missing_tools_and_files_fail_in_plain_words(self):
        with mock.patch.object(tools, "find_tool", return_value=None):
            r = {x["name"]: x for x in selfcheck.run(self.c, self.cfg)}
        self.assertEqual(r["Video tools"]["level"], "fail")
        self.assertIn("ffmpeg", r["Video tools"]["text"])
        (self.web / "app.js").unlink()
        self.assertEqual(self.levels()["Program files"], "fail")

    def test_missing_media_folder_and_all_channels_off(self):
        shutil.rmtree(self.root + "/Inbox")
        self.cfg.media_dir = Path(self.root) / "nope"
        self.assertEqual(self.levels()["Media folder"], "fail")
        Path(self.chf).write_text(json.dumps({"channels": [{"id": "a", "number": 1, "name": "A", "off": True}]}))
        self.assertEqual(self.levels()["Channels"], "fail")

    def test_empty_guide_fails_and_a_slot_makes_it_ok(self):
        self.assertEqual(self.levels()["TV guide"], "fail")
        with mock.patch("herotv.scheduler.current", return_value={"x": 1}):
            self.assertEqual(self.levels()["TV guide"], "ok")

    def test_a_crashing_check_is_reported_not_raised(self):
        with mock.patch.object(selfcheck, "_media", side_effect=RuntimeError("boom")), mock.patch.object(tools, "find_tool", return_value="x"):
            r = selfcheck.run(self.c, self.cfg)
        self.assertTrue(any(x["level"] == "fail" and "boom" in x["text"] for x in r))

    def test_log_errors_are_noticed_and_summary_counts(self):
        self.data.mkdir(parents=True, exist_ok=True)
        (self.data / "herotv.log").write_text("fine\nTraceback (most recent call last):\n  x\n[page-error] oops (app.js:1)\n")
        lv = self.levels()
        self.assertEqual(lv["Errors in the log"], "warn")
        self.assertEqual(lv["Screen errors"], "warn")
        self.assertEqual(selfcheck.summary([{"level": "fail"}, {"level": "warn"}])["level"], "fail")
        self.assertEqual(selfcheck.summary([{"level": "ok"}])["level"], "ok")

    def test_nothing_is_changed(self):
        before = sorted(p.name for p in Path(self.root).rglob("*") if p.is_file())
        self.levels()
        after = sorted(p.name for p in Path(self.root).rglob("*") if p.is_file())
        self.assertEqual(before, after)

    def test_new_version_is_noticed_once_and_first_start_is_not_an_update(self):
        self.assertFalse(selfcheck.new_version_started())            # first ever start
        self.assertFalse(selfcheck.new_version_started())            # same version again
        (self.data / "lastversion.txt").write_text("0.0.1")
        self.assertTrue(selfcheck.new_version_started())
        self.assertFalse(selfcheck.new_version_started())

    def test_routes(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(self.cfg)))
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        get = lambda p: json.load(urllib.request.urlopen(base + p))
        with mock.patch.object(tools, "find_tool", return_value="x"):
            r = get("/api/selfcheck")
            self.assertEqual(r["version"], __version__)
            self.assertTrue(r["checks"] and r["summary"]["level"] in ("ok", "warn", "fail"))
            (self.data / "lastversion.txt").write_text("0.0.1")
            s = get("/api/selfcheck?startup=1")
            self.assertTrue(s["update"])
            self.assertEqual(get("/api/selfcheck?startup=1")["update"], True)     # remembered for this run
            items = get("/api/attention")["items"]
            self.assertTrue(any(i["text"].startswith("After the update:") for i in items))


if __name__ == "__main__":
    unittest.main()
