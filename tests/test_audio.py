import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from herotv import launcher, library, tools  # noqa: E402
from herotv.config import Config  # noqa: E402

FF = tools.find_tool("ffmpeg")


@unittest.skipUnless(FF and tools.find_tool("ffprobe"), "ffmpeg not installed")
class AudioTests(unittest.TestCase):
    def make(self, name, first="jpn", second="eng", ext=".mkv"):
        d = tempfile.mkdtemp()
        path = os.path.join(d, name + ext)
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10:duration=2",
                        "-f", "lavfi", "-i", "sine=frequency=300:duration=2", "-f", "lavfi", "-i", "sine=frequency=900:duration=2",
                        "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        f"-metadata:s:a:0", f"language={first}", f"-metadata:s:a:1", f"language={second}",
                        "-disposition:a:0", "default", "-disposition:a:1", "0", path], check=True, **tools.HIDE)
        return d, path

    def test_reads_tracks(self):
        _d, path = self.make("Movie")
        t = library.audio_tracks(path)
        self.assertEqual([x["lang"] for x in t], ["jpn", "eng"])
        self.assertEqual([x["language"] for x in t], ["Japanese", "English"])
        self.assertEqual(library.playing_track(t), 0)

    def test_fix_audio_picks_english(self):
        d, path = self.make("Movie")
        env = os.environ.copy()
        saved = launcher._after_change
        launcher._after_change = lambda cfg, bad: 0
        try:
            self.assertEqual(launcher.fix_audio([path], "eng"), 0)
        finally:
            launcher._after_change = saved
        out = os.path.join(d, "Movie.mp4")
        t = library.audio_tracks(out)
        self.assertEqual([x["language"] for x in t], ["English"])
        self.assertTrue(os.path.exists(os.path.join(d, ".originals", "Movie.mkv")))
        self.assertFalse(os.path.exists(path))
        p = library.probe(out)
        self.assertTrue(p and library.video_ok(p["vcodec"], p["vfmt"]))

    def test_already_plays_wanted_language_and_missing_language(self):
        d, path = self.make("Dub", first="eng", second="jpn", ext=".mp4")
        saved = launcher._after_change
        launcher._after_change = lambda cfg, bad: 0
        try:
            self.assertEqual(launcher.fix_audio([path], "eng"), 0)          # nothing to change
            self.assertEqual(len(library.audio_tracks(path)), 2)
            self.assertFalse(os.path.exists(os.path.join(d, ".originals")))
            self.assertEqual(launcher.fix_audio([path], "spa"), 1)          # no such track: reported, file untouched
        finally:
            launcher._after_change = saved
        self.assertEqual(len(library.audio_tracks(path)), 2)

    def test_mp4_in_place_keeps_original(self):
        d, path = self.make("Same", ext=".mp4")
        saved = launcher._after_change
        launcher._after_change = lambda cfg, bad: 0
        try:
            self.assertEqual(launcher.fix_audio([path], "English"), 0)
        finally:
            launcher._after_change = saved
        self.assertEqual([x["language"] for x in library.audio_tracks(path)], ["English"])
        self.assertTrue(os.path.exists(os.path.join(d, ".originals", "Same.mp4")))


class FolderTests(unittest.TestCase):
    def test_ensure_folders(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "mcu"))            # different capitalisation already there: not duplicated
        open(os.path.join(d, "mcu", "keep.txt"), "w").close()
        cfg = Config()
        cfg.media_dir = d
        launcher.ensure_folders(cfg)
        names = {n.lower() for n in os.listdir(d)}
        for want in ("inbox", "mcu", "dc", "x-men", "dragon ball", "south park", "marvel television", "where things go.txt"):
            self.assertIn(want, names)
        self.assertEqual(len([n for n in os.listdir(d) if n.lower() == "mcu"]), 1)
        self.assertNotIn("weather", names)
        text = open(os.path.join(d, "WHERE THINGS GO.txt"), encoding="utf-8").read()
        self.assertIn("Inbox", text)
        mtime = os.path.getmtime(os.path.join(d, "WHERE THINGS GO.txt"))
        launcher.ensure_folders(cfg)                     # second run changes nothing
        self.assertEqual(os.path.getmtime(os.path.join(d, "WHERE THINGS GO.txt")), mtime)


if __name__ == "__main__":
    unittest.main()


class ImportTests(unittest.TestCase):
    def test_import_copies_into_inbox_and_keeps_originals(self):
        src, media = tempfile.mkdtemp(), tempfile.mkdtemp()
        os.makedirs(os.path.join(src, "Movies", ".hidden"))
        for rel in ("Movies/Iron Man (2008).mkv", "Movies/Notes.txt", "Movies/.hidden/skip.mp4", "Loose.mp4"):
            with open(os.path.join(src, rel), "wb") as fh:
                fh.write(b"x" * 100)
        cfg = Config()
        cfg.media_dir = media
        self.assertEqual(launcher.import_folder([src], cfg=cfg, sort=False, assume_yes=True), 0)
        base = os.path.basename(src)
        inbox = os.path.join(media, "Inbox", base)
        self.assertTrue(os.path.exists(os.path.join(inbox, "Movies", "Iron Man (2008).mkv")))
        self.assertTrue(os.path.exists(os.path.join(inbox, "Loose.mp4")))
        self.assertFalse(os.path.exists(os.path.join(inbox, "Movies", "Notes.txt")))
        self.assertFalse(os.path.exists(os.path.join(inbox, "Movies", ".hidden")))
        self.assertTrue(os.path.exists(os.path.join(src, "Loose.mp4")))              # original untouched
        self.assertEqual(os.listdir(os.path.join(media, "Inbox", base, "Movies")).count("Iron Man (2008).mkv.part"), 0)
        before = sorted(os.listdir(inbox))
        launcher.import_folder([src], cfg=cfg, sort=False, assume_yes=True)           # running again adds nothing new
        self.assertEqual(sorted(os.listdir(inbox)), before)
        self.assertFalse(any(n.endswith(")") or "(2)" in n for n in os.listdir(inbox)))

    def test_import_nothing_found(self):
        cfg = Config()
        cfg.media_dir = tempfile.mkdtemp()
        self.assertEqual(launcher.import_folder([tempfile.mkdtemp()], cfg=cfg, sort=False, assume_yes=True), 0)
        self.assertEqual(launcher.import_folder(["/definitely/not/here"], cfg=cfg, sort=False, assume_yes=True), 1)
