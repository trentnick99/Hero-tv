import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import add, make_db, T0  # noqa: E402
from herotv import freecontent as F, scheduler as S  # noqa: E402

PD = "http://creativecommons.org/publicdomain/mark/1.0/"


def item(ident, title, lic=PD, year="1941"):
    return {"identifier": ident, "title": title, "year": year, "licenseurl": lic, "downloads": 100}


def meta(files, lic=PD, desc="<p>A <b>cartoon</b>&nbsp;from long ago.</p>"):
    return {"metadata": {"licenseurl": lic, "description": desc}, "files": files}


def f(name, size, fmt="h.264"):
    return {"name": name, "size": str(size), "format": fmt}


class HelperTests(unittest.TestCase):
    def test_license_only_public_domain(self):
        self.assertTrue(F.license_ok(PD))
        self.assertTrue(F.license_ok(["https://creativecommons.org/publicdomain/zero/1.0/"]))
        for bad in (None, "", "http://creativecommons.org/licenses/by-nc/3.0/", "All rights reserved"):
            self.assertFalse(F.license_ok(bad), bad)

    def test_query_has_license_filter(self):
        q = F.build_query({"query": "collection:classic_cartoons"})
        self.assertIn("mediatype:movies", q)
        self.assertIn("publicdomain/mark", q)

    def test_pick_file_prefers_h264_and_respects_cap(self):
        files = [f("a.ogv", 10, "Ogg Video"), f("a_thumb.mp4", 5), f("a.mp4", 900), f("a_512kb.mp4", 100, "512Kb MPEG4"),
                 f("a_big.mp4", 5000, "h.264 HD"), f("sub/x.mp4", 50)]
        self.assertEqual(F.pick_file(meta(files), 2000), ("a.mp4", 900))
        self.assertEqual(F.pick_file(meta(files), 500), ("a_512kb.mp4", 100))
        self.assertIsNone(F.pick_file(meta([f("a.ogv", 10)]), 2000))
        self.assertIsNone(F.pick_file(meta([f("a.mp4", 9999)]), 2000))

    def test_names_and_descriptions(self):
        self.assertEqual(F.safe_name('Bad: "name"/with*chars?', 1941), "Bad name with chars (1941)")
        self.assertEqual(F.safe_name("...", None), "Untitled")
        self.assertEqual(F.clean_description("<p>A <b>cartoon</b>&nbsp;ok.</p>"), "A cartoon ok.")

    def test_sources_file(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "s.json")
        self.assertEqual(F.load_sources(p)[0]["name"], F.DEFAULT_SOURCES[0]["name"])      # missing file: defaults
        json.dump({"sources": [{"name": "Mine", "query": "subject:robots", "tags": ["x"]}]}, open(p, "w"))
        self.assertEqual(F.load_sources(p), [{"name": "Mine", "query": "subject:robots", "tags": ["x"]}])
        json.dump({"sources": [{"name": "No query"}]}, open(p, "w"))
        with self.assertRaises(ValueError):
            F.load_sources(p)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(F.load_sources(os.path.join(root, "config", "free-sources.json")))   # the shipped file is valid


