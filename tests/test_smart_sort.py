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
from herotv import art, config, inbox, sortrules  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402

F = {  # what TMDB would say (made up but realistic)
    "Iron Man (2008)": {"type": "movie", "companies": ["Marvel Studios"], "genres": ["Action", "Science Fiction"], "keywords": ["superhero"], "year": 2008},
    "Iron Man (1931)": {"type": "movie", "companies": ["Iron Works Pictures"], "genres": ["Drama"], "keywords": ["boxing"], "year": 1931},
    "Logan Lucky (2017)": {"type": "movie", "companies": ["Fingerprint Releasing"], "genres": ["Comedy", "Crime"], "keywords": ["heist"], "year": 2017},
    "Logan (2017)": {"type": "movie", "companies": ["20th Century Fox", "Marvel Entertainment"], "genres": ["Action", "Drama"],
                     "keywords": ["superhero", "wolverine"], "collection": "The Wolverine Collection", "year": 2017},
    "Spider-Man The Animated Series S01E01": {"type": "tv", "companies": ["Marvel Entertainment"], "genres": ["Animation"], "keywords": ["spider-man"]},
    "X-Men 97 S01E01": {"type": "tv", "companies": ["Marvel Studios Animation"], "genres": ["Animation"], "keywords": ["mutant"]},
    "Daredevil S01E01": {"type": "tv", "companies": ["Marvel Television"], "genres": ["Crime", "Drama"], "keywords": ["blind"]},
    "The Dark Knight (2008)": {"type": "movie", "companies": ["DC Comics", "Warner Bros. Pictures"], "genres": ["Drama", "Action", "Crime", "Thriller"],
                               "keywords": ["superhero"], "year": 2008},
    "Se7en (1995)": {"type": "movie", "companies": ["New Line Cinema"], "genres": ["Crime", "Mystery", "Thriller"], "keywords": [], "year": 1995},
    "Halloween (1978)": {"type": "movie", "companies": ["Compass International"], "genres": ["Horror", "Thriller"], "keywords": [], "year": 1978},
    "Superman (1978)": {"type": "movie", "companies": ["DC Comics"], "genres": ["Action", "Adventure"], "keywords": ["superhero"], "year": 1978},
    "Deadpool (2016)": {"type": "movie", "companies": ["20th Century Fox", "Marvel Entertainment"], "genres": ["Action", "Comedy"],
                        "keywords": ["superhero"], "collection": "Deadpool Collection", "year": 2016},
}


class SmartSortTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        shutil.copytree(Path(config.ROOT) / "config", Path(self.d) / "config")
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"), channels_file=str(Path(self.d) / "config" / "channels.json"))
        p = mock.patch.object(config, "settings_file", return_value=Path(self.d) / "settings.json")
        p.start(); self.addCleanup(p.stop)
        self.rules, self.chans = sortrules.load(self.cfg)
        self.smart = sortrules.smart_rules(self.cfg)

    def where(self, stem, facts=True):
        return sorted(c["id"] for c in sortrules.targets(stem, self.rules, self.chans, F.get(stem) if facts else None, self.smart))

    def test_studio_and_genre_decide(self):
        self.assertEqual(self.where("Iron Man (2008)"), ["mcu"])
        self.assertEqual(self.where("Iron Man (1931)"), [])                     # same name, not Marvel: stays in the Inbox
        self.assertEqual(self.where("Logan Lucky (2017)"), [])                  # the word "logan" alone no longer counts
        self.assertEqual(self.where("Logan (2017)"), ["x-men"])
        self.assertEqual(self.where("Spider-Man The Animated Series S01E01"), ["marvel-tv"])
        self.assertEqual(self.where("X-Men 97 S01E01"), ["marvel-animation"])
        self.assertEqual(self.where("Daredevil S01E01"), ["marvel-tv"])
        self.assertEqual(self.where("The Dark Knight (2008)"), ["dc"])           # an action thriller is not horror
        self.assertEqual(self.where("Se7en (1995)"), ["horror"])
        self.assertEqual(self.where("Halloween (1978)"), ["horror"])             # an old film is not a superhero classic
        self.assertEqual(self.where("Superman (1978)"), ["classics", "dc"])
        self.assertEqual(self.where("Deadpool (2016)"), ["comedy", "x-men"])

    def test_without_facts_keywords_still_work(self):
        self.assertIn("mcu", self.where("Iron Man (2008)", facts=False))
        self.assertIn("south-park", [c["id"] for c in sortrules.targets("South Park S01E01", self.rules, self.chans, None, self.smart)])
        self.assertIn("south-park", [c["id"] for c in sortrules.targets("South Park S01E01", self.rules, self.chans,
                                                                        {"type": "tv", "companies": ["Comedy Central"], "genres": ["Comedy"]}, self.smart)])

    def test_can_be_switched_off(self):
        (Path(self.d) / "settings.json").write_text('{"smart_sort": false}')
        self.assertEqual(sortrules.smart_rules(self.cfg), [])

    def test_facts_are_looked_up_once_and_remembered(self):
        calls = []

        def fj(path, params, key, timeout=20):
            calls.append(path)
            if path.startswith("/search/"):
                return {"results": [{"id": 5, "title": "Iron Man", "release_date": "2008-05-02"}]}
            return {"title": "Iron Man", "release_date": "2008-05-02", "genres": [{"name": "Action"}],
                    "production_companies": [{"name": "Marvel Studios"}], "keywords": {"keywords": [{"name": "superhero"}]}}
        c = connect(self.cfg.db_path)
        f = art.facts_for(c, self.cfg, "Iron.Man.2008.1080p.BluRay", key="k" * 20, fj=fj, fb=lambda u, timeout=30: b"")
        self.assertEqual((f["type"], f["companies"], f["keywords"]), ("movie", ["Marvel Studios"], ["superhero"]))
        n = len(calls)
        self.assertEqual(art.facts_for(c, self.cfg, "Iron Man (2008)", key="k" * 20, fj=fj), f)
        self.assertEqual(len(calls), n)                                          # remembered
        self.assertIsNone(art.facts_for(c, self.cfg, "Unknown (2001)", key=None))   # no key: keywords only
        boom = mock.Mock(side_effect=OSError("offline"))
        self.assertIsNone(art.facts_for(c, self.cfg, "Thor (2011)", key="k" * 20, fj=boom))

    def test_inbox_uses_facts(self):
        ib = Path(self.d) / "Inbox"; ib.mkdir()
        for n in ("Iron Man (1931).mp4", "Iron Man (2008).mp4"):
            (ib / n).write_bytes(b"x" * 10); old = time.time() - 600; os.utime(ib / n, (old, old))
        got = []
        place = lambda src, picked, media, force_move=False: got.append((os.path.basename(src), [c["id"] for c in picked])) or True
        seen = {}
        inbox.run_once(self.cfg, seen, place=place, facts=F.get)
        r = inbox.run_once(self.cfg, seen, place=place, facts=F.get)
        self.assertEqual(got, [("Iron Man (2008).mp4", ["mcu"])])
        self.assertEqual(r["left"], 1)


if __name__ == "__main__":
    unittest.main()
