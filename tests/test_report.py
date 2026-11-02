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

    def test_report_names_a_video_that_failed_to_start(self):
        v = os.path.join(self.d, "Dragon Ball Z - 042.mkv")
        self.c.execute("INSERT INTO media(path,title,franchise,series,season,episode,verified,playable,available,vcodec,acodec,atracks,ord,size) "
                       "VALUES(?,?,?,?,?,?,1,1,1,'hevc','eac3','jpn*,eng',1,5)", (v, "Episode 42", "Dragon Ball", "Dragon Ball Z", 1, 42))
        mid = self.c.execute("SELECT id FROM media").fetchone()[0]
        self.c.commit()
        report.PLAY_ERRORS.clear()
        report.play_error(mid, "player error 4: DEMUXER_ERROR_COULD_NOT_OPEN")
        t = report.build(self.c, self.cfg)
        self.assertIn("Videos that failed to start (newest last):", t)
        self.assertIn("Dragon Ball Z - 042.mkv: player error 4: DEMUXER_ERROR_COULD_NOT_OPEN", t)
        self.assertIn("languages jpn*,eng", t)
        self.assertIn("the browser was given:", t)
        report.PLAY_ERRORS.clear()
        self.assertIn("Videos that failed to start: none", report.build(self.c, self.cfg))

    def test_report_says_what_became_of_the_repair_of_a_failed_video(self):
        v = os.path.join(self.d, "Spider Man 2.mp4")
        self.c.execute("INSERT INTO media(path,title,franchise,series,season,episode,verified,playable,available,vcodec,acodec,atracks,ord,size) "
                       "VALUES(?,?,?,?,?,?,1,1,1,'h264','aac','eng*,hin',1,500)", (v, "Spider Man 2", "Movies", "", 0, 0))
        mid = self.c.execute("SELECT id FROM media").fetchone()[0]
        self.c.commit()
        report.PLAY_ERRORS.clear()
        self.addCleanup(report.PLAY_ERRORS.clear)
        report.play_error(mid, "player error 3: PIPELINE_ERROR_DECODE: Failed to send audio packet for decoding")
        self.assertIn("ready copy / repair: none, and nothing is queued for it", report.build(self.c, self.cfg))
        self.c.execute("INSERT INTO prepared(media_id,file,src_size,status,why,made,bytes,alang,mix) VALUES(?,?,?,?,?,?,?,?,?)",
                       (mid, "", 500, "fix", "", 1000, 0, "", 0))
        self.c.commit()
        self.assertIn("sound repair is waiting in line", report.build(self.c, self.cfg))
        self.c.execute("UPDATE prepared SET status='failed', why='the copy came out shorter than the original', mix=2")
        self.c.commit()
        t = report.build(self.c, self.cfg)
        self.assertIn("repair FAILED at", t)
        self.assertIn("the copy came out shorter than the original", t)
        self.assertIn("Ready-copy maker:", t)
        self.assertIn("1 failed copies remembered", t)

    def test_sound_diagnostic_describes_the_track_and_its_first_packets(self):
        import subprocess
        from herotv import tools
        ff = tools.find_tool("ffmpeg")
        if not ff or not tools.find_tool("ffprobe"):
            self.skipTest("ffmpeg not installed")
        v = os.path.join(self.d, "diag.mp4")
        subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-f", "lavfi", "-i", "sine=frequency=300",
                        "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", v], check=True)
        t = "\n".join(report._audio_diag(v))
        self.assertIn("sound track declared", t)
        self.assertIn("aac", t)
        self.assertIn("first sound packets", t)
        self.assertIn("exit 0", t)
        self.assertIn("the PICTURE: exit 0", t)
        self.assertIn("the repair's own command on the first 30 s: exit 0", t)
        self.assertIn("result 3.", t)                                                 # the 3-second test file came out whole
        self.assertIn("the same, first sound packet skipped: exit", t)               # (an older ffmpeg may refuse that one: still reported)
        self.assertEqual(len([x for x in os.listdir(tempfile.gettempdir()) if x.startswith("herotv-diag-")]), 0)   # no litter
        broken = os.path.join(self.d, "broken.mp4")
        Path(broken).write_bytes(b"not a video at all")
        self.assertIn("first sound packets", "\n".join(report._audio_diag(broken)))      # no crash on a file it cannot read

    def test_home_folder_and_user_name_are_hidden(self):
        home = os.path.expanduser("~")
        (Path(self.d) / "herotv.log").write_text(f"opened {home}{os.sep}Videos\n")
        t = report.build(self.c, self.cfg)
        if len(os.path.basename(home)) > 2:
            self.assertNotIn(home, t)
            self.assertIn("<home>", t)


if __name__ == "__main__":
    unittest.main()
