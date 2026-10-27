"""Play orders: mixed shows (each show's episodes stay in order) and fair share; the channel logo setting."""
import random
import unittest

from helpers import T0, S, add, make_db


def ep(c, show, n, franchise="Marvel Television"):
    i = add(c, f"{show} {n}", 1500, franchise=franchise)
    c.execute("UPDATE media SET series=?, season=1, episode=? WHERE id=?", (show, n, i))
    c.commit()
    return i


class Mix(unittest.TestCase):
    def setUp(self):
        self.c = make_db()
        self.dd = [ep(self.c, "Daredevil", n) for n in range(1, 14)]
        self.jj = [ep(self.c, "Jessica Jones", n) for n in range(1, 4)]
        self.lc = [ep(self.c, "Luke Cage", n) for n in range(1, 5)]
        self.rows = self.c.execute("SELECT * FROM media ORDER BY ord,series,season,episode,title,id").fetchall()

    def in_order(self, out, ids):
        got = [r["id"] for r in out if r["id"] in ids]
        self.assertEqual(got, sorted(got, key=ids.index))

    def test_mixed_keeps_each_show_in_order(self):
        out = S.mix_shows(self.rows, random.Random(1))
        self.assertEqual(sorted(r["id"] for r in out), sorted(r["id"] for r in self.rows))
        for ids in (self.dd, self.jj, self.lc):
            self.in_order(out, ids)
        self.assertNotEqual([r["series"] for r in out][:5], ["Daredevil"] * 5)   # shows take turns (seeded)

    def test_fair_share_limits_a_big_show_per_round(self):
        r0 = S.mix_shows(self.rows, random.Random(1), cycle=0, balanced=True)
        r1 = S.mix_shows(self.rows, random.Random(2), cycle=1, balanced=True)
        dd0 = [r["id"] for r in r0 if r["series"] == "Daredevil"]
        dd1 = [r["id"] for r in r1 if r["series"] == "Daredevil"]
        self.assertEqual(dd0, self.dd[:4])                 # typical show size here is 4 -> 4 Daredevils a round
        self.assertEqual(dd1, self.dd[4:8])                # and the next round carries on
        self.assertEqual(len(r0), 4 + 3 + 4)

    def test_channel_uses_the_mode(self):
        S.load_channels(self.c, [{"id": "mtv", "number": 2, "name": "MTV", "mode": "mixed",
                                  "match": {"franchise": ["Marvel Television"]}}])
        ch = self.c.execute("SELECT * FROM channels WHERE id='mtv'").fetchone()
        S.extend(self.c, ch, T0, 30 * 1500, tz="UTC")
        ids = [r[0] for r in self.c.execute("SELECT media_id FROM slots WHERE channel_id='mtv' ORDER BY start")]
        for show in (self.dd, self.jj, self.lc):
            got = [i for i in ids[:20] if i in show]
            self.assertEqual(got, sorted(got, key=show.index))


class Logo(unittest.TestCase):
    def test_logo_setting(self):
        from herotv import settings_api as SA
        self.assertEqual(SA.logo_mode({}), "sometimes")
        self.assertEqual(SA.logo_mode({"logo": "always"}), "always")
        self.assertEqual(SA.logo_mode({"logo": "weird"}), "sometimes")


if __name__ == "__main__":
    unittest.main()
