"""Ready-to-play copies (prepare.py) and Roku direct play: what plays as it is, what gets a copy, which file a PC browser
and a Roku are given, and that nothing about the original is ever touched."""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock
from http.server import ThreadingHTTPServer
from pathlib import Path

from helpers import S, make_db, tmpdb
from herotv import library, ondemand, prepare, tools
from herotv.config import Config
from herotv.server import App, make_handler

FF = tools.find_tool("ffmpeg")
HAVE_FF = bool(FF and tools.find_tool("ffprobe"))


def clip(path, secs=3, acodec="ac3", extra=()):
    subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-f", "lavfi", "-i",
                    "sine=frequency=300", "-t", str(secs), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", acodec, *extra, path], check=True)


def streams(path):
    j = json.loads(subprocess.run([tools.find_tool("ffprobe"), "-v", "error", "-print_format", "json", "-show_streams", path],
                                  capture_output=True, text=True).stdout)
    return {s["codec_type"]: s["codec_name"] for s in j["streams"]}


class Rules(unittest.TestCase):
    def test_what_the_pc_needs(self):
        self.assertEqual(library.pc_kind("h264", "aac", "yuv420p|high", ".mp4"), "direct")
        self.assertEqual(library.pc_kind("h264", "ac3", "yuv420p|high", ".mkv"), "prepare")       # Dolby: sound only
        self.assertEqual(library.pc_kind("h264", "dts", "yuv420p|high", ".mkv"), "prepare")
        self.assertEqual(library.pc_kind("h264", "pcm_s16le", "yuv420p|high", ".mp4"), "prepare")  # DVD rip in an .mp4
        self.assertEqual(library.pc_kind("h264", "aac", "yuv420p10le|high 10", ".mkv"), "convert")  # the picture itself
        self.assertEqual(library.pc_kind("mpeg4", "mp3", "yuv420p|", ".mkv"), "convert")

    def test_what_a_roku_plays_as_it_is(self):
        ok = library.roku_ok
        self.assertTrue(ok("h264", "ac3", "yuv420p|high", ".mkv"))                  # Dolby: fine on a Roku
        self.assertTrue(ok("h264", "eac3", "yuv420p|high", ".mp4"))
        self.assertTrue(ok("hevc", "ac3", "yuv420p10le|main 10", ".mkv"))           # H.265 in .mkv, 10-bit
        self.assertFalse(ok("h264", "aac", "yuv420p10le|high 10", ".mkv"))          # Hi10P: no
        self.assertFalse(ok("hevc", "aac", "yuv422p10le|main 4:2:2 10", ".mkv"))
        self.assertFalse(ok("h264", "dts", "yuv420p|high", ".mkv"))                 # DTS / TrueHD are not assumed
        self.assertFalse(ok("h264", "truehd", "yuv420p|high", ".mkv"))
        self.assertFalse(ok("mpeg4", "mp3", "yuv420p|", ".mkv"))
        self.assertFalse(ok("h264", "aac", "yuv420p|high", ".avi"))

    def test_command_copies_the_picture_and_converts_only_what_it_must(self):
        c = prepare.command("ffmpeg", "a.mkv", "b.part", "h264", "ac3")
        self.assertEqual(c[c.index("-c:v") + 1], "copy")
        self.assertEqual(c[c.index("-c:a") + 1], "aac")
        c = prepare.command("ffmpeg", "a.mkv", "b.part", "hevc", "aac")
        self.assertEqual(c[c.index("-c:a") + 1], "copy")
        self.assertIn("hvc1", c)
        self.assertIn("ignore_err", prepare.command("ffmpeg", "a", "b", "h264", "ac3", tolerant=True))


