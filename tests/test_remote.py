import json
import os
import socket
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import config, remote as R, server as SV  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402


class AddressOrder(unittest.TestCase):
    def addresses(self, route, others):
        class Fake:
            def __init__(self, *a): pass
            def connect(self, *a): pass
            def getsockname(self): return (route, 0)
            def close(self): pass
        with mock.patch.object(R.socket, "socket", Fake), mock.patch.object(R, "_other_addresses", return_value=others):
            return R.lan_addresses()

    def test_the_home_network_comes_before_a_vpn_card(self):
        # Mozilla VPN is what the PC would use to reach the internet, but a phone or TV cannot reach it
        self.assertEqual(self.addresses("10.155.18.0", ["192.168.12.198"]), ["192.168.12.198", "10.155.18.0"])

    def test_without_a_vpn_the_route_card_stays_first(self):
        self.assertEqual(self.addresses("10.0.0.5", ["10.0.0.5", "172.20.1.9"]), ["172.20.1.9", "10.0.0.5"])
        self.assertEqual(self.addresses("192.168.1.9", ["10.8.0.2"]), ["192.168.1.9", "10.8.0.2"])
        self.assertEqual(self.addresses("10.0.0.5", ["10.1.0.7"]), ["10.0.0.5", "10.1.0.7"])      # equals: the route card wins

    def test_a_network_address_is_last(self):
        self.assertEqual(self.addresses("192.168.1.0", ["10.0.0.5"]), ["10.0.0.5", "192.168.1.0"])


