"""Sorting beyond the Inbox: loose videos in the media folder, videos no channel shows, and release-style names."""
import os
import tempfile
import time
import unittest
from pathlib import Path

from herotv import config, inbox, library
from herotv.config import Config
from herotv.db import connect


def _cfg(d):
    return Config(media_dir=Path(d), db_path=os.path.join(d, "t.sqlite3"),
                  channels_file=str(Path(config.ROOT) / "config" / "channels.json"))


class LooseFileTests(unittest.TestCase):
    def test_loose_videos_are_sorted_and_unknown_ones_go_to_the_inbox(self):
        d = tempfile.mkdtemp()
        cfg = _cfg(d)
        for n in ("Iron Man (2008).mp4", "Grandma Birthday 2015.mp4", "Grandma Birthday 2015.srt", "readme.txt"):
            Path(d, n).write_bytes(b"x" * 10)
        Path(d, "MCU").mkdir()
        Path(d, "MCU", "Thor (2011).mp4").write_bytes(b"x" * 10)          # already in a channel folder: not touched
        old = time.time() - 600
        for f in Path(d).rglob("*"):
            os.utime(f, (old, old))
        got = []
        place = lambda src, picked, media, force_move=False: got.append(os.path.basename(src)) or True
        seen = {}
        inbox.run_once(cfg, seen, place=place, facts=lambda s: None)
        r = inbox.run_once(cfg, seen, place=place, facts=lambda s: None)
        self.assertEqual(got, ["Iron Man (2008).mp4"])
        self.assertEqual(r["left"], 1)
        ib = Path(d, "Inbox")
        self.assertTrue((ib / "Grandma Birthday 2015.mp4").is_file())
        self.assertTrue((ib / "Grandma Birthday 2015.srt").is_file())     # its subtitles went with it
        self.assertFalse(Path(d, "Grandma Birthday 2015.mp4").exists())
        self.assertTrue(Path(d, "readme.txt").exists())
        self.assertTrue(Path(d, "MCU", "Thor (2011).mp4").exists())
        self.assertEqual(inbox.waiting(cfg), 1)

    def test_move_in_keeps_a_shows_folder_together(self):
        d = tempfile.mkdtemp()
        cfg = _cfg(d)
        Path(d, "Downloads", "Some Show").mkdir(parents=True)
        for e in (1, 2):
            Path(d, "Downloads", "Some Show", f"Some Show S01E0{e}.mkv").write_bytes(b"x")
        Path(d, "Downloads", "Some Show", "Some Show S01E01.en.srt").write_bytes(b"x")
        paths = [str(p) for p in Path(d, "Downloads").rglob("*.mkv")]
        self.assertEqual(inbox.move_in(paths, cfg, keep_folder_of=d), 2)
        tgt = Path(d, "Inbox", "Downloads", "Some Show")
        self.assertEqual(sorted(p.name for p in tgt.iterdir()),
                         ["Some Show S01E01.en.srt", "Some Show S01E01.mkv", "Some Show S01E02.mkv"])
        self.assertEqual(inbox.move_in(paths, cfg, keep_folder_of=d), 0)   # already moved: nothing to do


class NotOnChannelsTests(unittest.TestCase):
    def test_lists_videos_no_channel_shows(self):
        d = tempfile.mkdtemp()
        cfg = _cfg(d)
        c = connect(cfg.db_path)
        rows = [("MCU/Thor.mp4", "Thor", "MCU", 6000), ("Random/Avengers Endgame.mp4", "Avengers Endgame", "Random", 9000),
                ("Shorts/Toon.mp4", "Toon", "Shorts", 400), ("Inbox/Waiting.mp4", "Waiting", "Inbox", 5000),
                ("MCU/.originals/Old.mkv", "Old", "MCU", 6000), ("Loose.mp4", "Loose", "", 5000)]
        for p, t, f, rt in rows:
            c.execute("INSERT INTO media(path,title,franchise,runtime_s,verified,playable,available) VALUES(?,?,?,?,1,1,1)",
                      (os.path.join(d, *p.split("/")), t, f, rt))
        c.commit()
        got = sorted(m["title"] for m in inbox.not_on_channels(c, cfg))
        self.assertEqual(got, ["Avengers Endgame", "Loose"])


class ReleaseNameTests(unittest.TestCase):
    def test_language_and_release_tags_after_the_year(self):
        t = library.tidy
        self.assertEqual(t("Avengers Endgame 2019 Hindi-English"), ("Avengers Endgame", 2019))
        self.assertEqual(t("Avengers.Endgame.2019.Hindi.English.1080p"), ("Avengers Endgame", 2019))
        self.assertEqual(t("Spider-Man No Way Home 2021 [Hindi + English] 720p WEB-DL"), ("Spider-Man No Way Home", 2021))
        self.assertEqual(t("Thor Ragnarok (2017) [Hindi-Eng]"), ("Thor Ragnarok", 2017))
        self.assertEqual(t("The Batman 2022 Dual Audio HEVC"), ("The Batman", 2022))
        self.assertEqual(t("Iron Man 2008 Hindi Dubbed"), ("Iron Man", 2008))

    def test_real_titles_are_left_alone(self):
        t = library.tidy
        self.assertEqual(t("Johnny English")[0], "Johnny English")
        self.assertEqual(t("The English Patient")[0], "The English Patient")
        self.assertEqual(t("Blade.Runner.2049.2017.1080p"), ("Blade Runner 2049", 2017))
        self.assertEqual(t("Line of Duty")[0], "Line of Duty")
        self.assertEqual(t("The Thin Red Line")[0], "The Thin Red Line")


if __name__ == "__main__":
    unittest.main()
