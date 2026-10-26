"""'Report a problem': one plain-text report, secrets hidden, page errors included."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import config, launcher, report  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        shutil.copytree(Path(config.ROOT) / "config", Path(self.d) / "config")
        (Path(self.d) / "settings.json").write_text(json.dumps({"tmdb_key": "abcdef1234567890SECRET", "windowed": True,
                                                                 "weather": {"name": "Austin"}}))
        p = mock.patch.object(config, "settings_file", return_value=Path(self.d) / "settings.json")
        p.start(); self.addCleanup(p.stop)
        q = mock.patch.object(launcher, "app_data_dir", return_value=Path(self.d))
        q.start(); self.addCleanup(q.stop)
        (Path(self.d) / "herotv.log").write_text("line one\nGET https://api.themoviedb.org/3/x?api_key=abcdef1234567890SECRET\nlast line\n")
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"), channels_file=str(Path(self.d) / "config" / "channels.json"))
        self.c = connect(self.cfg.db_path)
        self.addCleanup(self.c.close)

    def test_report_has_what_is_needed_and_no_secrets(self):
        report.page_error("TypeError: x is undefined", "app.js:120")
        t = report.build(self.c, self.cfg, "Up moves sideways on Home", lan=True, dlna_on=False, page="home 1280x720")
        for want in ("HERO TV ", "Up moves sideways on Home", "home 1280x720", "TypeError: x is undefined", "last line",
                     "\"windowed\": true", "\"tmdb_key\": \"<set>\"", "Other devices: listener on", "channels.json:"):
            self.assertIn(want, t)
        self.assertNotIn("SECRET", t)
        self.assertIn("api_key=<hidden>", t)
        f = report.save(t)
        self.assertTrue(os.path.isfile(f))
        self.assertEqual(Path(f).read_text(encoding="utf-8"), t)

    def test_home_folder_and_user_name_are_hidden(self):
        home = os.path.expanduser("~")
        (Path(self.d) / "herotv.log").write_text(f"opened {home}{os.sep}Videos\n")
        t = report.build(self.c, self.cfg)
        if len(os.path.basename(home)) > 2:
            self.assertNotIn(home, t)
            self.assertIn("<home>", t)


if __name__ == "__main__":
    unittest.main()
