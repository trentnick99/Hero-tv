import datetime as dt
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import make_db  # noqa: E402
from herotv import checklist as CL, config, launcher, scheduler as S, server as SV  # noqa: E402
from herotv.config import Config  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = dt.date(2026, 10, 24)


def row(title, year=None, franchise="", series="", season=0, episode=0, playable=1):
    return {"title": title, "year": year, "franchise": franchise, "series": series, "season": season, "episode": episode, "playable": playable}


def lst(*items, **kw):
    return {"name": "T", "kind": "movies", "items": list(items), **kw}


class MatchTests(unittest.TestCase):
    def test_sequels_are_not_confused(self):
        rows = [row("Iron Man", 2008), row("Iron Man 2", 2010)]
        r = CL.build(rows, [lst({"title": "Iron Man", "year": 2008}, {"title": "Iron Man 2", "year": 2010}, {"title": "Iron Man 3", "year": 2013})], TODAY)[0]
        self.assertEqual([i["have"] for i in r["items"]], [True, True, False])
        self.assertEqual((r["have"], r["missing"]), (2, 1))

    def test_a_file_without_a_year_needs_the_exact_title(self):
        r = CL.build([row("Spider Man 2")], [lst({"title": "Spider-Man", "year": 2002}, {"title": "Spider-Man 2", "year": 2004})], TODAY)[0]
        self.assertEqual([i["have"] for i in r["items"]], [False, True])

    def test_punctuation_the_and_aka(self):
        rows = [row("Avengers", 2012), row("Into the Spider Verse", 2018), row("Thunderbolts", 2025), row("Deadpool and Wolverine", 2024)]
        r = CL.build(rows, [lst({"title": "The Avengers", "year": 2012},
                                {"title": "Spider-Man: Into the Spider-Verse", "year": 2018, "aka": ["Into the Spider-Verse"]},
                                {"title": "Thunderbolts*", "year": 2025}, {"title": "Deadpool & Wolverine", "year": 2024})], TODAY)[0]
        self.assertTrue(all(i["have"] for i in r["items"]), r["items"])

    def test_wrong_year_by_more_than_one_is_not_a_match(self):
        r = CL.build([row("Halloween", 2018)], [lst({"title": "Halloween", "year": 1978})], TODAY)[0]
        self.assertFalse(r["items"][0]["have"])

    def test_unreleased_is_coming_soon_not_missing(self):
        r = CL.build([], [lst({"title": "Avengers: Doomsday", "year": 2026, "date": "2026-12-18"}, {"title": "Old one", "year": 2000})], TODAY)[0]
        self.assertTrue(r["items"][0]["soon"])
        self.assertEqual((r["soon"], r["missing"]), (1, 1))
        later = CL.build([], [lst({"title": "Avengers: Doomsday", "year": 2026, "date": "2026-12-18"})], dt.date(2026, 12, 19))[0]
        self.assertEqual((later["soon"], later["missing"]), (0, 1))

    def test_series_seasons_and_missing_episodes(self):
        rows = [row("Ep", franchise="Invincible", series="Invincible", season=1, episode=e) for e in range(1, 9)]
        rows += [row("Ep", franchise="Invincible", series="Invincible", season=2, episode=e) for e in (1, 2, 4)]
        r = CL.build(rows, [{"name": "Invincible", "kind": "series", "series": "Invincible", "seasons": {"1": 8, "2": 8, "3": 8}}], TODAY)[0]
        s1, s2, s3 = r["items"]
        self.assertTrue(s1["done"])
        self.assertEqual(s2["missing_eps"], [3, 5, 6, 7, 8])
        self.assertEqual(s3["have"], 0)
        self.assertEqual(r["have"], 11)
        self.assertEqual(r["missing"], 5 + 8)

    def test_series_without_known_totals_just_counts(self):
        rows = [row("Ep", franchise="South Park", series="South Park", season=2, episode=e) for e in (1, 2)]
        r = CL.build(rows, [{"name": "South Park", "kind": "series", "series": "South Park", "seasons": {}}], TODAY)[0]
        self.assertEqual(r["items"][0]["have"], 2)
        self.assertEqual(r["missing"], 0)

    def test_text_output(self):
        r = CL.build([row("Iron Man", 2008)], [lst({"title": "Iron Man", "year": 2008}, {"title": "Thor", "year": 2011}, name="Marvel", channel="1 Marvel")], TODAY)
        text = CL.to_text(r)
        self.assertIn("[x] Iron Man (2008)", text)
        self.assertIn("[ ] Thor (2011)", text)
        self.assertIn("you have 1 of 2", text)

    def test_shipped_lists_load_and_cover_the_wishes(self):
        lists = CL.load(os.path.join(ROOT, "config", "checklist.json"))
        names = [l["name"] for l in lists]
        for want in ("Marvel Movies", "Spider-Man", "DC Movies", "Invincible", "South Park"):
            self.assertIn(want, names)
        self.assertTrue(CL.build([], lists, TODAY))


