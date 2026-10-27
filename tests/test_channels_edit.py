import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import channels_api as CA, config, launcher, server as SV  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402


class ChannelEditTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        shutil.copytree(Path(config.ROOT) / "config", Path(self.d) / "config")
        self.media = Path(self.d) / "media"; self.media.mkdir()
        self.cfg = Config(media_dir=self.media, db_path=os.path.join(self.d, "t.sqlite3"),
                          channels_file=str(Path(self.d) / "config" / "channels.json"))

    def chans(self):
        return {c["id"]: c for c in json.loads(Path(self.cfg.channels_file).read_text())["channels"]}

    def rules(self):
        return json.loads((Path(self.d) / "config" / "auto-sort.json").read_text())

    def test_read_shows_folder_keywords_and_special(self):
        r = {c["id"]: c for c in CA.read(self.cfg)["channels"]}
        self.assertEqual(r["mcu"]["folder"], "MCU"); self.assertIn("iron man", r["mcu"]["keywords"])
        self.assertTrue(r["marvel-tv"]["special"]); self.assertFalse(r["mcu"]["special"])
        self.assertIsNone(r["action"]["folder"]); self.assertEqual(r["weather"]["kind"], "weather")

    def test_rename_recolour_and_keywords(self):
        CA.update(self.cfg, {"op": "save", "id": "mcu", "name": "Marvel Cinema", "color": "#00ff00", "mode": "shuffle",
                             "keywords": "iron man\nsecret wars, Iron Man"})
        c = self.chans()["mcu"]
        self.assertEqual((c["name"], c["color"], c["mode"]), ("Marvel Cinema", "#00ff00", "shuffle"))
        self.assertEqual(c["match"], {"franchise": ["MCU"]})
        own = [r for r in self.rules()["rules"] if r["channels"] == ["mcu"]]
        self.assertEqual(len(own), 1); self.assertEqual(own[0]["keywords"], ["iron man", "secret wars"])
        self.assertTrue((Path(self.cfg.channels_file).with_name("channels.json.bak")).exists())
        self.assertIn("_help", self.rules())

    def test_time_slots(self):
        r = CA.update(self.cfg, {"op": "add_block", "id": "mcu", "days": "sat", "from": "08:00", "to": "11:00",
                                 "mode": "mixed", "what": {"folder": "Marvel Animation"}})
        b = self.chans()["mcu"]["blocks"][0]
        self.assertEqual((b["days"], b["from"], b["to"], b["mode"], b["match"]),
                         ("sat", "08:00", "11:00", "mixed", {"franchise": ["Marvel Animation"]}))
        row = [c for c in r["channels"] if c["id"] == "mcu"][0]
        self.assertEqual(row["blocks"][0]["what"], "Marvel Animation")
        self.assertFalse(row["special"])                                      # its folder can still be edited
        CA.update(self.cfg, {"op": "add_block", "id": "mcu", "days": "daily", "from": "22:00", "to": "02:00",
                             "what": {"series": "Daredevil"}})
        self.assertEqual(len(self.chans()["mcu"]["blocks"]), 2)
        for bad in ({"from": "8am", "to": "11:00", "what": {"folder": "X"}}, {"from": "08:00", "to": "08:00", "what": {"folder": "X"}},
                    {"from": "08:00", "to": "09:00"}, {"days": "someday", "from": "08:00", "to": "09:00", "what": {"folder": "X"}}):
            with self.assertRaises(ValueError):
                CA.update(self.cfg, dict({"op": "add_block", "id": "mcu"}, **bad))
        CA.update(self.cfg, {"op": "remove_block", "id": "mcu", "name": b["name"]})
        self.assertEqual(len(self.chans()["mcu"]["blocks"]), 1)
        with self.assertRaises(ValueError):
            CA.update(self.cfg, {"op": "add_block", "id": "weather", "from": "08:00", "to": "09:00", "what": {"folder": "X"}})

    def test_start_times_setting(self):
        CA.update(self.cfg, {"op": "save", "id": "mcu", "starts": 30})
        self.assertEqual(self.chans()["mcu"]["starts"], 30)
        self.assertEqual([c for c in CA.read(self.cfg)["channels"] if c["id"] == "mcu"][0]["starts"], 30)
        CA.update(self.cfg, {"op": "save", "id": "mcu", "starts": 0})
        self.assertNotIn("starts", self.chans()["mcu"])
        with self.assertRaises(ValueError):
            CA.update(self.cfg, {"op": "save", "id": "mcu", "starts": 20})

    def test_renumber_moves_rules_and_checklist(self):
        CA.update(self.cfg, {"op": "save", "id": "south-park", "number": 20})
        self.assertEqual(self.chans()["south-park"]["number"], 20)
        self.assertIn(["south-park"], [r["channels"] for r in self.rules()["rules"]])
        with self.assertRaises(ValueError):
            CA.update(self.cfg, {"op": "save", "id": "south-park", "number": 1})
        CA.update(self.cfg, {"op": "save", "id": "mcu", "number": 30, "keywords": ["thor"]})
        kws = [k for r in self.rules()["rules"] if r["channels"] == ["mcu"] for k in r["keywords"]]
        self.assertEqual(kws, ["thor"])                       # rules follow the channel id, whatever its number
        self.assertFalse(any(isinstance(x, int) for r in self.rules()["rules"] for x in r["channels"]))
        labels = [l.get("channel") for l in json.loads((Path(self.d) / "config" / "checklist.json").read_text())["lists"]]
        self.assertIn("30 Marvel Movies", labels)

    def test_folder_change_keeps_special_rules_and_makes_folder(self):
        CA.update(self.cfg, {"op": "save", "id": "dc", "folder": "DC Universe"})
        self.assertEqual(self.chans()["dc"]["match"], {"franchise": ["DC Universe"]})
        self.assertTrue((self.media / "DC Universe").is_dir())
        with self.assertRaises(ValueError):
            CA.update(self.cfg, {"op": "save", "id": "action", "folder": "X"})          # tag channel: special rules
        with self.assertRaises(ValueError):
            CA.update(self.cfg, {"op": "save", "id": "dc", "folder": "..\\evil"})
        self.assertEqual(self.chans()["marvel-tv"]["also"][0]["tags"], ["spider-verse"])    # untouched

    def test_add_and_delete(self):
        r = CA.update(self.cfg, {"op": "add", "name": "Anime Night", "keywords": ["naruto", "bleach"], "color": "#ff2e88"})
        new = next(c for c in r["channels"] if c["name"] == "Anime Night")
        self.assertEqual(new["number"], 19); self.assertEqual(new["folder"], "Anime Night")   # 17 For You, 18 Cartoon Shorts
        self.assertTrue((self.media / "Anime Night").is_dir())
        self.assertEqual(self.chans()[new["id"]]["match"], {"franchise": ["Anime Night"]})
        with self.assertRaises(ValueError):
            CA.update(self.cfg, {"op": "add", "name": "Dupe", "number": 1})
        CA.update(self.cfg, {"op": "delete", "id": new["id"]})
        self.assertNotIn(new["id"], self.chans())
        self.assertFalse(any(new["id"] in r["channels"] for r in self.rules()["rules"]))

    def test_validation(self):
        for body in ({"op": "save", "id": "mcu", "name": " "}, {"op": "save", "id": "mcu", "color": "red"},
                     {"op": "save", "id": "mcu", "mode": "random"}, {"op": "save", "id": "nope"}, {"op": "boom"},
                     {"op": "save", "id": "mcu", "number": 5000}, {"op": "add", "name": ""}):
            with self.assertRaises(ValueError, msg=body):
                CA.update(self.cfg, body)

    def test_server_applies_and_undoes_bad_change(self):
        connect(self.cfg.db_path).close()
        app = SV.App(self.cfg)
        c = connect(self.cfg.db_path)
        from herotv import scheduler as S
        S.sync_channels(c, list(self.chans().values())); c.close()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(app))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def post(body):
            req = urllib.request.Request(base + "/api/channels-config", json.dumps(body).encode(), {"Content-Type": "application/json"}, method="POST")
            try:
                return urllib.request.urlopen(req).status
            except urllib.error.HTTPError as e:
                return e.code
        self.assertEqual(post({"op": "save", "id": "mcu", "name": "Marvel Cinema"}), 200)
        names = [c["name"] for c in json.load(urllib.request.urlopen(base + "/api/channels"))["channels"]]
        self.assertIn("Marvel Cinema", names); self.assertEqual(app.lib_version, 1)
        self.assertEqual(post({"op": "save", "id": "mcu", "number": 2}), 400)
        self.assertEqual(json.load(urllib.request.urlopen(base + "/api/channels-config"))["channels"][0]["number"], 1)


