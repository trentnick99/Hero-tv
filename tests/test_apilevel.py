import os
import re
import sys
import tempfile
import threading
import unittest
import json
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import make_db  # noqa: E402
from herotv import server as SV  # noqa: E402
from herotv.config import API_LEVEL, Config  # noqa: E402
from herotv.launcher import pids_listening  # noqa: E402


class StaleServerTests(unittest.TestCase):
    """An older HERO TV left running after an update must be noticed (and restarted by the launcher)."""

    def test_api_level_matches_between_server_and_page(self):
        page = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "index.html"), encoding="utf-8").read()
        self.assertEqual(int(re.search(r"const NEED_API=(\d+)", page)[1]), API_LEVEL)

    def test_health_reports_api_level(self):
        d = tempfile.mkdtemp()
        cfg = Config(); cfg.db_path = os.path.join(d, "t.sqlite3"); cfg.tz = "UTC"; cfg.media_dir = d
        make_db(cfg.db_path)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        j = json.load(urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/health"))
        self.assertEqual(j["api"], API_LEVEL)

    def test_finds_the_old_server_in_windows_netstat_output(self):
        text = ("Active Connections\r\n\r\n  Proto  Local Address          Foreign Address        State           PID\r\n"
                "  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1048\r\n"
                "  TCP    127.0.0.1:8787         0.0.0.0:0              LISTENING       12345\r\n"
                "  TCP    127.0.0.1:8787         127.0.0.1:50211        ESTABLISHED     12345\r\n"
                "  TCP    127.0.0.1:18787        0.0.0.0:0              LISTENING       777\r\n"
                "  TCP    [::1]:8787             [::]:0                 LISTENING       12345\r\n")
        self.assertEqual(pids_listening(text, 8787), [12345])
        self.assertEqual(pids_listening(text, 9999), [])


if __name__ == "__main__":
    unittest.main()
