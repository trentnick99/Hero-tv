"""Missing episodes, duplicates, and new episodes following their show."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import config, inbox, insights, sortrules  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402


class InsightTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        shutil.copytree(Path(config.ROOT) / "config", Path(self.d) / "config")
        self.media = os.path.join(self.d, "media")
        os.makedirs(os.path.join(self.media, "Inbox"))
        self.cfg = Config(media_dir=Path(self.media), db_path=os.path.join(self.d, "t.sqlite3"),
                          channels_file=str(Path(self.d) / "config" / "channels.json"))
        p = mock.patch.object(config, "settings_file", return_value=Path(self.d) / "settings.json")
        p.start(); self.addCleanup(p.stop)
        self.c = connect(self.cfg.db_path)
        self.addCleanup(self.c.close)
        self.rules, self.chans = sortrules.load(self.cfg)
        self.n = 0

    def add(self, title, series="", season=0, episode=0, franchise="", year=None, size=100, runtime=1500, playable=1):
        self.n += 1
        self.c.execute("INSERT INTO media(path,title,year,franchise,series,season,episode,size,runtime_s,playable,verified,available) "
                       "VALUES(?,?,?,?,?,?,?,?,?,?,1,1)", (f"/m/{franchise}/{title}-{self.n}.mp4", title, year, franchise, series, season, episode,
                                                           size, runtime, playable))
        self.c.commit()

    def test_new_episode_follows_its_show(self):
        for e in (1, 2):
            self.add(f"Ep {e}", "Peacemaker", 1, e, "DC")
        self.assertEqual([c["id"] for c in insights.series_channels(self.c, self.chans, "Peacemaker.S01E05.1080p")], ["dc"])
        self.assertEqual(insights.series_channels(self.c, self.chans, "Peacemaker (2022)"), [])     # a film of that name: no
        self.assertEqual(insights.series_channels(self.c, self.chans, "Other Show S01E01"), [])
        self.c.close()
        f = os.path.join(self.media, "Inbox", "Peacemaker S01E05.mp4")
        open(f, "wb").write(b"x")
        placed = []
        with mock.patch.object(inbox, "candidates", return_value=([f], {f: 1})):
            inbox.run_once(self.cfg, {}, place=lambda src, picked, media, force_move=False: placed.append([c["id"] for c in picked]) or True)
        self.assertEqual(placed, [["dc"]])
        self.c = connect(self.cfg.db_path)

    def tv(self, calls):
        def fj(path, params, key, timeout=20):
            calls.append(path)
            if path.startswith("/search/"):
                return {"results": [{"id": 77, "name": "Daredevil", "first_air_date": "2015-04-10"}]}
            return {"name": "Daredevil", "first_air_date": "2015-04-10", "genres": [], "seasons": [
                {"season_number": 0, "episode_count": 3}, {"season_number": 1, "episode_count": 5},
                {"season_number": 2, "episode_count": 8}, {"season_number": 3, "episode_count": 10}],
                "last_episode_to_air": {"season_number": 2, "episode_number": 2}}
        return fj

    def test_missing_episodes(self):
        for e in (1, 2, 3):
            self.add(f"Ep {e}", "Daredevil", 1, e, "Marvel Television")
        calls = []
        m = insights.missing(self.c, self.cfg, "Daredevil", key="k", fj=self.tv(calls), now=1000)
        self.assertEqual([(s["season"], s["missing"]) for s in m["seasons"]], [(1, [4, 5]), (2, [1, 2])])   # S3 not aired; S2 only 2 so far
        self.assertEqual((m["missing"], m["aired"]), (4, 7))
        self.assertEqual(insights.describe_missing(m), "Season 1: 4-5  ·  Season 2: all 2")
        n = len(calls)
        with mock.patch.object(insights.art, "fetch_json", side_effect=OSError("offline")):
            again = insights.missing(self.c, self.cfg, "Daredevil", key="k", now=2000)    # remembered: no lookup
        self.assertEqual(again["missing"], 4)
        self.assertEqual(len(calls), n)
        self.assertIsNone(insights.missing(self.c, self.cfg, "Unknown", key="", now=1000))                   # no key: quiet

    def test_absolute_numbering(self):
        for e in (1, 2, 4):
            self.add(f"Ep {e}", "Daredevil", 0, e, "Marvel Television")
        m = insights.missing(self.c, self.cfg, "Daredevil", key="k", fj=self.tv([]), now=1000)
        self.assertEqual(m["seasons"][0]["missing"], [3, 5, 6, 7])
        self.assertEqual(insights.describe_missing(m), "Episodes 3, 5-7")

    def test_duplicates(self):
        self.add("Iron Man", year=2008, franchise="MCU", size=4_000_000_000, runtime=7600)
        self.add("Iron Man", year=2008, franchise="Inbox", size=9_000_000_000, runtime=7620, playable=0)
        self.add("Iron Man", year=1931, franchise="Classics", size=1)                         # another film
        self.add("Blade Runner", year=1982, franchise="Films", runtime=7000)
        self.add("Blade Runner", year=1982, franchise="Films", runtime=13000)                  # far longer: another cut
        self.add("Pilot", "Invincible", 1, 1, "Invincible", size=5)
        self.add("Pilot", "Invincible", 1, 1, "Invincible", size=7)
        self.add("Untitled", franchise="X")
        self.add("Untitled", franchise="X")                                                    # no year: not sure
        d = insights.duplicates(self.c)
        self.assertEqual([g["name"] for g in d], ["Iron Man (2008)", "Invincible  S1E1"])
        im = d[0]["copies"]
        self.assertTrue(im[0]["keep"] and im[0]["plays"] and im[0]["folder"] == "MCU")         # plays here beats bigger
        self.assertEqual(d[0]["extra"], 9_000_000_000)


class AsideTests(unittest.TestCase):
    def test_set_aside_job_moves_into_originals(self):
        import threading
        import time
        import urllib.request
        from http.server import ThreadingHTTPServer
        from herotv import jobs, launcher, library, server as SV
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copytree(Path(config.ROOT) / "config", Path(d) / "config")
        media = os.path.join(d, "media", "MCU")
        os.makedirs(media)
        f = os.path.join(media, "Iron Man (2008) copy.mp4")
        open(f, "wb").write(b"x" * 10)
        library.write_sidecar(f, {"title": "x"})
        cfg = Config(media_dir=Path(d) / "media", db_path=os.path.join(d, "t.sqlite3"), channels_file=str(Path(d) / "config" / "channels.json"))
        cfg.tz = "UTC"
        with mock.patch.object(config, "settings_file", return_value=Path(d) / "settings.json"), \
                mock.patch.object(launcher, "rescan_running", return_value=None):
            c = connect(cfg.db_path)
            c.execute("INSERT INTO media(path,title,year,available) VALUES(?,?,?,1)", (f, "Iron Man", 2008)); c.commit()
            mid = c.execute("SELECT id FROM media").fetchone()[0]; c.close()
            srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
            r = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/api/job", json.dumps({"name": "aside", "media_id": mid}).encode(),
                                       {"Content-Type": "application/json"})
            urllib.request.urlopen(r).read()
            for _ in range(100):
                if jobs.current()["state"] != "running":
                    break
                time.sleep(0.05)
        self.assertEqual(jobs.current()["state"], "done")
        self.assertFalse(os.path.exists(f))
        self.assertEqual(sorted(os.listdir(os.path.join(media, ".originals"))), ["Iron Man (2008) copy.hero.json", "Iron Man (2008) copy.mp4"])


if __name__ == "__main__":
    unittest.main()
