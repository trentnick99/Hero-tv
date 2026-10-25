import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from helpers import T0, S, add, channel, make_db, slots, tmpdb

H = 3600


class Basics(unittest.TestCase):
    def setUp(self):
        self.c = make_db()
        self.a, self.b, self.d = add(self.c, "A", 1500.2), add(self.c, "B", 3000), add(self.c, "C", 61)
        self.ch = channel(self.c)

    def test_contiguous_no_overlap_and_covers_horizon(self):
        S.extend(self.c, self.ch, T0, 6 * H)
        s = slots(self.c)
        self.assertEqual(s[0][0], T0)
        for x, y in zip(s, s[1:]):
            self.assertEqual(x[1], y[0])            # no gap, no overlap
        self.assertGreaterEqual(s[-1][1], T0 + 6 * H)

    def test_duration_is_ceil_of_verified_runtime(self):
        S.extend(self.c, self.ch, T0, H)
        self.assertEqual(slots(self.c)[0][1] - T0, 1501)

    def test_sequential_order_and_wrap_increments_cycle(self):
        S.extend(self.c, self.ch, T0, 4 * H)
        s = slots(self.c)
        self.assertEqual([x[2] for x in s[:4]], [self.a, self.b, self.d, self.a])
        self.assertEqual([x[3] for x in s[:4]], [0, 0, 0, 1])

    def test_unverified_unplayable_unavailable_excluded(self):
        add(self.c, "bad1", 100, verified=0), add(self.c, "bad2", 100, playable=0), add(self.c, "bad3", 100, available=0)
        S.extend(self.c, self.ch, T0, 20 * H)
        titles = {r[0] for r in self.c.execute("SELECT m.title FROM slots s JOIN media m ON m.id=s.media_id")}
        self.assertEqual(titles, {"A", "B", "C"})

    def test_empty_channel_makes_no_slots_and_recovers(self):
        c = make_db(); ch = channel(c, "x", match={"franchise": ["None"]})
        self.assertEqual(S.extend(c, ch, T0, H), 0)

    def test_rules_filter(self):
        add(self.c, "Bat", 600, franchise="DC", tags=["action"])
        dc = channel(self.c, "dc", match={"franchise": ["DC"]}, number=2)
        S.extend(self.c, dc, T0, H)
        self.assertEqual({r[0] for r in self.c.execute("SELECT m.title FROM slots s JOIN media m ON m.id=s.media_id WHERE channel_id='dc'")}, {"Bat"})

    def test_shuffle_is_deterministic_and_covers_each_item_once_per_cycle(self):
        def run():
            c = make_db()
            for i in range(8):
                add(c, f"T{i}", 600)
            ch = channel(c, "m", mode="shuffle")
            S.extend(c, ch, T0, 3 * H)
            return slots(c, "m")
        r1, r2 = run(), run()
        self.assertEqual(r1, r2)
        first_cycle = [x[2] for x in r1 if x[3] == 0]
        self.assertEqual(sorted(first_cycle), list(range(1, 9)))
        self.assertNotEqual(first_cycle, sorted(first_cycle))  # actually shuffled


class Restarts(unittest.TestCase):
    def test_restart_does_not_change_existing_slots_and_extends_seamlessly(self):
        p = tmpdb()
        c = make_db(p)
        for t, r in (("A", 900), ("B", 1700), ("C", 2500)):
            add(c, t, r)
        ch = channel(c)
        S.extend(c, ch, T0, 3 * H)
        before = slots(c)
        c.close()
        c2 = make_db(p)                                  # "reboot"
        ch2 = c2.execute("SELECT * FROM channels").fetchone()
        S.extend(c2, ch2, T0 + 2 * H, 3 * H)
        after = slots(c2)
        self.assertEqual(after[:len(before)], before)    # history unchanged
        self.assertGreaterEqual(after[-1][1], T0 + 5 * H)
        for x, y in zip(after, after[1:]):
            self.assertEqual(x[1], y[0])

    def test_downtime_catchup_equals_uninterrupted_run(self):
        def build():
            c = make_db()
            for t, r in (("A", 900), ("B", 1700), ("C", 2500)):
                add(c, t, r)
            return c, channel(c)
        c1, ch1 = build(); S.extend(c1, ch1, T0, 20 * H)
        c2, ch2 = build(); S.extend(c2, ch2, T0, 1 * H)
        S.extend(c2, ch2, T0 + 10 * H, 1 * H)            # server was off for ~9 h
        now = T0 + 10 * H + 17
        self.assertEqual(tuple(S.current(c1, "mcu", now))[:4], tuple(S.current(c2, "mcu", now))[:4])

    def test_long_outage_resumes_at_now(self):
        c = make_db(); add(c, "A", 600); ch = channel(c)
        S.extend(c, ch, T0, H)
        late = T0 + 30 * 86400
        S.extend(c, ch, late, H)
        self.assertEqual(S.current(c, "mcu", late)["start"], late)

    def test_extend_is_idempotent(self):
        c = make_db(); add(c, "A", 600); ch = channel(c)
        S.extend(c, ch, T0, 2 * H); n = slots(c)
        self.assertEqual(S.extend(c, ch, T0, 2 * H), 0)
        self.assertEqual(slots(c), n)


