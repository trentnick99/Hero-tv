import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import config, server as SV, settings_api as SA  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = Path(self.d) / "sub" / "settings.json"
        p = mock.patch.object(config, "settings_file", return_value=self.f)
        p.start(); self.addCleanup(p.stop)
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"),
                          channels_file=str(Path(config.ROOT) / "config" / "channels.json"))

    def data(self):
        return json.loads(self.f.read_text())

    def test_station_saved_and_validated(self):
        SA.update({"station": {"name": " My Network ", "color": "#ff3b3b", "tagline": "Hi"}})
        self.assertEqual(config.station()["name"], "My Network")
        self.assertEqual(config.station()["color"], "#ff3b3b")
        for bad in ({"name": "  "}, {"color": "red"}, {"color": "#12"}):
            with self.assertRaises(ValueError):
                SA.update({"station": bad})
        SA.update({"reset_station": True})
        self.assertEqual(config.station(), config.DEFAULT_STATION)

    def test_other_keys_survive_and_backup_kept(self):
        self.f.parent.mkdir(parents=True)
        self.f.write_text(json.dumps({"media_dir": "X", "tmdb_key": "k" * 20, "weather": {"name": "Z"}}))
        SA.update({"auto_inbox": False})
        d = self.data()
        self.assertEqual((d["media_dir"], d["tmdb_key"], d["weather"]["name"], d["auto_inbox"]), ("X", "k" * 20, "Z", False))
        self.assertEqual(json.loads((self.f.parent / "settings.json.bak").read_text())["media_dir"], "X")

    def test_media_dir_and_key_rules(self):
        with self.assertRaises(ValueError):
            SA.update({"media_dir": os.path.join(self.d, "nope")})
        r = SA.update({"media_dir": self.d})
        self.assertTrue(r["restart"])
        with self.assertRaises(ValueError):
            SA.update({"tmdb_key": "short"})
        SA.update({"tmdb_key": "abcdef0123456789abcd"})
        self.assertTrue(SA.read(self.cfg)["art"]["has_key"])
        self.assertNotIn("abcdef0123456789abcd", json.dumps(SA.read(self.cfg)))        # the key itself is never sent to the page
        SA.update({"tmdb_key": ""})
        self.assertFalse(SA.read(self.cfg)["art"]["has_key"])

    def test_weather_lookup(self):
        fake = lambda q: [{"name": "Chicago, Illinois", "lat": 41.9, "lon": -87.6, "country_code": "US"}] if q == "Chicago" else []
        SA.update({"weather": "Chicago"}, geocode=fake)
        self.assertEqual(self.data()["weather"]["units"], "us")
        with self.assertRaises(ValueError):
            SA.update({"weather": "Nowhereville"}, geocode=fake)
        with self.assertRaises(ValueError):
            SA.update({"weather": "x"}, geocode=mock.Mock(side_effect=OSError("offline")))

    def test_rejects_junk(self):
        for bad in ({}, {"auto_inbox": "yes"}, {"unknown": 1}, "text"):
            with self.assertRaises(ValueError):
                SA.update(bad)
        self.assertFalse(self.f.exists())

    def test_endpoints(self):
        connect(self.cfg.db_path).close()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(self.cfg)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def post(path, body):
            req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"}, method="POST")
            try:
                return urllib.request.urlopen(req).status, json.load(urllib.request.urlopen(req)) if False else None
            except urllib.error.HTTPError as e:
                return e.code, None
        self.assertEqual(post("/api/settings", {"station": {"color": "bad"}})[0], 400)
        self.assertEqual(post("/api/settings", {"auto_inbox": True})[0], 200)
        j = json.load(urllib.request.urlopen(base + "/api/settings"))
        self.assertEqual(j["station"]["name"], "HERO TV"); self.assertIn("version", j["about"])
        self.assertEqual(post("/api/action", {"name": "format-c-drive"})[0], 400)        # only a fixed list of actions exists
        self.assertEqual(post("/api/action", {"name": "backup"})[0], 200)


if __name__ == "__main__":
    unittest.main()


class SubtitleStyleTests(unittest.TestCase):
    def test_style_saved_validated_and_in_theme(self):
        d = tempfile.mkdtemp()
        f = Path(d) / "settings.json"
        with mock.patch.object(config, "settings_file", return_value=f):
            self.assertEqual(SA.subs_style(), {"size": "normal", "bg": "box", "color": "white"})
            SA.update({"subs_style": {"size": "xl", "bg": "none", "color": "yellow"}})
            self.assertEqual(SA.subs_style()["size"], "xl")
            for bad in ({"size": "huge", "bg": "box", "color": "white"}, "big", {"size": "xl"}):
                with self.assertRaises(ValueError):
                    SA.update({"subs_style": bad})
            cfg = Config(media_dir=Path(d), db_path=os.path.join(d, "t.sqlite3"), channels_file=None)
            connect(cfg.db_path).close()
            srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
            j = json.load(urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/theme"))
            self.assertEqual(j["subs"], {"size": "xl", "bg": "none", "color": "yellow"})
