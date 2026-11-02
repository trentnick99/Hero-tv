import os
import tempfile
import unittest

from herotv import thumbs


class Cfg:
    def __init__(self, d):
        self.db_path = os.path.join(d, "t.sqlite3")


class HeroStillTests(unittest.TestCase):
    ROW = {"id": 7, "size": 1000, "runtime_s": 1400, "path": "x.mp4"}

    def test_the_banner_grab_has_its_own_file_name(self):
        n = thumbs.hero_name(self.ROW)
        self.assertNotEqual(n, thumbs.thumb_name(self.ROW))
        self.assertTrue(n.startswith("7-1000-1400") and n.endswith("-hero.jpg"))

    def test_cleanup_keeps_banner_grabs_of_current_videos_and_removes_old_ones(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Cfg(d)
            td = thumbs.thumb_dir(cfg)
            os.makedirs(td)
            keep = [thumbs.thumb_name(self.ROW), thumbs.hero_name(self.ROW)]
            stale = ["7-999-1400.jpg", "7-999-1400-hero.jpg"]          # the video was replaced: same id, other size
            for n in keep + stale:
                open(os.path.join(td, n), "wb").write(b"x")
            thumbs._prune(cfg, [self.ROW])
            self.assertEqual(sorted(os.listdir(td)), sorted(keep))

    def test_no_video_file_means_no_grab_and_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(thumbs.make_hero(Cfg(d), dict(self.ROW, path=os.path.join(d, "missing.mp4"))))


if __name__ == "__main__":
    unittest.main()
