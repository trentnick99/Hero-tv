"""Live TV in other apps: M3U, XMLTV guide, HDHomeRun look-alike and the live MPEG-TS stream."""
import io
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
from herotv import config, iptv, remote as R, scheduler as S, server as SV, tools  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402


class IptvTests(unittest.TestCase):
    def setUp(self):
        from test_remote import free_pair_of_ports
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.sf = Path(self.d) / "settings.json"
        self.sf.write_text('{"lan_share": true}')
        p = mock.patch.object(config, "settings_file", return_value=self.sf)
        p.start(); self.addCleanup(p.stop)
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"),
                          channels_file=str(Path(config.ROOT) / "config" / "channels.json"))
        self.cfg.port = free_pair_of_ports()
        self.cfg.tz = "UTC"
        os.makedirs(os.path.join(self.d, "MCU"))
        self.vid = Path(self.d) / "MCU" / "Iron Man (2008).mp4"
        ff = tools.find_tool("ffmpeg")
        if ff:
            subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25", "-f", "lavfi", "-i",
                            "sine=f=440", "-t", "6", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", str(self.vid)], check=True)
        else:
            self.vid.write_bytes(b"0" * 1000)
        c = connect(self.cfg.db_path)
        c.execute("INSERT INTO media(path,title,year,franchise,verified,playable,available,runtime_s,vcodec,acodec,plot) "
                  "VALUES(?,?,?,?,1,1,1,6,'h264','aac','Tony & co.')", (str(self.vid), "Iron Man", 2008, "MCU"))
        c.commit()
        S.sync_channels(c, json.load(open(self.cfg.channels_file, encoding="utf-8-sig"))["channels"], tz="UTC")
        S.extend_all(c, time.time(), 3600, tz="UTC")
        c.close()
        self.app = SV.App(self.cfg)
        self.app.start_lan()
        self.addCleanup(self.app.stop_lan)
        self.lan = f"http://127.0.0.1:{R.lan_port(self.cfg)}"

    def get(self, path):
        with urllib.request.urlopen(self.lan + path, timeout=10) as r:
            return r.read()

    def test_off_by_default_and_keyed(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/discover.json")
        self.assertEqual(cm.exception.code, 404)
        iptv.set_enabled(True)
        k = iptv.key()
        self.assertGreaterEqual(len(k), 16)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/iptv/wrongkeywrongkeywrong/channels.m3u")
        self.assertEqual(cm.exception.code, 404)
        disc = json.loads(self.get("/discover.json"))
        self.assertEqual(disc["LineupURL"], f"{self.lan}/iptv/{k}/lineup.json")
        lineup = json.loads(self.get(f"/iptv/{k}/lineup.json"))
        self.assertEqual(lineup[0]["GuideName"], "Marvel Movies")
        self.assertNotIn("Weather", [x["GuideName"] for x in lineup])
        self.assertTrue(lineup[0]["URL"].endswith("/ch/mcu.ts"))
        m3u = self.get(f"/iptv/{k}/channels.m3u").decode()
        self.assertIn('tvg-id="mcu"', m3u)
        self.assertIn(f"/iptv/{k}/guide.xml", m3u)
        self.assertEqual(self.get("/tv.m3u").decode(), m3u)                        # the short address
        self.assertIn(b"<tv ", self.get("/tv.xml"))
        xml = self.get(f"/iptv/{k}/guide.xml").decode()
        self.assertIn("<title>Iron Man</title>", xml)
        self.assertIn("Tony &amp; co.", xml)
        import xml.etree.ElementTree as ET
        ET.fromstring(xml)                                                   # well-formed
        iptv.set_enabled(False)
        with self.assertRaises(urllib.error.HTTPError):
            self.get(f"/iptv/{k}/channels.m3u")

    @unittest.skipUnless(tools.find_tool("ffmpeg"), "needs ffmpeg")
    def test_live_stream_is_mpeg_ts(self):
        iptv.set_enabled(True)
        k = iptv.key()
        r = urllib.request.urlopen(f"{self.lan}/iptv/{k}/ch/mcu.ts", timeout=20)
        self.assertEqual(r.headers["Content-Type"], "video/mp2t")
        data = r.read(188 * 40)
        r.close()
        self.assertEqual(data[0], 0x47)                                      # MPEG-TS sync byte
        self.assertEqual(data[188], 0x47)

    def test_ffmpeg_commands(self):
        m = {"path": "/x.mkv", "vcodec": "h264", "acodec": "dts"}
        cmd = iptv.ffmpeg_cmd("ffmpeg", {}, m, 12.5, 100, 30)
        self.assertEqual(cmd[cmd.index("-c:v") + 1], "copy")
        self.assertEqual(cmd[cmd.index("-c:a") + 1], "aac")                 # DTS is converted
        self.assertEqual(cmd[cmd.index("-ss") + 1], "12.500")
        self.assertEqual(cmd[cmd.index("-output_ts_offset") + 1], "30.000")
        vp9 = iptv.ffmpeg_cmd("ffmpeg", {}, {"path": "/x.webm", "vcodec": "vp9", "acodec": "opus"}, 0, 10, 0)
        self.assertEqual(vp9[vp9.index("-c:v") + 1], "libx264")
        card = iptv.ffmpeg_cmd("ffmpeg", None, None, 0, 30, 0)
        self.assertIn("anullsrc=r=48000:cl=stereo", card)

    def test_stream_follows_the_schedule(self):
        calls, out = [], io.BytesIO()

        class P:
            def __init__(self, cmd, **kw):
                calls.append(cmd)
                self.stdout = io.BytesIO(b"\x47" * 188)

            def kill(self):
                pass

            def wait(self, timeout=None):
                return 0
        iptv.stream_channel(self.app, "mcu", out.write, "ffmpeg", popen=P, max_parts=2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(out.getvalue()[:1], b"\x47")
        self.assertIn(str(self.vid), calls[0])


if __name__ == "__main__":
    unittest.main()
