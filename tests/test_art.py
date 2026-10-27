import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import art, config, server as SV  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402

JPG = b"\xff\xd8\xff\xe0fakejpeg"


def canned(calls=None):
    def fj(path, params, key, timeout=20):
        if calls is not None:
            calls.append((path, dict(params)))
        if path == "/search/movie":
            return {"results": [{"id": 1, "title": "Iron Man", "release_date": "2008-05-02", "poster_path": "/p.jpg"},
                                {"id": 2, "title": "Iron Man 2", "release_date": "2010-05-07"}]}
        if path == "/search/tv":
            return {"results": [{"id": 9, "name": "Invincible", "first_air_date": "2021-03-26"}]}
        if path == "/movie/1":
            return {"title": "Iron Man", "release_date": "2008-05-02", "overview": "A billionaire builds a suit.",
                    "tagline": "Heroes aren't born.", "genres": [{"name": "Action"}], "vote_average": 7.64, "runtime": 126,
                    "poster_path": "/p.jpg", "credits": {"cast": [{"name": "Robert Downey Jr."}, {"name": "Gwyneth Paltrow"}]}}
        if path == "/tv/9":
            return {"name": "Invincible", "first_air_date": "2021-03-26", "overview": "A teen hero.", "genres": [],
                    "vote_average": 8.7, "episode_run_time": [45], "poster_path": "/t.jpg", "credits": {"cast": []}}
        return {"results": []}
    return fj


def fb(url, timeout=30):
    return JPG


def media(c, path, title, year=None, series=None, runtime=100):
    c.execute("INSERT INTO media(path,title,year,series,verified,playable,available,runtime_s) VALUES(?,?,?,?,1,1,1,?)",
              (path, title, year, series, runtime))
    c.commit()
    return c.execute("SELECT * FROM media WHERE path=?", (path,)).fetchone()


class ArtTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"), channels_file=None)
        self.c = connect(self.cfg.db_path)

    def test_lookup_movie_and_year_tolerance(self):
        calls = []
        r = art.lookup("movie", "Iron Man", 2008, "k" * 32, canned(calls))
        self.assertEqual(r["tmdb_id"], 1)
        self.assertEqual(r["cast"][0], "Robert Downey Jr.")
        self.assertEqual(r["rating"], 7.6)
        self.assertIsNone(art.lookup("movie", "Iron Man", 1990, "k" * 32, canned()))   # wrong year -> no match
        self.assertEqual(art.lookup("movie", "The Iron Man", 2009, "k" * 32, canned())["tmdb_id"], 1)

    def test_small_title_differences_still_match(self):
        r = [{"id": 1, "title": "Spider-Man 2", "release_date": "2004-06-30"},
             {"id": 2, "title": "Spider-Man 3", "release_date": "2007-05-01"}]
        self.assertEqual(art._pick(r, "Spiderman 3", None, "movie")["id"], 2)
        self.assertIsNone(art._pick(r, "Spider-Man 4", None, "movie"))            # sequel numbers must agree
        w = [{"id": 5, "title": "X-Men Origins: Wolverine", "release_date": "2009-04-28"}]
        self.assertEqual(art._pick(w, "Xmen Origins Wolverine", 2009, "movie")["id"], 5)
        self.assertIsNone(art._pick([{"id": 7, "title": "Batman Begins", "release_date": "2005"}], "Batman Returns", None, "movie"))

    def test_only_title_and_year_are_sent(self):
        calls = []
        art.lookup("movie", "Iron Man", 2008, "k" * 32, canned(calls))
        for _, params in calls:
            self.assertLessEqual(set(params), {"query", "year", "include_adult", "language", "append_to_response"})

    def test_key_header_vs_param(self):
        seen = {}

        class R:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def read(s): return b"{}"

        def fake(req, timeout=0):
            seen["url"], seen["h"] = req.full_url, dict(req.header_items())
            return R()
        with mock.patch.object(art.net, "urlopen", fake):
            art.fetch_json("/x", {}, "short")
            self.assertIn("api_key=short", seen["url"])
            art.fetch_json("/x", {}, "L" * 60)
            self.assertNotIn("api_key", seen["url"])
            self.assertEqual(seen["h"].get("Authorization"), "Bearer " + "L" * 60)

    def test_pass_saves_art_and_misses_and_retries(self):
        media(self.c, "/a/Iron Man (2008).mp4", "Iron Man", 2008)
        media(self.c, "/a/Invincible S01E01.mp4", "Ep1", None, "Invincible", 45)
        media(self.c, "/a/Nothing Known.mp4", "Nothing Known", 2001)
        self.assertEqual(len(art.pending(self.c)), 3)
        done, hit = art.run_pass(self.c, self.cfg, "k", canned(), fb, delay=0)
        self.assertEqual((done, hit), (3, 2))
        self.assertEqual(art.pending(self.c), [])
        self.assertTrue(os.path.isfile(art.poster_file(self.cfg, "m:iron man:2008")))
        self.assertEqual(art.stats(self.c)["not_found"], 1)
        self.c.execute("UPDATE art SET fetched=? WHERE miss=1", (int(time.time()) - 8 * 86400,))
        self.c.commit()
        self.assertEqual(len(art.pending(self.c)), 1)       # the miss is tried again after a week

    def test_network_failure_records_nothing(self):
        media(self.c, "/a/Iron Man (2008).mp4", "Iron Man", 2008)

        def boom(*a, **k):
            raise OSError("offline")
        self.assertEqual(art.run_pass(self.c, self.cfg, "k", boom, fb, delay=0), (0, 0))
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM art").fetchone()[0], 0)

    def test_local_picture_wins_and_series_poster(self):
        m = media(self.c, os.path.join(self.d, "Film (2001).mp4"), "Film", 2001)
        self.assertIsNone(art.local_picture(m))
        open(os.path.join(self.d, "Film (2001).jpg"), "wb").write(JPG)
        self.assertTrue(art.local_picture(m).endswith("Film (2001).jpg"))
        open(os.path.join(self.d, "poster.jpg"), "wb").write(JPG)
        movie_other = media(self.c, os.path.join(self.d, "Other (2002).mp4"), "Other", 2002)
        self.assertIsNone(art.local_picture(movie_other))     # poster.jpg is only for shows
        ep = media(self.c, os.path.join(self.d, "Show S01E01.mp4"), "E1", None, "Show")
        self.assertTrue(art.local_picture(ep).endswith("poster.jpg"))

    def test_info_without_and_with_data(self):
        m = media(self.c, "/a/Iron Man (2008).mp4", "Iron Man", 2008, runtime=7560)
        with mock.patch.object(art, "api_key", return_value=""):
            i = art.info(self.c, self.cfg, m)
        self.assertFalse(i["has_key"]); self.assertFalse(i["poster"]); self.assertEqual(i["runtime_min"], 126)
        art.run_pass(self.c, self.cfg, "k", canned(), fb, delay=0)
        i = art.info(self.c, self.cfg, m)
        self.assertEqual(i["source"], "TMDB"); self.assertTrue(i["poster"]); self.assertIn("suit", i["overview"] if "overview" in i else i["plot"])

    def test_endpoints(self):
        m = media(self.c, "/a/Iron Man (2008).mp4", "Iron Man", 2008)
        art.run_pass(self.c, self.cfg, "k", canned(), fb, delay=0)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(self.cfg)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        j = json.load(urllib.request.urlopen(f"{base}/api/info/{m['id']}"))
        self.assertEqual(j["cast"][0], "Robert Downey Jr.")
        r = urllib.request.urlopen(f"{base}/poster/{m['id']}")
        self.assertEqual(r.read(), JPG)
        self.assertEqual(r.headers["Content-Type"], "image/jpeg")
        for bad in ("/poster/999", "/poster/abc", "/api/info/999"):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(base + bad)
            self.assertEqual(cm.exception.code, 404, bad)

    def test_set_poster_key_saves(self):
        from herotv import launcher
        f = Path(self.d) / "settings.json"
        f.write_text(json.dumps({"media_dir": "X"}))
        with mock.patch.object(config, "settings_file", return_value=f), \
                mock.patch.object(art, "fetch_json", side_effect=OSError("offline")):
            self.assertEqual(launcher.set_poster_key("abc123"), 0)
        d = json.loads(f.read_text())
        self.assertEqual(d["tmdb_key"], "abc123"); self.assertEqual(d["media_dir"], "X")


