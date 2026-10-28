"""H.265 and Dolby sound: what the TV window on this PC was tested to play decides what is skipped."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from herotv import config, library, tools


class CapsTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.sf = Path(self.d) / "settings.json"
        p = mock.patch.object(config, "settings_file", return_value=self.sf)
        p.start()
        self.addCleanup(p.stop)
        w = mock.patch.object(library, "IS_WIN", True)
        w.start()
        self.addCleanup(w.stop)
        os.environ.pop("HEROTV_ALLOW_HEVC", None)
        library._caps["mtime"] = None

    def write(self, caps):
        self.sf.write_text(json.dumps({"browser_caps": caps}), encoding="utf-8")
        st = os.stat(self.sf)
        os.utime(self.sf, (st.st_atime, st.st_mtime + len(json.dumps(caps))))   # a new mtime each time

    def test_untested_pc_skips_hevc_and_dolby(self):
        self.assertFalse(library.video_ok("hevc", "yuv420p|main", ".mp4"))
        self.assertFalse(library.audio_ok("ac3"))
        self.assertTrue(library.audio_ok("aac"))
        self.assertIn("H.265", library.why_not_playable("hevc", "aac", "yuv420p|main", ".mp4"))

    def test_hevc_plays_once_the_pc_passes_the_test(self):
        self.write({"hevc": True, "hevc10": False, "hevc_mkv": False, "ac3": True, "eac3": False, "checked": 5})
        self.assertTrue(library.video_ok("hevc", "yuv420p|main", ".mp4"))
        self.assertFalse(library.video_ok("hevc", "yuv420p10le|main 10", ".mp4"))   # 10-bit failed its own test
        self.assertFalse(library.video_ok("hevc", "yuv420p|main", ".mkv"))          # Fix repackages it quickly
        self.assertFalse(library.video_ok("hevc", "yuv422p|rext", ".mp4"))
        self.assertTrue(library.audio_ok("ac3"))
        self.assertFalse(library.audio_ok("eac3"))
        self.assertEqual(library.caps()["checked"], 5)
        self.assertIn("seconds", library.why_not_playable("hevc", "aac", "yuv420p|main", ".mkv"))

    def test_everything_passes(self):
        self.write({"hevc": True, "hevc10": True, "hevc_mkv": True, "ac3": True, "eac3": True})
        self.assertTrue(library.video_ok("hevc", "yuv420p10le|main 10", ".mkv"))
        self.assertTrue(library.audio_ok("eac3"))

    def test_broken_settings_file_means_untested(self):
        self.sf.write_text("{not json", encoding="utf-8")
        self.assertEqual(library.caps(), {})
        self.assertFalse(library.video_ok("hevc", "yuv420p|main", ".mp4"))


class EncoderTests(unittest.TestCase):
    def setUp(self):
        tools._ENC.clear()

    def test_uses_the_first_graphics_card_encoder_that_works(self):
        tried = []

        def run(cmd, **kw):
            name = cmd[cmd.index("-c:v") + 1]
            tried.append(name)
            return mock.Mock(returncode=0 if name == "h264_qsv" else 1)
        a = tools.h264_encoder("ffmpeg-x", run=run)
        self.assertIn("h264_qsv", a)
        self.assertEqual(tried[:2], ["h264_nvenc", "h264_qsv"])
        self.assertEqual(tools.h264_encoder("ffmpeg-x", run=lambda *a, **k: 1 / 0), a)    # remembered

    def test_falls_back_to_the_processor(self):
        a = tools.h264_encoder("ffmpeg-y", run=lambda cmd, **kw: mock.Mock(returncode=1))
        self.assertIn("libx264", a)
        self.assertIn("yuv420p", a)


if __name__ == "__main__":
    unittest.main()
