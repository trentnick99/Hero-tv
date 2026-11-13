"""Phones: watching away from home through Tailscale, pairing with one-time links, and videos converted while you watch
(HLS) - with a real ffmpeg where the computer has one."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import away, config, netcheck, remote as R, server as SV, stream, tools  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402
from test_remote import NoRedirect, free_pair_of_ports  # noqa: E402

FF = tools.find_tool("ffmpeg")
FP = tools.find_tool("ffprobe")

STATUS = json.dumps({
    "BackendState": "Running",
    "Self": {"HostName": "DESKTOP-F3NLP4N", "DNSName": "desktop-f3nlp4n.tail1234.ts.net.", "OS": "windows",
             "TailscaleIPs": ["100.101.102.103", "fd7a:115c:a1e0::1234"], "Online": True},
    "CurrentTailnet": {"Name": "nick@example.com", "MagicDNSSuffix": "tail1234.ts.net", "MagicDNSEnabled": True},
    "Peer": {"k1": {"HostName": "Nicks-iPhone", "OS": "iOS", "Online": True, "TailscaleIPs": ["100.90.1.2"]},
             "k2": {"HostName": "laptop", "OS": "windows", "Online": False, "TailscaleIPs": ["100.90.1.3"]}}})


def make_video(path, seconds=30, audio="ac3"):
    r = subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=640x360:r=24:d={seconds}", "-f", "lavfi",
                        "-i", f"sine=f=330:d={seconds}", "-c:v", "libx264", "-preset", "ultrafast", "-g", "120", "-c:a", audio,
                        "-shortest", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def start_time(f):
    r = subprocess.run([FP, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=start_time", "-of", "csv=p=0", f],
                       capture_output=True, text=True)
    return float(r.stdout.split()[0])


# ---------------------------------------------------------------- Tailscale

class TailscaleStatus(unittest.TestCase):
    def setUp(self):
        away.clear_cache()
        self.addCleanup(away.clear_cache)

    def test_reads_what_tailscale_says(self):
        s = away.status(fresh=True, run=lambda p: STATUS, find=lambda: "tailscale.exe")
        self.assertTrue(s["installed"] and s["running"])
        self.assertEqual((s["ip"], s["dns"]), ("100.101.102.103", "desktop-f3nlp4n.tail1234.ts.net"))
        self.assertEqual([p["name"] for p in s["peers"]], ["Nicks-iPhone", "laptop"])            # phones first
        self.assertTrue(s["peers"][0]["phone"] and s["peers"][0]["online"])
        self.assertIn("Nicks-iPhone is on your Tailscale network", s["words"])
        self.assertEqual(away.own_names(s), {"desktop-f3nlp4n.tail1234.ts.net", "desktop-f3nlp4n"})

    def test_each_state_in_plain_words(self):
        none = away.status(fresh=True, find=lambda: "")
        self.assertFalse(none["installed"])
        self.assertIn("not on this PC", none["words"])
        out = away.status(fresh=True, run=lambda p: json.dumps({"BackendState": "NeedsLogin"}), find=lambda: "x")
        self.assertIn("not signed in", out["words"])
        off = away.status(fresh=True, run=lambda p: json.dumps({"BackendState": "Stopped"}), find=lambda: "x")
        self.assertIn("switched off", off["words"])
        lone = json.loads(STATUS)
        lone["Peer"] = {}
        self.assertIn("install Tailscale on your phone", away.status(fresh=True, run=lambda p: json.dumps(lone), find=lambda: "x")["words"])
        self.assertFalse(away.status(fresh=True, run=lambda p: "not json at all", find=lambda: "x")["running"])

    def test_tailscale_addresses(self):
        for a in ("100.64.0.1", "100.127.255.254", "100.101.102.103", "fd7a:115c:a1e0::1", "[fd7a:115c:a1e0::1]", "::ffff:100.90.1.2"):
            self.assertTrue(away.is_tailnet(a), a)
        for a in ("100.63.255.255", "100.128.0.1", "192.168.1.5", "8.8.8.8", "fd00::1", "", "not an address"):
            self.assertFalse(away.is_tailnet(a), a)

    def test_the_network_port_answers_on_tailscale_but_not_to_strangers(self):
        with mock.patch.object(away, "own_names", return_value={"desktop-f3nlp4n.tail1234.ts.net", "desktop-f3nlp4n"}):
            for h in ("100.101.102.103:8788", "[fd7a:115c:a1e0::1234]:8788", "desktop-f3nlp4n.tail1234.ts.net:8788", "desktop-f3nlp4n"):
                self.assertTrue(R.host_ok(h), h)
            for h in ("evil.example", "someone-else.tail9999.ts.net", "8.8.8.8:8788", "100.200.1.1", ""):
                self.assertFalse(R.host_ok(h), h)


class PairingLinks(unittest.TestCase):
    def setUp(self):
        self.c = connect(os.path.join(tempfile.mkdtemp(), "t.sqlite3"))
        R._links.clear()

    def test_a_link_pairs_one_device_once(self):
        t = R.make_link(now=1000)
        self.assertTrue(R.link_ok(t, now=1000))
        tok, mk = R.pair_link(self.c, t, "iPhone (away from home)", "100.90.1.2", now=1010)
        self.assertEqual(R.device_for(self.c, tok)["name"], "iPhone (away from home)")
        with self.assertRaises(ValueError):
            R.pair_link(self.c, t, "again", now=1020)                  # used up

    def test_links_run_out(self):
        t = R.make_link(now=1000)
        with self.assertRaises(ValueError):
            R.pair_link(self.c, t, "late", now=1000 + R.LINK_SECONDS + 1)
        with self.assertRaises(ValueError):
            R.pair_link(self.c, "made-up", "x", now=1000)
        for i in range(20):
            R.make_link(now=2000 + i)
        self.assertLessEqual(len(R._links), 8)                         # only a few at a time


class AwayFirewall(unittest.TestCase):
    def snap(self, category, rules):
        return {"profiles": [{"alias": "Tailscale", "category": category}], "ips": [{"alias": "Tailscale", "ip": "100.101.102.103"}],
                "rules": rules}

    def test_firewall_answers(self):
        ip = "100.101.102.103"
        self.assertEqual(netcheck.away_firewall(ip, self.snap("Public", [])), "missing")
        self.assertEqual(netcheck.away_firewall(ip, self.snap("Public", [{"name": netcheck.RULE, "action": "Allow", "profile": "Private, Domain"}])), "missing")
        self.assertEqual(netcheck.away_firewall(ip, self.snap("Private", [{"name": netcheck.RULE, "action": "Allow", "profile": "Private, Domain"}])), "ok")
        self.assertEqual(netcheck.away_firewall(ip, self.snap("Public", [{"name": netcheck.RULE_AWAY, "action": "Allow", "profile": "Any"}])), "ok")
        self.assertEqual(netcheck.away_firewall(ip, self.snap("Public", [{"name": "x", "action": "Block", "profile": "Public"},
                                                                          {"name": netcheck.RULE_AWAY, "action": "Allow", "profile": "Any"}])), "blocked")
        self.assertIsNone(netcheck.away_firewall(ip, None))

    def test_the_fix_only_lets_tailscale_in(self):
        s = netcheck.fix_away_script()
        self.assertIn("-RemoteAddress '100.64.0.0/10','fd7a:115c:a1e0::/48'", s)
        self.assertIn("-Profile Any", s)
        self.assertIn("Remove-NetFirewallRule", s)


# ---------------------------------------------------------------- what a phone gets

def src(**kw):
    d = {"id": 1, "path": "/x.mkv", "runtime": 6000.0, "height": 1080, "kbps": 8000, "audio": 0, "phone_ok": False, "ext": ".mkv"}
    d.update(kw)
    return d


class Choosing(unittest.TestCase):
    def test_a_file_the_phone_cannot_play_is_converted(self):
        self.assertEqual(stream.choose(src(), "auto", True, False)[0], "high")       # at home
        self.assertEqual(stream.choose(src(), "auto", True, True)[0], "medium")      # away
        self.assertEqual(stream.choose(src(), "original", True, False)[0], "high")   # 'original' cannot play: still converted
        self.assertEqual(stream.choose(src(), "saver", True, False)[0], "saver")

    def test_a_file_that_plays_is_sent_as_it_is_when_it_suits(self):
        ok = src(phone_ok=True, ext=".mp4", kbps=2000, height=800)
        self.assertEqual(stream.choose(ok, "auto", True, False)[0], "direct")
        self.assertEqual(stream.choose(ok, "auto", True, True)[0], "direct")         # small enough for away too
        big = src(phone_ok=True, ext=".mp4", kbps=20000)
        self.assertEqual(stream.choose(big, "auto", True, False)[0], "direct")       # at home: the file itself
        self.assertEqual(stream.choose(big, "auto", True, True)[0], "medium")        # away: too big
        self.assertEqual(stream.choose(big, "original", True, True)[0], "direct")    # asked for
        self.assertEqual(stream.choose(ok, "high", True, True)[0], "direct")         # already smaller than High: no work
        self.assertEqual(stream.choose(ok, "saver", True, True)[0], "saver")

    def test_a_player_without_hls_gets_the_file_as_before(self):
        self.assertEqual(stream.choose(src(), "medium", False, True)[0], "direct")

    def test_converting_never_makes_it_bigger_or_sharper(self):
        p = stream.plan(src(height=480, kbps=900), "high")
        self.assertEqual(p["h"], 480)
        self.assertLess(p["v"], 1000)
        p = stream.plan(src(height=1080, kbps=20000), "medium")
        self.assertEqual((p["h"], p["v"]), (720, 3000))
        self.assertEqual(stream.plan(src(height=0, kbps=0), "low")["h"], 480)
        self.assertEqual(stream.plan(src(height=817, kbps=0), "high")["h"], 816)    # always even


class Playlist(unittest.TestCase):
    def test_every_piece_is_listed(self):
        text = stream.playlist(10.5, "k=abc")
        lines = text.splitlines()
        self.assertEqual(lines[0], "#EXTM3U")
        self.assertIn("#EXT-X-PLAYLIST-TYPE:VOD", lines)
        self.assertEqual(lines[-1], "#EXT-X-ENDLIST")
        segs = [x for x in lines if x.endswith(".ts?k=abc")]
        self.assertEqual(segs, ["0.ts?k=abc", "1.ts?k=abc", "2.ts?k=abc"])
        durs = [float(x[8:-1]) for x in lines if x.startswith("#EXTINF:")]
        self.assertEqual(durs, [4.0, 4.0, 2.5])
        self.assertEqual(stream.pieces(8.0), 2)
        self.assertEqual(stream.pieces(0), 1)


class FakeProc:
    def __init__(self, cmd, made, **kw):
        self.cmd, self.alive = cmd, True
        made.append(self)

    def poll(self):
        return None if self.alive else 0

    def kill(self):
        self.alive = False

    def wait(self, timeout=None):
        return 0


class SessionRules(unittest.TestCase):
    """When ffmpeg starts, where, and when it takes a break - with a pretend ffmpeg."""

    def setUp(self):
        d = tempfile.mkdtemp()
        self.cfg = Config(media_dir=Path(d), db_path=os.path.join(d, "t.sqlite3"))
        self.made = []
        self.s = stream.Session(self.cfg, src(runtime=400.0), "low", "ffmpeg", popen=lambda cmd, **kw: FakeProc(cmd, self.made), enc="libx264")
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))

    def put(self, *ns):
        for n in ns:
            open(self.s.file(n), "wb").write(b"ts")

    def arg(self, p, flag):
        return p.cmd[p.cmd.index(flag) + 1]

    def test_a_piece_that_is_there_needs_no_ffmpeg(self):
        self.put(0)
        self.assertEqual(self.s.get(0, wait=0), self.s.file(0))
        self.assertEqual(self.made, [])

    def test_a_missing_piece_starts_ffmpeg_exactly_there(self):
        self.assertIsNone(self.s.get(30, wait=0.05))
        p = self.made[-1]
        self.assertEqual((self.arg(p, "-ss"), self.arg(p, "-start_number"), self.arg(p, "-output_ts_offset")), ("120.000", "30", "120.000"))
        self.assertNotIn("-t", p.cmd)                                        # nothing after it yet: to the end
        self.assertIn("expr:gte(t,n_forced*4)", p.cmd)
        self.assertIn("0:a:0?", p.cmd)

    def test_it_stops_before_pieces_that_are_already_there(self):
        self.put(10, 11, 12)
        self.s.get(5, wait=0.05)
        self.assertEqual(self.arg(self.made[-1], "-t"), "20.000")            # pieces 5-9 only

    def test_a_jump_starts_a_new_run_and_close_pieces_wait(self):
        self.s.get(0, wait=0.05)
        first = self.made[-1]
        self.put(0, 1)
        self.s.get(2 + stream.AHEAD, wait=0.05)                              # just ahead of what is ready: wait for it
        self.assertEqual(len(self.made), 1)
        self.s.get(60, wait=0.05)                                            # a jump: new run there
        self.assertEqual(len(self.made), 2)
        self.assertFalse(first.alive)
        self.assertEqual(self.arg(self.made[-1], "-start_number"), "60")

    def test_it_takes_a_break_far_ahead_and_comes_back_in_time(self):
        self.s.get(0, wait=0.05)
        self.put(*range(0, stream.LEAD + 3))
        self.s.tidy(time.monotonic())
        self.assertFalse(self.s.running())                                   # far enough ahead of the phone: break
        self.s.want = stream.LEAD + 3 - stream.REFILL
        self.s.tidy(time.monotonic())
        self.assertTrue(self.s.running())                                    # the phone is catching up: more
        self.assertEqual(self.arg(self.made[-1], "-start_number"), str(stream.LEAD + 3))

    def test_idle_stops_then_forgets(self):
        self.s.get(0, wait=0.05)
        self.assertFalse(self.s.tidy(time.monotonic() + stream.IDLE_STOP + 1))
        self.assertFalse(self.s.running())
        self.assertTrue(self.s.tidy(time.monotonic() + stream.IDLE_DROP + 1))

    def test_out_of_range(self):
        self.assertIsNone(self.s.get(-1, wait=0))
        self.assertIsNone(self.s.get(self.s.total, wait=0))

    def test_quiet_and_loud_films_are_evened_out(self):
        s = stream.Session(self.cfg, src(), "low", "ffmpeg", gain_db=6.0, popen=lambda cmd, **kw: FakeProc(cmd, self.made), enc="libx264")
        self.assertIn("volume=6.0dB,alimiter=limit=0.9:level=disabled", s.command(0, s.total))
        self.assertNotIn("-af", self.s.command(0, self.s.total))

    def test_at_most_two_conversions_at_once(self):
        stream.stop_all()
        made = []
        ss = [stream.session(self.cfg, src(id=i, runtime=400.0), "low", "ffmpeg") for i in range(3)]
        for s in ss:
            s.popen, s.enc = (lambda cmd, **kw: FakeProc(cmd, made)), "libx264"
        for i, s in enumerate(ss):
            s.touched = time.monotonic() + i
            s.get(0, wait=0.01)
        self.assertEqual(sum(s.running() for s in ss), 2)
        self.assertFalse(ss[0].running())                                    # the least recently used one stopped
        stream.stop_all()

    def test_encoder_falls_back_to_the_processor(self):
        stream._enc.clear()
        calls = []

        def run(cmd, **kw):
            calls.append(cmd[cmd.index("-c:v") + 1])
            return subprocess.CompletedProcess(cmd, 1)
        self.assertEqual(stream.encoder("ffx", run=run, tmp=tempfile.mkdtemp()), "libx264")
        self.assertEqual(calls, ["h264_nvenc", "h264_qsv", "h264_amf"])
        stream._enc.clear()


@unittest.skipUnless(FF and FP, "needs ffmpeg")
class RealConversion(unittest.TestCase):
    """A real .mkv with Dolby sound (which an iPhone cannot open) converted piece by piece."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.d, ignore_errors=True))
        self.vid = os.path.join(self.d, "film.mkv")
        make_video(self.vid, 30)
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"))

    def test_pieces_line_up_on_the_grid_across_runs(self):
        s = stream.Session(self.cfg, src(path=self.vid, runtime=30.0, height=360, kbps=900), "saver", FF, enc="libx264")
        self.addCleanup(s.drop)
        f0 = s.get(0)
        self.assertIsNotNone(f0)
        base = start_time(f0)
        f5 = s.get(5)                                                        # made by the same run, or a new one
        self.assertAlmostEqual(start_time(f5) - base, 20.0, delta=0.15)
        s.stop()
        for n in (3, 4):                                                    # a gap before piece 5: filled by a run that stops at 4
            if os.path.exists(s.file(n)):
                os.remove(s.file(n))
        f3 = s.get(3)
        self.assertAlmostEqual(start_time(f3) - base, 12.0, delta=0.15)
        r = subprocess.run([FP, "-v", "error", "-show_entries", "stream=codec_name,height", "-of", "json", f3], capture_output=True, text=True)
        streams = json.loads(r.stdout)["streams"]
        self.assertEqual(sorted(x["codec_name"] for x in streams), ["aac", "h264"])          # what an iPhone plays
        self.assertEqual(next(x["height"] for x in streams if x["codec_name"] == "h264"), 360)
        last = s.get(s.total - 1)
        self.assertIsNotNone(last)


