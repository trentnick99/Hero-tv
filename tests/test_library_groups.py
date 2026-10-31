"""Library: one row per show (instead of one per episode), the show's own episodes, and plain videos untouched."""
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from helpers import make_db, tmpdb
from herotv.config import Config
from herotv.server import App, make_handler


class Groups(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.cfg = Config(media_dir=self.root, db_path=tmpdb(), channels_file=os.path.join(self.root, "ch.json"), tz="America/New_York", port=0)
        Path(self.cfg.channels_file).write_text(json.dumps({"channels": []}))
        self.c = make_db(self.cfg.db_path)
        self.addCleanup(self.c.close)
        sf = mock.patch("herotv.config.settings_file", return_value=Path(self.root) / "settings.json")
        sf.start()
        self.addCleanup(sf.stop)
        self.n = 0
        for s in (1, 2):
            for e in (1, 2, 3):
                self.add("Cartoons", "South Park", s, e, f"Ep {s}x{e}")
        for e in (1, 2):
            self.add("Sci-Fi", "Galactica", 1, e, f"Old {e}", year=1978)      # same name as the next show, other folder
            self.add("Drama", "Galactica", 1, e, f"New {e}", year=2004)
        self.add("Movies", "", 0, 0, "A Movie", year=1999)
        self.add("Movies", "", 0, 0, "Another Movie", year=2001)
        self.c.commit()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(self.cfg)))
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        self.base = f"http://127.0.0.1:{srv.server_address[1]}"

    def add(self, franchise, series, season, ep, title, year=None):
        self.n += 1
        self.c.execute("INSERT INTO media(path,title,year,franchise,series,season,episode,verified,playable,available,runtime_s,ord,size) "
                       "VALUES(?,?,?,?,?,?,?,1,1,1,60,?,5)", (os.path.join(self.root, franchise, f"{self.n}.mp4"), title, year, franchise, series,
                                                               season, ep, self.n))

    def get(self, qs):
        with urllib.request.urlopen(self.base + "/api/library?" + qs) as r:
            return json.load(r)["items"]

    def test_grouped_list_has_one_row_per_show_and_keeps_movies(self):
        items = self.get("view=all&group=1&limit=1000")
        shows = [i for i in items if i.get("show")]
        self.assertEqual(len(items), 5)                                     # 3 shows (two share a name) + 2 movies
        self.assertEqual(sorted((i["series"], i["franchise"], i["episodes"], i["seasons"]) for i in shows),
                         [("Galactica", "Drama", 2, 1), ("Galactica", "Sci-Fi", 2, 1), ("South Park", "Cartoons", 6, 2)])
        self.assertEqual(sorted(i["title"] for i in items if not i.get("show")), ["A Movie", "Another Movie"])
        sp = next(i for i in shows if i["series"] == "South Park")
        self.assertEqual((sp["title"], sp["season"], sp["episode"]), ("South Park", 0, 0))
        first = self.c.execute("SELECT title FROM media WHERE id=?", (sp["id"],)).fetchone()[0]
        self.assertEqual(first, "Ep 1x1")                                   # a picture comes from the first episode

    def test_same_named_shows_in_two_folders_stay_separate(self):
        gal = [i for i in self.get("view=all&group=1&limit=1000") if i.get("series") == "Galactica"]
        self.assertEqual(sorted(i["franchise"] for i in gal), ["Drama", "Sci-Fi"])
        eps = self.get("view=all&series=Galactica&franchise=Drama&limit=1000")
        self.assertEqual([e["title"] for e in eps], ["New 1", "New 2"])
        eps = self.get("view=all&series=Galactica&franchise=Sci-Fi&limit=1000")
        self.assertEqual([e["title"] for e in eps], ["Old 1", "Old 2"])

    def test_a_shows_episodes_come_in_order(self):
        eps = self.get("view=all&series=South+Park&franchise=Cartoons&limit=1000")
        self.assertEqual([(e["season"], e["episode"]) for e in eps], [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)])
        self.assertFalse(any(e.get("show") for e in eps))

    def test_search_still_groups_and_counts_the_whole_show(self):
        items = self.get("view=all&group=1&limit=1000&q=Ep+2x3")            # matches one episode title only
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["series"], items[0]["episodes"]), ("South Park", 6))   # still says 6, not 1

    def test_other_views_and_the_plain_list_are_flat(self):
        flat = self.get("view=all&limit=1000")
        self.assertEqual(len(flat), 12)
        self.assertFalse(any(i.get("show") for i in flat))
        self.assertFalse(any(i.get("show") for i in self.get("view=recent&group=1&limit=1000")))
        self.assertFalse(any(i.get("show") for i in self.get("view=favorites&group=1")))

    def test_limit_applies_to_rows_after_grouping(self):
        self.assertEqual(len(self.get("view=all&group=1&limit=2")), 2)


if __name__ == "__main__":
    unittest.main()
