import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import add, make_db  # noqa: E402
from herotv import server as SV  # noqa: E402
from herotv.config import Config  # noqa: E402


class UiFeatureServerTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        cfg = Config(); cfg.db_path = os.path.join(self.d, "t.sqlite3"); cfg.tz = "UTC"; cfg.media_dir = self.d
        self.c = make_db(cfg.db_path)
        self.app = SV.App(cfg)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(self.app))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        self.base = f"http://127.0.0.1:{srv.server_address[1]}"

    def get(self, path):
        return json.load(urllib.request.urlopen(self.base + path))

    def post(self, path, body):
        r = urllib.request.Request(self.base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(r))

    def test_skip_settings_roundtrip(self):
        self.assertEqual(self.get("/api/skip?series=Naruto"), {"series": "Naruto", "intro": 0, "outro": 0})
        self.post("/api/skip", {"series": "Naruto", "intro": 82.5})
        self.post("/api/skip", {"series": "Naruto", "outro": 95})
        self.assertEqual(self.get("/api/skip?series=Naruto"), {"series": "Naruto", "intro": 82.5, "outro": 95})
        self.post("/api/skip", {"series": "Naruto", "intro": 0})          # turning it off keeps the other setting
        self.assertEqual(self.get("/api/skip?series=Naruto")["outro"], 95)
        self.assertEqual(self.get("/api/skip?series=Naruto")["intro"], 0)

    def test_skip_validation(self):
        for body in ({"intro": 5}, {"series": "A"}, {"series": "A", "intro": -1}, {"series": "A", "intro": 99999}, {"series": "A", "outro": "soon"}):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.post("/api/skip", body)
            self.assertEqual(cm.exception.code, 400, body)

    def test_bigtext_is_remembered(self):
        self.assertNotIn("bigtext", self.get("/api/prefs"))
        self.post("/api/prefs", {"bigtext": True})
        self.assertIs(self.get("/api/prefs")["bigtext"], True)
        self.post("/api/prefs", {"bigtext": False})
        self.assertIs(self.get("/api/prefs")["bigtext"], False)

    def test_help_lists_problems_in_plain_english(self):
        add(self.c, "Good movie", 600)
        add(self.c, "Anime rip", 600, playable=0)
        self.c.execute("UPDATE media SET vcodec='h264', vfmt='yuv420p10le|High 10', acodec='aac' WHERE title='Anime rip'")
        add(self.c, "Free one", 600, franchise="Free Movies")
        self.c.commit()
        h = self.get("/api/help")
        self.assertEqual(h["playable"], 2)
        self.assertEqual(h["free"], 1)
        self.assertEqual(h["problem_count"], 1)
        p = h["problems"][0]
        self.assertEqual(p["title"], "Anime rip")
        self.assertIn("10-bit", p["why"])
        self.assertIn("Settings > Tools > Fix", p["fix"])
        self.assertIn("media_dir", h)

    def test_renaming_a_show_keeps_its_skip_settings(self):
        d = os.path.join(self.d, "Anime", "Naruto")
        os.makedirs(d)
        path = os.path.join(d, "Naruto S01E01.mp4")
        open(path, "wb").close()
        self.c.execute("INSERT INTO media(path,title,franchise,series,season,episode,runtime_s,verified,playable,available) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (path, "Ep 1", "Anime", "Naruto", 1, 1, 600, 1, 1, 1))
        self.c.commit()
        mid = self.c.execute("SELECT id FROM media").fetchone()[0]
        self.post("/api/skip", {"series": "Naruto", "intro": 70})
        self.post("/api/rename", {"media_id": mid, "series": "Naruto Shippuden"})
        self.assertEqual(self.get("/api/skip?series=Naruto%20Shippuden")["intro"], 70)

    def test_empty_channels_are_flagged_and_listed_in_help(self):
        from herotv import scheduler as S
        S.sync_channels(self.c, [{"id": "mcu", "number": 1, "name": "MCU", "match": {"franchise": ["MCU"]}},
                                 {"id": "dc", "number": 2, "name": "DC", "match": {"franchise": ["DC"]}},
                                 {"id": "all", "number": 3, "name": "All", "match": {}},
                                 {"id": "wx", "number": 4, "name": "Weather", "kind": "weather"}], tz="UTC")
        self.assertTrue(all(ch["empty"] for ch in self.get("/api/channels")["channels"] if ch["kind"] == "tv"))
        add(self.c, "Iron", 600, franchise="MCU")
        by = {ch["id"]: ch for ch in self.get("/api/channels")["channels"]}
        self.assertFalse(by["mcu"]["empty"])
        self.assertFalse(by["all"]["empty"])
        self.assertTrue(by["dc"]["empty"])
        self.assertFalse(by["wx"]["empty"])
        self.assertEqual(self.get("/api/help")["hidden_channels"], ["2 DC"])

    def test_page_has_the_new_screens(self):
        page = __import__("helpers").page_source()
        for needle in ('id="home"', 'id="help"', 'id="upnext"', "cycleSleep", "markSkip", "setBig", "body.big"):
            self.assertIn(needle, page)


if __name__ == "__main__":
    unittest.main()


class SpiderSplitTests(unittest.TestCase):
    def test_spider_shows_go_to_marvel_television_and_movies_stay(self):
        import json as _j
        from helpers import make_db as mk
        from herotv import scheduler as S
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data = _j.load(open(os.path.join(root, "config", "channels.json"), encoding="utf-8-sig"))["channels"]
        c = mk()
        S.sync_channels(c, data, tz="UTC")

        def vid(title, mins, series="", ep=0, franchise="", tags=("spider-verse",)):
            c.execute("INSERT INTO media(path,title,franchise,series,episode,tags,runtime_s,verified,playable,available) VALUES(?,?,?,?,?,?,?,1,1,1)",
                      (f"/x/{title}.mp4", title, franchise, series, ep, _j.dumps(list(tags)), mins * 60))
            return c.execute("SELECT * FROM media WHERE title=?", (title,)).fetchone()

        def on(row):
            return {ch["id"] for ch in data if ch.get("kind", "tv") == "tv" and S.matches(S.config_rules(ch), row)}

        movie = vid("Into the Spider-Verse", 117)
        show = vid("Spider-Man S1E1", 22, series="Spider-Man", ep=1)
        short = vid("Loose short", 25)
        ordinary = vid("Plain Marvel show", 45, series="Night Watch", ep=2, franchise="Marvel Television", tags=())
        self.assertIn("spider-verse", on(movie)); self.assertNotIn("marvel-tv", on(movie))
        self.assertIn("marvel-tv", on(show)); self.assertNotIn("spider-verse", on(show))
        self.assertIn("marvel-tv", on(short)); self.assertNotIn("spider-verse", on(short))
        self.assertEqual(on(ordinary) & {"marvel-tv", "spider-verse"}, {"marvel-tv"})
