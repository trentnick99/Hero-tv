"""Your watching (stats), the New this week row and the swipe picker's pool."""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import smart, stats  # noqa: E402
from herotv.db import connect  # noqa: E402
from test_smart_rows import add, art_row  # noqa: E402


class Stats(unittest.TestCase):
    def setUp(self):
        self.c = connect(os.path.join(tempfile.mkdtemp(), "t.sqlite3"))
        now = int(time.time())
        add(self.c, 1, "Heat", 1995, runtime=7200, added=now - 30 * 86400)
        add(self.c, 2, "Up", 2009, runtime=5400, added=now - 2 * 86400)
        for e in range(1, 4):
            add(self.c, 10 + e, f"Ep {e}", series="Cool Show", season=1, episode=e, runtime=1800, added=now - 86400)
        art_row(self.c, "m:heat:1995", ["Crime"], 8)
        art_row(self.c, "s:cool show", ["Comedy"], 9)
        self.c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(1,0,1,?)", (now - 40 * 86400,))   # Heat: finished long ago
        self.c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(11,900,0,?)", (now,))               # half an episode today
        self.c.execute("INSERT INTO seen(media_id,secs,last) VALUES(12,1800,?)", (now,))                                     # a whole episode on live TV
        self.c.commit()

    def test_totals_top_and_genres(self):
        s = stats.build(self.c)
        self.assertEqual(s["hours"], round((7200 + 900 + 1800) / 3600, 1))
        self.assertEqual(s["week_hours"], round((900 + 1800) / 3600, 1))
        self.assertEqual((s["finished"], s["started"]), (1, 3))
        self.assertEqual([t["name"] for t in s["top"]], ["Heat (1995)", "Cool Show"])
        self.assertEqual(s["genres"][0]["name"], "Crime")
        self.assertEqual(s["added_week"], 4)

    def test_week_row_and_pick_pool(self):
        r = smart.build(self.c, ["week"])["week"]
        self.assertEqual(r["sub"], "1 film and 3 episodes added")
        self.assertEqual([d["title"] for d in r["items"]], ["Ep 1", "Up"])
        pool = smart.pick_pool(self.c)
        self.assertNotIn(1, [d["id"] for d in pool])                       # finished: not offered
        self.assertEqual(sum(1 for d in pool if d["series"]), 1)           # one tile for the show
        self.assertTrue(smart.valid_id("week"))
