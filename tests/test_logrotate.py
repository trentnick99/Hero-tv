import os
import tempfile
import unittest
from pathlib import Path

from herotv.launcher import RotatingLog


class RotatingLogTests(unittest.TestCase):
    def test_starts_over_past_the_limit_and_keeps_one_old_copy(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "herotv.log"
            log = RotatingLog(p, limit=2000)
            log.CHECK_EVERY = 5
            for i in range(60):
                log.write(f"line {i:03d} " + "x" * 80 + "\n")
            log.flush()
            self.assertTrue(p.with_suffix(".old.log").exists())
            self.assertLess(p.stat().st_size, 2000 + 200)
            self.assertIn("line 059", p.read_text())          # the newest lines are in the new file
            self.assertIn("line 0", p.with_suffix(".old.log").read_text())
            log.f.close()

    def test_small_logs_are_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "herotv.log"
            log = RotatingLog(p)
            for i in range(500):
                log.write("hello\n")
            log.f.close()
            self.assertFalse(p.with_suffix(".old.log").exists())
            self.assertEqual(p.read_text().count("hello"), 500)

    def test_file_like_attributes_still_work(self):
        with tempfile.TemporaryDirectory() as d:
            log = RotatingLog(Path(d) / "herotv.log")
            log.flush()
            self.assertFalse(log.isatty())
            self.assertIsInstance(log.fileno(), int)
            log.f.close()


if __name__ == "__main__":
    unittest.main()