if __name__ == "__main__":
    unittest.main()


class AppBuildTests(unittest.TestCase):
    def test_root_when_frozen(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", os.path.join(tempfile.gettempdir(), "HeroApp", "HERO-TV.exe")):
            self.assertEqual(config._root(), Path(tempfile.gettempdir()).resolve() / "HeroApp")
        self.assertTrue((config._root() / "web" / "index.html").is_file())

    def test_entry_point_defaults_to_launch(self):
        with mock.patch("herotv.__main__.main", return_value=0) as m:
            import importlib, runpy
            ns = runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_entry.py"))
            with mock.patch.object(sys, "argv", ["HERO-TV.exe"]):
                with self.assertRaises(SystemExit):
                    runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_entry.py"), run_name="__main__")
        m.assert_called_with(["launch"])

    def test_build_script_and_launcher_present(self):
        root = Path(config.ROOT)
        b = (root / "Build-App.bat").read_bytes()
        self.assertIn(b"PyInstaller", b); self.assertIn(b"\r\n", b)
        self.assertIn(b"HERO-TV.exe", (root / "HERO-TV.bat").read_bytes())


def _zip(path, files):
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)


class UpdateInboxTests(unittest.TestCase):
    def test_update_keeps_mine_and_backs_up(self):
        from herotv import updater
        d = tempfile.mkdtemp()
        root = Path(d, "app"); (root / "herotv").mkdir(parents=True); (root / "config").mkdir(); (root / "data").mkdir()
        (root / "herotv" / "__init__.py").write_text("old"); (root / "herotv" / "x.py").write_text("same")
        (root / "config" / "channels.json").write_text("MINE"); (root / "config" / "auto-sort.json").write_text("std")
        (root / "data" / "herotv.sqlite3").write_text("DB")
        z = os.path.join(d, "my hero-tv-windows (2).zip")
        _zip(z, {"hero-tv/herotv/__init__.py": "new", "hero-tv/herotv/x.py": "same", "hero-tv/herotv/new.py": "n",
                 "hero-tv/config/channels.json": "THEIRS", "hero-tv/config/auto-sort.json": "std",
                 "hero-tv/data/herotv.sqlite3": "EVIL", "hero-tv/../evil.txt": "x", "hero-tv/HERO-TV.exe": "no"})
        self.assertEqual(updater.find_zip(None, d).name, "my hero-tv-windows (2).zip")
        r = updater.apply(z, root)
        self.assertEqual((root / "herotv" / "__init__.py").read_text(), "new")
        self.assertTrue((root / "herotv" / "new.py").exists())
        self.assertEqual((root / "config" / "channels.json").read_text(), "MINE")
        self.assertEqual((root / "config" / "channels.json.new").read_text(), "THEIRS")
        self.assertEqual((root / "data" / "herotv.sqlite3").read_text(), "DB")
        self.assertFalse((Path(d) / "evil.txt").exists()); self.assertFalse((root / "HERO-TV.exe").exists())
        self.assertEqual(r["kept"], ["channels.json"])
        self.assertEqual(Path(r["backup"], "herotv", "__init__.py").read_text(), "old")
        self.assertEqual(updater.apply(z, root)["replaced"], 0)      # second run: nothing left to do... except kept config
        with self.assertRaises(ValueError):
            _zip(z + "2", {"a.txt": "x"}); updater.plan(z + "2", root)

    def test_inbox_waits_for_stable_files_and_files_by_title(self):
        from herotv import inbox
        d = tempfile.mkdtemp()
        cfg = Config(media_dir=Path(d), db_path=os.path.join(d, "t.sqlite3"),
                     channels_file=str(Path(config.ROOT) / "config" / "channels.json"))
        ib = Path(d, "Inbox"); ib.mkdir()
        for n in ("Iron Man (2008).mp4", "Random Home Video.mp4", "Big.mp4.part", "notes.txt"):
            (ib / n).write_bytes(b"x" * 10)
        old = time.time() - 600
        for f in ib.iterdir():
            os.utime(f, (old, old))
        got = []
        place = lambda src, picked, media, force_move=False: got.append((os.path.basename(src), [c["name"] for c in picked])) or True
        seen = {}
        self.assertEqual(inbox.run_once(cfg, seen, place=place)["filed"], [])      # first sight: wait one pass
        r = inbox.run_once(cfg, seen, place=place)
        self.assertEqual([g[0] for g in got], ["Iron Man (2008).mp4"])
        self.assertIn("Marvel Movies", got[0][1])
        self.assertEqual(r["left"], 1)
        self.assertEqual(inbox.waiting(cfg), 2)


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"), channels_file=None)
        connect(self.cfg.db_path).close()
        self.app = SV.App(self.cfg)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(self.app))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        self.base = f"http://127.0.0.1:{srv.server_address[1]}"

    def post(self, name, data=b"video!", token=True, headers=None, ctype="application/octet-stream"):
        h = {"Content-Type": ctype, "X-HeroTV-Upload": "1"}
        h.update(headers or {})
        tok = self.app.upload_token if token is True else (token or "")
        req = urllib.request.Request(f"{self.base}/api/upload?name={urllib.parse.quote(name)}&token={tok}", data=data, headers=h, method="POST")
        try:
            r = urllib.request.urlopen(req)
            return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def test_clean_names(self):
        from herotv import inbox
        self.assertEqual(inbox.clean_name("..\\..\\evil/Iron Man (2008).MP4"), "Iron Man (2008).mp4")
        self.assertIsNone(inbox.clean_name("virus.exe")); self.assertIsNone(inbox.clean_name("a.bat"))
        self.assertEqual(inbox.clean_name("CON.mp4"), "CON_.mp4")
        self.assertEqual(inbox.clean_name("sub.srt"), "sub.srt")

    def test_upload_lands_in_inbox(self):
        code, j = self.post("Iron Man (2008).mp4")
        self.assertEqual((code, j["name"]), (200, "Iron Man (2008).mp4"))
        self.assertEqual(Path(self.d, "Inbox", "Iron Man (2008).mp4").read_bytes(), b"video!")
        code, j = self.post("Iron Man (2008).mp4")
        self.assertEqual(j["name"], "Iron Man (2008) 2.mp4")                   # never overwrites
        self.assertEqual([f for f in os.listdir(Path(self.d, "Inbox")) if f.endswith(".part")], [])

    def test_upload_refused(self):
        self.assertEqual(self.post("a.mp4", token=False)[0], 403)
        self.assertEqual(self.post("a.mp4", token="wrong")[0], 403)
        self.assertEqual(self.post("a.mp4", headers={"X-HeroTV-Upload": "0"})[0], 403)
        self.assertEqual(self.post("a.mp4", headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.post("a.mp4", ctype="text/plain")[0], 403)
        self.assertEqual(self.post("virus.exe")[0], 400)
        self.assertEqual(self.post("a.mp4", data=b"")[0], 400)
        self.assertFalse(os.path.exists(Path(self.d, "Inbox")) and os.listdir(Path(self.d, "Inbox")))
        j = json.load(urllib.request.urlopen(self.base + "/api/upload-token"))
        self.assertEqual(j["token"], self.app.upload_token)


class StaleAppTests(unittest.TestCase):
    def test_stamp(self):
        from herotv import updater
        r = Path(tempfile.mkdtemp()); (r / "herotv").mkdir(); (r / "herotv" / "__init__.py").write_text("a")
        self.assertTrue(updater.app_is_stale(r))            # never stamped
        updater.write_stamp(r)
        self.assertFalse(updater.app_is_stale(r))
        (r / "herotv" / "__init__.py").write_text("b")      # files updated, exe not rebuilt
        self.assertTrue(updater.app_is_stale(r))
        updater.write_stamp(r)
        self.assertFalse(updater.app_is_stale(r))


class ReleaseUpdateTests(unittest.TestCase):
    def make_root(self, d, exe=b"OLD-EXE", dll=b"old-dll"):
        root = Path(d, "app"); (root / "herotv").mkdir(parents=True); (root / "_internal").mkdir()
        (root / "herotv" / "__init__.py").write_text('__version__ = "1.0.0"\n')
        (root / "HERO-TV.exe").write_bytes(exe); (root / "_internal" / "python.dll").write_bytes(dll)
        (root / "_internal" / "same.pyd").write_bytes(b"same")
        (root / "Update-HERO-TV.bat").write_text("old bat")
        return root

    def release_zip(self, d, version="1.1.0", exe=b"NEW-EXE"):
        z = os.path.join(d, f"HERO-TV-v{version}-windows.zip")
        _zip(z, {"HERO TV/herotv/__init__.py": f'__version__ = "{version}"\n', "HERO TV/HERO-TV.exe": exe,
                 "HERO TV/_internal/python.dll": "new-dll", "HERO TV/_internal/same.pyd": "same",
                 "HERO TV/app-build.txt": "stamp", "HERO TV/Update-HERO-TV.bat": "new bat"})
        return z

    def test_release_zip_is_found_and_read(self):
        from herotv import updater
        d = tempfile.mkdtemp()
        z = self.release_zip(d)
        self.assertEqual(updater.find_zip(None, d).name, "HERO-TV-v1.1.0-windows.zip")
        self.assertEqual(updater.zip_info(z), {"version": "1.1.0", "app": True})
        self.assertLess(updater.version_tuple("1.0.9"), updater.version_tuple("1.1.0"))

    def test_app_files_are_staged_whole_then_swapped(self):
        from herotv import updater
        d = tempfile.mkdtemp()
        root = self.make_root(d)
        res = updater.apply(self.release_zip(d), root)
        self.assertEqual((root / "HERO-TV.exe").read_bytes(), b"OLD-EXE")              # running exe untouched
        self.assertTrue((root / ".update-stage" / "_internal" / "same.pyd").exists())   # full set staged, even unchanged files
        self.assertEqual(res["staged"], 4)
        self.assertEqual((root / "Update-HERO-TV.bat").read_text(), "old bat")          # the running bat is not overwritten
        self.assertEqual((root / "Update-HERO-TV.bat.new").read_text(), "new bat")
        self.assertEqual(updater.finish_swap(root), 4)
        self.assertEqual((root / "HERO-TV.exe").read_bytes(), b"NEW-EXE")
        self.assertEqual((root / "_internal" / "python.dll").read_bytes(), b"new-dll")
        self.assertEqual((root / "app-build.txt").read_text(), "stamp")
        self.assertTrue(list((root / ".update-backup").glob("*-app/HERO-TV.exe")))
        updater.clean_stage(root); updater.apply_deferred(root)
        self.assertFalse((root / ".update-stage").exists())
        self.assertEqual((root / "Update-HERO-TV.bat").read_text(), "new bat")

    def test_source_zip_never_touches_the_exe(self):
        from herotv import updater
        d = tempfile.mkdtemp()
        root = self.make_root(d)
        z = os.path.join(d, "hero-tv-windows.zip")
        _zip(z, {"hero-tv/herotv/__init__.py": '__version__ = "1.1.0"\n', "hero-tv/_internal/python.dll": "evil"})
        self.assertEqual(updater.apply(z, root)["staged"], 0)
        self.assertEqual((root / "_internal" / "python.dll").read_bytes(), b"old-dll")

    def test_whatsnew_endpoint_shows_once(self):
        from herotv import whatsnew
        self.assertEqual(whatsnew.since(whatsnew.current()), [])
        self.assertEqual([v for v, _ in whatsnew.since("1.0.0")], [v for v in whatsnew.NOTES if v != "1.0.0"])
        self.assertTrue(whatsnew.since("0.1.0"))
        d = tempfile.mkdtemp()
        cfg = Config(media_dir=Path(d), db_path=os.path.join(d, "t.sqlite3"), channels_file=None)
        connect(cfg.db_path).close()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        self.assertTrue(json.load(urllib.request.urlopen(base + "/api/whatsnew"))["notes"])
        urllib.request.urlopen(urllib.request.Request(base + "/api/whatsnew", b"{}", {"Content-Type": "application/json"}, method="POST"))
        self.assertEqual(json.load(urllib.request.urlopen(base + "/api/whatsnew"))["notes"], [])
