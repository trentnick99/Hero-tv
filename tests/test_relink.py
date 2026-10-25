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


class NewNextWelcomeTests(unittest.TestCase):
    def setUp(self):
        import json as _j, threading
        from http.server import ThreadingHTTPServer
        from pathlib import Path
        from herotv import server as SV
        from herotv.config import Config
        from herotv.db import connect
        self.j = _j
        self.root = tempfile.mkdtemp()
        cfg = Config(media_dir=Path(self.root), db_path=os.path.join(self.root, "t.sqlite3"), channels_file=None)
        self.c = connect(cfg.db_path)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        self.base = f"http://127.0.0.1:{srv.server_address[1]}"

    def get(self, path, body=None):
        import urllib.request
        r = urllib.request.Request(self.base + path, None if body is None else self.j.dumps(body).encode(),
                                   {"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
        return self.j.load(urllib.request.urlopen(r))

    def add(self, title, series="", season=0, episode=0, added=0):
        self.c.execute("INSERT INTO media(path,title,series,season,episode,verified,playable,available,runtime_s,added) "
                       "VALUES(?,?,?,?,?,1,1,1,1200,?)", (f"/x/{title}.mp4", title, series, season, episode, added))
        self.c.commit()
        return self.c.execute("SELECT id FROM media WHERE title=?", (title,)).fetchone()[0]

    def test_recent_view_newest_first(self):
        now = int(time.time())
        self.add("Old one", added=0); self.add("Last month", added=now - 40 * 86400)
        self.add("Yesterday", added=now - 86400); self.add("Today", added=now)
        j = self.get("/api/library?view=recent")
        self.assertEqual([i["title"] for i in j["items"]], ["Today", "Yesterday"])
        self.assertEqual(j["counts"]["recent"], 2)

    def test_next_episode(self):
        e1 = self.add("Ep 1", "Invincible", 1, 1); e8 = self.add("Ep 8", "Invincible", 1, 8)
        self.add("S2 Ep 1", "Invincible", 2, 1); self.add("Other", "South Park", 1, 2)
        film = self.add("A Film")
        self.assertEqual(self.get(f"/api/next/{e1}")["next"]["title"], "Ep 8")
        self.assertEqual(self.get(f"/api/next/{e8}")["next"]["title"], "S2 Ep 1")       # on to the next season
        last = self.c.execute("SELECT id FROM media WHERE title='S2 Ep 1'").fetchone()[0]
        self.assertIsNone(self.get(f"/api/next/{last}")["next"])
        self.assertIsNone(self.get(f"/api/next/{film}")["next"])

    def test_welcome_only_for_new_users(self):
        self.assertTrue(self.get("/api/welcome")["show"])
        self.get("/api/welcome", {})
        self.assertFalse(self.get("/api/welcome")["show"])
        self.assertEqual(self.get("/api/whatsnew")["notes"], [])                       # a new user is not shown old news

    def test_existing_users_never_see_welcome(self):
        mid = self.add("Film")
        self.c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(?,50,0,1)", (mid,)); self.c.commit()
        self.assertFalse(self.get("/api/welcome")["show"])
        self.assertTrue(self.get("/api/whatsnew")["notes"])                            # ...but they do get What's new
