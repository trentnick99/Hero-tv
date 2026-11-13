

import os as _os
import unittest as _ut


class GiveUpTests(_ut.TestCase):
    """A video whose conversion fails is tried twice, not every 30 seconds for ever."""

    def test_a_failing_video_is_left_alone_after_two_tries(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from herotv import inbox, launcher, sortrules
        from herotv.config import Config
        os = _os
        d = tempfile.mkdtemp()
        cfg = Config(media_dir=Path(d), db_path=os.path.join(d, "t.sqlite3"), channels_file=os.path.join(d, "channels.json"))
        f = os.path.join(d, "Bad.Movie.2007.mkv")
        open(f, "wb").write(b"x" * 10)
        calls = []
        inbox._tries.clear()
        with mock.patch.object(inbox, "candidates", lambda cfg, seen, now=None: ([f], {})), \
                mock.patch.object(sortrules, "load", lambda cfg: ({}, [])), mock.patch.object(sortrules, "smart_rules", lambda cfg: None), \
                mock.patch.object(sortrules, "targets", lambda *a, **k: ["DC"]), mock.patch.object(inbox, "series_lookup", lambda cfg, ch: lambda s: None), \
                mock.patch.object(launcher, "is_busy", lambda p: False):
            place = lambda src, picked, media, **kw: calls.append(src) or False
            for _ in range(5):
                inbox.run_once(cfg, {}, place=place)
            self.assertEqual(len(calls), 2)
            self.assertTrue(inbox.gave_up(f))
            open(f, "wb").write(b"a different download")           # replaced: it gets a fresh start
            self.assertFalse(inbox.gave_up(f))
            inbox.run_once(cfg, {}, place=place)
            self.assertEqual(len(calls), 3)