if __name__ == "__main__":
    unittest.main()


class MigrationTests(unittest.TestCase):
    def test_old_number_rules_are_converted_once(self):
        from herotv import sortrules
        d = tempfile.mkdtemp()
        shutil.copytree(Path(config.ROOT) / "config", Path(d) / "config")
        af = Path(d) / "config" / "auto-sort.json"
        af.write_text(json.dumps({"_help": "old", "rules": [{"keywords": ["iron man"], "channels": [1, 4, 99]},
                                                              {"keywords": ["batman"], "channels": ["6"]}],
                                  "year_rules": [{"year_max": 1979, "channels": [7]}]}))
        cfg = Config(media_dir=Path(d), db_path=os.path.join(d, "t.sqlite3"), channels_file=str(Path(d) / "config" / "channels.json"))
        rules, chans = sortrules.load(cfg)
        self.assertEqual(rules["rules"][0]["channels"], ["mcu", "spider-verse"])           # 99 does not exist: dropped
        self.assertEqual(rules["rules"][1]["channels"], ["dc"])
        self.assertEqual(rules["year_rules"][0]["channels"], ["classics"])
        self.assertEqual(json.loads(af.read_text())["rules"][0]["channels"], ["mcu", "spider-verse"])   # saved
        self.assertEqual(json.loads((af.with_name("auto-sort.json.bak")).read_text())["rules"][0]["channels"], [1, 4, 99])
        names = [c["name"] for c in sortrules.targets("Iron Man (2008)", rules, chans)]
        self.assertEqual(names, ["Marvel Movies", "Spider-Verse"])
        self.assertFalse(sortrules.migrate(rules, chans))                                  # nothing left to convert
