"""The HERO TV app for Roku TVs: finding the TV, building the app, installing it, and what the app asks the PC."""
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import __version__, config, remote as R, roku, scheduler as S, server as SV  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402

DEVICE_INFO = b"""<?xml version="1.0" encoding="UTF-8" ?>
<device-info><udn>x</udn><model-name>65R635</model-name><friendly-model-name>TCL 6-Series</friendly-model-name>
<user-device-name>Living Room TV</user-device-name><developer-enabled>true</developer-enabled></device-info>"""


class FakeSock:
    def __init__(self, replies):
        self.replies, self.sent = list(replies), []

    def settimeout(self, t):
        pass

    def setsockopt(self, *a):
        pass

    def sendto(self, data, addr):
        self.sent.append((data, addr))

    def recvfrom(self, n):
        if self.replies:
            return self.replies.pop(0)
        time.sleep(0.05)
        raise socket.timeout()


class Page:
    def __init__(self, text):
        self.text = text

    def read(self):
        return self.text.encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    def __init__(self, page=None, error=None):
        self.page, self.error, self.reqs = page, error, []

    def open(self, req, timeout=0):
        self.reqs.append(req)
        if self.error:
            raise self.error
        return Page(self.page)


class RokuTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        p = mock.patch.object(config, "settings_file", return_value=Path(self.d) / "settings.json")
        p.start(); self.addCleanup(p.stop)
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"))
        self.cfg.port = 8787
        self.c = connect(self.cfg.db_path)
        self.addCleanup(self.c.close)
        q = mock.patch.object(R, "lan_addresses", return_value=["192.168.12.20"])
        q.start(); self.addCleanup(q.stop)

    def test_device_info(self):
        info = roku.device_info("192.168.12.40", fetch=lambda u: DEVICE_INFO)
        self.assertEqual(info, {"ip": "192.168.12.40", "name": "Living Room TV", "model": "TCL 6-Series", "dev": True})
        self.assertIsNone(roku.device_info("8.8.8.8", fetch=lambda u: DEVICE_INFO))          # home network only
        self.assertIsNone(roku.device_info("192.168.12.40", fetch=lambda u: b"<not xml"))

    def test_discover(self):
        reply = (b"HTTP/1.1 200 OK\r\nST: roku:ecp\r\nLOCATION: http://192.168.12.40:8060/\r\nUSN: uuid:roku:ecp:X\r\n\r\n", ("192.168.12.40", 1900))
        other = (b"HTTP/1.1 200 OK\r\nST: upnp:rootdevice\r\nLOCATION: http://192.168.12.9:80/\r\n\r\n", ("192.168.12.9", 1900))
        sock = FakeSock([reply, other, reply])
        with mock.patch.object(roku, "device_info", side_effect=lambda ip: {"ip": ip, "name": "Living Room TV", "model": "", "dev": True}):
            found = roku.discover(timeout=0.3, sock=sock)
        self.assertEqual([f["ip"] for f in found], ["192.168.12.40"])
        self.assertIn(b"ST: roku:ecp", sock.sent[0][0])

    def test_build_zip(self):
        z = zipfile.ZipFile(io.BytesIO(roku.build_zip("http://192.168.12.20:8788", 'tok"en', "mk1", 'My "TV"', "#ff0000")))
        names = z.namelist()
        for want in ("manifest", "source/main.brs", "source/config.brs", "components/MainScene.xml", "components/ApiTask.brs", "images/icon_fhd.png"):
            self.assertIn(want, names)
        cfg = z.read("source/config.brs").decode()
        self.assertIn('server: "http://192.168.12.20:8788"', cfg)
        self.assertIn('token: "tok""en"', cfg)                                                 # quotes escaped for BrightScript
        self.assertIn('station: "My ""TV"""', cfg)
        self.assertIn(f"build_version={roku.build_number()}", z.read("manifest").decode())
        self.assertEqual(roku.build_number("1.16.2"), 11602)

    def test_install_results(self):
        zipb = b"PK"
        ok = FakeOpener("<html><font color='red'>Install Success.</font></html>")
        self.assertEqual(roku.install("192.168.12.40", "pw", zipb, ok), "installed")
        req = ok.reqs[0]
        self.assertEqual(req.full_url, "http://192.168.12.40/plugin_install")
        self.assertIn(b'name="mysubmit"', req.data)
        self.assertIn(b'name="archive"; filename="herotv.zip"', req.data)
        self.assertEqual(roku.install("192.168.12.40", "pw", zipb, FakeOpener("Identical to previous version -- not replacing.")), "already up to date")
        with self.assertRaisesRegex(ValueError, "manifest is missing"):
            roku.install("192.168.12.40", "pw", zipb, FakeOpener("Install Failure: manifest is missing"))
        with self.assertRaisesRegex(ValueError, "password"):
            roku.install("192.168.12.40", "pw", zipb, FakeOpener(error=urllib.error.HTTPError("u", 401, "no", {}, None)))
        with self.assertRaisesRegex(ValueError, "developer mode"):
            roku.install("192.168.12.40", "pw", zipb, FakeOpener(error=urllib.error.URLError("refused")))
        with self.assertRaises(ValueError):
            roku.install("example.com", "pw", zipb, ok)
        with self.assertRaises(ValueError):
            roku.install("192.168.12.40", "", zipb, ok)

    def test_install_on_tv_pairs_remembers_and_replaces_its_key(self):
        res = roku.install_on_tv(self.c, self.cfg, "192.168.12.40", "pw", "Living Room TV", FakeOpener("Install Success"), launcher=lambda ip: True)
        self.assertEqual(res, {"result": "installed", "server": "http://192.168.12.20:8788", "started": True})
        devs = R.devices(self.c)
        self.assertEqual(len(devs), 1)
        self.assertIn("Roku TV", devs[0]["name"])
        sv = roku.saved("192.168.12.40")
        self.assertEqual((sv["ip"], sv["password"], sv["installed"], sv["key_id"]), ("192.168.12.40", "pw", __version__, devs[0]["id"]))
        self.assertEqual(roku.needs_update(self.cfg, sv), "")
        roku.install_on_tv(self.c, self.cfg, "192.168.12.40", "pw", "", FakeOpener("Install Success"), launcher=lambda ip: True)
        self.assertEqual(len(R.devices(self.c)), 1)                                          # the old key is gone
        with self.assertRaises(ValueError):
            roku.install_on_tv(self.c, self.cfg, "192.168.12.40", "bad", "", FakeOpener(error=urllib.error.HTTPError("u", 401, "no", {}, None)))
        self.assertEqual(len(R.devices(self.c)), 1)                                          # a failed install leaves no key

    def test_every_tv_in_the_house_keeps_its_own_key(self):
        ok = FakeOpener("Install Success")
        roku.install_on_tv(self.c, self.cfg, "192.168.12.40", "pw1", "Living Room TV", ok, launcher=lambda ip: True)
        roku.install_on_tv(self.c, self.cfg, "192.168.12.41", "pw2", "Bedroom TV", ok, launcher=lambda ip: True)
        self.assertEqual([t["name"] for t in roku.tvs()], ["Bedroom TV", "Living Room TV"])
        self.assertEqual(len(R.devices(self.c)), 2)                                          # the second TV did not knock out the first
        roku.install_on_tv(self.c, self.cfg, "192.168.12.41", "pw2", "", ok, launcher=lambda ip: True)
        self.assertEqual(len(R.devices(self.c)), 2)                                          # updating one replaces only its own key
        self.assertEqual(roku.saved("192.168.12.41")["name"], "Bedroom TV")
        roku.forget("192.168.12.41")
        self.assertEqual([t["ip"] for t in roku.tvs()], ["192.168.12.40"])

    def test_an_older_single_tv_setting_is_moved_over(self):
        (Path(self.d) / "settings.json").write_text(json.dumps({"roku": {"ip": "192.168.12.40", "name": "Old TV", "password": "pw",
                                                                         "installed": "1.16.0", "server": "http://192.168.12.20:8788"}}))
        self.assertEqual([t["name"] for t in roku.tvs()], ["Old TV"])
        roku.remember("192.168.12.41", name="New TV")
        d = json.loads((Path(self.d) / "settings.json").read_text())
        self.assertNotIn("roku", d)
        self.assertEqual(sorted(d["rokus"]), ["192.168.12.40", "192.168.12.41"])

    def test_needs_update(self):
        tv = {"ip": "192.168.12.40", "password": "pw", "installed": "1.0.0", "server": "http://192.168.12.20:8788"}
        self.assertEqual(roku.needs_update(self.cfg, {}), "")
        self.assertEqual(roku.needs_update(self.cfg, tv), "HERO TV was updated")
        tv.update(installed=__version__, server="http://192.168.12.99:8788")
        self.assertEqual(roku.needs_update(self.cfg, tv), "this PC's network address changed")


