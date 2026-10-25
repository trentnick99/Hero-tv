import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from herotv import launcher, library, thumbs, tools  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402

HAVE_FFMPEG = bool(tools.find_tool("ffmpeg") and tools.find_tool("ffprobe"))
CHANNELS = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "channels.json")))["channels"]


def clip(path, seconds=3, acodec="aac", vcodec="libx264"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = tools.run([tools.find_tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10",
                   "-f", "lavfi", "-i", "sine=frequency=440", "-t", str(seconds), "-c:v", vcodec, "-pix_fmt", "yuv420p",
                   "-c:a", acodec, path])
    assert r.returncode == 0, r.stderr


class NamingTests(unittest.TestCase):
    def g(self, *parts):
        return library._guess(list(parts), os.path.splitext(parts[-1])[0] if "." in parts[-1] else parts[-1])

    def test_anime_numbering(self):
        a = self.g("Dragon Ball", "Dragon Ball Z", "Dragon Ball Z - 001 - The New Threat")
        self.assertEqual((a["series"], a["episode"], a["title"]), ("Dragon Ball Z", 1, "The New Threat"))
        b = self.g("Dragon Ball", "Dragon Ball Z Kai", "[Group] Dragon Ball Z Kai Episode 12 [1080p]")
        self.assertEqual((b["series"], b["episode"], b["title"]), ("Dragon Ball Z Kai", 12, "Episode 12"))
        c = self.g("Dragon Ball", "Dragon Ball Super - E045")
        self.assertEqual((c["series"], c["episode"]), ("Dragon Ball Super", 45))

    def test_movies_and_classic_episodes_unchanged(self):
        m = self.g("MCU", "Iron Man (2008)")
        self.assertEqual((m["title"], m["year"], m["episode"], m["series"]), ("Iron Man", 2008, 0, ""))
        e = self.g("Marvel Television", "Daredevil", "Daredevil S01E02 Cut Man")
        self.assertEqual((e["season"], e["episode"], e["title"], e["series"]), (1, 2, "Cut Man", "Daredevil"))

    def test_episodes_play_in_order(self):
        c = connect(":memory:")
        d = tempfile.mkdtemp()
        for n in (3, 1, 2):
            p = os.path.join(d, "Dragon Ball", "DBZ", f"DBZ - 00{n} - T{n}.mp4")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(b"x")
        library.scan(c, d, probe_fn=lambda p: {"runtime_s": 60, "vcodec": "h264", "acodec": "aac", "title": ""})
        rows = c.execute("SELECT episode FROM media ORDER BY ord,series,season,episode,title,id").fetchall()
        self.assertEqual([r[0] for r in rows], [1, 2, 3])


class DbTests(unittest.TestCase):
    def test_old_database_is_upgraded(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "old.sqlite3")
        old = sqlite3.connect(path)       # a v1 database: no color column, no favorites table
        old.executescript("CREATE TABLE channels(id TEXT PRIMARY KEY, number INTEGER UNIQUE, name TEXT NOT NULL, "
                          "mode TEXT DEFAULT 'sequential', rules TEXT DEFAULT '{}', description TEXT DEFAULT '');")
        old.commit()
        old.close()
        c = connect(path)
        cols = [r[1] for r in c.execute("PRAGMA table_info(channels)")]
        self.assertIn("color", cols)
        self.assertIsNotNone(c.execute("SELECT name FROM sqlite_master WHERE name='favorites'").fetchone())


@unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg")
class ThumbTests(unittest.TestCase):
    def test_thumbnail_is_a_real_jpeg_and_pruned_when_video_changes(self):
        d = tempfile.mkdtemp()
        cfg = Config()
        cfg.db_path, cfg.media_dir = os.path.join(d, "t.sqlite3"), os.path.join(d, "media")
        vid = os.path.join(cfg.media_dir, "MCU", "Film (2010).mp4")
        clip(vid, 6)
        c = connect(cfg.db_path)
        library.scan(c, cfg.media_dir)
        c.close()
        self.assertEqual(thumbs.generate_missing(cfg, connect), 1)
        f = thumbs.thumb_file(cfg, connect(cfg.db_path).execute("SELECT id,size,runtime_s FROM media").fetchone())
        self.assertEqual(open(f, "rb").read(3), b"\xff\xd8\xff")
        self.assertEqual(thumbs.generate_missing(cfg, connect), 0)       # nothing to redo
        clip(vid, 9)                                                      # replaced video -> new grab, old one removed
        c = connect(cfg.db_path)
        library.scan(c, cfg.media_dir)
        c.close()
        self.assertEqual(thumbs.generate_missing(cfg, connect), 1)
        self.assertEqual(len(os.listdir(thumbs.thumb_dir(cfg))), 1)


@unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg")
class ImportTests(unittest.TestCase):
    def test_ac3_file_is_converted_then_filed(self):
        media = tempfile.mkdtemp()
        src = os.path.join(media, "Inbox", "Spider-Man (2002).mkv")
        clip(src, 3, acodec="ac3")
        self.assertFalse(library.probe(src)["acodec"] in library.PLAY_A)
        picked = [c for c in CHANNELS if c["id"] == "spider-verse"]
        self.assertTrue(launcher._place(src, picked, media, force_move=True))
        out = os.path.join(media, "Spider-Verse", "Spider-Man (2002).mp4")
        self.assertTrue(os.path.isfile(out))
        self.assertEqual(library.probe(out)["acodec"], "aac")
        self.assertTrue(os.path.isfile(os.path.join(media, "Inbox", ".originals", "Spider-Man (2002).mkv")))
        self.assertIn("spider-verse", json.load(open(os.path.join(media, "Spider-Verse", "Spider-Man (2002).hero.json")))["tags"])

    def test_avi_is_accepted_for_conversion(self):
        media = tempfile.mkdtemp()
        src = os.path.join(media, "Old Film (1950).avi")
        clip(src, 2, acodec="mp3", vcodec="mpeg4")
        picked = [c for c in CHANNELS if c["id"] == "dc"]
        self.assertTrue(launcher._place(src, picked, media, force_move=True))
        self.assertTrue(os.path.isfile(os.path.join(media, "DC", "Old Film (1950).mp4")))


if __name__ == "__main__":
    unittest.main()


class PictureFormatTests(unittest.TestCase):
    def test_which_pictures_a_browser_can_show(self):
        ok = library.video_ok
        self.assertTrue(ok("h264", "yuv420p|high"))
        self.assertTrue(ok("h264", ""))                                  # old rows with no format info
        self.assertFalse(ok("h264", "yuv420p10le|high 10"))              # 10-bit anime rips: sound but black screen
        self.assertFalse(ok("h264", "yuv444p|high 4:4:4 predictive"))
        self.assertTrue(ok("vp9", "yuv420p10le|profile 2"))
        self.assertFalse(ok("mpeg4", "yuv420p|"))
        old = library.IS_WIN
        try:
            library.IS_WIN = True
            self.assertFalse(ok("hevc", "yuv420p|main"))
            os.environ["HEROTV_ALLOW_HEVC"] = "1"
            self.assertTrue(ok("hevc", "yuv420p|main"))
        finally:
            library.IS_WIN = old
            os.environ.pop("HEROTV_ALLOW_HEVC", None)

    def test_scan_skips_10bit_and_explains_it(self):
        c = connect(":memory:")
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "DC"))
        open(os.path.join(d, "DC", "Anime (2001).mkv"), "wb").write(b"x")
        library.scan(c, d, probe_fn=lambda p: {"runtime_s": 60, "vcodec": "h264", "vfmt": "yuv420p10le|high 10", "acodec": "aac", "title": ""})
        r = c.execute("SELECT playable,vfmt,vcodec,acodec FROM media").fetchone()
        self.assertEqual(r["playable"], 0)
        self.assertIn("10-bit", library.why_not_playable(r["vcodec"], r["acodec"], r["vfmt"]))
        library.scan(c, d, probe_fn=lambda p: None)         # rescan of an unchanged file keeps the verdict
        self.assertEqual(c.execute("SELECT playable FROM media").fetchone()[0], 0)

    @unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg")
    def test_real_10bit_file_is_detected_and_converted(self):
        d = tempfile.mkdtemp()
        src = os.path.join(d, "Ten Bit (2010).mkv")
        r = tools.run([tools.find_tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10",
                       "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p10le",
                       "-c:a", "aac", src])
        if r.returncode != 0:
            self.skipTest("this ffmpeg has no 10-bit x264")
        p = library.probe(src)
        self.assertFalse(library.video_ok(p["vcodec"], p["vfmt"]))
        st, out = launcher._convert_one(src, tools.find_tool("ffmpeg"))
        self.assertEqual(st, "converted")
        q = library.probe(out)
        self.assertTrue(library.video_ok(q["vcodec"], q["vfmt"]), q)


@unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg")
class StorageTests(unittest.TestCase):
    def fat_clip(self, path, seconds=8, size="640x360"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        r = tools.run([tools.find_tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=24",
                       "-f", "lavfi", "-i", "sine=frequency=440", "-t", str(seconds), "-c:v", "libx264", "-b:v", "6M",
                       "-minrate", "6M", "-maxrate", "6M", "-bufsize", "2M", "-pix_fmt", "yuv420p", "-c:a", "aac", path])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_shrink_keeps_length_verifies_and_keeps_original(self):
        d = tempfile.mkdtemp()
        src = os.path.join(d, "Dragon Ball", "Show", "Show - 001 - Pilot.mp4")
        self.fat_clip(src)
        before = os.path.getsize(src)
        self.assertEqual(launcher.shrink([d], delete_originals=False, fast=True, yes=True), 0)
        self.assertLess(os.path.getsize(src), before * 0.9)
        self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(src), ".originals", "Show - 001 - Pilot.mp4")))
        self.assertAlmostEqual(library.probe(src)["runtime_s"], 8, delta=1)
        self.assertIn(launcher.SHRUNK_TAG, library.probe(src)["comment"])
        # run again: already shrunk -> nothing happens, the saved original is untouched
        self.assertEqual(launcher.shrink([d], delete_originals=False, fast=True, yes=True), 0)
        saved = os.path.join(os.path.dirname(src), ".originals")
        self.assertEqual(os.listdir(saved), ["Show - 001 - Pilot.mp4"])
        self.assertEqual(os.path.getsize(os.path.join(saved, "Show - 001 - Pilot.mp4")), before)

    def test_saved_original_is_never_overwritten(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "a.mp4")
        open(f, "w").write("first")
        launcher._keep_original(f)
        open(f, "w").write("second")
        launcher._keep_original(f)
        keep = os.path.join(d, ".originals")
        self.assertEqual(sorted(os.listdir(keep)), ["a (2).mp4", "a.mp4"])
        self.assertEqual(open(os.path.join(keep, "a.mp4")).read(), "first")

    def test_shrink_can_delete_original_and_cleanup_frees_space(self):
        d = tempfile.mkdtemp()
        a, b = os.path.join(d, "DC", "A (2001).mp4"), os.path.join(d, "DC", "B (2002).mp4")
        self.fat_clip(a)
        self.fat_clip(b)
        launcher.shrink([a], delete_originals=True, fast=True, yes=True)
        self.assertFalse(os.path.exists(os.path.join(d, "DC", ".originals")))
        launcher.shrink([b], delete_originals=False, fast=True, yes=True)
        self.assertTrue(os.path.isdir(os.path.join(d, "DC", ".originals")))
        os.environ["HEROTV_MEDIA"] = d
        try:
            self.assertEqual(launcher.cleanup_originals(yes=True), 0)
        finally:
            os.environ.pop("HEROTV_MEDIA")
        self.assertFalse(os.path.exists(os.path.join(d, "DC", ".originals")))
        self.assertTrue(os.path.isfile(b))


