import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import qr  # noqa: E402

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None


def decode(text):
    m = qr.matrix(text)
    n = len(m)
    img = np.full(((n + 8) * 8, (n + 8) * 8), 255, np.uint8)
    for r, row in enumerate(m):
        for c, x in enumerate(row):
            if x:
                img[(r + 4) * 8:(r + 5) * 8, (c + 4) * 8:(c + 5) * 8] = 0
    return cv2.QRCodeDetector().detectAndDecode(img)[0]


class QrTests(unittest.TestCase):
    def test_sizes_and_svg(self):
        self.assertEqual(len(qr.matrix("HERO TV")), 21)
        self.assertEqual(len(qr.matrix("http://192.168.1.20:8788")), 25)
        s = qr.svg("http://192.168.1.20:8788")
        self.assertTrue(s.startswith("<svg") and s.endswith("</svg>"))
        with self.assertRaises(ValueError):
            qr.matrix("x" * 400)

    @unittest.skipUnless(cv2, "needs OpenCV (installed in CI)")
    def test_a_real_reader_can_read_them(self):
        for t in ("HERO TV", "http://192.168.1.20:8788", "http://10.0.0.5:8788", "http://192.168.100.200:8788/pair",
                  "http://192.168.100.200:8788/pair?x=" + "a" * 60, "y" * 120, "z" * 200, "http://192.168.1.20:8788/" + "b" * 180):
            self.assertEqual(decode(t), t, f"version {(len(qr.matrix(t)) - 17) // 4}")


if __name__ == "__main__":
    unittest.main()
