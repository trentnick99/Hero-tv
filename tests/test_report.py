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

    def test_report_lists_the_sound_of_recently_played_videos(self):
        import subprocess
        from herotv import tools
        ff = tools.find_tool("ffmpeg")
        if not ff or not tools.find_tool("ffprobe"):
            self.skipTest("ffmpeg not installed")
        v = os.path.join(self.d, "Iron Test 3 (2013).mp4")
        subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-f", "lavfi", "-i", "sine=frequency=300",
                        "-f", "lavfi", "-i", "sine=frequency=900", "-t", "2", "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "6", "-metadata:s:a:0", "language=hin", "-metadata:s:a:1", "language=eng", v], check=True)
        self.c.execute("INSERT INTO media(path,title,franchise,series,season,episode,verified,playable,available,vcodec,acodec,atracks,ord,size) "
                       "VALUES(?,?,?,?,?,?,1,1,1,'h264','aac','hin*,eng',1,5)", (v, "Iron Test 3", "Movies", "", 0, 0))
        mid = self.c.execute("SELECT id FROM media").fetchone()[0]
        self.c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(?,?,0,?)", (mid, 30, 1000))
        self.c.commit()
        t = report.build(self.c, self.cfg)
        self.assertIn("Videos played last", t)
        self.assertIn("Iron Test 3 (2013).mp4", t)
        self.assertIn("track 1: hin aac 6 ch default", t)
        self.assertIn("track 2: eng aac 6 ch", t)
        self.assertIn("ready copy: none", t)
        self.assertIn("browser gets: the original file", t)

    def test_home_folder_and_user_name_are_hidden(self):
        home = os.path.expanduser("~")
        (Path(self.d) / "herotv.log").write_text(f"opened {home}{os.sep}Videos\n")
        t = report.build(self.c, self.cfg)
        if len(os.path.basename(home)) > 2:
            self.assertNotIn(home, t)
            self.assertIn("<home>", t)


if __name__ == "__main__":
    unittest.main()
