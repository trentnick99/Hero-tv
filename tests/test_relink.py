import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import make_db  # noqa: E402
from herotv import library as L  # noqa: E402

RUNTIME = {}


def fake_probe(path):
    return {"title": "", "runtime_s": RUNTIME.get(os.path.basename(path), 1200.0), "vcodec": "h264", "acodec": "aac",
            "vfmt": "yuv420p|High"}


class RelinkTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "MCU"))
        self.c = make_db()

    def put(self, rel, data=b"x" * 5000):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(data)
        return p

    def mid(self, rel):
        r = self.c.execute("SELECT id FROM media WHERE path=? AND available=1", (os.path.join(self.root, rel),)).fetchone()
        return r and r["id"]

    def mark(self, mid):
        self.c.execute("INSERT INTO favorites(media_id,added) VALUES(?,1)", (mid,))
        self.c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(?,600,0,1)", (mid,))
        self.c.execute("INSERT INTO seen(media_id,secs,last) VALUES(?,900,1)", (mid,))
        self.c.execute("INSERT INTO slots(channel_id,start,end,media_id,cycle) VALUES('mcu',100,200,?,0)", (mid,))
        self.c.commit()

    def kept(self, mid):
        return (self.c.execute("SELECT COUNT(*) FROM favorites WHERE media_id=?", (mid,)).fetchone()[0],
                self.c.execute("SELECT position FROM progress WHERE media_id=?", (mid,)).fetchone()[0],
                self.c.execute("SELECT secs FROM seen WHERE media_id=?", (mid,)).fetchone()[0],
                self.c.execute("SELECT COUNT(*) FROM slots WHERE media_id=?", (mid,)).fetchone()[0])

    def test_moved_to_another_folder(self):
        self.put("Inbox/Iron Man (2008).mp4")
        L.scan(self.c, self.root, fake_probe)
        old = self.mid("Inbox/Iron Man (2008).mp4"); self.mark(old)
        shutil.move(os.path.join(self.root, "Inbox/Iron Man (2008).mp4"), os.path.join(self.root, "MCU/Iron Man (2008).mp4"))
        st = L.scan(self.c, self.root, fake_probe)
        new = self.mid("MCU/Iron Man (2008).mp4")
        self.assertEqual(st["relinked"], 1)
        self.assertEqual(self.kept(new), (1, 600, 900, 1))
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM media").fetchone()[0], 1)

    def test_renamed_in_windows(self):
        self.put("MCU/iron.man.2008.1080p.mp4")
        open(os.path.join(self.root, "MCU/iron.man.2008.1080p.hero.json"), "w").write('{"title": "My Iron Man"}')
        L.scan(self.c, self.root, fake_probe)
        old = self.mid("MCU/iron.man.2008.1080p.mp4"); self.mark(old)
        os.rename(os.path.join(self.root, "MCU/iron.man.2008.1080p.mp4"), os.path.join(self.root, "MCU/Iron Man (2008).mp4"))
        L.scan(self.c, self.root, fake_probe)
        self.assertEqual(self.kept(self.mid("MCU/Iron Man (2008).mp4")), (1, 600, 900, 1))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "MCU/Iron Man (2008).hero.json")))
        L.scan(self.c, self.root, fake_probe)
        self.assertEqual(self.c.execute("SELECT title FROM media WHERE available=1").fetchone()[0], "My Iron Man")

    def test_converted_copy_keeps_history(self):
        self.put("MCU/Thor (2011).mkv", b"m" * 7000)
        L.scan(self.c, self.root, fake_probe)
        old = self.mid("MCU/Thor (2011).mkv"); self.mark(old)
        os.makedirs(os.path.join(self.root, "MCU/.originals"))
        shutil.move(os.path.join(self.root, "MCU/Thor (2011).mkv"), os.path.join(self.root, "MCU/.originals/Thor (2011).mkv"))
        self.put("MCU/Thor (2011).mp4", b"p" * 6000)                     # different size: a converted copy
        L.scan(self.c, self.root, fake_probe)
        self.assertEqual(self.kept(self.mid("MCU/Thor (2011).mp4")), (1, 600, 900, 1))

    def test_ambiguous_or_different_is_left_alone(self):
        self.put("MCU/A.mp4"); self.put("MCU/B.mp4")
        L.scan(self.c, self.root, fake_probe)
        self.mark(self.mid("MCU/A.mp4"))
        os.remove(os.path.join(self.root, "MCU/A.mp4")); os.remove(os.path.join(self.root, "MCU/B.mp4"))
        self.put("MCU/C.mp4")                                             # same size as BOTH missing files: ambiguous
        st = L.scan(self.c, self.root, fake_probe)
        self.assertEqual(st["relinked"], 0)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM favorites WHERE media_id=?", (self.mid("MCU/C.mp4"),)).fetchone()[0], 0)
        RUNTIME["D.mp4"] = 3000.0
        self.put("MCU/D.mp4", b"y" * 9999)                                 # different file entirely
        self.assertEqual(L.scan(self.c, self.root, fake_probe)["relinked"], 0)


if __name__ == "__main__":
    unittest.main()
