"""Clean start times: shows begin on the quarter/half hour; the gap is filled with whole shorts and an Up next card."""
import unittest

from helpers import T0, S, add, make_db

H = 3600


def chan(c, starts, filler=None, cid="mcu"):
    d = {"id": cid, "number": 1, "name": "MCU", "mode": "sequential", "match": {"franchise": ["MCU"]}, "starts": starts}
    if filler:
        d["filler"] = filler
    S.load_channels(c, [d])
    return c.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone()


def rows(c):
    return [tuple(r) for r in c.execute("SELECT start,end,media_id,pl FROM slots WHERE channel_id='mcu' ORDER BY start")]


class StartTimes(unittest.TestCase):
    def setUp(self):
        self.c = make_db()
        self.ep = [add(self.c, f"Ep{i}", 22 * 60 + 10) for i in range(4)]

    def check_contiguous(self, s):
        for x, y in zip(s, s[1:]):
            self.assertEqual(x[1], y[0])

    def test_shows_start_on_the_half_hour_with_shorts_and_a_card(self):
        s7 = add(self.c, "Superman short", 7 * 60, franchise="Shorts")
        add(self.c, "Popeye short", 6 * 60 + 30, franchise="Shorts")
        S.extend(self.c, chan(self.c, 30), T0, 4 * H, tz="UTC")
        s = rows(self.c)
        self.check_contiguous(s)
        shows = [x for x in s if x[3] == ""]
        self.assertTrue(all(x[0] % 1800 == 0 for x in shows), shows)      # every show on :00 or :30
        gap = [x for x in s if x[0] >= shows[0][1] and x[1] <= shows[1][0]]
        self.assertEqual([x[3] for x in gap], [S.SHORTS, S.CARD])           # a 7:50 gap: the 7:00 short fits, then a card
        self.assertEqual(gap[0][2], s7)
        self.assertEqual(gap[1][2], self.ep[1])                             # the card shows the next episode
        self.assertNotEqual([x[2] for x in s if x[3] == S.SHORTS][:2][0], [x[2] for x in s if x[3] == S.SHORTS][1])

    def test_without_shorts_the_card_fills_the_gap(self):
        S.extend(self.c, chan(self.c, 15), T0, 2 * H, tz="UTC")
        s = rows(self.c)
        self.check_contiguous(s)
        self.assertEqual([x[3] for x in s[:4]], ["", S.CARD, "", S.CARD])
        self.assertEqual(s[1][1] - T0, 30 * 60)

    def test_a_tiny_leftover_joins_the_short(self):
        add(self.c, "Exact", 7 * 60 + 47, franchise="Shorts")              # leaves 3 s of a 7:50 gap
        S.extend(self.c, chan(self.c, 30), T0, H, tz="UTC")
        s = rows(self.c)
        self.assertEqual([x[3] for x in s[:3]], ["", S.SHORTS, ""])
        self.assertEqual(s[2][0], T0 + 1800)

    def test_any_time_is_unchanged_and_a_minute_late_is_fine(self):
        S.extend(self.c, chan(self.c, 0), T0, H, tz="UTC")
        self.assertTrue(all(x[3] == "" for x in rows(self.c)))
        z = S.get_tz("UTC")
        self.assertEqual(S.next_start(T0 + 50, 30, z), T0 + 50)
        self.assertEqual(S.next_start(T0 + 61, 30, z), T0 + 1800)
        self.assertEqual(S.next_start(T0 + 61, 30, S.get_tz("America/Chicago")), T0 + 1800)

    def test_filler_folders_and_free_cartoons(self):
        sup = add(self.c, "Superman", 420, franchise="Shorts")
        self.c.execute("UPDATE media SET series='Superhero' WHERE id=?", (sup,))
        add(self.c, "Bugs", 420, franchise="Shorts")
        pd = add(self.c, "Popeye", 400, franchise="Free Movies", tags=["cartoon", "free"])
        add(self.c, "Long film", 4000, franchise="Free Movies", tags=["cartoon"])
        self.assertEqual({r["title"] for r in S.shorts_pool(self.c)}, {"Superman", "Bugs", "Popeye"})
        self.assertEqual([r["id"] for r in S.shorts_pool(self.c, ["superhero"])], [sup])
        self.assertIn(pd, [r["id"] for r in S.shorts_pool(self.c, ["cartoon"])])

    def test_card_in_the_api_and_switching_on_later(self):
        ch = chan(self.c, 0)
        S.extend(self.c, ch, T0, H, tz="UTC")
        self.c.execute("DELETE FROM slots WHERE start>?", (T0,))           # as if the setting was just switched on
        S.extend(self.c, chan(self.c, 30), T0, 2 * H, tz="UTC")
        s = rows(self.c)
        self.assertEqual(s[1][3], S.CARD)
        self.assertEqual(s[2][0], T0 + 1800)
        d = S.slot_dict(S.current(self.c, "mcu", s[1][0]), "UTC")
        self.assertEqual((d["card"], d["title"], d["next_title"], d["filler"]), (True, "Up next", "Ep1", "card"))


class SeasonalFolders(unittest.TestCase):
    def test_month_folders_play_only_in_their_month(self):
        import datetime as dt
        import json
        from herotv import library as L
        self.assertEqual(L.season_month(["MCU", "December", "x.mp4"]), 12)
        self.assertEqual(L.season_month(["Shorts", "Halloween", "x.mp4"]), 10)
        self.assertEqual(L.season_month(["MCU", "May December (2023).mp4"]), 0)    # only folders count
        c = make_db()
        a = add(c, "Regular", 1800)
        x = add(c, "Xmas special", 1800)
        c.execute("UPDATE media SET tags=? WHERE id=?", (json.dumps(["month:12"]), x))
        c.commit()
        ch = chan(c, 0)
        S.extend(c, ch, T0, 6 * H, tz="UTC")                                  # T0 is in January
        self.assertEqual({r[0] for r in c.execute("SELECT media_id FROM slots")}, {a})
        dec = int(dt.datetime(2026, 12, 10, tzinfo=dt.timezone.utc).timestamp())
        c.execute("DELETE FROM slots")
        S.extend(c, ch, dec, 6 * H, tz="UTC")
        self.assertEqual({r[0] for r in c.execute("SELECT media_id FROM slots")}, {a, x})
        only = make_db()
        y = add(only, "Only xmas", 1800)
        only.execute("UPDATE media SET tags=? WHERE id=?", (json.dumps(["month:12"]), y))
        self.assertEqual(S.extend(only, chan(only, 0), T0, H, tz="UTC"), 0)   # nothing in season: nothing scheduled
        sh = add(only, "Popeye", 400, franchise="Shorts")
        S.extend(only, chan(only, 0), T0, H, tz="UTC")                        # ...or shorts, when there are some
        self.assertEqual({r[0] for r in only.execute("SELECT media_id FROM slots")}, {sh})


if __name__ == "__main__":
    unittest.main()
