"""Intros and credits found by comparing episodes of a show."""
import os
import random
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock

from helpers import make_db
from herotv import intros as I, ondemand, tools


def ep(c, n, path="/x", runtime=1300, series="Show"):
    c.execute("INSERT INTO media(path,title,franchise,series,season,episode,verified,playable,available,runtime_s) "
              "VALUES(?,?,?,?,1,?,1,1,1,?)", (f"{path}{n}.mkv", f"Ep {n}", "TV", series, n, runtime))
    c.commit()
    return c.execute("SELECT * FROM media WHERE episode=? AND series=?", (n, series)).fetchone()


class Matching(unittest.TestCase):
    def test_shared_stretch_is_found_and_chance_is_not(self):
        rng = random.Random(5)
        theme = [rng.getrandbits(15) for _ in range(160)]                       # 40 s of the same sound
        a = [rng.getrandbits(15) for _ in range(300)] + theme + [rng.getrandbits(15) for _ in range(400)]
        b = [rng.getrandbits(15) for _ in range(80)] + theme + [rng.getrandbits(15) for _ in range(500)]
        m = I.best_match(a, b)
        self.assertEqual((m[0], m[2]), (300, 80))
        self.assertAlmostEqual(m[1] - m[0], 160, delta=3)
        self.assertIsNone(I.best_match(a[:300], b[:80] + b[240:]))             # no theme in common: nothing
        self.assertIsNone(I.best_match([None] * 400, [None] * 400))              # silence never matches

    def test_codes(self):
        lv = [[-20, -30, -25, -40, -50, -50, -60, -70], [-10, -30, -25, -40, -50, -50, -60, -70]]
        c = I.codes(lv + [[-90] * 8])
        self.assertEqual(c[2], None)
        self.assertNotEqual(c[0], c[1])                                           # band 1 got louder


class Storage(unittest.TestCase):
    def test_todo_partner_save_and_play(self):
        c = make_db()
        e1, e2, e3 = ep(c, 1), ep(c, 2), ep(c, 3)
        ep(c, 1, series="Lonely")                                                  # one episode only: never checked
        self.assertEqual([r["id"] for r in I.todo(c)], [e1["id"], e2["id"], e3["id"]])
        self.assertEqual(I.partner(c, e1)["id"], e2["id"])
        self.assertEqual(I.partner(c, e3)["id"], e2["id"])
        I.save(c, {e1["id"]: {"intro_start": 62.0, "intro_end": 101.5, "credits": 1250.0},
                   e2["id"]: {"intro_start": 0, "intro_end": 0, "credits": 0}})
        self.assertEqual([r["id"] for r in I.todo(c)], [e3["id"]])
        self.assertEqual(I.for_media(c, e1["id"])["intro_end"], 101.5)
        self.assertIsNone(I.for_media(c, e2["id"]))
        p = ondemand.play(c, e1["id"])
        self.assertEqual(p["skip"], {"intro_start": 62.0, "intro_end": 101.5, "credits": 1250.0})
        c.execute("INSERT INTO skips(series,intro,outro) VALUES('Show',30,60)")       # your own points win
        self.assertEqual(ondemand.play(c, e1["id"])["skip"], {"intro_start": 0, "intro_end": 30, "credits": 1240})
        st = I.status(c)
        self.assertEqual((st["episodes"], st["found"]), (4, 1))


@unittest.skipUnless(tools.find_tool("ffmpeg"), "needs ffmpeg")
class RealSound(unittest.TestCase):
    def test_theme_song_in_two_episodes(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        ff = tools.find_tool("ffmpeg")

        def run(*a):
            subprocess.run([ff, "-v", "error", "-y", *a], check=True)
        theme = ("aevalsrc=exprs='0.3*sin(2*PI*(220+110*floor(mod(t*2\\,4)))*t)+0.2*sin(2*PI*(330+55*floor(mod(t*3\\,5)))*t)"
                 "*(0.5+0.5*sin(2*PI*0.7*t))':s=22050:d=25")
        run("-f", "lavfi", "-i", theme, os.path.join(d, "theme.wav"))
        for n, (pre, seed) in enumerate(((50, 1), (20, 2)), 1):
            run("-f", "lavfi", "-i", f"anoisesrc=c=pink:seed={seed}:a=0.3:d={pre}:r=22050", "-i", os.path.join(d, "theme.wav"),
                "-f", "lavfi", "-i", f"anoisesrc=c=brown:seed={seed + 7}:a=0.4:d=60:r=22050",
                "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1", "-c:a", "aac", os.path.join(d, f"ep{n}.m4a"))
        a = {"id": 1, "path": os.path.join(d, "ep1.m4a"), "runtime_s": 135}
        b = {"id": 2, "path": os.path.join(d, "ep2.m4a"), "runtime_s": 105}
        with unittest.mock.patch.object(I, "MIN_MATCH_S", 12):
            r = I.find_pair(ff, a, b)
        self.assertAlmostEqual(r[1]["intro_start"], 50, delta=1.5)
        self.assertAlmostEqual(r[1]["intro_end"], 75, delta=1.5)
        self.assertAlmostEqual(r[2]["intro_start"], 20, delta=1.5)


if __name__ == "__main__":
    import unittest.mock  # noqa: F401
    unittest.main()