class TvEndpointTests(unittest.TestCase):
    """What the Roku app asks the PC, through the paired-devices listener."""
    def setUp(self):
        from test_remote import free_pair_of_ports
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        sf = Path(self.d) / "settings.json"
        sf.write_text('{"lan_share": true}')
        p = mock.patch.object(config, "settings_file", return_value=sf)
        p.start(); self.addCleanup(p.stop)
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"),
                          channels_file=str(Path(config.ROOT) / "config" / "channels.json"))
        self.cfg.port = free_pair_of_ports()
        self.cfg.tz = "UTC"
        c = connect(self.cfg.db_path)
        os.makedirs(os.path.join(self.d, "MCU"))
        vid = Path(self.d) / "MCU" / "Iron Man (2008).mkv"; vid.write_bytes(b"0123456789" * 100)
        (Path(self.d) / "MCU" / "Iron Man (2008).en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")
        c.execute("INSERT INTO media(path,title,year,franchise,verified,playable,available,runtime_s) VALUES(?,?,?,?,1,1,1,600)",
                  (str(vid), "Iron Man", 2008, "MCU"))
        c.commit()
        S.sync_channels(c, json.load(open(self.cfg.channels_file, encoding="utf-8-sig"))["channels"], tz="UTC")
        S.extend_all(c, time.time(), 12 * 3600, tz="UTC")                                     # as HERO TV does when it starts
        self.tok, self.mk = R.add_device(c, roku.DEVICE_NAME)
        c.close()
        self.app = SV.App(self.cfg)
        self.app.start_lan()
        self.addCleanup(self.app.stop_lan)
        self.lan = f"http://127.0.0.1:{R.lan_port(self.cfg)}"

    def get(self, path, cookie=True):
        h = {"Cookie": f"{R.COOKIE}={self.tok}"} if cookie else {}
        with urllib.request.urlopen(urllib.request.Request(self.lan + path, headers=h), timeout=10) as r:
            return r.read()

    def test_tv_now_has_the_file_type_and_subtitles(self):
        j = json.loads(self.get("/api/tv/mcu"))
        slot = j["slot"]
        self.assertEqual((slot["title"], slot["ext"]), ("Iron Man", "mkv"))
        self.assertEqual(slot["subs"][0]["url"], f"/sub/{slot['media_id']}/x0.vtt")
        self.assertIsInstance(j["offset"], (int, float))
        video = self.get(f"/media/{slot['media_id']}.mkv?k={self.mk}", cookie=False)            # the extension the Roku needs
        self.assertEqual(video, b"0123456789" * 100)
        head = urllib.request.Request(f"{self.lan}/media/{slot['media_id']}.mkv?k={self.mk}", method="HEAD")
        with urllib.request.urlopen(head, timeout=10) as r:                                     # players ask for the size first
            self.assertEqual((r.status, r.headers["Content-Length"], r.read()), (200, "1000", b""))
        self.assertIn(b"Hello", self.get(f"/sub/{slot['media_id']}/x0.vtt?k={self.mk}", cookie=False))
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/api/tv/mcu", cookie=False)                                              # unpaired: refused
        self.assertEqual(cm.exception.code, 401)

    def test_the_tv_can_read_the_guide(self):
        now = int(time.time())
        j = json.loads(self.get(f"/api/guide?hours=12&from={now - now % 1800}"))
        mcu = [c for c in j["channels"] if c["id"] == "mcu"][0]
        self.assertTrue(mcu["slots"] and mcu["slots"][0]["title"] == "Iron Man")
        self.assertTrue(all(k in mcu["slots"][0] for k in ("start", "end", "start_local", "end_local")))

    def test_seen_from_the_tv_counts(self):
        mid = json.loads(self.get("/api/tv/mcu"))["slot"]["media_id"]
        r = urllib.request.Request(self.lan + "/api/seen", json.dumps({"media_id": mid, "secs": 30}).encode(),
                                   {"Content-Type": "application/json", "Cookie": f"{R.COOKIE}={self.tok}"})
        urllib.request.urlopen(r, timeout=10).read()
        c = connect(self.cfg.db_path)
        self.addCleanup(c.close)
        self.assertEqual(c.execute("SELECT secs FROM seen WHERE media_id=?", (mid,)).fetchone()[0], 30)


if __name__ == "__main__":
    unittest.main()
