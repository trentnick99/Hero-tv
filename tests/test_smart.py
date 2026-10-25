import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import add, make_db, T0  # noqa: E402
from herotv import scheduler as S  # noqa: E402


def lib(n=5, runtime=1200):
    c = make_db()
    ids = [add(c, f"Ep{i}", runtime, "Show", order=i) for i in range(n)]
    return c, ids


def chan(c, mode="sequential", match=None, smart=True, blocks=None):
    ch = {"id": "x", "number": 1, "name": "X", "mode": mode, "match": match or {}}
    if not smart:
        ch["smart"] = False
    if blocks:
        ch["blocks"] = blocks
    S.sync_channels(c, [ch], now=T0, tz="UTC")
    return c.execute("SELECT * FROM channels").fetchone()


def watched(c, mid, fraction=1.0):
    rt = c.execute("SELECT runtime_s FROM media WHERE id=?", (mid,)).fetchone()[0]
    c.execute("INSERT OR REPLACE INTO seen(media_id,secs,last) VALUES(?,?,?)", (mid, rt * fraction, T0))
    c.commit()


def order(c, limit=None):
    q = [r[0] for r in c.execute("SELECT media_id FROM slots ORDER BY start")]
    return q[:limit] if limit else q


class SmartTests(unittest.TestCase):
    def test_sequential_passes_over_watched_episodes(self):
        c, ids = lib()
        watched(c, ids[0]); watched(c, ids[1])
        S.extend(c, chan(c), T0, 3 * 1200, "UTC")
        self.assertEqual(order(c, 3), ids[2:5])

    def test_half_watched_counts_but_a_glimpse_does_not(self):
        c, ids = lib(3)
        watched(c, ids[0], 0.6); watched(c, ids[1], 0.2)
        S.extend(c, chan(c), T0, 1200, "UTC")
        self.assertEqual(order(c, 1), [ids[1]])

    def test_library_playback_counts_as_watched(self):
        c, ids = lib(3)
        c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(?,?,1,0)", (ids[0], 1200))
        c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(?,?,0,0)", (ids[1], 1150))
        c.commit()
        S.extend(c, chan(c), T0, 1200, "UTC")
        self.assertEqual(order(c, 1), [ids[2]])

    def test_shuffle_does_not_repeat_watched_until_everything_is_seen(self):
        c, ids = lib(6)
        for i in ids[:3]:
            watched(c, i)
        S.extend(c, chan(c, "shuffle"), T0, 3 * 1200, "UTC")
        first3 = order(c, 3)
        self.assertEqual(sorted(first3), sorted(ids[3:]))

    def test_everything_watched_plays_normally(self):
        c, ids = lib(3)
        for i in ids:
            watched(c, i)
        S.extend(c, chan(c), T0, 4 * 1200, "UTC")
        self.assertEqual(order(c, 4), [ids[0], ids[1], ids[2], ids[0]])

    def test_a_lone_unwatched_video_is_not_repeated_back_to_back(self):
        c, ids = lib(4)
        for i in ids[:3]:
            watched(c, i)
        S.extend(c, chan(c), T0, 6 * 1200, "UTC")
        o = order(c, 6)
        self.assertEqual(o[0], ids[3])
        self.assertNotEqual(o[1], ids[3])

    def test_smart_can_be_switched_off(self):
        c, ids = lib(3)
        watched(c, ids[0])
        S.extend(c, chan(c, smart=False), T0, 1200, "UTC")
        self.assertEqual(order(c, 1), [ids[0]])

    def test_restart_resumes_at_first_unwatched_not_where_the_schedule_ran_to(self):
        c, ids = lib(8)
        ch = chan(c)
        S.extend(c, ch, T0 - 6 * 1200, 12 * 1200, "UTC")           # the channel kept "running" while you were away
        for i in ids[:3]:
            watched(c, i)
        S.rebuild_future(c, ch, T0, 4 * 1200, "UTC", resume=True)
        o = [r[0] for r in c.execute("SELECT media_id FROM slots WHERE start>=? ORDER BY start", (T0,))]
        on_air = c.execute("SELECT media_id FROM slots WHERE start<=? AND end>? ", (T0, T0)).fetchone()[0]
        after = [m for m in o if m != on_air] if o and o[0] == on_air else o
        self.assertEqual(after[0], ids[3] if on_air != ids[3] else ids[4])
        self.assertNotIn(on_air, after[:1])

    def test_runtime_and_type_rules(self):
        c = make_db()
        short = add(c, "Short", 1300, "A")
        movie = add(c, "Movie", 6000, "A")
        c.execute("INSERT INTO media(path,title,franchise,series,episode,runtime_s,verified,playable,available) VALUES('/x/e','E','A','Show',3,1300,1,1,1)")
        c.commit()
        rows = {r["title"]: r for r in c.execute("SELECT * FROM media")}
        self.assertFalse(S.matches({"min_minutes": 75}, rows["Short"]))
        self.assertTrue(S.matches({"min_minutes": 75}, rows["Movie"]))
        self.assertTrue(S.matches({"max_minutes": 30}, rows["Short"]))
        self.assertTrue(S.matches({"type": "movie"}, rows["Movie"]))
        self.assertFalse(S.matches({"type": "movie"}, rows["E"]))
        self.assertTrue(S.matches({"type": "episode"}, rows["E"]))
        self.assertTrue(S.matches({"type": "movie"}, rows["Short"]), "no series, no episode number -> a movie")

    def test_movie_night_block_only_airs_long_videos(self):
        import datetime as dt
        c = make_db()
        eps = [add(c, f"E{i}", 1300, "Show") for i in range(5)]
        mv = [add(c, f"M{i}", 6600, "Film") for i in range(3)]
        night = {"name": "Movie Night", "days": ["fri"], "from": "20:00", "to": "23:59", "match": {"min_minutes": 75}}
        ch = chan(c, "shuffle", blocks=[night])
        fri_8 = int(dt.datetime(2026, 10, 23, 19, 30, tzinfo=dt.timezone.utc).timestamp())
        S.extend(c, ch, fri_8, 4 * 3600, "UTC")
        inblock = [r["media_id"] for r in c.execute("SELECT media_id FROM slots WHERE pl='Movie Night'")]
        self.assertTrue(inblock and all(m in mv for m in inblock))


if __name__ == "__main__":
    unittest.main()
