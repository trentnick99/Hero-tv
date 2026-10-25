import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from herotv.launcher import plan_sort  # noqa: E402

RULES = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "auto-sort.json")))


class SortTests(unittest.TestCase):
    def test_titles(self):
        cases = {
            "Spider-Man (2002)": {"spider-verse"}, "The.Amazing.Spiderman.2012": {"spider-verse"},
            "Spider-Man Homecoming (2017)": {"mcu", "spider-verse"}, "Batman Begins (2005)": {"dc"},
            "X-Men: Days of Future Past (2014)": {"x-men"}, "Deadpool (2016)": {"x-men", "comedy"},
            "Flashdance (1983)": set(), "Thorn Birds (1983)": set(), "Superman (1978)": {"dc", "classics"},
            "Random Movie (2020)": set(), "Jessica_Jones S01E01": {"marvel-tv"},
        }
        for name, want in cases.items():
            self.assertEqual(plan_sort(name, RULES), want, name)


if __name__ == "__main__":
    unittest.main()


class SyncTests(unittest.TestCase):
    def test_edit_swap_and_remove(self):
        from herotv import scheduler as S
        from helpers import make_db
        c = make_db()
        ch = lambda i, n, name: {"id": i, "number": n, "name": name, "match": {}}
        S.sync_channels(c, [ch("a", 1, "A"), ch("b", 2, "B"), ch("c", 3, "C")])
        S.sync_channels(c, [ch("a", 2, "Alpha"), ch("b", 1, "B")])        # swap numbers, rename, drop c
        rows = {r["id"]: (r["number"], r["name"]) for r in S.channels(c)}
        self.assertEqual(rows, {"a": (2, "Alpha"), "b": (1, "B")})
        with self.assertRaises(ValueError):
            S.sync_channels(c, [ch("a", 1, "A"), ch("b", 1, "B")])


class FavoritesTests(unittest.TestCase):
    def test_favorite_and_continue_views(self):
        import json as _j
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        from helpers import add, channel, make_db
        from herotv import server as SV
        from herotv.config import Config
        import tempfile
        d = tempfile.mkdtemp()
        cfg = Config(); cfg.db_path = os.path.join(d, "t.sqlite3"); cfg.tz = "UTC"; cfg.web_dir = cfg.web_dir
        c = make_db(cfg.db_path)
        a, b = add(c, "A", 600), add(c, "B", 600)
        c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(?,?,?,?)", (b, 120, 0, 5)); c.commit(); c.close()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def get(path):
            return _j.load(urllib.request.urlopen(base + path))

        def post(path, body):
            r = urllib.request.Request(base + path, _j.dumps(body).encode(), {"Content-Type": "application/json"})
            return _j.load(urllib.request.urlopen(r))
        self.assertEqual([i["title"] for i in get("/api/library?view=continue")["items"]], ["B"])
        self.assertEqual(get("/api/library?view=favorites")["items"], [])
        post("/api/favorite", {"media_id": a, "on": True})
        self.assertEqual([i["title"] for i in get("/api/library?view=favorites")["items"]], ["A"])
        self.assertEqual(get("/api/library")["counts"], {"continue": 1, "favorites": 1})
        post("/api/favorite", {"media_id": a, "on": False})
        self.assertEqual(get("/api/library?view=favorites")["items"], [])
        with self.assertRaises(Exception):
            get("/api/library?view=bogus")