def free_pair_of_ports():
    """Two free neighbouring ports (PC port and the home-network port next to it). Picked outside the range
    Windows hands out for outgoing connections (49152-65535), where a port that was free a moment ago can be
    taken again (WinError 10013 on the CI runner)."""
    import random
    rng = random.Random()
    for _ in range(200):
        p = rng.randrange(20000, 40000)
        socks = []
        try:
            for addr in (("127.0.0.1", p), ("0.0.0.0", p + 1)):
                t = socket.socket()
                socks.append(t)
                t.bind(addr)
            return p
        except OSError:
            continue
        finally:
            for t in socks:
                t.close()
    raise RuntimeError("no ports")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.sf = Path(self.d) / "settings.json"
        p = mock.patch.object(config, "settings_file", return_value=self.sf)
        p.start(); self.addCleanup(p.stop)
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"),
                          channels_file=str(Path(config.ROOT) / "config" / "channels.json"))
        self.cfg.port = free_pair_of_ports()
        c = connect(self.cfg.db_path)
        vid = Path(self.d) / "Film.mp4"; vid.write_bytes(b"0123456789" * 100)
        c.execute("INSERT INTO media(path,title,verified,playable,available,runtime_s) VALUES(?,?,1,1,1,60)", (str(vid), "Film"))
        c.commit(); c.close()
        self.app = SV.App(self.cfg)
        R.cancel_pairing()
        self.addCleanup(self.app.stop_lan)
        self.lan = f"http://127.0.0.1:{R.lan_port(self.cfg)}"
        self.opener = urllib.request.build_opener(NoRedirect)

    def req(self, path, body=None, cookie=None, host=None, method=None):
        h = {}
        if body is not None:
            h["Content-Type"] = "application/json"
        if cookie:
            h["Cookie"] = f"{R.COOKIE}={cookie}"
        if host:
            h["Host"] = host
        r = urllib.request.Request(self.lan + path, None if body is None else json.dumps(body).encode(), h, method=method)
        try:
            resp = self.opener.open(r, timeout=10)
            return resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def enable(self):
        R.set_enabled(True)
        for _ in range(8):              # Windows reserves some ports at random: pick again if this one is refused
            try:
                self.app.start_lan()
                break
            except ValueError:
                self.cfg.port = free_pair_of_ports()
        else:
            self.fail("could not open a test port")
        self.lan = f"http://127.0.0.1:{R.lan_port(self.cfg)}"

    def pair(self):
        code = R.start_pairing()["code"]
        st, body, hdr = self.req("/api/pair", {"code": code})
        self.assertEqual(st, 200, body)
        return hdr["Set-Cookie"].split(";")[0].split("=", 1)[1], hdr["Set-Cookie"]

    def test_off_by_default(self):
        self.assertFalse(R.enabled())
        self.assertIsNone(self.app.lan_srv)

    def test_everything_needs_pairing(self):
        self.enable()
        st, _, hdr = self.req("/")
        self.assertEqual((st, hdr["Location"]), (302, "/pair"))
        self.assertEqual(self.req("/pair")[0], 200)
        for p in ("/api/channels", "/media/1", "/thumb/1", "/api/settings", "/index.html"):
            self.assertIn(self.req(p)[0], (401, 302), p)

    def test_pairing_flow_and_cookie_rules(self):
        self.enable()
        tok, raw = self.pair()
        self.assertIn("HttpOnly", raw); self.assertIn("SameSite=Strict", raw)
        self.assertEqual(self.req("/", cookie=tok)[0], 200)
        self.assertEqual(self.req("/api/channels", cookie=tok)[0], 200)
        st, body, hdr = self.req("/media/1", cookie=tok)
        self.assertEqual((st, len(body)), (200, 1000))
        dev = json.loads(self.req("/api/device", cookie=tok)[1])
        self.assertTrue(dev["remote"]); self.assertTrue(dev["mk"])
        self.assertEqual(self.req(f"/media/1?k={dev['mk']}")[0], 200)                    # AirPlay-style fetch, no cookie
        self.assertEqual(self.req("/media/1?k=wrong")[0], 401)
        self.assertEqual(self.req(f"/api/channels?k={dev['mk']}")[0], 401)               # the media key opens media only
        self.assertEqual(self.req("/api/channels", cookie="forged")[0], 401)

    def test_paired_device_is_watch_only(self):
        self.enable()
        tok, _ = self.pair()
        for p in ("/api/settings", "/api/tools", "/api/job", "/api/channels-config", "/api/upload-token", "/api/devices",
                  "/api/whatsnew"):
            self.assertEqual(self.req(p, cookie=tok)[0], 403, p)
        for p, b in (("/api/settings", {"station": {"name": "x"}}), ("/api/job", {"name": "sort"}), ("/api/action", {"name": "backup"}),
                     ("/api/devices", {"op": "pair"}), ("/api/rename", {"media_id": 1, "title": "x"}), 
                     ("/api/report-error", {"media_id": 1}), ("/api/channels-config", {"op": "delete", "id": "mcu"})):
            self.assertEqual(self.req(p, b, cookie=tok)[0], 403, p)
        up = urllib.request.Request(self.lan + "/api/upload?name=a.mp4&token=" + self.app.upload_token, b"video",
                                    {"Content-Type": "application/octet-stream", "X-HeroTV-Upload": "1", "Cookie": f"{R.COOKIE}={tok}"}, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(up, timeout=10)
        self.assertEqual(cm.exception.code, 403)                                           # even with the right upload token
        self.assertFalse((Path(self.d) / "Inbox" / "a.mp4").exists())
        self.assertEqual(self.req("/api/favorite", {"media_id": 1, "on": True}, cookie=tok)[0], 200)
        self.assertEqual(self.req("/api/prefs", {"volume": 0.1}, cookie=tok)[0], 200)               # answered...
        c = connect(self.cfg.db_path)
        self.assertIsNone(c.execute("SELECT value FROM prefs WHERE key='volume'").fetchone()); c.close()   # ...not saved

    def test_wrong_codes_cancel_and_one_code_one_device(self):
        self.enable()
        code = R.start_pairing()["code"]
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(R.MAX_TRIES - 1):
            self.assertEqual(self.req("/api/pair", {"code": wrong})[0], 403)
        self.assertEqual(self.req("/api/pair", {"code": wrong})[0], 403)
        self.assertEqual(self.req("/api/pair", {"code": code})[0], 403)                    # cancelled after 5 tries
        code = R.start_pairing()["code"]
        self.assertEqual(self.req("/api/pair", {"code": code})[0], 200)
        self.assertEqual(self.req("/api/pair", {"code": code})[0], 403)                    # used up
        R.start_pairing(now=time.time() - R.PAIR_SECONDS - 1)
        self.assertIsNone(R.pairing_state())                                               # expired

    def test_host_header_rules(self):
        self.enable()
        tok, _ = self.pair()
        self.assertEqual(self.req("/api/channels", cookie=tok, host="evil.example.com")[0], 403)
        self.assertEqual(self.req("/api/channels", cookie=tok, host=f"192.168.1.20:{R.lan_port(self.cfg)}")[0], 200)
        self.assertFalse(R.host_ok("8.8.8.8")); self.assertTrue(R.host_ok("10.0.0.5:8788")); self.assertFalse(R.host_ok(""))

    def test_remove_device_and_switch_off(self):
        self.enable()
        tok, _ = self.pair()
        c = connect(self.cfg.db_path)
        devs = R.devices(c)
        self.assertEqual(len(devs), 1)
        R.remove(c, devs[0]["id"]); c.close()
        self.assertEqual(self.req("/api/channels", cookie=tok)[0], 401)
        tok, _ = self.pair()
        R.set_enabled(False)
        self.assertEqual(self.req("/api/channels", cookie=tok)[0], 403)                    # switched off: refused at once
        self.app.stop_lan()
        with self.assertRaises(Exception):
            urllib.request.urlopen(self.lan + "/pair", timeout=3)

    def test_pc_controls_devices(self):
        from http.server import ThreadingHTTPServer
        import threading
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(self.app))
        while R.lan_port(self.cfg) == srv.server_address[1]:          # never let the two test servers share a port
            self.cfg.port = free_pair_of_ports()
        self.lan = f"http://127.0.0.1:{R.lan_port(self.cfg)}"
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def op(b):
            r = urllib.request.Request(base + "/api/devices", json.dumps(b).encode(), {"Content-Type": "application/json"}, method="POST")
            return json.load(urllib.request.urlopen(r))
        with self.assertRaises(urllib.error.HTTPError):
            op({"op": "pair"})                                                              # must be switched on first
        j = op({"op": "enable"})
        self.assertTrue(j["enabled"] and j["running"])
        j = op({"op": "pair"})
        self.assertEqual(len(j["pairing"]["code"]), 6)
        st, _, _ = self.req("/api/pair", {"code": j["pairing"]["code"]})
        self.assertEqual(st, 200)
        self.assertEqual(len(op({"op": "cancel"})["devices"]), 1)
        self.assertEqual(op({"op": "remove-all"})["devices"], [])
        j = op({"op": "disable"})
        self.assertFalse(j["enabled"] or j["running"])
        self.assertFalse(json.load(urllib.request.urlopen(base + "/api/device"))["remote"])


