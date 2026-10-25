"""Your own corrections: Inbox helper ("Put it here"), Move to another channel, and remembering them."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import config, fixes, launcher, library, sortrules  # noqa: E402
from herotv.config import Config  # noqa: E402


def touch(p, size=10):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(b"x" * size)


class MoveTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        shutil.copytree(Path(config.ROOT) / "config", Path(self.d) / "config")
        self.media = os.path.join(self.d, "media")
        os.makedirs(self.media)
        self.cfg = Config(media_dir=Path(self.media), db_path=os.path.join(self.d, "t.sqlite3"),
                          channels_file=str(Path(self.d) / "config" / "channels.json"))
        p = mock.patch.object(config, "settings_file", return_value=Path(self.d) / "settings.json")
        p.start(); self.addCleanup(p.stop)
        r = mock.patch.object(launcher, "rescan_running", return_value=None)
        r.start(); self.addCleanup(r.stop)
        self.rules, self.chans = sortrules.load(self.cfg)
        self.by = {c["id"]: c for c in self.chans}

    def test_keys(self):
        self.assertEqual(fixes.key("Daredevil S01E02 Cut Man"), "daredevil")
        self.assertEqual(fixes.key("Daredevil.S02E05.1080p"), "daredevil")
        self.assertEqual(fixes.key("Iron Man (2008)"), "iron man 2008")

    def test_remembered_choice_beats_keywords_and_smart_rules(self):
        smart = sortrules.smart_rules(self.cfg)
        facts = {"type": "movie", "companies": ["Marvel Studios"], "genres": ["Action"], "keywords": [], "year": 2008}
        self.assertEqual([c["id"] for c in sortrules.targets("Iron Man (2008)", self.rules, self.chans, facts, smart)], ["mcu"])
        fixes.remember(self.cfg, "Iron Man (2008) 1080p", ["classics"])
        mine = fixes.load(self.cfg)
        self.assertEqual([c["id"] for c in sortrules.targets("Iron Man (2008)", self.rules, self.chans, facts, smart, mine)], ["classics"])
        self.assertEqual([c["id"] for c in sortrules.targets("Some Show S01E01", self.rules, self.chans, None, smart, mine)], [])
        fixes.remember(self.cfg, "Some Show S01E01", ["south-park"])                      # a show: every episode follows
        mine = fixes.load(self.cfg)
        self.assertEqual([c["id"] for c in sortrules.targets("Some.Show.S03E09", self.rules, self.chans, None, smart, mine)], ["south-park"])
        data = json.loads(open(fixes.path(self.cfg), encoding="utf-8").read())
        self.assertIn("_help", data)

    def test_broken_file_is_ignored(self):
        open(fixes.path(self.cfg), "w").write("{nope")
        self.assertEqual(fixes.load(self.cfg), {})

    def test_move_a_whole_show_keeps_seasons_and_companions(self):
        base = os.path.join(self.media, "Marvel Television", "Daredevil")
        eps = [os.path.join(base, "Season 1", f"Daredevil S01E0{i}.mp4") for i in (1, 2)]
        for e in eps:
            touch(e)
        touch(os.path.join(base, "Season 1", "Daredevil S01E01.en.srt"))
        touch(os.path.join(base, "poster.jpg"))
        library.write_sidecar(eps[0], {"title": "Into the Ring"})
        rc = launcher.move_to(self.cfg, eps, [self.by["horror"]], self.chans)
        self.assertEqual(rc, 0)
        new = os.path.join(self.media, "Thriller & Horror", "Daredevil", "Season 1")
        self.assertTrue(os.path.isfile(os.path.join(new, "Daredevil S01E01.mp4")))
        self.assertTrue(os.path.isfile(os.path.join(new, "Daredevil S01E02.mp4")))
        self.assertTrue(os.path.isfile(os.path.join(new, "Daredevil S01E01.en.srt")))
        self.assertEqual(json.load(open(os.path.join(new, "Daredevil S01E01.hero.json")))["title"], "Into the Ring")
        self.assertTrue(os.path.isfile(os.path.join(self.media, "Thriller & Horror", "Daredevil", "poster.jpg")))
        self.assertFalse(os.path.exists(base))                      # emptied folders are tidied away...
        self.assertTrue(os.path.isdir(os.path.join(self.media, "Marvel Television")))  # ...but not the channel folder

    def test_move_to_a_tag_channel_swaps_tags(self):
        f = os.path.join(self.media, "MCU", "Iron Man (2008).mp4")
        touch(f)
        library.write_sidecar(f, {"tags": ["action", "favourite-of-dad"]})
        launcher.move_to(self.cfg, [f], [self.by["comedy"]], self.chans)
        dest = os.path.join(self.media, self.by["comedy"]["name"], "Iron Man (2008).mp4")
        self.assertTrue(os.path.isfile(dest))                           # out of the MCU folder
        tags = json.load(open(os.path.splitext(dest)[0] + ".hero.json"))["tags"]
        self.assertEqual(tags, ["favourite-of-dad", "comedy"])          # old channel tag gone, your own tag kept

    def test_tag_only_move_outside_channel_folders_stays_put(self):
        f = os.path.join(self.media, "Misc", "Mystery Men (1999).mp4")
        touch(f)
        launcher.move_to(self.cfg, [f], [self.by["comedy"]], self.chans)
        self.assertTrue(os.path.isfile(f))
        self.assertEqual(json.load(open(os.path.splitext(f)[0] + ".hero.json"))["tags"], ["comedy"])

    def test_never_overwrites(self):
        a = os.path.join(self.media, "MCU", "Logan (2017).mp4")
        b = os.path.join(self.media, "X-Men", "Logan (2017).mp4")
        touch(a, 5); touch(b, 7)
        rc = launcher.move_to(self.cfg, [a], [self.by["x-men"]], self.chans)
        self.assertEqual(rc, 1)
        self.assertEqual(os.path.getsize(b), 7)
        self.assertTrue(os.path.isfile(a))


class ServerMoveTests(unittest.TestCase):
    def setUp(self):
        import threading
        from http.server import ThreadingHTTPServer
        from herotv import db, jobs, server as SV
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        shutil.copytree(Path(config.ROOT) / "config", Path(self.d) / "config")
        self.media = os.path.join(self.d, "media")
        os.makedirs(os.path.join(self.media, "Inbox"))
        cfg = Config(media_dir=Path(self.media), db_path=os.path.join(self.d, "t.sqlite3"),
                     channels_file=str(Path(self.d) / "config" / "channels.json"))
        cfg.tz = "UTC"
        self.cfg = cfg
        p = mock.patch.object(config, "settings_file", return_value=Path(self.d) / "settings.json")
        p.start(); self.addCleanup(p.stop)
        r = mock.patch.object(launcher, "rescan_running", return_value=None)
        r.start(); self.addCleanup(r.stop)
        self.c = db.connect(cfg.db_path)
        self.app = SV.App(cfg)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(self.app))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        self.base = f"http://127.0.0.1:{srv.server_address[1]}"
        self.jobs = jobs

    def call(self, path, body=None):
        import urllib.request
        r = urllib.request.Request(self.base + path, json.dumps(body).encode() if body is not None else None,
                                   {"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(r))

    def wait(self):
        import time
        for _ in range(200):
            j = self.jobs.current()
            if j and j["state"] != "running":
                return j
            time.sleep(0.05)
        self.fail("job did not finish")

    def test_inbox_helper_lists_and_places(self):
        touch(os.path.join(self.media, "Inbox", "Mystery.Men.(1999).mp4"))
        t = self.call("/api/tools")
        self.assertEqual([f["title"] for f in t["inbox_files"]], ["Mystery Men (1999)"])
        ids = [c["id"] for c in t["move_channels"]]
        self.assertIn("comedy", ids)
        self.assertNotIn("weather", ids)
        self.assertNotIn("marathon", ids)
        with mock.patch.object(launcher, "_place", return_value=True) as pl:
            self.call("/api/job", {"name": "place", "file": "Mystery.Men.(1999).mp4", "channels": ["comedy"], "remember": True})
            self.assertEqual(self.wait()["state"], "done")
        self.assertEqual(pl.call_args[0][1][0]["id"], "comedy")
        self.assertEqual(fixes.load(self.cfg), {"mystery men 1999": ["comedy"]})

    def test_place_refuses_paths_outside_the_inbox_and_unknown_channels(self):
        import urllib.error
        touch(os.path.join(self.media, "secret.mp4"))
        for body in ({"name": "place", "file": "../secret.mp4", "channels": ["comedy"]},
                     {"name": "place", "file": "x.mp4", "channels": ["weather"]},
                     {"name": "place", "file": "x.mp4", "channels": []}):
            with self.assertRaises(urllib.error.HTTPError):
                self.call("/api/job", body)

    def test_new_channel_for_a_pack_nobody_planned_for(self):
        ib = os.path.join(self.media, "Inbox")
        for i in (1, 2, 3):
            touch(os.path.join(ib, "Zoboomafoo Collection", f"Episode {i}.mp4"))
        for i in (1, 2):
            touch(os.path.join(ib, f"Arthur.S01E0{i}.mp4"))
        touch(os.path.join(ib, "Other Film (1999).mp4"))
        files = {f["file"]: f for f in self.call("/api/tools")["inbox_files"]}
        self.assertEqual(sorted(files), ["Arthur.S01E01.mp4", "Other Film (1999).mp4", "Zoboomafoo Collection/Episode 1.mp4"])   # one row per show/pack
        self.assertEqual((files["Arthur.S01E01.mp4"]["pack"], files["Arthur.S01E01.mp4"]["group"]), ("Arthur", 2))
        z = files["Zoboomafoo Collection/Episode 1.mp4"]
        self.assertEqual((z["pack"], z["group"]), ("Zoboomafoo Collection", 3))
        placed = []
        with mock.patch.object(launcher, "_place", side_effect=lambda src, picked, media, force_move=False: placed.append((os.path.basename(src), picked[0]["id"])) or True):
            self.call("/api/job", {"name": "newchan", "file": "Arthur.S01E01.mp4", "channel_name": "PBS Kids"})
            self.assertEqual(self.wait()["state"], "done")
        self.assertEqual(sorted(placed), [("Arthur.S01E01.mp4", "pbs-kids"), ("Arthur.S01E02.mp4", "pbs-kids")])
        chans = json.load(open(self.cfg.channels_file, encoding="utf-8"))["channels"]
        new = [c for c in chans if c["id"] == "pbs-kids"][0]
        self.assertEqual(new["match"], {"franchise": ["PBS Kids"]})
        self.assertTrue(os.path.isdir(os.path.join(self.media, "PBS Kids")))
        self.assertEqual(fixes.load(self.cfg)["arthur"], ["pbs-kids"])                     # Arthur S02 will follow

    def test_details_say_which_channels_and_move_whole_show(self):
        base = os.path.join(self.media, "Marvel Television", "Daredevil")
        for i in (1, 2):
            touch(os.path.join(base, f"Daredevil S01E0{i}.mp4"), 10 + i)
        library.scan(self.c, self.media, probe_fn=lambda p: {"runtime_s": 3000, "vcodec": "h264", "acodec": "aac", "vfmt": "yuv420p|high", "title": ""})
        self.c.commit()
        mid = self.c.execute("SELECT id FROM media WHERE path LIKE '%S01E01%'").fetchone()[0]
        info = self.call(f"/api/info/{mid}")
        self.assertEqual(info["on_ids"], ["marvel-tv"])
        self.assertEqual(info["episodes"], 2)
        self.call("/api/job", {"name": "move", "media_id": mid, "channels": ["horror"], "remember": True})
        self.assertEqual(self.wait()["state"], "done")
        self.assertEqual(sorted(os.listdir(os.path.join(self.media, "Thriller & Horror", "Daredevil"))),
                         ["Daredevil S01E01.mp4", "Daredevil S01E02.mp4"])
        self.assertEqual(fixes.load(self.cfg), {"daredevil": ["horror"]})


if __name__ == "__main__":
    unittest.main()
