"""The database is set up once per version of db.py, not on every connection (each web request opens its own)."""
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from herotv import db


class DbSetup(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "t.db")

    def test_setup_runs_once(self):
        db.connect(self.path).close()
        with mock.patch.object(db, "_setup", side_effect=AssertionError("set up again")):
            c = db.connect(self.path)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM media").fetchone()[0], 0)
            c.close()

    def test_older_database_is_brought_up_to_date(self):
        c = sqlite3.connect(self.path)
        c.execute("CREATE TABLE channels(id TEXT PRIMARY KEY, number INTEGER UNIQUE, name TEXT NOT NULL)")
        c.commit()
        c.close()
        c = db.connect(self.path)
        self.assertIn("kind", [r[1] for r in c.execute("PRAGMA table_info(channels)")])
        c.close()

    def test_changed_setup_runs_again(self):
        db.connect(self.path).close()
        with mock.patch.object(db, "_STAMP", db._STAMP ^ 1), mock.patch.object(db, "_setup") as again:
            db.connect(self.path).close()
        again.assert_called_once()


if __name__ == "__main__":
    unittest.main()
