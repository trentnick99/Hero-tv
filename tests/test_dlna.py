import json
import os
import re
import socket
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import config, dlna, server as SV  # noqa: E402
from herotv.config import Config  # noqa: E402
from herotv.db import connect  # noqa: E402

NS = {"d": "urn:schemas-upnp-org:device-1-0", "didl": "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/",
      "dc": "http://purl.org/dc/elements/1.1/", "upnp": "urn:schemas-upnp-org:metadata-1-0/upnp/"}
UID = "12345678-1234-1234-1234-123456789abc"


def msearch(st, man='"ssdp:discover"'):
    return (f"M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: {man}\r\nMX: 1\r\nST: {st}\r\n\r\n").encode()


class SsdpTests(unittest.TestCase):
    def test_answers(self):
        self.assertEqual(len(dlna.answers(msearch("ssdp:all"), 8789, "192.168.1.20", UID)), 5)
        r = dlna.answers(msearch(dlna.DEVICE), 8789, "192.168.1.20", UID)
        self.assertEqual(len(r), 1)
        t = r[0].decode()
        self.assertIn("LOCATION: http://192.168.1.20:8789/dlna/description.xml", t)
        self.assertIn(f"USN: uuid:{UID}::{dlna.DEVICE}", t)
        self.assertEqual(dlna.answers(msearch("urn:schemas-upnp-org:device:MediaRenderer:1"), 8789, "x", UID), [])
        self.assertEqual(dlna.answers(msearch("ssdp:all", man="nope"), 8789, "x", UID), [])
        self.assertEqual(dlna.answers(b"NOTIFY * HTTP/1.1\r\n\r\n", 8789, "x", UID), [])
        self.assertEqual(dlna.answers(b"\xff\xfe garbage", 8789, "x", UID), [])
        self.assertTrue(all(b"NTS: ssdp:byebye" in p for p in dlna.notify("byebye", 8789, "x", UID)))


class DlnaServerTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.sf = Path(self.d) / "settings.json"
        p = mock.patch.object(config, "settings_file", return_value=self.sf)
        p.start(); self.addCleanup(p.stop)
        self.cfg = Config(media_dir=Path(self.d), db_path=os.path.join(self.d, "t.sqlite3"), channels_file=None)
        s = socket.socket(); s.bind(("127.0.0.1", 0)); self.cfg.port = s.getsockname()[1] - 2 if s.getsockname()[1] > 3000 else 40000; s.close()
        c = connect(self.cfg.db_path)
        self.files = {}
        for i, (title, fr, series, se, ep, ext) in enumerate((("Iron Man", "MCU", "", 0, 0, ".mp4"), ("Thor", "MCU", "", 0, 0, ".mkv"),
                                                               ("Ep1", "South Park", "South Park", 1, 1, ".mp4"),
                                                               ("Ep2", "South Park", "South Park", 1, 2, ".mp4"))):
            f = Path(self.d) / f"{title}{ext}"; f.write_bytes(bytes(range(256)) * 4)
            c.execute("INSERT INTO media(path,title,year,franchise,series,season,episode,verified,playable,available,runtime_s,size,added) "
                      "VALUES(?,?,?,?,?,?,?,1,1,1,3725.5,1024,?)", (str(f), title, 2008 + i, fr, series, se, ep, int(time.time()) if i == 0 else 0))
        c.commit(); c.close()
        self.app = SV.App(self.cfg)
        dlna.set_enabled(True)
        with mock.patch.object(dlna, "Announcer", side_effect=OSError("no multicast in tests")):
            self.app.dlna.start()
        self.addCleanup(self.app.dlna.stop)
        self.base = f"http://127.0.0.1:{dlna.port(self.cfg)}"

    def req(self, path, data=None, headers=None, method=None):
        r = urllib.request.Request(self.base + path, data, headers or {}, method=method)
        try:
            resp = urllib.request.urlopen(r, timeout=10)
            return resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def browse(self, oid, flag="BrowseDirectChildren", start=0, count=0):
        body = (f'<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
                f'<u:Browse xmlns:u="{dlna.CDS}"><ObjectID>{oid}</ObjectID><BrowseFlag>{flag}</BrowseFlag><Filter>*</Filter>'
                f'<StartingIndex>{start}</StartingIndex><RequestedCount>{count}</RequestedCount><SortCriteria></SortCriteria>'
                f'</u:Browse></s:Body></s:Envelope>').encode()
        st, raw, _ = self.req("/dlna/control/cds", body, {"Content-Type": 'text/xml; charset="utf-8"', "SOAPACTION": f'"{dlna.CDS}#Browse"'})
        return st, raw

    def didl(self, raw):
        env = ET.fromstring(raw)
        result = env.find(".//Result").text
        total = int(env.find(".//TotalMatches").text)
        return ET.fromstring(result), total

    def test_description_and_service_documents_are_valid_xml(self):
        st, raw, h = self.req("/dlna/description.xml")
        self.assertEqual(st, 200)
        root = ET.fromstring(raw)
        self.assertEqual(root.find(".//d:deviceType", NS).text, dlna.DEVICE)
        self.assertTrue(root.find(".//d:UDN", NS).text.startswith("uuid:"))
        self.assertIn("(HERO TV)", root.find(".//d:friendlyName", NS).text)
        for p in ("/dlna/cds.xml", "/dlna/cms.xml"):
            st, raw, _ = self.req(p)
            self.assertEqual(st, 200); ET.fromstring(raw)

    def test_browse_tree(self):
        st, raw = self.browse("0")
        self.assertEqual(st, 200)
        d, total = self.didl(raw)
        titles = [c.find("dc:title", NS).text for c in d.findall("didl:container", NS)]
        self.assertEqual(titles, ["New in your library", "MCU", "South Park"])
        d, total = self.didl(self.browse("f:MCU")[1])
        items = d.findall("didl:item", NS)
        self.assertEqual([i.find("dc:title", NS).text for i in items], ["Iron Man (2008)", "Thor (2009)"])
        res = items[1].find("didl:res", NS)
        self.assertIn("video/x-matroska", res.get("protocolInfo"))
        self.assertEqual(res.get("duration"), "1:02:05.500")
        self.assertRegex(res.text, r"^http://127\.0\.0\.1:\d+/dlna/media/\d+\.mkv$")
        d, _ = self.didl(self.browse("f:South Park")[1])
        show = d.find("didl:container", NS)
        self.assertEqual(show.find("dc:title", NS).text, "South Park")
        d, _ = self.didl(self.browse(show.get("id"))[1])
        self.assertEqual([i.find("dc:title", NS).text for i in d.findall("didl:item", NS)],
                         ["South Park S1E1 - Ep1", "South Park S1E2 - Ep2"])
        d, total = self.didl(self.browse("f:MCU", start=1, count=1)[1])            # paging
        self.assertEqual((len(d.findall("didl:item", NS)), total), (1, 2))
        d, total = self.didl(self.browse("0", "BrowseMetadata")[1])
        self.assertEqual(d.find("didl:container", NS).get("id"), "0")

    def test_bad_requests(self):
        st, raw = self.browse("f:Nope")
        self.assertEqual(st, 500); self.assertIn(b"<errorCode>701</errorCode>", raw)
        st, raw = self.browse("&lt;!ENTITY x SYSTEM 'file:///etc/passwd'&gt;")       # never expanded, just not found
        self.assertEqual(st, 500)
        st, _, _ = self.req("/dlna/control/cds", b"x" * (dlna.MAX_SOAP + 1), {"SOAPACTION": f'"{dlna.CDS}#Browse"'})
        self.assertEqual(st, 413)
        for p in ("/", "/api/settings", "/dlna/media/999.mp4", "/dlna/media/../../etc/passwd", "/media/1"):
            self.assertEqual(self.req(p)[0], 404, p)

    def test_media_ranges_and_dlna_headers(self):
        st, raw, h = self.req("/dlna/media/1.mp4", headers={"Range": "bytes=10-19"})
        self.assertEqual((st, raw, h["Content-Range"]), (206, bytes(range(10, 20)), "bytes 10-19/1024"))
        self.assertEqual(h["transferMode.dlna.org"], "Streaming")
        st, raw, h = self.req("/dlna/media/1.mp4", method="HEAD")
        self.assertEqual((st, raw, h["Content-Length"]), (200, b"", "1024"))
        self.assertEqual(self.req("/dlna/media/1.mp4", headers={"Range": "bytes=5000-"})[0], 416)
        self.assertEqual(self.req("/dlna/thumb/1.jpg")[0], 404)                       # no screengrab made in this test

    def test_subscribe_and_switch_off(self):
        st, _, h = self.req("/dlna/event/cds", method="SUBSCRIBE")
        self.assertEqual(st, 200); self.assertTrue(h["SID"].startswith("uuid:"))
        dlna.set_enabled(False)
        self.assertEqual(self.req("/dlna/description.xml")[0], 503)

    def test_upnp_client_library_can_browse(self):
        try:
            import asyncio
            from async_upnp_client.aiohttp import AiohttpRequester
            from async_upnp_client.client_factory import UpnpFactory
        except ImportError:
            self.skipTest("async-upnp-client not installed (installed in CI)")

        async def run():
            req = AiohttpRequester()
            dev = await UpnpFactory(req, non_strict=True).async_create_device(self.base + "/dlna/description.xml")
            svc = dev.service("urn:schemas-upnp-org:service:ContentDirectory:1")
            out = await svc.action("Browse").async_call(ObjectID="0", BrowseFlag="BrowseDirectChildren", Filter="*",
                                                         StartingIndex=0, RequestedCount=0, SortCriteria="")
            return dev.friendly_name, out
        name, out = asyncio.run(run())
        self.assertIn("HERO TV", name)
        self.assertEqual(out["TotalMatches"], 3)
        self.assertIn("South Park", out["Result"])


class LiveSsdpTest(unittest.TestCase):
    def test_answers_a_real_search_packet(self):
        try:
            ann = dlna.Announcer(8789, UID)
        except OSError as e:
            self.skipTest(f"cannot open the SSDP port here: {e}")
        import threading
        t = threading.Thread(target=ann.run, daemon=True); t.start()
        self.addCleanup(ann.stop)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(3)
        s.sendto(msearch(dlna.DEVICE), ("127.0.0.1", dlna.SSDP_PORT))
        try:
            data, _ = s.recvfrom(4096)
        except socket.timeout:
            self.skipTest("no SSDP reply on this machine's loopback (multicast-only networking)")
        self.assertIn(b"/dlna/description.xml", data)
        self.assertIn(dlna.DEVICE.encode(), data)


if __name__ == "__main__":
    unittest.main()