@unittest.skipUnless(HAVE_FF, "ffmpeg/ffprobe not installed")
class RealFiles(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(f"{self.root}/Movies")
        self.dolby = f"{self.root}/Movies/Dolby Film (2020).mkv"
        self.plain = f"{self.root}/Movies/Plain Film (2021).mp4"
        self.hi10 = f"{self.root}/Movies/Hi10 Film (2019).mkv"
        clip(self.dolby, 3, "ac3")
        clip(self.plain, 2, "aac")
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-t", "2", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p10le", self.hi10], check=True)
        self.size = os.path.getsize(self.dolby)
        self.cfg = Config(media_dir=self.root, db_path=tmpdb(), channels_file=os.path.join(self.root, "ch.json"),
                          tz="America/New_York", port=0)
        Path(self.cfg.channels_file).write_text(json.dumps({"channels": [{"id": "m", "number": 1, "name": "M", "match": {"franchise": ["Movies"]}}]}))
        self.c = make_db(self.cfg.db_path)
        self.addCleanup(self.c.close)
        S.load_channels(self.c, json.loads(Path(self.cfg.channels_file).read_text())["channels"])
        prepare.set_folder(self.root)
        sf = mock.patch("herotv.config.settings_file", return_value=Path(self.root) / "settings.json")   # never the real settings
        sf.start()
        self.addCleanup(sf.stop)
        library.scan(self.c, self.root)

    def row(self, path):
        return self.c.execute("SELECT * FROM media WHERE path=?", (os.path.normpath(path),)).fetchone()   # Windows: backslashes

    def make(self):
        self.assertTrue(prepare.run_once(self.c, FF, self.root))

    # -- the library's view
    def test_scan_marks_roku_and_pc_separately(self):
        d, p, h = self.row(self.dolby), self.row(self.plain), self.row(self.hi10)
        self.assertEqual((d["playable"], d["roku"]), (0, 1))     # the PC cannot play it yet, a Roku can
        self.assertEqual((p["playable"], p["roku"]), (1, 1))
        self.assertEqual((h["playable"], h["roku"]), (0, 0))     # neither
        self.assertEqual([r["id"] for r in prepare.todo(self.c, self.root)], [d["id"]])   # only the one a copy can help

    # -- making the copy
    def test_copy_is_made_and_the_original_is_untouched(self):
        before = Path(self.dolby).read_bytes()
        mt = os.path.getmtime(self.dolby)
        self.make()
        r = self.row(self.dolby)
        self.assertEqual(r["playable"], 1)
        cp = prepare.copy_path(self.c, r["id"], r["size"])
        self.assertTrue(cp and cp.endswith(".mp4") and os.path.dirname(cp) == os.path.join(self.root, ".prepared"))
        self.assertEqual(streams(cp), {"video": "h264", "audio": "aac"})          # picture copied, Dolby became AAC
        self.assertAlmostEqual(library.probe(cp)["runtime_s"], r["runtime_s"], delta=0.5)
        self.assertEqual(Path(self.dolby).read_bytes(), before)
        self.assertEqual(os.path.getmtime(self.dolby), mt)
        self.assertEqual(streams(self.dolby)["audio"], "ac3")
        self.assertFalse(prepare.run_once(self.c, FF, self.root))                 # nothing left to do
        self.assertEqual(os.listdir(os.path.join(self.root, ".prepared")), [os.path.basename(cp)])   # no leftovers

    def test_who_gets_which_file(self):
        self.make()
        mid = self.row(self.dolby)["id"]
        self.assertEqual(prepare.delivery(self.c, mid, "browser")[1], "mp4")      # a browser gets the copy
        self.assertTrue(prepare.delivery(self.c, mid, "browser")[0].endswith(".mp4"))
        self.assertEqual(prepare.delivery(self.c, mid, "roku"), (os.path.normpath(self.dolby), "mkv"))   # a Roku plays the original
        self.assertEqual(prepare.alt(self.c, mid), "mp4")                         # ... with the copy as its fallback
        self.assertEqual(prepare.delivery(self.c, mid, "safe")[1], "mp4")
        pid = self.row(self.plain)["id"]
        self.assertEqual(prepare.delivery(self.c, pid, "browser"), (os.path.normpath(self.plain), "mp4"))
        self.assertEqual(prepare.alt(self.c, pid), "")                            # nothing to fall back to

    def test_scan_keeps_it_playable_and_tidy_drops_a_copy_nobody_needs(self):
        self.make()
        library.scan(self.c, self.root)                                           # unchanged file: still playable
        self.assertEqual(self.row(self.dolby)["playable"], 1)
        mid = self.row(self.dolby)["id"]
        os.remove(prepare.copy_path(self.c, mid, self.size))                      # someone cleared the folder
        prepare.tidy(self.c)
        self.assertEqual(self.row(self.dolby)["playable"], 0)
        self.assertIsNone(self.c.execute("SELECT 1 FROM prepared WHERE media_id=?", (mid,)).fetchone())
        self.make()                                                               # ... and it is simply made again
        self.assertEqual(self.row(self.dolby)["playable"], 1)

    def test_a_replaced_original_invalidates_the_copy(self):
        self.make()
        clip(self.dolby, 4, "ac3")                                                # a different file under the same name
        library.scan(self.c, self.root)
        r = self.row(self.dolby)
        self.assertEqual(r["playable"], 0)
        self.assertIsNone(prepare.copy_path(self.c, r["id"], r["size"]))
        self.assertEqual([x["id"] for x in prepare.todo(self.c, self.root)], [r["id"]])

    def test_failure_is_remembered_for_a_week_and_retry_forgets_it(self):
        mid = self.row(self.dolby)["id"]
        bad = lambda cmd, rt: tools.FFResult(1, ["Invalid data found"])
        self.assertTrue(prepare.run_once(self.c, FF, self.root, run=bad))
        p = self.c.execute("SELECT status,why FROM prepared WHERE media_id=?", (mid,)).fetchone()
        self.assertEqual((p["status"], p["why"]), ("failed", "Invalid data found"))
        self.assertEqual(self.row(self.dolby)["playable"], 0)
        self.assertEqual(prepare.todo(self.c, self.root), [])
        self.assertEqual(len(prepare.todo(self.c, self.root, now=time.time() + 8 * 86400)), 1)
        self.assertIn("could not prepare", prepare.why(self.c, self.row(self.dolby)))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".prepared", f"{mid}-{self.size}.part")))
        prepare.retry(self.c)
        self.assertEqual(len(prepare.todo(self.c, self.root)), 1)

    def test_damaged_sound_uses_the_other_track(self):
        mid = self.row(self.dolby)["id"]
        calls = []

        def run(cmd, rt):
            calls.append(cmd)
            if len(calls) == 1:                                                   # the first try: ffmpeg cannot decode the sound
                return tools.FFResult(1, ["[dec:ac3 @ 0x1] Decode error rate 0.74 exceeds maximum 0.666667"])
            return tools.run_ffmpeg(cmd, rt)
        # a file with two sound tracks: the first (default) one is "damaged" by the fake first attempt
        two = f"{self.root}/Movies/Two Tracks (2018).mkv"
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-f", "lavfi", "-i", "sine=frequency=300",
                        "-f", "lavfi", "-i", "sine=frequency=500", "-t", "3", "-map", "0", "-map", "1", "-map", "2", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "ac3", two], check=True)
        library.scan(self.c, self.root)
        r = self.row(two)
        self.assertEqual(prepare.prepare_one(self.c, r, FF, run=run), "ready")
        self.assertGreaterEqual(len(calls), 2)
        self.assertIn("0:a:1?", calls[1])                                         # tried the second track
        self.assertEqual(self.row(two)["playable"], 1)

    def test_the_inbox_is_left_to_the_inbox_and_nothing_else_is_deleted(self):
        os.makedirs(f"{self.root}/Inbox")
        clip(f"{self.root}/Inbox/New (2022).mkv", 2, "ac3")
        library.scan(self.c, self.root)
        names = [os.path.basename(r["path"]) for r in prepare.todo(self.c, self.root)]
        self.assertNotIn("New (2022).mkv", names)
        self.make()
        mine = os.path.join(self.root, ".prepared", "notes.mp4")                  # a file that is not ours stays
        Path(mine).write_bytes(b"x")
        prepare.tidy(self.c)
        self.assertTrue(os.path.exists(mine))

    def test_clear_removes_every_copy_and_the_video_stops_counting_as_playable(self):
        self.make()
        prepare.clear(self.c)
        self.assertEqual(self.row(self.dolby)["playable"], 0)
        self.assertEqual(os.listdir(os.path.join(self.root, ".prepared")), [])
        self.assertTrue(os.path.exists(self.dolby))                               # the original is still there

    def test_a_renamed_video_keeps_its_copy(self):
        self.make()
        old = self.row(self.dolby)
        new = f"{self.root}/Movies/Dolby Film Renamed (2020).mkv"
        os.rename(self.dolby, new)
        library.scan(self.c, self.root)
        r = self.row(new)
        self.assertNotEqual(r["id"], old["id"])
        self.assertEqual(r["playable"], 1)                                        # relinked: the copy followed
        self.assertTrue(prepare.copy_path(self.c, r["id"], r["size"]))
        self.assertIsNone(self.c.execute("SELECT 1 FROM prepared WHERE media_id=?", (old["id"],)).fetchone())

    def test_status(self):
        s = prepare.status(self.c)
        self.assertEqual((s["need"], s["ready"], s["failed"], s["convert"]), (1, 0, 0, 1))
        self.make()
        s = prepare.status(self.c)
        self.assertEqual((s["need"], s["ready"]), (1, 1))
        self.assertGreater(s["bytes"], 0)

    # -- the space limit stops NEW copies and never deletes one
    def test_space_limit_stops_new_copies_but_never_removes_one(self):
        self.make()                                                               # the first copy exists
        mid = self.row(self.dolby)["id"]
        cp = prepare.copy_path(self.c, mid, self.size)
        other = f"{self.root}/Movies/Second Dolby (2022).mkv"
        clip(other, 3, "ac3")
        library.scan(self.c, self.root)
        self.assertEqual(self.row(other)["playable"], 0)
        with mock.patch.object(prepare, "cap_gb", return_value=1), mock.patch.object(prepare, "used_bytes", return_value=2 * 1024 ** 3):
            prepare.run_once(self.c, FF, self.root)                               # (first pass only reads the new file's sound tracks)
            self.assertFalse(prepare.run_once(self.c, FF, self.root))             # over the limit: no new copy
            s = prepare.status(self.c)
        self.assertEqual((s["cap_gb"], s["blocked"]), (1, True))
        self.assertEqual(self.row(other)["playable"], 0)
        self.assertTrue(os.path.isfile(cp))                                       # the existing copy is untouched
        self.assertEqual(self.row(self.dolby)["playable"], 1)
        self.assertTrue(os.path.exists(other) and os.path.exists(self.dolby))     # and so are the videos
        self.assertTrue(prepare.run_once(self.c, FF, self.root))                  # limit lifted (0 = none): carries on
        self.assertFalse(prepare.status(self.c)["blocked"])
        self.assertEqual(self.row(other)["playable"], 1)

    def test_limit_setting_is_validated_and_saved(self):
        base = self.serve()
        call = lambda body: self.post(base, "/api/prepare", body)
        self.assertEqual(call({"cap": "lots"})[0], 400)
        self.assertEqual(call({"cap": -5})[0], 400)
        self.assertEqual(call({"cap": 10 ** 9})[0], 400)
        st, j = call({"cap": 100})
        self.assertEqual((st, j["cap_gb"]), (200, 100))
        self.assertEqual(prepare.cap_gb(), 100)
        self.assertEqual(call({"cap": 0})[1]["cap_gb"], 0)

    def test_inside_is_not_fooled_by_a_sibling_folder(self):
        from herotv.server import _inside
        root = os.path.join(self.root, "Media")
        self.assertTrue(_inside(os.path.join(root, "a", "x.mkv"), root))
        self.assertTrue(_inside(root, root))
        self.assertFalse(_inside(os.path.join(self.root, "Media2", "x.mkv"), root))   # a plain prefix test would say yes
        self.assertFalse(_inside(os.path.join(root, "..", "x.mkv"), root))

    def test_a_missing_checklist_file_is_not_a_server_error(self):
        base = self.serve()
        with urllib.request.urlopen(base + "/api/checklist") as r:
            j = json.load(r)
        self.assertEqual((r.status, j["lists"]), (200, []))
        self.assertIn("checklist.json", j["error"])

    def serve(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(self.cfg)))
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    def post(self, base, path, body):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, None

    # -- the Roku's view
    def test_on_demand_lists_what_a_roku_can_play_before_the_copy_exists(self):
        titles = [t["title"] for row in ondemand.rows(self.c, time.time())["rows"] for t in row["items"]]
        self.assertIn("Dolby Film", " ".join(titles))                             # playable=0 for the PC, yet on the Roku
        self.assertIn("Plain Film", " ".join(titles))
        self.assertNotIn("Hi10 Film", " ".join(titles))
        d = ondemand.play(self.c, self.row(self.dolby)["id"])
        self.assertEqual((d["ext"], d["alt"]), ("mkv", ""))                       # original, no fallback yet
        self.make()
        d = ondemand.play(self.c, self.row(self.dolby)["id"])
        self.assertEqual((d["ext"], d["alt"]), ("mkv", "mp4"))                    # now with a fallback

    # -- what is really sent over HTTP
    def test_http_browser_and_roku_get_different_files(self):
        self.make()
        mid = self.row(self.dolby)["id"]
        app = App(self.cfg)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def get(p, rng=None):
            req = urllib.request.Request(base + p, headers={"Range": rng} if rng else {})
            with urllib.request.urlopen(req) as r:
                return r.status, r.headers.get("Content-Type"), r.read()
        st, ct, body = get(f"/media/{mid}")                                        # the PC's TV screen
        self.assertEqual((st, ct), (200, "video/mp4"))
        self.assertNotEqual(len(body), self.size)
        cp = prepare.copy_path(self.c, mid, self.size)
        self.assertEqual(body, Path(cp).read_bytes())
        st, ct, body = get(f"/media/{mid}.mkv")                                    # the Roku app
        self.assertEqual(len(body), self.size)
        self.assertEqual(body, Path(self.dolby).read_bytes())
        st, ct, body = get(f"/media/{mid}.mp4?safe=1")                             # a Roku that refused the original
        self.assertEqual(body, Path(cp).read_bytes())
        st, ct, body = get(f"/media/{mid}", "bytes=0-99")                          # seeking still works on the copy
        self.assertEqual((st, len(body)), (206, 100))
        with urllib.request.urlopen(base + "/api/prepare") as r:
            j = json.load(r)
        self.assertEqual((j["need"], j["ready"], j["on"]), (1, 1, True))
        pid = self.row(self.plain)["id"]
        self.assertEqual(get(f"/media/{pid}")[2], Path(self.plain).read_bytes())  # a file that plays as it is: untouched


if __name__ == "__main__":
    unittest.main()
