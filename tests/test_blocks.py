import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import add, make_db  # noqa: E402
from herotv import scheduler as S  # noqa: E402

UTC = dt.timezone.utc


def ts(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=UTC).timestamp())


SAT_BLOCK = {"name": "Saturday Morning Cartoons", "days": ["sat"], "from": "07:00", "to": "12:00",
             "match": {"franchise": ["Toon"]}}


def setup(blocks, toons=3):
    c = make_db()
    films = [add(c, f"Film{i}", 1800, "Film") for i in range(4)]
    cartoons = [add(c, f"Toon{i}", 1200, "Toon", order=100 + i) for i in range(toons)]
    S.sync_channels(c, [{"id": "m", "number": 1, "name": "M", "match": {}, "blocks": blocks}], now=ts(2026, 10, 23, 12), tz="UTC")
    return c, films, cartoons


class BlockTests(unittest.TestCase):
    def test_block_at(self):
        night = {"name": "n", "days": [4], "start": 22 * 60, "end": 2 * 60, "match": {}, "mode": None}   # Fri 22:00 -> Sat 02:00
        fri_23, sat_01, sat_03, fri_01 = (dt.datetime(2026, 10, 23, 23), dt.datetime(2026, 10, 24, 1),
                                          dt.datetime(2026, 10, 24, 3), dt.datetime(2026, 10, 23, 1))
        self.assertIs(S.block_at([night], fri_23), night)
        self.assertIs(S.block_at([night], sat_01), night)
        self.assertIsNone(S.block_at([night], sat_03))
        self.assertIsNone(S.block_at([night], fri_01))

    def test_bad_blocks_give_plain_messages(self):
        bad = [({"from": "7am", "to": "12:00"}, "24-hour"), ({"from": "07:00"}, '"to"'),
               ({"from": "07:00", "to": "12:00", "days": ["funday"]}, "not a day"),
               ({"from": "07:00", "to": "07:00"}, "same time")]
        for b, word in bad:
            with self.assertRaises(ValueError) as cm:
                S.parse_blocks({"name": "X", "blocks": [b]})
            self.assertIn(word, str(cm.exception))
        with self.assertRaises(ValueError):
            S.parse_blocks({"name": "X", "blocks": [{"name": "a", "from": "1:00", "to": "2:00"}] * 2})
        ok = S.parse_blocks({"name": "X", "blocks": [{"from": "7:00", "to": "12:00", "days": "weekends"}]})
        self.assertEqual(ok[0]["days"], [5, 6])

    def test_block_starts_on_the_dot_and_ends_back_to_normal(self):
        c, films, cartoons = setup([SAT_BLOCK])
        now = ts(2026, 10, 24, 6, 50)
        ch = c.execute("SELECT * FROM channels").fetchone()
        S.extend(c, ch, now, 6 * 3600, "UTC")
        rows = c.execute("SELECT start,end,media_id,pl FROM slots ORDER BY start").fetchall()
        self.assertEqual(rows[0]["end"], ts(2026, 10, 24, 7), "the film on air at 6:50 is cut at exactly 7:00")
        inblock = [r for r in rows if r["start"] >= ts(2026, 10, 24, 7) and r["start"] < ts(2026, 10, 24, 12)]
        self.assertEqual(len(inblock), 15)
        self.assertTrue(all(r["pl"] == SAT_BLOCK["name"] and r["media_id"] in cartoons for r in inblock))
        self.assertEqual(inblock[0]["start"], ts(2026, 10, 24, 7))
        after = [r for r in rows if r["start"] >= ts(2026, 10, 24, 12)]
        self.assertTrue(after and all(r["pl"] == "" and r["media_id"] in films for r in after))
        for a, b in zip(rows, rows[1:]):
            self.assertEqual(a["end"], b["start"], "no gaps")

    def test_block_remembers_its_place_between_weeks(self):
        c, films, cartoons = setup([SAT_BLOCK], toons=4)
        ch = c.execute("SELECT * FROM channels").fetchone()
        S.extend(c, ch, ts(2026, 10, 24, 6, 0), 7 * 3600, "UTC")            # Saturday 1
        seq1 = [r["media_id"] for r in c.execute("SELECT media_id FROM slots WHERE pl!='' ORDER BY start")]
        self.assertEqual(seq1[:5], [cartoons[0], cartoons[1], cartoons[2], cartoons[3], cartoons[0]])
        last = seq1[-1]
        S.extend(c, ch, ts(2026, 10, 31, 6, 0), 7 * 3600, "UTC")            # Saturday 2
        seq2 = [r["media_id"] for r in c.execute("SELECT media_id FROM slots WHERE pl!='' AND start>=? ORDER BY start", (ts(2026, 10, 31),))]
        self.assertEqual(seq2[0], cartoons[(cartoons.index(last) + 1) % 4])

    def test_empty_block_falls_back_to_normal_programming(self):
        b = dict(SAT_BLOCK, match={"franchise": ["Nothing"]})
        c, films, _ = setup([b])
        ch = c.execute("SELECT * FROM channels").fetchone()
        S.extend(c, ch, ts(2026, 10, 24, 6, 0), 3 * 3600, "UTC")
        rows = c.execute("SELECT media_id,pl FROM slots").fetchall()
        self.assertTrue(rows and all(r["pl"] == "" for r in rows))

    def test_editing_blocks_replans_the_future(self):
        c, films, cartoons = setup([])
        ch = c.execute("SELECT * FROM channels").fetchone()
        now = ts(2026, 10, 24, 6, 0)
        S.extend(c, ch, now, 8 * 3600, "UTC")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM slots WHERE pl!=''").fetchone()[0], 0)
        S.sync_channels(c, [{"id": "m", "number": 1, "name": "M", "match": {}, "blocks": [SAT_BLOCK]}], now=now, tz="UTC")
        self.assertGreater(c.execute("SELECT COUNT(*) FROM slots WHERE pl!=''").fetchone()[0], 0)

    def test_slot_dict_exposes_block_name(self):
        c, _, _ = setup([SAT_BLOCK])
        ch = c.execute("SELECT * FROM channels").fetchone()
        S.extend(c, ch, ts(2026, 10, 24, 7, 5), 3600, "UTC")
        d = S.slot_dict(S.current(c, "m", ts(2026, 10, 24, 7, 10)), "UTC")
        self.assertEqual(d["block"], SAT_BLOCK["name"])


if __name__ == "__main__":
    unittest.main()
