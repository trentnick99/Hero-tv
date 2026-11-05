"""Smart rows for Home: not watched yet, quick watches, movies, top rated and one row per genre."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import settings_api, smart  # noqa: E402
from herotv.db import connect  # noqa: E402


def add(c, i, title, year=0, series="", season=0, episode=0, runtime=3000, added=0):
    c.execute("INSERT INTO media(id,path,title,year,franchise,series,season,episode,verified,playable,available,runtime_s,ord,added) "
              "VALUES(?,?,?,?,?,?,?,?,1,1,1,?,?,?)", (i, f"/m/{i}.mp4", title, year or None, "F", series, season, episode, runtime, i, added or i))


def art_row(c, key, genres, rating):
    c.execute("INSERT INTO art(key,tmdb_id,kind,title,genres,rating,miss) VALUES(?,?,?,?,?,?,0)", (key, 1, "m", key, json.dumps(genres), rating))


class Smart(unittest.TestCase):
    def setUp(self):
        self.c = connect(os.path.join(tempfile.mkdtemp(), "t.sqlite3"))
        for i in range(1, 5):                                   # four movies
            add(self.c, i, f"Movie {i}", 2000 + i, runtime=6000)
            art_row(self.c, f"m:movie {i}:{2000 + i}", ["Comedy"] if i < 4 else ["Drama"], 5 + i)
        for e in range(1, 6):                                   # one show with five short episodes
            add(self.c, 10 + e, f"Ep {e}", series="Cool Show", season=1, episode=e, runtime=1500, added=100 + e)
        art_row(self.c, "s:cool show", ["Comedy"], 10)
        self.c.commit()

    def test_validation(self):
        self.assertTrue(smart.valid_id("unwatched"))
        self.assertTrue(smart.valid_id("genre:Comedy"))
        self.assertFalse(smart.valid_id("nope"))
        self.assertFalse(smart.valid_id(5))
        self.assertEqual(settings_api._home_rows(["new", "genre:Comedy", "bogus", "new"]), ["new", "genre:Comedy"])

    def test_genre_row_one_tile_per_show(self):
        r = smart.build(self.c, ["genre:Comedy"])["genre:Comedy"]
        titles = [d["title"] for d in r["items"]]
        self.assertEqual(len(titles), 4)                        # 3 comedy movies + 1 tile for the show, not 5 episodes
        self.assertEqual(sum(1 for d in r["items"] if d["series"] == "Cool Show"), 1)

    def test_unwatched_skips_started_and_picks_first_episode(self):
        self.c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(11,0,1,1)")
        self.c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(1,500,0,1)")
        self.c.commit()
        r = smart.build(self.c, ["unwatched"])["unwatched"]
        self.assertNotIn(1, [d["id"] for d in r["items"]])
        show = [d for d in r["items"] if d["series"] == "Cool Show"]
        self.assertEqual([d["episode"] for d in show], [2])      # episode 1 is finished, so the next one stands for the show

    def test_quick_and_movies_and_top(self):
        self.assertNotIn("short", smart.build(self.c, ["short"]))       # only one show tile is short: too few for a row
        self.assertEqual(len(smart.build(self.c, ["movies"])["movies"]["items"]), 4)
        top = smart.build(self.c, ["toprated"])["toprated"]["items"]
        self.assertEqual(top[0]["series"], "Cool Show")

    def test_featured_picks_good_unwatched_with_details(self):
        from unittest import mock
        with mock.patch("herotv.art.info", return_value={"plot": "A plot.", "rating": 8.1, "genres": ["Comedy"]}):
            r = smart.build(self.c, ["featured"], None)["featured"]["items"]
        self.assertTrue(2 <= len(r) <= smart.FEATURED_LEN)
        self.assertEqual(r[0]["about"], "A plot.")
        self.assertEqual(r[0]["genres"], ["Comedy"])
        self.assertNotIn("_genres", r[0])

    def test_surprise_is_unwatched_and_none_when_empty(self):
        self.c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(?,?,1,1)", (1, 0))
        self.c.commit()
        for _ in range(20):
            self.assertNotEqual(smart.surprise(self.c)["id"], 1)
        self.c.execute("UPDATE media SET available=0")
        self.c.commit()
        self.assertIsNone(smart.surprise(self.c))

    def test_height_column_exists_and_scan_fills_it(self):
        from pathlib import Path
        from herotv import library
        cols = [r[1] for r in self.c.execute("PRAGMA table_info(media)")]
        self.assertIn("height", cols)
        d = Path(tempfile.mkdtemp())
        (d / "Film (2010).mp4").write_bytes(b"x" * 10)
        library.scan(self.c, d, probe_fn=lambda p: {"runtime_s": 6000, "vcodec": "h264", "acodec": "aac", "vfmt": "yuv420p|high", "title": "", "height": 2160})
        h = self.c.execute("SELECT height FROM media WHERE path LIKE '%Film%'").fetchone()[0]
        self.assertEqual(h, 2160)

    def test_catalog_lists_genres(self):
        ids = [x["id"] for x in smart.catalog(self.c)]
        self.assertIn("genre:Comedy", ids)
        self.assertNotIn("genre:Drama", ids)                     # only one title


if __name__ == "__main__":
    unittest.main()
