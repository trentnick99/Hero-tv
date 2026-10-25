"""'Pick your channels': switching channels off and on (nothing deleted)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import channels_api, config, scheduler as S, sortrules  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402


class LineupTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        shutil.copytree(Path(config.ROOT) / "config", Path(self.d) / "config")
        os.makedirs(os.path.join(self.d, "media"))
        self.cfg = Config(media_dir=Path(self.d) / "media", db_path=os.path.join(self.d, "t.sqlite3"),
                          channels_file=str(Path(self.d) / "config" / "channels.json"))
        p = mock.patch.object(config, "settings_file", return_value=Path(self.d) / "settings.json")
        p.start(); self.addCleanup(p.stop)

    def chans(self):
        return json.loads(Path(self.cfg.channels_file).read_text(encoding="utf-8"))["channels"]

    def test_groups_cover_every_channel_once(self):
        groups = channels_api.lineup(self.cfg)
        ids = [c["id"] for g in groups for c in g["channels"]]
        self.assertEqual(sorted(ids), sorted(c["id"] for c in self.chans()))
        self.assertEqual(groups[0]["name"], "Superheroes")
        self.assertTrue(all(c["on"] for g in groups for c in g["channels"]))
        channels_api.update(self.cfg, {"op": "add", "name": "PBS Kids"})
        self.assertEqual(channels_api.lineup(self.cfg)[-1], {"name": "Your own channels", "channels": [
            {"id": "pbs-kids", "number": mock.ANY, "name": "PBS Kids", "description": "", "on": True}]})

    def test_lineup_switches_off_without_deleting(self):
        n = len(self.chans())
        r = channels_api.update(self.cfg, {"op": "lineup", "off": ["south-park", "dragon-ball"]})
        self.assertIn("2 channel(s) switched off", r["note"])
        self.assertEqual(len(self.chans()), n)
        self.assertEqual(sorted(c["id"] for c in self.chans() if c.get("off")), ["dragon-ball", "south-park"])
        self.assertTrue(next(c for c in r["channels"] if c["id"] == "south-park")["off"])
        channels_api.update(self.cfg, {"op": "switch", "id": "south-park", "off": False})
        self.assertEqual([c["id"] for c in self.chans() if c.get("off")], ["dragon-ball"])
        channels_api.update(self.cfg, {"op": "lineup", "off": []})
        self.assertFalse(any("off" in c for c in self.chans()))

    def test_refuses_switching_everything_off(self):
        with self.assertRaises(ValueError):
            channels_api.update(self.cfg, {"op": "lineup", "off": [c["id"] for c in self.chans()]})
        with self.assertRaises(ValueError):
            channels_api.update(self.cfg, {"op": "switch", "id": "nope", "off": True})
        with self.assertRaises(ValueError):
            channels_api.update(self.cfg, {"op": "lineup", "off": "south-park"})

    def test_off_channels_leave_the_tv_and_get_nothing_new(self):
        channels_api.update(self.cfg, {"op": "lineup", "off": ["south-park"]})
        c = connect(self.cfg.db_path)
        self.addCleanup(c.close)
        S.sync_channels(c, self.chans(), tz="UTC")
        ids = [r["id"] for r in S.channels(c)]
        self.assertNotIn("south-park", ids)
        self.assertIn("invincible", ids)
        rules, chans = sortrules.load(self.cfg)
        self.assertEqual(sortrules.targets("South Park S01E01", rules, chans), [])
        channels_api.update(self.cfg, {"op": "switch", "id": "south-park", "off": False})
        S.sync_channels(c, self.chans(), tz="UTC")
        self.assertIn("south-park", [r["id"] for r in S.channels(c)])
        rules, chans = sortrules.load(self.cfg)
        self.assertEqual([x["id"] for x in sortrules.targets("South Park S01E01", rules, chans)], ["south-park"])


if __name__ == "__main__":
    unittest.main()
