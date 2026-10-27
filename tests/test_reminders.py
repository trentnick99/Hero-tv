"""Reminders: set from the guide, offered when the show starts, cleared afterwards; phones and the Roku app too."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import add, channel, make_db  # noqa: E402
from herotv import reminders, remote as R, scheduler as S  # noqa: E402

T0 = 1_800_000_000


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.c = make_db()
        self.a = add(self.c, "Iron Man", 6000)
        self.b = add(self.c, "Thor", 6000)
        ch = channel(self.c, "mcu")
        S.extend(self.c, ch, T0, 6 * 3600, tz="UTC")
        self.slots = [dict(r) for r in self.c.execute("SELECT * FROM slots WHERE channel_id='mcu' ORDER BY start")]

    def test_add_list_due_and_clear(self):
        later = self.slots[1]
        r = reminders.add(self.c, "mcu", later["start"], now=T0)
        self.assertEqual((r["channel"], r["start"]), ("mcu", later["start"]))
        lst = reminders.listing(self.c, now=T0)
        self.assertEqual([x["start"] for x in lst["reminders"]], [later["start"]])
        self.assertEqual(lst["due"], [])
        self.assertEqual(lst["reminders"][0]["channel_name"], "MCU")
        due = reminders.listing(self.c, now=later["start"] - 30)["due"]                # a minute before: due
        self.assertEqual([x["title"] for x in due], [r["title"]])
        self.assertEqual(reminders.listing(self.c, now=later["start"] + 600)["due"], [])   # 10 minutes in: not any more
        reminders.listing(self.c, now=later["start"] + 7 * 3600)                            # long past: cleared
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM reminders").fetchone()[0], 0)

    def test_remove_and_refusals(self):
        later = self.slots[1]
        reminders.add(self.c, "mcu", later["start"], now=T0)
        self.assertEqual(reminders.remove(self.c, "mcu", later["start"]), 1)
        with self.assertRaises(ValueError):
            reminders.add(self.c, "mcu", later["start"] + 7, now=T0)                       # no show starts then
        with self.assertRaises(ValueError):
            reminders.add(self.c, "mcu", self.slots[0]["start"], now=self.slots[0]["end"] + 1)   # already over
        with self.assertRaises(ValueError):
            reminders.add(self.c, "mcu", "soon", now=T0)

    def test_phones_and_the_roku_app_may_use_them(self):
        self.assertIn("reminders", R.REMOTE_GET_API)
        self.assertIn("reminders", R.REMOTE_POST_API)


if __name__ == "__main__":
    unittest.main()
