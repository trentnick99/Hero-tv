import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from pathlib import Path

from helpers import S, make_db, tmpdb
from herotv import library
from herotv.config import Config
from herotv.server import App, make_handler

HAVE_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def clip(path, secs, acodec="aac"):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-f", "lavfi", "-i",
                    "sine=frequency=300", "-t", str(secs), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", acodec, path], check=True)


@unittest.skipUnless(HAVE_FF, "ffmpeg/ffprobe not installed")
class LibraryAndServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        os.makedirs(f"{cls.root}/MCU")
        clip(f"{cls.root}/MCU/Hero One (2020).mp4", 3)
        clip(f"{cls.root}/MCU/Hero Two (2021).mp4", 2)
        clip(f"{cls.root}/MCU/AC3 Film (2022).mkv", 2, "ac3")
        Path(f"{cls.root}/MCU/Hero One (2020).hero.json").write_text(json.dumps({"tags": ["action"], "plot": "P"}))
        cls.cfgf = os.path.join(cls.root, "ch.json")
        Path(cls.cfgf).write_text(json.dumps({"channels": [{"id": "mcu", "number": 1, "name": "MCU", "match": {"franchise": ["MCU"]}}]}))
        cls.cfg = Config(media_dir=cls.root, db_path=tmpdb(), channels_file=cls.cfgf, tz="America/New_York", port=0)
        c = make_db(cls.cfg.db_path)
        S.load_channels(c, json.loads(Path(cls.cfgf).read_text())["channels"])
        cls.stats = library.scan(c, cls.root)
        S.extend_all(c, time.time(), 3600)
        c.close()
        cls.app = App(cls.cfg)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.app))
        cls.srv.daemon_threads = True
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def get(self, p, headers=None, data=None):
        headers = dict(headers or {})
        if data:
            headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(self.base + p, headers=headers, data=json.dumps(data).encode() if data else None)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def test_scan_verifies_runtime_and_flags_unplayable_audio(self):
        c = make_db(self.cfg.db_path)
        r = {x["title"]: x for x in c.execute("SELECT * FROM media")}
        self.assertAlmostEqual(r["Hero One"]["runtime_s"], 3, delta=0.3)
        self.assertEqual((r["Hero One"]["verified"], r["Hero One"]["playable"]), (1, 1))
        self.assertEqual(r["AC3 Film"]["playable"], 0)               # Chromium can't decode ac3
        self.assertEqual(r["Hero One"]["tags"], '["action"]')
        again = library.scan(c, self.root, probe_fn=lambda p: self.fail("unchanged file re-probed"))
        self.assertEqual((again["added"], again["updated"]), (0, 0))

    def test_ac3_never_scheduled(self):
        s, b, _ = self.get("/api/guide?hours=1")
        titles = {x["title"] for ch in json.loads(b)["channels"] for x in ch["slots"]}
        self.assertEqual(titles, {"Hero One", "Hero Two"})

    def test_api_now_guide_labelled_generated(self):
        s, b, _ = self.get("/api/channel/mcu/now")
        j = json.loads(b)
        self.assertEqual(s, 200)
        self.assertLessEqual(j["slot"]["start"], j["now"]); self.assertGreater(j["slot"]["end"], j["now"])
        self.assertEqual(j["slot"]["source"], "generated")
        g = json.loads(self.get("/api/guide?date=2026-03-08")[1])
        self.assertEqual(g["to"] - g["from"], 23 * 3600)
        self.assertIn("not official", g["notice"])

    def test_range_requests(self):
        mid = json.loads(self.get("/api/channel/mcu/now")[1])["slot"]["media_id"]
        s, b, h = self.get(f"/media/{mid}", {"Range": "bytes=0-9"})
        self.assertEqual((s, len(b), h["Content-Range"].startswith("bytes 0-9/")), (206, 10, True))
        s, b, h = self.get(f"/media/{mid}", {"Range": "bytes=-5"}); self.assertEqual((s, len(b)), (206, 5))
        s, _, _ = self.get(f"/media/{mid}", {"Range": "bytes=999999999-"}); self.assertEqual(s, 416)
        s, b, _ = self.get(f"/media/{mid}"); self.assertEqual(s, 200)
        self.assertEqual(self.get("/media/9999")[0], 404)
        self.assertEqual(self.get("/..%2f..%2fetc/passwd")[0], 404)

    def test_rejects_invalid_api_inputs(self):
        self.assertEqual(self.get("/api/guide?hours=999")[0], 400)
        self.assertEqual(self.get("/api/guide?date=not-a-date")[0], 400)
        self.assertEqual(self.get("/api/progress", data={"media_id": -1, "position": 2})[0], 400)
        self.assertEqual(self.get("/api/progress", data={"media_id": 999999, "position": 2})[0], 404)

    def test_security_headers_are_present(self):
        status, _, headers = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")

    def raw(self, payload, wait=1.0):
        s = socket.create_connection(self.srv.server_address[:2]); s.sendall(payload); s.settimeout(wait); out = b""
        try:
            while True:
                d = s.recv(65536)
                if not d:
                    break
                out += d
        except socket.timeout:
            pass
        s.close()
        return out

    def test_post_requires_json_content_type_and_local_host(self):
        s, _, _ = self.get("/api/progress", {"Content-Type": "text/plain"}, {"media_id": 1, "position": 1})
        self.assertEqual(s, 415)                       # cross-site "simple" POST is refused
        s, _, _ = self.get("/api/health", {"Host": "evil.example"})
        self.assertEqual(s, 403)                       # DNS-rebinding guard

    def test_no_duplicate_security_headers(self):
        r = self.raw(b"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n").decode().lower()
        self.assertEqual(r.count("x-content-type-options"), 1)
        self.assertEqual(r.count("referrer-policy"), 1)

    def test_rejected_oversized_body_does_not_desync_keepalive(self):
        req = (b"POST /api/progress HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n"
               b"Content-Length: 70000\r\n\r\n" + b"x" * 70000 +
               b"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        r = self.raw(req, 1.5)
        self.assertTrue(r.startswith(b"HTTP/1.1 400"))
        self.assertEqual(r.count(b"HTTP/1.1 "), 2)     # exactly one reply per request; no garbage-parsed extras
        self.assertIn(b"HTTP/1.1 200", r)

    def test_range_edge_cases(self):
        mid = json.loads(self.get("/api/channel/mcu/now")[1])["slot"]["media_id"]
        for bad in ("bytes=5-2", "bytes=-0", "bytes=0-1,3-4", "items=0-1"):
            self.assertEqual(self.get(f"/media/{mid}", {"Range": bad})[0], 416, bad)

    def test_progress_and_library_search(self):
        mid = json.loads(self.get("/api/library?q=Hero%20Two")[1])["items"][0]["id"]
        self.get("/api/progress", data={"media_id": mid, "position": 1.5})
        it = json.loads(self.get("/api/library?q=hero%20two")[1])["items"][0]
        self.assertEqual(it["position"], 1.5)
        self.assertEqual(json.loads(self.get("/api/library?q=zzzz")[1])["items"], [])

    def test_a_damaged_sound_error_queues_a_repair(self):
        mid = json.loads(self.get("/api/library?q=Hero%20Two")[1])["items"][0]["id"]
        why = "player error 3: PipelineStatus::PIPELINE_ERROR_DECODE: Failed to send audio packet for decoding"
        res = json.loads(self.get("/api/report-error", data={"media_id": mid, "reason": why})[1])
        self.assertTrue(res.get("repair"))
        c = make_db(self.cfg.db_path)
        self.assertEqual(c.execute("SELECT status FROM prepared WHERE media_id=?", (mid,)).fetchone()[0], "fix")
        other = json.loads(self.get("/api/library?q=Hero%20Two")[1])["items"][0]["id"]
        res = json.loads(self.get("/api/report-error", data={"media_id": other, "reason": "player error 4: DEMUXER_ERROR"})[1])
        self.assertFalse(res.get("repair"))

    def test_missing_file_reported_triggers_reschedule_without_gap(self):
        tmp = os.path.join(self.root, "MCU", "Gone (2023).mp4"); clip(tmp, 2)
        c = make_db(self.cfg.db_path); library.scan(c, self.root); S.extend_all(c, time.time(), 3600, rebuild=True)
        gid = c.execute("SELECT id FROM media WHERE title='Gone'").fetchone()[0]
        os.remove(tmp)
        self.assertEqual(json.loads(self.get("/api/report-error", data={"media_id": gid})[1])["action"], "marked-missing")
        rows = c.execute("SELECT start,end,media_id FROM slots WHERE channel_id='mcu' ORDER BY start").fetchall()
        self.assertNotIn(gid, [r[2] for r in rows if r[1] > time.time()])
        for a, b in zip(rows, rows[1:]):
            self.assertEqual(a[1], b[0])


class ScanSafety(unittest.TestCase):
    """No ffmpeg needed: uses a fake probe."""

    def fake_probe(self, path):
        return {"runtime_s": 60.0, "vcodec": "h264", "acodec": "aac", "title": ""}

    def setUp(self):
        self.root = tempfile.mkdtemp(); os.makedirs(f"{self.root}/MCU")
        Path(f"{self.root}/MCU/A (2020).mp4").write_bytes(b"x")
        self.c = make_db()
        library.scan(self.c, self.root, self.fake_probe)

    def test_transiently_unplayable_file_is_restored_by_rescan(self):
        self.c.execute("UPDATE media SET playable=0"); self.c.commit()   # what repeated client errors do
        library.scan(self.c, self.root, probe_fn=lambda p: self.fail("unchanged file re-probed"))
        self.assertEqual(self.c.execute("SELECT playable FROM media").fetchone()[0], 1)

    def test_genuinely_unsupported_codec_stays_unplayable(self):
        self.c.execute("UPDATE media SET acodec='ac3', playable=0"); self.c.commit()
        library.scan(self.c, self.root)
        self.assertEqual(self.c.execute("SELECT playable FROM media").fetchone()[0], 0)

    def test_missing_or_empty_media_root_keeps_library(self):
        st = library.scan(self.c, "/definitely/not/mounted", self.fake_probe)
        self.assertTrue(st.get("offline"))
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM media WHERE available=1").fetchone()[0], 1)

    def test_deleted_single_file_is_marked_missing(self):
        Path(f"{self.root}/MCU/B (2021).mp4").write_bytes(b"y")
        library.scan(self.c, self.root, self.fake_probe)
        os.remove(f"{self.root}/MCU/A (2020).mp4")
        st = library.scan(self.c, self.root, self.fake_probe)
        self.assertEqual(st["missing"], 1)


if __name__ == "__main__":
    unittest.main()