class Rebuild(unittest.TestCase):
    def test_removed_media_leaves_airing_slot_then_disappears(self):
        c = make_db(); ids = [add(c, t, 600) for t in "ABC"]; ch = channel(c)
        S.extend(c, ch, T0, 3 * H)
        now = T0 + 700                                   # inside slot 2 (B)
        c.execute("UPDATE media SET available=0 WHERE title='C'"); c.commit()
        S.rebuild_future(c, ch, now, 3 * H)
        s = slots(c)
        self.assertEqual(s[1][2], ids[1])                # B still on air
        self.assertNotIn(ids[2], [x[2] for x in s])
        for x, y in zip(s, s[1:]):
            self.assertEqual(x[1], y[0])

    def test_broken_current_media_is_replaced_without_gap(self):
        c = make_db(); ids = [add(c, t, 600) for t in "AB"]; ch = channel(c)
        S.extend(c, ch, T0, 2 * H)
        now = T0 + 100                                   # A airing
        c.execute("UPDATE media SET available=0 WHERE title='A'"); c.commit()
        S.rebuild_future(c, ch, now, 2 * H)
        cur = S.current(c, "mcu", now)
        self.assertEqual(cur["media_id"], ids[1])
        s = slots(c)
        for x, y in zip(s, s[1:]):
            self.assertEqual(x[1], y[0])


class Timezones(unittest.TestCase):
    def test_local_day_lengths_around_dst(self):
        for day, hrs in (("2026-03-08", 23), ("2026-11-01", 25), ("2026-07-01", 24)):
            a, b = S.local_day_bounds("America/New_York", day)
            self.assertEqual((b - a) / H, hrs, day)

    def test_southern_hemisphere_and_half_hour_zones(self):
        a, b = S.local_day_bounds("Australia/Lord_Howe", "2026-10-04")   # 30-minute DST shift
        self.assertEqual((b - a) / 60, 23 * 60 + 30)
        a, b = S.local_day_bounds("Asia/Kolkata", "2026-01-01")
        self.assertEqual((b - a) / H, 24)

    def test_slot_across_spring_forward_keeps_exact_duration_and_shifts_offset(self):
        c = make_db(); add(c, "Long", 2 * H); ch = channel(c)
        z = ZoneInfo("America/New_York")
        start = int(dt.datetime(2026, 3, 8, 1, 30, tzinfo=z).timestamp())   # 01:30 EST
        S.extend(c, ch, start, 1)
        d = S.slot_dict(S.current(c, "mcu", start), "America/New_York")
        self.assertEqual(d["end"] - d["start"], 2 * H)                        # 2 real hours
        self.assertTrue(d["start_local"].endswith("-05:00"))
        self.assertTrue(d["end_local"].endswith("-04:00"))
        self.assertTrue(d["end_local"].startswith("2026-03-08T04:30"))        # wall clock jumped 3 h

    def test_slot_across_fall_back(self):
        c = make_db(); add(c, "Long", 2 * H); ch = channel(c)
        start = int(dt.datetime(2026, 11, 1, 5, 30, tzinfo=dt.timezone.utc).timestamp())  # 01:30 EDT
        S.extend(c, ch, start, 1)
        d = S.slot_dict(S.current(c, "mcu", start), "America/New_York")
        self.assertTrue(d["start_local"].startswith("2026-11-01T01:30") and d["start_local"].endswith("-04:00"))
        self.assertTrue(d["end_local"].startswith("2026-11-01T02:30") and d["end_local"].endswith("-05:00"))  # 2 real hours, wall clock +1 h

    def test_slot_crossing_local_midnight_is_in_both_days_and_boundaries_are_half_open(self):
        c = make_db(); add(c, "N", 3600); ch = channel(c)
        z = ZoneInfo("Europe/Paris")
        start = int(dt.datetime(2026, 6, 1, 23, 30, tzinfo=z).timestamp())
        S.extend(c, ch, start, 1)
        d1, d2 = S.local_day_bounds("Europe/Paris", "2026-06-01"), S.local_day_bounds("Europe/Paris", "2026-06-02")
        self.assertEqual(d1[1], d2[0])
        self.assertEqual(len(S.window(c, *d1)), 1 if S.current(c, "mcu", start) else 0)
        self.assertTrue(any(r["start"] == start for r in S.window(c, *d1)))
        self.assertTrue(any(r["start"] == start for r in S.window(c, *d2)))
        # a window that starts exactly when a slot ends does not include it
        cur = S.current(c, "mcu", start)
        self.assertFalse(any(r["start"] == cur["start"] for r in S.window(c, cur["end"], cur["end"] + 60)))

    def test_current_boundaries(self):
        c = make_db(); add(c, "A", 600); add(c, "B", 600); ch = channel(c)
        S.extend(c, ch, T0, H)
        self.assertEqual(S.current(c, "mcu", T0 + 599)["title"], "A")
        self.assertEqual(S.current(c, "mcu", T0 + 600)["title"], "B")   # end-exclusive
        self.assertIsNone(S.current(c, "mcu", T0 - 1))


if __name__ == "__main__":
    unittest.main()
