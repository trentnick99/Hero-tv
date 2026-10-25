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
from helpers import make_db  # noqa: E402
from herotv import library, server as SV  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.library import _guess, tidy  # noqa: E402

PROBE = lambda p: {"runtime_s": 60, "vcodec": "h264", "acodec": "aac", "title": ""}  # noqa: E731


class NameCleanupTests(unittest.TestCase):
    def test_download_style_names(self):
        cases = {
            ("MCU", "Spider.Man.No.Way.Home.2021.1080p.BluRay.x264-GRP"): ("Spider Man No Way Home", 2021),
            ("MCU", "Iron_Man_2008"): ("Iron Man", 2008),
            ("MCU", "Thor (2011)"): ("Thor", 2011),
            ("Marvel", "Avengers Endgame (2019) [YTS.MX]"): ("Avengers Endgame", 2019),
            ("X", "Blade Runner 2049"): ("Blade Runner 2049", None),       # looks like a year but is not one
            ("X", "Mr. Robot"): ("Mr. Robot", None),
            ("X", "Iron Man 2008"): ("Iron Man 2008", None),                 # plain, human-typed names are left alone
        }
        for (fr, stem), (title, year) in cases.items():
            g = _guess([fr, stem + ".mkv"], stem)
            self.assertEqual((g["title"], g["year"]), (title, year), stem)

    def test_episode_names(self):
        g = _guess(["Dragon Ball", "Dragon.Ball.Z.S02E05.Goku.Arrives.1080p.WEB-DL.mkv"], "Dragon.Ball.Z.S02E05.Goku.Arrives.1080p.WEB-DL")
        self.assertEqual((g["series"], g["title"], g["season"], g["episode"]), ("Dragon Ball Z", "Goku Arrives", 2, 5))

    def test_tidy_never_returns_empty(self):
        self.assertEqual(tidy("1080p")[0], "1080p")


class RenameTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.root = os.path.join(self.d, "media")
        for rel in ("South Park/Season 1/South.Park.S01E01.mp4", "South Park/Season 1/South.Park.S01E02.mp4", "MCU/Iron.Man.2008.1080p.BluRay.mp4"):
            p = os.path.join(self.root, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(b"x")
        cfg = Config(); cfg.db_path = os.path.join(self.d, "t.sqlite3"); cfg.tz = "UTC"; cfg.media_dir = self.root
        self.c = make_db(cfg.db_path)
        library.scan(self.c, self.root, probe_fn=PROBE)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        self.base = f"http://127.0.0.1:{srv.server_address[1]}"

    def post(self, body):
        r = urllib.request.Request(self.base + "/api/rename", json.dumps(body).encode(), {"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(r))

    def row(self, like):
        return self.c.execute("SELECT * FROM media WHERE path LIKE ?", (f"%{like}%",)).fetchone()

    def test_rename_title_survives_rescan_and_can_be_reverted(self):
        m = self.row("Iron.Man")
        self.assertEqual(m["title"], "Iron Man")            # tidied automatically
        self.assertEqual(self.post({"media_id": m["id"], "title": "Iron Man (Ultimate Cut)"})["title"], "Iron Man (Ultimate Cut)")
        side = library.sidecar_path(m["path"])
        self.assertEqual(json.load(open(side, encoding="utf-8"))["title"], "Iron Man (Ultimate Cut)")
        library.scan(self.c, self.root, probe_fn=lambda p: self.fail("re-probed after rename"))
        self.assertEqual(self.row("Iron.Man")["title"], "Iron Man (Ultimate Cut)")
        os.utime(m["path"], (1, 1))                           # force a full re-read: the sidecar still wins
        library.scan(self.c, self.root, probe_fn=PROBE)
        self.assertEqual(self.row("Iron.Man")["title"], "Iron Man (Ultimate Cut)")
        self.post({"media_id": m["id"], "title": ""})
        self.assertEqual(self.row("Iron.Man")["title"], "Iron Man")
        self.assertNotIn("title", json.load(open(side, encoding="utf-8")))

    def test_rename_whole_show(self):
        e1, e2 = self.row("S01E01"), self.row("S01E02")
        self.assertEqual(e1["series"], "Season 1")            # folder-based name is what a user wants to fix
        self.post({"media_id": e1["id"], "series": "South Park"})
        self.assertEqual({self.row("S01E01")["series"], self.row("S01E02")["series"]}, {"South Park"})
        library.scan(self.c, self.root, probe_fn=PROBE)
        self.assertEqual(self.row("S01E02")["series"], "South Park")
        self.assertEqual(self.row("S01E02")["title"], self.row("S01E02")["title"])
        self.post({"media_id": e2["id"], "series": ""})       # revert
        self.assertEqual(self.row("S01E01")["series"], "Season 1")

    def test_errors_are_plain(self):
        m = self.row("Iron.Man")
        for body, code in (({"media_id": 9999, "title": "x"}, 404), ({"media_id": m["id"], "title": "x" * 200}, 400),
                           ({"media_id": m["id"]}, 400), ({"media_id": m["id"], "series": "Nope"}, 400), ({"title": "x"}, 400)):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.post(body)
            self.assertEqual(cm.exception.code, code, body)

    def test_unicode_names(self):
        m = self.row("Iron.Man")
        self.post({"media_id": m["id"], "title": "Hombre de Hierro – ドラゴンボール"})
        self.assertEqual(self.row("Iron.Man")["title"], "Hombre de Hierro – ドラゴンボール")


if __name__ == "__main__":
    unittest.main()
