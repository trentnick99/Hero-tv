"""Tidying HERO TV's own leftovers: old schedule rows go, the newest rows and every video stay."""
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from herotv import housekeeping
from herotv.config import Config
from herotv.db import connect

DAY = 86400


class Tidy(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.cfg = Config(media_dir=Path(self.d) / "media", db_path=os.path.join(self.d, "t.sqlite3"))
        (Path(self.d) / "media").mkdir()
        self.video = Path(self.d) / "media" / "Film (2000).mp4"
        self.video.write_bytes(b"x" * 1000)
        self.root, self.data = Path(self.d) / "app", Path(self.d) / "data"
        self.root.mkdir(); self.data.mkdir()
        self.c = connect(self.cfg.db_path)
        self.c.execute("INSERT INTO media(path,title,verified,playable,available,runtime_s) VALUES(?,?,1,1,1,60)", (str(self.video), "Film"))
        self.now = time.time()
        for ch, pl in (("a", ""), ("a", "blk"), ("b", "")):
            for i in range(40, 0, -1):                            # 40 days ago .. 1 day ago, one row a day
                st = int(self.now - i * DAY)
                self.c.execute("INSERT INTO slots(channel_id,start,end,media_id,cycle,pl) VALUES(?,?,?,1,0,?)", (ch, st + (7 if pl else 0), st + 3600, pl))
        self.c.commit()

    def rows(self, ch=None):
        return self.c.execute("SELECT COUNT(*) FROM slots" + (" WHERE channel_id=?" if ch else ""), (ch,) if ch else ()).fetchone()[0]

    def test_old_rows_go_recent_and_newest_stay(self):
        before = self.rows()
        self.newest = self.c.execute("SELECT channel_id,MAX(start) FROM slots GROUP BY channel_id ORDER BY 1").fetchall()
        r = housekeeping.report(self.c, self.cfg, self.root, self.data, self.now)
        n = next(i for i in r["items"] if i["id"] == "slots")["count"]
        self.assertGreater(n, 0)
        housekeeping.clean(self.c, self.cfg, self.root, self.data, ["slots"], self.now)
        self.assertEqual(before - self.rows(), n)
        oldest_kept = self.c.execute("SELECT MIN(end) FROM slots").fetchone()[0]
        self.assertGreaterEqual(oldest_kept, self.now - housekeeping.KEEP_DAYS * DAY - 3600)      # nothing newer than 14 days went
        self.assertEqual(self.newest, self.c.execute("SELECT channel_id,MAX(start) FROM slots GROUP BY channel_id ORDER BY 1").fetchall())   # newest rows stay

    def test_the_last_row_of_each_block_stays_even_when_old(self):
        self.c.execute("DELETE FROM slots WHERE channel_id='a' AND pl='blk' AND start > ?", (int(self.now - 30 * DAY),))   # the block's last row is 30+ days old
        self.c.commit()
        last = self.c.execute("SELECT MAX(start) FROM slots WHERE channel_id='a' AND pl='blk'").fetchone()[0]
        housekeeping.clean(self.c, self.cfg, self.root, self.data, ["slots"], self.now)
        self.assertEqual(self.c.execute("SELECT MAX(start) FROM slots WHERE channel_id='a' AND pl='blk'").fetchone()[0], last)

    def test_videos_and_settings_are_never_touched(self):
        subs = Path(os.path.splitext(self.cfg.db_path)[0] + "-subs"); subs.mkdir()
        (subs / "a.vtt").write_text("WEBVTT")
        upd = self.root / ".update-download"; upd.mkdir()
        z = upd / "x.zip"; z.write_bytes(b"z" * 10)
        old = self.now - 7200
        os.utime(z, (old, old))
        (self.data / "herotv.old.log").write_text("old")
        r = housekeeping.clean(self.c, self.cfg, self.root, self.data, ["slots", "subs", "updates", "log"], self.now)
        self.assertEqual(sorted(r["done"]), ["log", "slots", "subs", "updates"])
        self.assertFalse(subs.exists() or upd.exists() or (self.data / "herotv.old.log").exists())
        self.assertEqual(self.video.read_bytes(), b"x" * 1000)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM media").fetchone()[0], 1)

    def test_a_fresh_update_download_is_left_alone(self):
        upd = self.root / ".update-download"; upd.mkdir()
        (upd / "x.zip").write_bytes(b"z")
        r = housekeeping.clean(self.c, self.cfg, self.root, self.data, ["updates"], self.now + 1)
        self.assertNotIn("updates", r["done"])
        self.assertTrue(upd.exists())