@unittest.skipUnless(FF and FP, "needs ffmpeg")
class ThroughTheNetworkPort(unittest.TestCase):
    """The whole path a phone takes: pair with a link, ask how to watch, fetch the list and the pieces."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.sf = Path(self.d) / "settings.json"
        p = mock.patch.object(config, "settings_file", return_value=self.sf)
        p.start()
        self.addCleanup(p.stop)
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"),
                          channels_file=str(Path(config.ROOT) / "config" / "channels.json"))
        self.cfg.port = free_pair_of_ports()
        self.vid = Path(self.d) / "Film.mkv"
        make_video(self.vid, 20)
        c = connect(self.cfg.db_path)
        c.execute("INSERT INTO media(path,title,verified,playable,available,runtime_s,vcodec,acodec,height,size) VALUES(?,?,1,1,1,20,'h264','ac3',360,?)",
                  (str(self.vid), "Film", os.path.getsize(self.vid)))
        c.commit()
        c.close()
        self.app = SV.App(self.cfg)
        self.addCleanup(self.app.stop_lan)
        self.addCleanup(stream.stop_all)
        R.set_enabled(True)
        for _ in range(8):
            try:
                self.app.start_lan()
                break
            except ValueError:
                self.cfg.port = free_pair_of_ports()
        self.lan = f"http://127.0.0.1:{R.lan_port(self.cfg)}"
        self.opener = urllib.request.build_opener(NoRedirect)
        away.clear_cache()
        self.addCleanup(away.clear_cache)

    def req(self, path, body=None, cookie=None, host=None):
        h = {}
        if body is not None:
            h["Content-Type"] = "application/json"
        if cookie:
            h["Cookie"] = f"{R.COOKIE}={cookie}"
        if host:
            h["Host"] = host
        r = urllib.request.Request(self.lan + path, None if body is None else json.dumps(body).encode(), h)
        try:
            resp = self.opener.open(r, timeout=60)
            return resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def test_a_phone_pairs_with_a_link_and_watches_an_mkv(self):
        st, body, hdr = self.req("/api/pair", {"link": R.make_link()})
        self.assertEqual(st, 200, body)
        tok = hdr["Set-Cookie"].split(";")[0].split("=", 1)[1]
        st, body, _ = self.req("/api/device", cookie=tok)
        mk = json.loads(body)["mk"]
        st, body, _ = self.req("/api/watch/1?q=auto&hls=1", cookie=tok)
        w = json.loads(body)
        self.assertEqual((st, w["mode"], w["quality"]), (200, "hls", "high"), w)
        self.assertIn(f"k={mk}", w["url"])
        st, body, _ = self.req("/api/watch/1?q=auto&hls=0", cookie=tok)
        self.assertEqual(json.loads(body)["mode"], "direct")               # a PC browser: the file as before
        # the iPhone's player asks with the media key, not the cookie
        st, body, hdr = self.req(w["url"])
        self.assertEqual(st, 200, body)
        self.assertEqual(hdr["Content-Type"], "application/vnd.apple.mpegurl")
        segs = [x for x in body.decode().splitlines() if ".ts" in x]
        self.assertEqual(len(segs), 5)
        self.assertTrue(all(f"k={mk}" in x for x in segs))
        base = w["url"].split("index.m3u8")[0]
        st, body, hdr = self.req(base + segs[2])
        self.assertEqual((st, hdr["Content-Type"]), (200, "video/mp2t"))
        self.assertGreater(len(body), 1000)
        self.assertEqual(self.req(base + "2.ts")[0], 401)                    # no key, no cookie: no video
        self.assertEqual(self.req(base + "2.ts?k=wrong")[0], 401)
        self.assertEqual(self.req("/stream/1/medium/../../t.sqlite3")[0] in (401, 404), True)
        self.assertEqual(self.req("/stream/1/ultra/index.m3u8", cookie=tok)[0], 404)

    def test_a_paired_phone_gets_links_for_its_home_screen_and_for_away(self):
        st, body, hdr = self.req("/api/pair", {"link": R.make_link()})
        tok = hdr["Set-Cookie"].split(";")[0].split("=", 1)[1]
        st, body, _ = self.req("/api/device/link", {"for": "home"}, cookie=tok, host="192.168.12.198:8788")
        j = json.loads(body)
        self.assertEqual(st, 200, body)
        self.assertTrue(j["url"].startswith("http://192.168.12.198:8788/pair?t=") and j["url"].endswith("&home=1"))
        st, body, _ = self.req("/api/device/link", {"for": "away"}, cookie=tok)
        self.assertEqual(st, 400)
        self.assertIn("Tailscale is not set up", json.loads(body)["error"])
        with mock.patch.object(away, "status", return_value=dict(away.parse(STATUS), installed=True, words="")):
            st, body, _ = self.req("/api/device/link", {"for": "away"}, cookie=tok)
            url = json.loads(body)["url"]
            self.assertTrue(url.startswith(f"http://100.101.102.103:{R.lan_port(self.cfg)}/pair?t="), url)
            # the link pairs a second 'device' (the same phone on its away address), once
            t = url.split("t=")[1]
            st, _, _ = self.req("/api/pair", {"link": t}, host=f"100.101.102.103:{R.lan_port(self.cfg)}")
            self.assertEqual(st, 200)
            self.assertEqual(self.req("/api/pair", {"link": t})[0], 403)
        self.assertEqual(self.req("/api/device/link", {"for": "away"})[0], 401)      # only a paired device may ask
        self.assertEqual(self.req("/icon.png")[0], 200)                              # the Home Screen icon, before pairing

    def test_settings_on_the_pc_show_the_away_card(self):
        with mock.patch.object(away, "status", return_value=dict(away.parse(STATUS), installed=True, words="Ready.")):
            r = urllib.request.Request(f"http://127.0.0.1:{self.cfg.port}/api/devices")
            srv = SV._TVServer(("127.0.0.1", 0), SV.make_handler(self.app))
            import threading
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.addCleanup(srv.shutdown)
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            d = json.loads(urllib.request.urlopen(base + "/api/devices", timeout=20).read())
            self.assertEqual(d["away"]["url"], f"http://100.101.102.103:{R.lan_port(self.cfg)}")
            self.assertEqual(d["away"]["url_name"], f"http://desktop-f3nlp4n.tail1234.ts.net:{R.lan_port(self.cfg)}")
            r = urllib.request.Request(base + "/api/devices", json.dumps({"op": "away-qr"}).encode(), {"Content-Type": "application/json"})
            d = json.loads(urllib.request.urlopen(r, timeout=20).read())
            self.assertIn("<svg", d["away"]["qr"])
            self.assertIn("/pair?t=", d["away"]["link"])
            self.assertTrue(R.link_ok(d["away"]["link"].split("t=")[1]))


if __name__ == "__main__":
    unittest.main()
