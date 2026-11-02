"""The app window shows the HERO TV icon and a dark title bar instead of the browser's default."""
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


class AppLook(unittest.TestCase):
    def test_icon_and_title_bar_color(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('rel="icon" href="favicon.ico"', html)
        self.assertIn('name="theme-color"', html)
        self.assertEqual((WEB / "favicon.ico").read_bytes()[:4], b"\x00\x00\x01\x00")      # a real .ico
