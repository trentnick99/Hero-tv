"""The 'Needs a look' list at the top of Settings, and that phones cannot read it."""
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from helpers import make_db, tmpdb
from herotv import remote, selfupdate, tools
from herotv.config import Config
from herotv.server import App, make_handler


class Attention(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(f"{self.root}/Inbox")
        self.cfg = Config(media_dir=self.root, db_path=tmpdb(), channels_file=os.path.join(self.root, "ch.json"),
                          tz="America/New_York", port=0)
        Path(self.cfg.channels_file).write_text(json.dumps({"channels": []}))
        self.c = make_db(self.cfg.db_path)
        self.addCleanup(self.c.close)
        sf = mock.patch("herotv.config.settings_file", return_value=Path(self.root) / "settings.json")
        sf.start()
        self.addCleanup(sf.stop)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(self.cfg)))
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        self.base = f"http://127.0.0.1:{srv.server_address[1]}"

    def get(self):
        with urllib.request.urlopen(self.base + "/api/attention") as r:
            return json.load(r)["items"]

    def test_quiet_when_nothing_needs_a_look(self):
        with mock.patch.object(tools, "find_tool", return_value="/usr/bin/x"), \
                mock.patch.object(selfupdate, "status", return_value={"available": False}):
            self.assertEqual(self.get(), [])

    def test_lists_what_needs_a_look_and_where_to_go(self):
        Path(self.root, "Inbox", "a.mkv").write_bytes(b"x")
        self.c.execute("INSERT INTO media(path,title,available,playable,verified,size) VALUES(?,?,1,0,1,5)",
                       (os.path.join(self.root, "Movies", "Bad.mkv"), "Bad"))
        self.c.commit()
        with mock.patch.object(tools, "find_tool", return_value=None), \
                mock.patch.object(selfupdate, "status", return_value={"available": True, "latest": "9.9.9"}):
            items = self.get()
        cards = {i["card"] for i in items}
        self.assertEqual(cards, {"", "This PC", "Videos that are skipped", "Inbox"})
        self.assertEqual({i["cat"] for i in items}, {"about", "tools"})
        self.assertTrue(any("9.9.9" in i["text"] for i in items))

    def test_a_video_waiting_in_the_inbox_is_not_counted_as_cannot_play(self):
        self.c.execute("INSERT INTO media(path,title,available,playable,verified,size) VALUES(?,?,1,0,1,5)",
                       (os.path.join(self.root, "Inbox", "New.mkv"), "New"))
        self.c.commit()
        with mock.patch.object(tools, "find_tool", return_value="/usr/bin/x"), \
                mock.patch.object(selfupdate, "status", return_value={"available": False}):
            self.assertNotIn("Videos that are skipped", {i["card"] for i in self.get()})

    def setup(self):
        with urllib.request.urlopen(self.base + "/api/setup") as r:
            return json.load(r)

    def test_setup_list_follows_what_is_there(self):
        with mock.patch.object(tools, "find_tool", return_value=None):
            j = self.setup()
        self.assertEqual([(x["id"], x["done"]) for x in j["steps"]], [("videos", False), ("tools", False)])   # no videos: no "playable" step yet
        self.assertFalse(j["done"])
        self.c.execute("INSERT INTO media(path,title,available,playable,verified,size) VALUES(?,?,1,0,1,5)",
                       (os.path.join(self.root, "Movies", "A.mkv"), "A"))
        self.c.commit()
        with mock.patch.object(tools, "find_tool", return_value="/usr/bin/x"):
            j = self.setup()
        self.assertEqual([(x["id"], x["done"]) for x in j["steps"]], [("videos", True), ("tools", True), ("play", False)])
        self.c.execute("UPDATE media SET playable=1")
        self.c.commit()
        with mock.patch.object(tools, "find_tool", return_value="/usr/bin/x"):
            self.assertTrue(self.setup()["done"])                  # all done: the Home tile goes away

    def test_phones_cannot_read_it(self):
        self.assertNotIn("setup", remote.REMOTE_GET_API)
        self.assertNotIn("attention", remote.REMOTE_GET_API)
        self.assertFalse(any("attention".startswith(p) for p in remote.REMOTE_GET_API_PREFIX))


if __name__ == "__main__":
    unittest.main()
