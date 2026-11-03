"""Descriptions for loose episodes: the folder is the show, release leftovers are cut, and each episode gets its own plot."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import art  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402


def fj(path, params, key, timeout=20):
    if path == "/search/tv":
        q = params["query"].lower()
        if q == "south park":
            return {"results": [{"id": 5, "name": "South Park", "first_air_date": "1997-08-13"}]}
        if q == "dragon ball super":
            return {"results": [{"id": 6, "name": "Dragon Ball Super", "first_air_date": "2015-07-05"}]}
        if q == "spider-man the animated series":
            return {"results": [{"id": 8, "name": "Spider-Man: The New Animated Series", "first_air_date": "2003-07-11"},
                                {"id": 7, "name": "Spider-Man", "first_air_date": "1994-11-19"}]}
        return {"results": []}
    if path == "/search/movie":
        if params["query"] == "Bigger Longer and Uncut":
            return {"results": [{"id": 3, "title": "South Park: Bigger, Longer & Uncut", "release_date": "1999-06-30"}]}
        return {"results": []}
    if path.startswith("/tv/") and "/season/" not in path:
        n = int(path.split("/")[2])
        return {"name": {5: "South Park", 6: "Dragon Ball Super", 7: "Spider-Man"}.get(n, "x"), "first_air_date": "1997-08-13",
                "overview": "Show plot %d." % n, "genres": [{"name": "Animation"}], "seasons": [{"season_number": 0}, {"season_number": 1}, {"season_number": 5}],
                "credits": {"cast": []}}
    if path == "/tv/5/season/5":
        return {"episodes": [{"episode_number": 1, "name": "Scott Tenorman Must Die", "overview": "Cartman's revenge.", "air_date": "2001-07-11"}]}
    if path == "/tv/5/season/1":
        return {"episodes": [{"episode_number": 1, "name": "Cartman Gets an Anal Probe", "overview": "Aliens.", "air_date": "1997-08-13"}]}
    if path == "/tv/6/season/1":
        return {"episodes": [{"episode_number": 42, "name": "A Chaotic Victory Party! Showdown at Last! Monaka vs. Goku!", "overview": "Goku fights Monaka.", "air_date": ""}]}
    if path.startswith("/movie/"):
        return {"title": "South Park: Bigger, Longer & Uncut", "release_date": "1999-06-30", "overview": "The movie.", "genres": [], "credits": {"cast": []}}
    return {"results": [], "episodes": []}


class Episodes(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.c = connect(os.path.join(self.d, "t.db"))
        self.cfg = Config(media_dir=self.d, db_path=os.path.join(self.d, "t.db"), port=0)
        p = mock.patch("herotv.config.settings_file", return_value=Path(self.d) / "s.json")
        p.start(); self.addCleanup(p.stop)

    def add(self, title, franchise, episode=0, season=0, series="", year=None):
        self.c.execute("INSERT INTO media(path,title,year,series,season,episode,franchise,verified,playable,available,runtime_s) VALUES(?,?,?,?,?,?,?,1,1,1,1300)",
                       (f"{self.d}/{franchise}/{title}.mp4", title, year, series, season, episode, franchise))
        self.c.commit()
        return self.c.execute("SELECT * FROM media ORDER BY id DESC LIMIT 1").fetchone()

    def test_names_and_keys(self):
        k = lambda **r: art.key_for({"series": "", "title": "t", "year": None, "episode": 0, "franchise": "", "season": 0, **r})
        self.assertEqual(k(series="Invincible season 1")[0], "s:invincible")
        self.assertEqual(k(series="Spider-Man The Animated Series 1994 Complete Seasons 1 to 5 TVRip x264 [i_c]")[1:], ("tv", "Spider-Man The Animated Series", 1994))
        self.assertEqual(k(title="X", episode=4, franchise="South Park")[0], "s:south park")
        self.assertEqual(k(title="X", episode=42, franchise="Dragon Ball")[2], "Dragon Ball Super")       # the folder is really Super
        self.assertEqual(k(title="X", episode=42, franchise="Dragon Ball Super EP.19-76")[2], "Dragon Ball Super")
        self.assertEqual(k(title="X", episode=3, franchise="Inbox")[1], "movie")                            # Inbox is not a show
        self.assertEqual(k(title="[60FPS] Spider-Man Into the Spider-Verse", year=2018)[2:], ("Spider-Man Into the Spider-Verse", 2018))
        self.assertEqual(k(title="Avengers Endgame 2019 Hindi English")[2:], ("Avengers Endgame", 2019))
        self.assertEqual(k(title="Blade Runner 2049")[2:], ("Blade Runner 2049", None))                    # a year in a real title stays
        self.assertEqual(k(title="Wonder Woman 1984")[2:], ("Wonder Woman 1984", None))

    def test_alias_can_come_from_settings(self):
        (Path(self.d) / "s.json").write_text('{"art_aliases": {"Some Folder": "Real Show"}}')
        self.assertEqual(art.key_for({"series": "", "title": "t", "year": None, "episode": 3, "franchise": "Some Folder", "season": 0})[2], "Real Show")

    def test_loose_episodes_get_the_show_and_their_own_plot(self):
        sp = self.add("Scott Tenorman Must Die", "South Park", episode=4)
        db = self.add("A Chaotic Victory Party! Showdown at Last! Monaka vs. Goku!", "Dragon Ball", episode=42)
        mv = self.add("Bigger Longer and Uncut", "South Park Movie")
        sk = self.add("Night of the Lizard", "Inbox", series="Spider-Man The Animated Series 1994 Complete Seasons 1 to 5 TVRip x264 [i_c]", season=1, episode=1)
        done, hit = art.run_pass(self.c, self.cfg, "k", fj=fj, fb=lambda u, timeout=30: b"x", delay=0)
        self.assertGreaterEqual(hit, 4)
        i = art.info(self.c, self.cfg, sp)
        self.assertEqual(i["plot"], "Cartman's revenge.")                    # the episode's own plot (found by its title; ep04 is not a season number)
        self.assertEqual(art.info(self.c, self.cfg, db)["plot"], "Goku fights Monaka.")
        self.assertEqual(art.info(self.c, self.cfg, mv)["plot"], "The movie.")
        self.assertIn("Show plot 7", art.info(self.c, self.cfg, sk)["plot"])  # the 1994 show, not the 2003 'New Animated Series'

    def test_show_plot_is_the_fallback_and_a_local_plot_wins(self):
        r = self.add("Some Unlisted Episode", "South Park", episode=9)
        art.run_pass(self.c, self.cfg, "k", fj=fj, fb=lambda u, timeout=30: b"x", delay=0)
        self.assertEqual(art.info(self.c, self.cfg, r)["plot"], "Show plot 5.")
        self.c.execute("UPDATE media SET plot='From the file' WHERE id=?", (r["id"],)); self.c.commit()
        r = self.c.execute("SELECT * FROM media WHERE id=?", (r["id"],)).fetchone()
        self.assertEqual(art.info(self.c, self.cfg, r)["plot"], "From the file")

    def test_episode_lists_are_fetched_once_and_a_network_failure_is_retried(self):
        self.add("Scott Tenorman Must Die", "South Park", episode=4)
        calls = []

        def counting(path, params, key, timeout=20):
            calls.append(path)
            return fj(path, params, key, timeout)
        art.run_pass(self.c, self.cfg, "k", fj=counting, fb=lambda u, timeout=30: b"x", delay=0)
        n = sum(1 for p in calls if "/season/" in p)
        self.assertEqual(n, 2)
        art.run_pass(self.c, self.cfg, "k", fj=counting, fb=lambda u, timeout=30: b"x", delay=0)
        self.assertEqual(sum(1 for p in calls if "/season/" in p), 2)       # not fetched again
        self.c.execute("DELETE FROM prefs WHERE key LIKE 'art_eps:%'"); self.c.execute("DELETE FROM art_ep"); self.c.commit()

        def offline(path, params, key, timeout=20):
            if "/season/" in path:
                raise OSError("offline")
            return fj(path, params, key, timeout)
        self.assertEqual(art.episodes_pass(self.c, "k", fj=offline, delay=0), 0)
        self.assertEqual(art.episodes_pass(self.c, "k", fj=fj, delay=0), 1)


if __name__ == "__main__":
    unittest.main()