class PlanTests(unittest.TestCase):
    def test_plan_caps_resolution_and_spots_compact_files(self):
        movie = {"runtime_s": 7200, "height": 2160, "vcodec": "h264", "vfmt": "yuv420p|high", "acodec": "aac", "bitrate": 30_000_000}
        pl = launcher._shrink_plan(movie, "MCU/Film (2012).mkv")
        self.assertEqual((pl["scale_to"], pl["crf"], pl["already_small"]), (1080, 23, False))
        ep = {"runtime_s": 1320, "height": 1080, "vcodec": "h264", "vfmt": "yuv420p|high", "acodec": "aac", "bitrate": 9_000_000}
        pe = launcher._shrink_plan(ep, "South Park/S01/ep.mkv")
        self.assertEqual((pe["scale_to"], pe["tune_animation"]), (720, True))
        self.assertLess(pe["est_bytes"], ep["bitrate"] / 8 * ep["runtime_s"] * 0.2)
        small = dict(ep, height=480, bitrate=700_000)
        self.assertTrue(launcher._shrink_plan(small, "South Park/S01/ep.mp4")["already_small"])

    def test_saved_media_folder_is_used(self):
        import importlib
        from herotv import config
        d = tempfile.mkdtemp()
        os.environ["LOCALAPPDATA"] = d
        os.environ.pop("HEROTV_MEDIA", None)
        old_win = config.IS_WIN
        try:
            config.IS_WIN = True
            vids = tempfile.mkdtemp()
            self.assertEqual(launcher.set_media_folder(vids), 0)
            self.assertEqual(str(config.Config().media_dir), vids)
        finally:
            config.IS_WIN = old_win
            os.environ.pop("LOCALAPPDATA", None)
