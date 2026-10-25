import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import make_db  # noqa: E402
from herotv import backup, config, library, server as SV, subtitles as SUB, tools  # noqa: E402
from herotv.config import Config  # noqa: E402

FF = tools.find_tool("ffmpeg")
SRT = "1\n00:00:00,500 --> 00:00:01,500\nHello there\n\n2\n00:00:01,600 --> 00:00:02,000\nGeneral Kenobi\n"


class ConvertTests(unittest.TestCase):
    def test_srt_to_vtt(self):
        v = SUB.srt_to_vtt("\ufeff" + SRT.replace("\n", "\r\n"))
        self.assertTrue(v.startswith("WEBVTT\n\n"))
        self.assertIn("00:00:00.500 --> 00:00:01.500", v)
        self.assertNotIn(",500", v)
        self.assertEqual(SUB.srt_to_vtt("WEBVTT\n\n00:00.000 --> 00:01.000\nx\n"), "WEBVTT\n\n00:00.000 --> 00:01.000\nx\n")

    def test_decoding_old_encodings(self):
        self.assertEqual(SUB.decode("café".encode("cp1252")), "café")
        self.assertEqual(SUB.decode("café".encode("utf-8")), "café")

    def test_external_files_match_only_this_video(self):
        d = tempfile.mkdtemp()
        for n in ("Iron Man (2008).mp4", "Iron Man (2008).srt", "Iron Man (2008).en.srt", "Iron Man (2008).spanish.vtt",
                  "Iron Man (2008).en.forced.srt", "Iron Man 2 (2010).srt", "Iron Man (2008).txt"):
            open(os.path.join(d, n), "w", encoding="utf-8").write(SRT)
        f = SUB.external_files(os.path.join(d, "Iron Man (2008).mp4"))
        self.assertEqual(sorted(os.path.basename(x["file"]) for x in f),
                         ["Iron Man (2008).en.forced.srt", "Iron Man (2008).en.srt", "Iron Man (2008).spanish.vtt", "Iron Man (2008).srt"])
        langs = {os.path.basename(x["file"]): x["language"] for x in f}
        self.assertEqual(langs["Iron Man (2008).en.srt"], "English")
        self.assertEqual(langs["Iron Man (2008).spanish.vtt"], "Spanish")
        self.assertEqual(langs["Iron Man (2008).srt"], "")

    def test_vtt_bad_keys(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "a.mp4")
        for key in ("../../x", "x9", "e", "", "x-1"):
            self.assertIsNone(SUB.vtt(p, key, d))


@unittest.skipUnless(FF and tools.find_tool("ffprobe"), "ffmpeg not installed")
class EmbeddedTests(unittest.TestCase):
    def make(self):
        d = tempfile.mkdtemp()
        srt = os.path.join(d, "s.srt")
        open(srt, "w").write(SRT)
        out = os.path.join(d, "Movie.mkv")
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10:duration=3", "-f", "lavfi", "-i", "sine=duration=3",
                        "-i", srt, "-map", "0:v", "-map", "1:a", "-map", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-c:s", "srt",
                        "-metadata:s:s:0", "language=eng", out], check=True, **tools.HIDE)
        return d, out

    def test_embedded_track_is_listed_and_extracted(self):
        d, out = self.make()
        info = SUB.tracks(out)
        self.assertEqual([t["label"] for t in info["tracks"]], ["English"])
        data = SUB.vtt(out, info["tracks"][0]["key"], os.path.join(d, "cache"), 1)
        self.assertIn(b"WEBVTT", data)
        self.assertIn(b"General Kenobi", data)
        self.assertTrue(os.listdir(os.path.join(d, "cache")))
        self.assertEqual(SUB.vtt(out, "e5", os.path.join(d, "cache")), None)

    def test_save_embedded_writes_srt_next_to_video(self):
        d, out = self.make()
        self.assertEqual(SUB.save_embedded(out, d, "Movie"), 1)
        self.assertTrue(os.path.exists(os.path.join(d, "Movie.english.srt")))
        self.assertEqual(SUB.save_embedded(out, d, "Movie"), 1)               # second time does not overwrite
        self.assertTrue(os.path.exists(os.path.join(d, "Movie.english2.srt")))