class FetchTests(unittest.TestCase):
    """The whole flow, with the two network functions replaced by canned Internet Archive answers."""

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.saved = (F.fetch_json, F.download)
        self.downloads = []
        self.docs = [item("sup1", "Superman: The Mechanical Monsters"), item("nolic", "Not free", lic="All rights reserved"),
                     item("pop1", "Popeye Meets Sindbad")]
        self.metas = {"sup1": meta([f("sup1.mp4", 1000)]), "pop1": meta([f("pop1.mp4", 2000)]),
                      "nolic": meta([f("nolic.mp4", 1)], lic="")}

        def fake_json(url, timeout=30):
            if "advancedsearch" in url:
                return {"response": {"docs": self.docs}}
            return self.metas[url.rsplit("/", 1)[1]]

        def fake_download(url, dest, expected=0, progress=None, timeout=60):
            self.downloads.append(url)
            with open(dest, "wb") as fh:
                fh.write(b"x" * expected)
            return expected

        F.fetch_json, F.download = fake_json, fake_download
        self.addCleanup(lambda: setattr(F, "fetch_json", self.saved[0]) or setattr(F, "download", self.saved[1]))
        self.src = [{"name": "Cartoons", "query": "collection:classic_cartoons", "tags": ["cartoon", "classic", "free"]}]

    def test_downloads_only_public_domain_and_writes_sidecars(self):
        out = F.fetch(self.src, self.media, count=5, say=lambda *a: None)
        self.assertEqual(sorted(out["got"]), ["Popeye Meets Sindbad", "Superman: The Mechanical Monsters"])
        folder = os.path.join(self.media, "Free Movies")
        names = sorted(n for n in os.listdir(folder) if n.endswith(".mp4"))
        self.assertEqual(names, ["Popeye Meets Sindbad (1941).mp4", "Superman The Mechanical Monsters (1941).mp4"])
        side = json.load(open(os.path.join(folder, "Superman The Mechanical Monsters (1941).hero.json"), encoding="utf-8"))
        self.assertEqual(side["franchise"], "Free Movies")
        self.assertEqual(side["year"], 1941)
        self.assertIn("classic", side["tags"])
        self.assertEqual(side["plot"], "A cartoon from long ago.")
        self.assertTrue(side["source"].endswith("/sup1"))
        self.assertNotIn("nolic", " ".join(self.downloads))

    def test_license_rechecked_on_item_page(self):
        self.docs = [item("sneaky", "Looks free in search")]
        self.metas["sneaky"] = meta([f("s.mp4", 10)], lic="http://creativecommons.org/licenses/by-nc-nd/4.0/")
        out = F.fetch(self.src, self.media, say=lambda *a: None)
        self.assertEqual(out["got"], [])
        self.assertEqual(self.downloads, [])

    def test_second_run_skips_what_it_has_and_count_limits(self):
        out = F.fetch(self.src, self.media, count=1, say=lambda *a: None)
        self.assertEqual(len(out["got"]), 1)
        out2 = F.fetch(self.src, self.media, count=1, say=lambda *a: None)
        self.assertEqual(len(out2["got"]), 1)
        self.assertNotEqual(out["got"], out2["got"])
        out3 = F.fetch(self.src, self.media, count=1, say=lambda *a: None)
        self.assertEqual(out3["got"], [])
        self.assertEqual(len(self.downloads), 2)

    def test_deleted_file_is_downloaded_again(self):
        F.fetch(self.src, self.media, count=5, say=lambda *a: None)
        folder = os.path.join(self.media, "Free Movies")
        os.remove(os.path.join(folder, "Popeye Meets Sindbad (1941).mp4"))
        out = F.fetch(self.src, self.media, count=5, say=lambda *a: None)
        self.assertEqual(out["got"], ["Popeye Meets Sindbad"])

    def test_network_failure_is_reported_not_raised(self):
        def boom(url, timeout=30):
            raise OSError("no internet")
        F.fetch_json = boom
        out = F.fetch(self.src, self.media, say=lambda *a: None)
        self.assertEqual(out["got"], [])
        self.assertIn("could not search", out["errors"][0])

    def test_stops_when_disk_is_nearly_full(self):
        real = F.shutil.disk_usage
        F.shutil.disk_usage = lambda p: type("U", (), {"free": F.RESERVE_BYTES})()
        self.addCleanup(lambda: setattr(F.shutil, "disk_usage", real))
        out = F.fetch(self.src, self.media, say=lambda *a: None)
        self.assertEqual(out["got"], [])
        self.assertIn("not enough free disk space", out["errors"][0])


class _Range(BaseHTTPRequestHandler):
    data = bytes(range(256)) * 4000        # ~1 MB

    def log_message(self, *a):
        pass

    def do_GET(self):
        rng = self.headers.get("Range")
        if rng and self.server.honour:
            start = int(rng.split("=")[1].split("-")[0])
            body = self.data[start:]
            self.send_response(206)
        else:
            body = self.data
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class DownloadTests(unittest.TestCase):
    """The real download() against a local server: resume, and a server that ignores resume."""

    def serve(self, honour):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _Range)
        srv.honour = honour
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}/f.mp4"

    def test_plain_download(self):
        dest = os.path.join(tempfile.mkdtemp(), "a.mp4")
        n = F.download(self.serve(True), dest, len(_Range.data))
        self.assertEqual(open(dest, "rb").read(), _Range.data)
        self.assertFalse(os.path.exists(dest + ".part"))
        self.assertEqual(n, len(_Range.data))

    def test_resume_partial(self):
        for honour in (True, False):
            dest = os.path.join(tempfile.mkdtemp(), "a.mp4")
            open(dest + ".part", "wb").write(_Range.data[:300000])
            F.download(self.serve(honour), dest, len(_Range.data))
            self.assertEqual(open(dest, "rb").read(), _Range.data, honour)

    def test_wrong_size_is_an_error_and_keeps_part(self):
        dest = os.path.join(tempfile.mkdtemp(), "a.mp4")
        with self.assertRaises(IOError):
            F.download(self.serve(True), dest, len(_Range.data) + 5)
        self.assertFalse(os.path.exists(dest))


class RetiredFillerTests(unittest.TestCase):
    """Filler was removed: a leftover "filler" setting in an old channels.json must be harmless and must not air anything."""

    def test_old_filler_setting_is_ignored(self):
        c = make_db()
        add(c, "Free cartoon", 600, franchise="Free Movies")
        S.sync_channels(c, [{"id": "x", "number": 1, "name": "X-Men", "match": {"franchise": ["X-Men"]},
                             "filler": {"franchise": ["Free Movies"]}}], now=T0, tz="UTC")
        ch = S.channels(c)[0]
        self.assertEqual(S.extend(c, ch, T0, 3600, "UTC"), 0)

    def test_shipped_channels_file_is_valid_and_has_no_filler(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data = json.load(open(os.path.join(root, "config", "channels.json"), encoding="utf-8-sig"))["channels"]
        S.sync_channels(make_db(), data, now=T0, tz="UTC")
        self.assertFalse(any("filler" in c for c in data))
        self.assertEqual(next(c for c in data if c["id"] == "free")["match"], {"franchise": ["Free Movies"]})


class NetTests(unittest.TestCase):
    def test_context_still_verifies_but_not_strict(self):
        import ssl
        from herotv import net
        ctx = net.ssl_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            self.assertFalse(ctx.verify_flags & ssl.VERIFY_X509_STRICT)
