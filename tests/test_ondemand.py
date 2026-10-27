"""On demand on the Roku: library rows, shows folded into one tile, next episode, play info - and the PC staying
awake while a TV watches."""
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import awake, ondemand  # noqa: E402
from herotv.db import connect  # noqa: E402


def add(c, path, **kw):
    cols = dict(path=path, verified=1, playable=1, available=1, **kw)
    c.execute(f"INSERT INTO media({','.join(cols)}) VALUES({','.join('?' * len(cols))})", tuple(cols.values()))
    return c.execute("SELECT id FROM media WHERE path=?", (path,)).fetchone()[0]


class RowsTests(unittest.TestCase):
    def setUp(self):
        self.c = connect(":memory:")
        self.addCleanup(self.c.close)
        self.film = add(self.c, "/v/im.mp4", title="Iron Man", year=2008, franchise="MCU", runtime_s=7560, plot="Tony.")
        self.eps = [add(self.c, f"/v/dd{e}.mkv", title=f"Ep {e}", franchise="Marvel Television", series="Daredevil",
                        season=1, episode=e, runtime_s=3000) for e in (1, 2, 3)]
        add(self.c, "/v/other.mp4", title="Daredevil", franchise="Movies", year=2003)       # same name, not the show
        self.c.commit()

    def prog(self, mid, pos, done=0, when=1):
        self.c.execute("INSERT OR REPLACE INTO progress(media_id,position,completed,updated) VALUES(?,?,?,?)", (mid, pos, done, when))
        self.c.commit()

    def test_rows_fold_a_show_into_one_tile(self):
        rows = {r["title"]: r["items"] for r in ondemand.rows(self.c, time.time() + 90 * 86400)["rows"]}
        self.assertEqual(list(rows), ["Marvel Television", "MCU", "Movies"])
        tv = rows["Marvel Television"]
        self.assertEqual(len(tv), 1)
        self.assertEqual((tv[0]["type"], tv[0]["title"], tv[0]["id"]), ("series", "Daredevil", self.eps[0]))
        self.assertIn("3 episodes", tv[0]["line"])
        self.assertEqual(rows["MCU"][0]["line"], "2008  -  2 h 6 min")
        self.assertEqual(rows["MCU"][0]["thumb"], f"/thumb/{self.film}")

    def test_next_up_and_continue_watching(self):
        self.prog(self.eps[0], 2990, 1, when=5)
        now = time.time() + 90 * 86400
        tile = [r for r in ondemand.rows(self.c, now)["rows"] if r["title"] == "Marvel Television"][0]["items"][0]
        self.assertEqual(tile["id"], self.eps[1])                     # finished episode 1: episode 2 is next
        self.prog(self.eps[2], 600, 0, when=9)
        rows = ondemand.rows(self.c, now)["rows"]
        self.assertEqual(rows[0]["title"], "Continue watching")
        self.assertEqual(rows[0]["items"][0]["title"], "Daredevil  S1 E3")
        self.assertIn("40 min left", rows[0]["items"][0]["line"])
        e = ondemand.episodes(self.c, "Marvel Television", "Daredevil")
        self.assertEqual((len(e["items"]), e["next"]), (3, self.eps[2]))
        self.assertIn("watched", e["items"][0]["line"])

    def test_new_favorites_and_search(self):
        self.c.execute("UPDATE media SET added=?", (int(time.time()),))
        self.c.execute("INSERT INTO favorites(media_id,added) VALUES(?,1)", (self.film,))
        self.c.commit()
        titles = [r["title"] for r in ondemand.rows(self.c, time.time())["rows"]]
        self.assertEqual(titles[:2], ["Favorites", "New in your library"])
        found = ondemand.rows(self.c, time.time(), "dare")["rows"]
        self.assertEqual(len(found), 1)
        self.assertEqual(sorted(t["type"] for t in found[0]["items"]), ["series", "video"])
        self.assertIn("Nothing found", ondemand.rows(self.c, time.time(), "zzz")["rows"][0]["title"])

    def test_play_info(self):
        self.prog(self.eps[0], 1200)
        p = ondemand.play(self.c, self.eps[0])
        self.assertEqual((p["ext"], p["resume"], p["next"]["id"]), ("mkv", 1200, self.eps[1]))
        self.assertIsNone(ondemand.play(self.c, self.eps[2])["next"])
        self.prog(self.film, 7530)
        self.assertEqual(ondemand.play(self.c, self.film)["resume"], 0)  # practically finished: from the start
        self.assertIsNone(ondemand.play(self.c, 9999))


class AwakeTests(unittest.TestCase):
    def test_awake_while_streaming_and_after(self):
        with mock.patch.object(awake, "_ensure"), mock.patch.object(awake, "always", return_value=False):
            awake._state.update(active=0, last=0.0)
            self.assertFalse(awake.wanted())
            with awake.streaming():
                self.assertTrue(awake.wanted())
            self.assertTrue(awake.wanted())                               # still a while after (pause, menu)
            self.assertFalse(awake.wanted(now=time.time() + awake.GRACE + 1))

    def test_default_follows_roku_setup(self):
        self.assertFalse(awake.always({}))
        self.assertTrue(awake.always({"rokus": {"192.168.1.5": {"ip": "192.168.1.5"}}}))
        self.assertFalse(awake.always({"rokus": {"192.168.1.5": {}}, "stay_awake": False}))
        self.assertTrue(awake.always({"stay_awake": True}))

    def test_windows_call(self):
        calls = []
        awake._set(True, calls.append)
        awake._set(False, calls.append)
        self.assertEqual(calls, [0x80000001, 0x80000000])


if __name__ == "__main__":
    unittest.main()