class ChannelsAndSortTests(unittest.TestCase):
    def test_new_channels_exist_and_sort_keywords_point_at_them(self):
        data = json.load(open(os.path.join(ROOT, "config", "channels.json"), encoding="utf-8-sig"))["channels"]
        by = {c["id"]: c for c in data}
        S.sync_channels(make_db(), data, tz="UTC")
        self.assertEqual(by["invincible"]["match"], {"franchise": ["Invincible"]})
        self.assertEqual(by["horror"]["match"], {"franchise": ["Thriller & Horror"]})
        rules = json.load(open(os.path.join(ROOT, "config", "auto-sort.json"), encoding="utf-8-sig"))
        self.assertEqual(launcher.plan_sort("Invincible S01E01 Its About Time", rules), {"invincible"})
        self.assertIn("horror", launcher.plan_sort("Hereditary (2018)", rules))
        self.assertEqual(launcher.plan_sort("Iron Man (2008)", rules) & {"invincible", "horror"}, set())

    def test_thriller_tagged_video_lands_on_horror_channel(self):
        data = json.load(open(os.path.join(ROOT, "config", "channels.json"), encoding="utf-8-sig"))["channels"]
        horror = next(c for c in data if c["id"] == "horror")
        c = make_db()
        c.execute("INSERT INTO media(path,title,tags,franchise,verified,playable,available,runtime_s) VALUES('/x/a.mp4','A','[\"thriller\"]','',1,1,1,600)")
        r = c.execute("SELECT * FROM media").fetchone()
        self.assertTrue(S.matches(S.config_rules(horror), r))


class PersonalizeAndServerTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.settings = os.path.join(self.d, "settings.json")
        self._saved = config.settings_file
        from pathlib import Path
        config.settings_file = lambda: Path(self.settings)
        import herotv.launcher as L
        self.addCleanup(lambda: setattr(config, "settings_file", self._saved))

    def test_default_then_personalized(self):
        self.assertEqual(config.station()["name"], "HERO TV")
        self.assertEqual(launcher.personalize("Nick's Hero TV", "2", "Your hero, your shows"), 0)
        st = config.station()
        self.assertEqual((st["name"], st["color"], st["tagline"]), ("Nick's Hero TV", "#ff3b3b", "Your hero, your shows"))
        self.assertEqual(launcher.personalize(color="Blue"), 0)
        self.assertEqual(config.station()["color"], "#3d6bff")
        self.assertEqual(config.station()["name"], "Nick's Hero TV")          # untouched settings stay
        self.assertEqual(launcher.personalize(color="banana"), 1)
        self.assertEqual(config.station()["color"], "#3d6bff")

    def test_personalize_keeps_other_settings(self):
        json.dump({"media_dir": "E:\\Videos", "weather": {"x": 1}}, open(self.settings, "w"))
        launcher.personalize("Mine")
        d = json.load(open(self.settings))
        self.assertEqual(d["media_dir"], "E:\\Videos")
        self.assertEqual(d["weather"], {"x": 1})

    def test_bad_settings_file_gives_defaults(self):
        open(self.settings, "w").write("{not json")
        self.assertEqual(config.station()["name"], "HERO TV")

    def test_api_theme_and_checklist(self):
        launcher.personalize("Nick's Hero TV", "Gold")
        cfg = Config(); cfg.db_path = os.path.join(self.d, "t.sqlite3"); cfg.tz = "UTC"; cfg.media_dir = self.d
        c = make_db(cfg.db_path)
        c.execute("INSERT INTO media(path,title,year,verified,playable,available,runtime_s) VALUES('/x/i.mp4','Iron Man',2008,1,1,1,6000)")
        c.commit()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        theme = json.load(urllib.request.urlopen(base + "/api/theme"))
        self.assertEqual(theme["name"], "Nick's Hero TV")
        lists = json.load(urllib.request.urlopen(base + "/api/checklist"))["lists"]
        marvel = next(l for l in lists if l["name"] == "Marvel Movies")
        self.assertEqual(marvel["have"], 1)
        self.assertTrue(marvel["missing"] > 20)
        page = open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8").read()
        for needle in ('id="check"', "openCheck", "/api/theme"):
            self.assertIn(needle, page)


if __name__ == "__main__":
    unittest.main()
