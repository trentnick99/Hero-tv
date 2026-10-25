"""The For You channel, films in release order, and new built-in channels reaching existing users."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import art, channels_api, config, insights, library, scheduler as S  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402

NOW = 1_800_000_000
DAY = 86400


class ForYouTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.c = connect(os.path.join(self.d, "t.sqlite3"))
        self.addCleanup(self.c.close)
        self.n = 0

    def add(self, title, franchise="", series="", season=0, episode=0, year=None, runtime=6000, added=0, facts=None):
        self.n += 1
        self.c.execute("INSERT INTO media(path,title,year,franchise,series,season,episode,runtime_s,verified,playable,available,added) "
                       "VALUES(?,?,?,?,?,?,?,?,1,1,1,?)", (f"/m/{self.n}.mp4", title, year, franchise, series, season, episode, runtime, added))
        mid = self.c.execute("SELECT last_insert_rowid()").fetchone()[0]
        if facts is not None:
            row = self.c.execute("SELECT * FROM media WHERE id=?", (mid,)).fetchone()
            self.c.execute("INSERT OR REPLACE INTO art(key,kind,title,facts,miss) VALUES(?,?,?,?,0)",
                           (art.key_for(row)[0], "tv" if series else "movie", title, json.dumps(facts)))
        self.c.commit()
        return mid

    def watched(self, mid, ago_days=1, secs=None):
        rt = self.c.execute("SELECT runtime_s FROM media WHERE id=?", (mid,)).fetchone()[0]
        self.c.execute("INSERT OR REPLACE INTO seen(media_id,secs,last) VALUES(?,?,?)", (mid, secs if secs is not None else rt, NOW - ago_days * DAY))
        self.c.commit()

    def titles(self, **k):
        return [r["title"] for r in insights.for_you(self.c, now=NOW, **k)]

    def test_no_history_newest_first(self):
        self.add("Old", added=NOW - 100 * DAY)
        self.add("New", added=NOW - DAY)
        self.assertEqual(self.titles()[0], "New")

    def test_learns_from_what_you_watch(self):
        spidey = {"genres": ["Action"], "companies": ["Marvel Studios"], "keywords": ["superhero", "spider-man"], "collection": "Spider-Man Collection"}
        a = self.add("Spider-Man Homecoming", "Spider-Verse", year=2017, facts=spidey)
        self.add("Spider-Man Far From Home", "Spider-Verse", year=2019, facts=spidey)
        self.add("Iron Man", "MCU", year=2008, facts={"genres": ["Action"], "companies": ["Marvel Studios"], "keywords": ["superhero"]})
        self.add("Pride and Prejudice", "Drama", year=2005, facts={"genres": ["Romance"], "companies": ["Working Title"], "keywords": ["love"]})
        self.watched(a)
        t = self.titles()
        self.assertNotIn("Spider-Man Homecoming", t)                      # already seen
        self.assertEqual(t[:2], ["Spider-Man Far From Home", "Iron Man"])  # same film series first, then same studio
        self.assertEqual(t[-1], "Pride and Prejudice")

    def test_next_episode_of_what_you_are_watching(self):
        for e in (1, 2, 3):
            self.add(f"Ep {e}", "Invincible", "Invincible", 1, e, runtime=2700)
        self.add("Random Film", "Films", year=1999, added=NOW - DAY)
        ep1 = self.c.execute("SELECT id FROM media WHERE title='Ep 1'").fetchone()[0]
        self.watched(ep1)
        t = self.titles()
        self.assertEqual(t[0], "Ep 2")                                    # carry on with the show
        self.assertNotIn("Ep 3", t)                                       # one episode at a time

    def test_half_watched_film_comes_back(self):
        m = self.add("Long Film", "Films", year=2001)
        self.add("Other", "Films", year=2002)
        self.c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(?,?,0,?)", (m, 2400, NOW - DAY))
        self.c.commit()
        self.assertEqual(self.titles()[0], "Long Film")

    def test_variety_cap_per_folder(self):
        for i in range(10):
            self.add(f"MCU {i}", "MCU", year=2000 + i)
        for i in range(3):
            self.add(f"DC {i}", "DC", year=2000 + i)
        top = self.titles(limit=7)
        self.assertEqual(sum(1 for x in top if x.startswith("MCU")), 4)

    def test_channel_plays_it(self):
        self.add("A", "Films", year=2001, added=NOW - DAY)
        S.load_channels(self.c, [{"id": "for-you", "number": 17, "name": "For You", "kind": "foryou"}])
        ch = self.c.execute("SELECT * FROM channels WHERE id='for-you'").fetchone()
        S.extend(self.c, ch, NOW, 6 * 3600, tz="UTC")
        self.assertTrue(self.c.execute("SELECT COUNT(*) FROM slots WHERE channel_id='for-you'").fetchone()[0] > 0)

    def test_history_signature_changes_when_watching(self):
        m = self.add("A")
        before = insights.history_signature(self.c)
        self.watched(m, secs=30)
        self.assertNotEqual(before, insights.history_signature(self.c))


class ReleaseOrderTests(unittest.TestCase):
    def test_films_follow_tmdb_release_dates(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        c = connect(os.path.join(d, "t.sqlite3"))
        self.addCleanup(c.close)
        cfg = Config(media_dir=Path(d), db_path=os.path.join(d, "t.sqlite3"))
        media = os.path.join(d, "MCU")
        os.makedirs(media)
        for n in ("Ant-Man (2015).mp4", "Avengers Age of Ultron (2015).mp4", "Thor.mp4"):
            with open(os.path.join(media, n), "wb") as fh:
                fh.write(b"x")
        probe = lambda p: {"runtime_s": 6000, "vcodec": "h264", "acodec": "aac", "vfmt": "yuv420p|high", "title": ""}
        library.scan(c, d, probe_fn=probe)
        order = lambda: [r[0] for r in c.execute("SELECT title FROM media ORDER BY ord,title")]
        self.assertEqual(order(), ["Ant-Man", "Avengers Age of Ultron", "Thor"])   # same year: alphabetical; no year: last
        for title, year, rel in (("Ant-Man", 2015, "2015-07-14"), ("Avengers Age of Ultron", 2015, "2015-04-22"), ("Thor", None, "2011-04-21")):
            art.save(c, art.key_for({"series": "", "title": title, "year": year})[0],
                     {"tmdb_id": 1, "kind": "movie", "title": title, "year": int(rel[:4]), "overview": "", "tagline": "", "genres": [],
                      "cast": [], "rating": 0, "runtime": 0, "poster": "", "facts": {"released": rel}}, cfg)
        self.assertEqual(order(), ["Thor", "Avengers Age of Ultron", "Ant-Man"])   # TMDB release dates
        c.execute("UPDATE media SET mtime=0")                                     # a rescan keeps the TMDB order
        library.scan(c, d, probe_fn=probe)
        ords = dict(c.execute("SELECT title, ord FROM media"))
        self.assertLess(ords["Avengers Age of Ultron"], ords["Ant-Man"])
        self.assertEqual(ords["Thor"], 2011 * 10_000_000 + 4 * 100_000 + 21 * 1000)


class BuiltinChannelTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        shutil.copytree(Path(config.ROOT) / "config", Path(self.d) / "config")
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"), channels_file=str(Path(self.d) / "config" / "channels.json"))
        p = mock.patch.object(config, "settings_file", return_value=Path(self.d) / "settings.json")
        p.start(); self.addCleanup(p.stop)
        self.cf = Path(self.cfg.channels_file)

    def ids(self):
        return [c["id"] for c in json.loads(self.cf.read_text(encoding="utf-8"))["channels"]]

    def test_for_you_reaches_an_older_channels_file_once(self):
        old = json.loads(self.cf.read_text(encoding="utf-8"))
        old["channels"] = [c for c in old["channels"] if c["id"] != "for-you"]
        old["channels"].append({"id": "mine", "number": 17, "name": "Mine", "match": {"franchise": ["Mine"]}})
        self.cf.write_text(json.dumps(old), encoding="utf-8")
        self.assertTrue(channels_api.ensure_builtin(self.cfg))
        fy = [c for c in json.loads(self.cf.read_text(encoding="utf-8"))["channels"] if c["id"] == "for-you"][0]
        self.assertEqual((fy["kind"], fy["number"]), ("foryou", 18))           # 17 was taken by your own channel
        channels_api.update(self.cfg, {"op": "delete", "id": "for-you"})
        self.assertFalse(channels_api.ensure_builtin(self.cfg))                 # deleted by you: stays gone
        self.assertNotIn("for-you", self.ids())

    def test_new_installs_already_have_it(self):
        self.assertIn("for-you", self.ids())
        self.assertTrue(channels_api.ensure_builtin(self.cfg))                  # only notes it as done
        self.assertEqual(self.ids().count("for-you"), 1)
        groups = {g["name"]: [c["id"] for c in g["channels"]] for g in channels_api.lineup(self.cfg)}
        self.assertIn("for-you", groups["Extras"])


if __name__ == "__main__":
    unittest.main()


class DaypartTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        p = mock.patch.object(config, "settings_file", return_value=Path(self.d) / "settings.json")
        p.start(); self.addCleanup(p.stop)

    def test_marathon_follows_the_clock_and_can_be_switched_off(self):
        import datetime as dt
        chans = [{"id": "marathon", "number": 10, "name": "Hero Marathon", "match": {},
                  "blocks": [{"name": "My Block", "days": "daily", "from": "23:30", "to": "23:45", "match": {"franchise": ["X"]}}]}]
        got = S.with_seasonal(chans)[0]["blocks"]
        names = [b["name"] for b in got]
        self.assertEqual(names[names.index("My Block") + 1:], ["Weekend Morning Cartoons", "Prime Time Heroes", "Late Night Frights"])
        blocks = S.parse_blocks({"blocks": got})
        z = dt.timezone.utc
        self.assertEqual(S.block_at(blocks, dt.datetime(2026, 11, 10, 23, 35, tzinfo=z))["name"], "My Block")      # yours win
        self.assertEqual(S.block_at(blocks, dt.datetime(2026, 11, 3, 1, 0, tzinfo=z))["name"], "Late Night Frights")
        self.assertEqual(S.block_at(blocks, dt.datetime(2026, 11, 7, 8, 0, tzinfo=z))["name"], "Weekend Morning Cartoons")  # Saturday
        self.assertIsNone(S.block_at(blocks, dt.datetime(2026, 11, 4, 8, 0, tzinfo=z)))                              # Wednesday morning
        (Path(self.d) / "settings.json").write_text('{"dayparts": false, "seasonal": false}')
        self.assertEqual([b["name"] for b in S.with_seasonal(chans)[0]["blocks"]], ["My Block"])