class ServerSubsTests(unittest.TestCase):
    def test_endpoints(self):
        d = tempfile.mkdtemp()
        cfg = Config(); cfg.db_path = os.path.join(d, "t.sqlite3"); cfg.tz = "UTC"; cfg.media_dir = d
        c = make_db(cfg.db_path)
        vid = os.path.join(d, "Film (2001).mp4")
        open(vid, "wb").write(b"x")
        open(os.path.join(d, "Film (2001).en.srt"), "w").write(SRT)
        c.execute("INSERT INTO media(path,title,verified,playable,available,runtime_s) VALUES(?,?,1,1,1,60)", (vid, "Film"))
        c.commit()
        mid = c.execute("SELECT id FROM media").fetchone()[0]
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        j = json.load(urllib.request.urlopen(f"{base}/api/subs/{mid}"))
        self.assertEqual(j["tracks"][0]["label"], "English (file)")
        r = urllib.request.urlopen(f"{base}/sub/{mid}/x0.vtt")
        self.assertEqual(r.headers["Content-Type"], "text/vtt; charset=utf-8")
        self.assertIn("Hello there", r.read().decode())
        for bad in (f"/sub/{mid}/x7.vtt", "/sub/999/x0.vtt", "/sub/abc/x0.vtt", f"/sub/{mid}/..%2f..%2fetc.vtt"):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(base + bad)
            self.assertEqual(cm.exception.code, 404, bad)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(f"{base}/api/subs/999")
        self.assertEqual(cm.exception.code, 404)
        req = urllib.request.Request(base + "/api/prefs", json.dumps({"subs": "English"}).encode(), {"Content-Type": "application/json"})
        self.assertEqual(json.load(urllib.request.urlopen(req))["subs"], "English")


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.settings = Path(self.d) / "settings.json"
        self._saved = config.settings_file
        config.settings_file = lambda: self.settings
        self.addCleanup(lambda: setattr(config, "settings_file", self._saved))
        self.media = os.path.join(self.d, "media")
        os.makedirs(os.path.join(self.media, "MCU"))
        self.cfgdir = os.path.join(self.d, "config")
        os.makedirs(self.cfgdir)

    def cfg(self, media=None, name="a"):
        c = Config()
        c.media_dir = media or self.media
        c.db_path = os.path.join(self.d, name + ".sqlite3")
        c.tz = "UTC"
        c.channels_file = os.path.join(self.cfgdir, "channels.json")
        return c

    def add_media(self, conn, rel):
        p = os.path.join(self.media, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b"x")
        conn.execute("INSERT INTO media(path,title,verified,playable,available,runtime_s) VALUES(?,?,1,1,1,100)", (p, rel))
        conn.commit()
        return conn.execute("SELECT id FROM media WHERE path=?", (p,)).fetchone()[0]

    def test_round_trip_onto_a_fresh_install(self):
        cfg = self.cfg()
        conn = make_db(cfg.db_path)
        a, b = self.add_media(conn, "MCU/Iron Man (2008).mp4"), self.add_media(conn, "MCU/Thor (2011).mp4")
        conn.execute("INSERT INTO favorites(media_id,added) VALUES(?,1)", (a,))
        conn.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(?,321,0,5)", (b,))
        conn.execute("INSERT INTO seen(media_id,secs,last) VALUES(?,900,5)", (a,))
        conn.execute("INSERT INTO skips(series,intro,outro) VALUES('Naruto',70,90)")
        conn.execute("INSERT INTO prefs(key,value) VALUES('bigtext','true')")
        conn.commit()
        open(os.path.join(self.cfgdir, "channels.json"), "w").write('{"channels": [{"id":"mine"}]}')
        self.settings.write_text(json.dumps({"station": {"name": "Nick's Hero TV"}, "media_dir": self.media}))
        zpath = backup.make(cfg, conn, os.path.join(self.d, "bk"))
        self.assertTrue(os.path.basename(zpath).startswith("HERO-TV-backup-"))
        self.assertEqual(backup.latest(os.path.join(self.d, "bk")), zpath)
        # new PC: different database, original channels file, no settings
        self.settings.unlink()
        open(os.path.join(self.cfgdir, "channels.json"), "w").write('{"channels": []}')
        cfg2 = self.cfg(name="b")
        conn2 = make_db(cfg2.db_path)
        r = backup.restore(cfg2, conn2, zpath)
        self.assertEqual((r["favorites"], r["progress"], r["seen"], r["skips"], r["not_found"]), (1, 1, 1, 1, 0))
        self.assertIn("mine", open(os.path.join(self.cfgdir, "channels.json")).read())
        self.assertEqual(open(os.path.join(self.cfgdir, "channels.json.before-restore")).read(), '{"channels": []}')
        self.assertEqual(json.loads(self.settings.read_text())["station"]["name"], "Nick's Hero TV")
        fav = conn2.execute("SELECT m.path FROM favorites f JOIN media m ON m.id=f.media_id").fetchone()[0]
        self.assertTrue(fav.endswith("Iron Man (2008).mp4"))
        self.assertEqual(conn2.execute("SELECT position FROM progress").fetchone()[0], 321)
        self.assertEqual(conn2.execute("SELECT intro,outro FROM skips").fetchone()[:], (70, 90))
        self.assertEqual(json.loads(conn2.execute("SELECT value FROM prefs WHERE key='bigtext'").fetchone()[0]), True)

    def test_media_folder_that_does_not_exist_here_is_not_restored(self):
        cfg = self.cfg()
        conn = make_db(cfg.db_path)
        self.settings.write_text(json.dumps({"media_dir": "Z:\\Gone", "station": {"name": "X"}}))
        zpath = backup.make(cfg, conn, os.path.join(self.d, "bk"))
        self.settings.write_text(json.dumps({"media_dir": self.media}))
        backup.restore(self.cfg(name="c"), make_db(self.cfg(name="c").db_path), zpath)
        d = json.loads(self.settings.read_text())
        self.assertEqual(d["media_dir"], self.media)
        self.assertEqual(d["station"]["name"], "X")

    def test_rejects_other_zips_and_broken_config(self):
        bad = os.path.join(self.d, "x.zip")
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("hello.txt", "hi")
        cfg = self.cfg()
        with self.assertRaises(ValueError):
            backup.restore(cfg, make_db(cfg.db_path), bad)
        open(os.path.join(self.d, "notzip.zip"), "w").write("nope")
        with self.assertRaises(ValueError):
            backup.restore(cfg, make_db(cfg.db_path), os.path.join(self.d, "notzip.zip"))
        evil = os.path.join(self.d, "evil.zip")
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("manifest.json", "{}")
            z.writestr("data.json", "{}")
            z.writestr("config/channels.json", "{this is not json")
        with self.assertRaises(ValueError):
            backup.restore(cfg, make_db(cfg.db_path), evil)

    def test_missing_videos_are_counted(self):
        cfg = self.cfg()
        conn = make_db(cfg.db_path)
        a = self.add_media(conn, "MCU/Iron Man (2008).mp4")
        conn.execute("INSERT INTO favorites(media_id,added) VALUES(?,1)", (a,))
        conn.commit()
        zpath = backup.make(cfg, conn, os.path.join(self.d, "bk"))
        os.remove(os.path.join(self.media, "MCU", "Iron Man (2008).mp4"))
        cfg2 = self.cfg(name="n")
        r = backup.restore(cfg2, make_db(cfg2.db_path), zpath)
        self.assertEqual((r["favorites"], r["not_found"]), (0, 1))


if __name__ == "__main__":
    unittest.main()