if __name__ == "__main__":
    unittest.main()


class PhoneFriendlyTests(unittest.TestCase):
    def test_rules(self):
        from herotv import library as L
        self.assertTrue(L.phone_ok("a.mp4", "h264", "aac", "yuv420p|High"))
        self.assertTrue(L.phone_ok("a.MOV", "h264", "ac3", "yuv420p|High"))
        self.assertFalse(L.phone_ok("a.mkv", "h264", "aac", "yuv420p|High"))        # Safari cannot open .mkv
        self.assertFalse(L.phone_ok("a.mp4", "vp9", "opus", "yuv420p|"))
        self.assertFalse(L.phone_ok("a.mp4", "h264", "dts", "yuv420p|High"))
        self.assertFalse(L.phone_ok("a.mp4", "h264", "aac", "yuv420p10le|High 10"))

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_mkv_becomes_iphone_friendly_mp4_without_reencoding(self):
        from herotv import launcher, library as L, tools
        d = tempfile.mkdtemp()
        src = os.path.join(d, "Show S01E01.mkv")
        r = tools.run([tools.find_tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10",
                       "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                       "-c:a", "aac", src], timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        with mock.patch.object(launcher, "_after_change", return_value=0):
            self.assertEqual(launcher.make_phone_ready([src]), 0)
        out = os.path.join(d, "Show S01E01.mp4")
        p = L.probe(out)
        self.assertTrue(L.phone_ok(out, p["vcodec"], p["acodec"], p.get("vfmt", "")))
        self.assertTrue(os.path.isfile(os.path.join(d, ".originals", "Show S01E01.mkv")))
        self.assertFalse(os.path.exists(src))
