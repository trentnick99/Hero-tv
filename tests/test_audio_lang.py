"""Preferred sound language (English...): videos with several sound tracks get a hidden copy that plays the preferred one."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import S, make_db, tmpdb
from herotv import library, prepare, tools
from herotv.config import Config
from test_prepare import FF, HAVE_FF, streams


def two_tracks(path, first="jpn", second="eng", secs=3, acodec="aac", container_ext=None):
    """A video whose first (default) sound is `first`, with `second` as another track."""
    subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10",
                    "-f", "lavfi", "-i", "sine=frequency=300", "-f", "lavfi", "-i", "sine=frequency=900", "-t", str(secs),
                    "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", acodec,
                    "-metadata:s:a:0", f"language={first}", "-metadata:s:a:1", f"language={second}",
                    "-disposition:a:0", "default", "-disposition:a:1", "0", path], check=True)


def tone_hz_guess(path):
    """Which sound is in the first audio track: 300 Hz or 900 Hz (zero-crossings per second of a decoded sample)."""
    raw = subprocess.run([FF, "-v", "error", "-i", path, "-map", "0:a:0", "-t", "1", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    import struct
    v = struct.unpack("<%dh" % (len(raw) // 2), raw)
    return sum(1 for a, b in zip(v, v[1:]) if (a < 0) != (b < 0)) / 2


class Rules(unittest.TestCase):
    def test_summary_and_wants(self):
        tr = [{"n": 0, "lang": "jpn", "default": True}, {"n": 1, "lang": "eng", "default": False}]
        self.assertEqual(library.track_summary(tr), "jpn*,eng")
        self.assertEqual(library.track_summary([]), "-")
        self.assertTrue(library.wants_lang("jpn*,eng", "eng"))
        self.assertFalse(library.wants_lang("eng*,jpn", "eng"))       # English already plays
        self.assertFalse(library.wants_lang("jpn*", "eng"))           # no English track at all
        self.assertFalse(library.wants_lang("eng*", "eng"))
        self.assertFalse(library.wants_lang("jpn*,eng", ""))          # switched off
        self.assertFalse(library.wants_lang("", "eng"))               # not read yet
        self.assertFalse(library.wants_lang("-", "eng"))
        self.assertTrue(library.wants_lang("und*,eng", "eng"))        # untagged default, English second

    def test_pick_track_and_codes(self):
        tr = [{"n": 0, "lang": "jpn", "default": True}, {"n": 1, "lang": "en", "default": False}, {"n": 2, "lang": "eng", "default": True}]
        self.assertEqual(library.pick_track(tr, "eng"), 2)            # 'en' counts as English; the default-flagged one wins
        self.assertIsNone(library.pick_track(tr, "spa"))
        self.assertIsNone(library.pick_track(tr, ""))
        self.assertEqual(library.lang_code("FRA"), "fre")
        self.assertEqual(library.lang_code(""), "und")


@unittest.skipUnless(HAVE_FF, "ffmpeg/ffprobe not installed")
class Real(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(f"{self.root}/Movies")
        self.cfg = Config(media_dir=self.root, db_path=tmpdb(), channels_file=os.path.join(self.root, "ch.json"),
                          tz="America/New_York", port=0)
        Path(self.cfg.channels_file).write_text(json.dumps({"channels": [{"id": "m", "number": 1, "name": "M", "match": {"franchise": ["Movies"]}}]}))
        self.c = make_db(self.cfg.db_path)
        self.addCleanup(self.c.close)
        S.load_channels(self.c, json.loads(Path(self.cfg.channels_file).read_text())["channels"])
        prepare.set_folder(self.root)
        self.settings = Path(self.root) / "settings.json"
        sf = mock.patch("herotv.config.settings_file", return_value=self.settings)
        sf.start()
        self.addCleanup(sf.stop)
        self.anime = f"{self.root}/Movies/Anime Film (2020).mp4"          # plays fine as it is - but in Japanese
        self.dub = f"{self.root}/Movies/Dubbed Film (2021).mp4"           # English already plays
        self.one = f"{self.root}/Movies/Silent Film (2019).mp4"
        two_tracks(self.anime, "jpn", "eng")
        two_tracks(self.dub, "eng", "jpn")
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-f", "lavfi", "-i", "sine=frequency=500",
                        "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-metadata:s:a:0", "language=jpn", self.one], check=True)
        library.scan(self.c, self.root)

    def row(self, path):
        return self.c.execute("SELECT * FROM media WHERE path=?", (os.path.normpath(path),)).fetchone()

    def settle(self):
        """Run the copy-maker until it has nothing left (reads languages first, then makes copies)."""
        for _ in range(10):
            if not prepare.run_once(self.c, FF, self.root):
                return
        self.fail("the copy-maker never finished")

    def test_languages_are_read_in_the_background(self):
        self.assertEqual(self.row(self.anime)["atracks"], "")
        prepare.run_once(self.c, FF, self.root)
        self.assertEqual(self.row(self.anime)["atracks"], "jpn*,eng")
        self.assertEqual(self.row(self.dub)["atracks"], "eng*,jpn")
        self.assertEqual(self.row(self.one)["atracks"], "jpn*")

    def test_english_copy_is_made_only_where_needed_and_served(self):
        self.settle()
        a, d, o = self.row(self.anime), self.row(self.dub), self.row(self.one)
        cp = prepare.copy_path(self.c, a["id"], a["size"])
        self.assertTrue(cp and os.path.isfile(cp))
        self.assertLess(abs(tone_hz_guess(cp) - 900), 60)               # the copy's first sound is the English (900 Hz) track
        self.assertLess(abs(tone_hz_guess(self.anime) - 300), 60)       # the original still plays Japanese first
        self.assertIsNone(prepare.copy_path(self.c, d["id"], d["size"]))   # English already plays: no copy
        self.assertIsNone(prepare.copy_path(self.c, o["id"], o["size"]))   # no English track: no copy
        self.assertEqual(prepare.delivery(self.c, a["id"], "browser")[0], cp)   # the PC gets the English copy
        self.assertEqual(prepare.delivery(self.c, a["id"], "roku")[0], cp)      # so does a Roku (it would have played the original)
        self.assertEqual(prepare.delivery(self.c, d["id"], "browser")[0], os.path.normpath(self.dub))
        self.assertEqual(self.row(self.anime)["playable"], 1)           # never left a channel
        self.assertTrue(os.path.isfile(self.anime))                     # the original is untouched
        s = prepare.status(self.c)
        self.assertEqual((s["lang"], s["lang_need"], s["lang_ready"]), ("eng", 1, 1))
        self.assertEqual(streams(cp)["audio"], "aac")

    def test_a_fixed_video_that_lost_english_gets_a_copy_from_its_saved_original(self):
        # What an older Fix did: the .mp4 kept only the first (Hindi) sound track; the untouched file went to .originals
        hindi_only = f"{self.root}/Movies/Iron Film 2 (2010).mp4"
        two_tracks(hindi_only, "hin", "hin")
        os.makedirs(f"{self.root}/Movies/.originals")
        saved = f"{self.root}/Movies/.originals/Iron Film 2 (2010).mp4"
        two_tracks(saved, "hin", "eng")
        library.scan(self.c, self.root)
        self.settle()
        r = self.row(hindi_only)
        self.assertEqual(r["atracks"], "hin*,hin")
        self.assertTrue(library.lacks_lang(r["atracks"], "eng"))
        cp = prepare.copy_path(self.c, r["id"], r["size"])
        self.assertTrue(cp and os.path.isfile(cp))
        self.assertLess(abs(tone_hz_guess(cp) - 900), 60)               # English, taken from the saved original
        self.assertEqual(prepare.delivery(self.c, r["id"], "browser")[0], cp)
        self.assertEqual(prepare.delivery(self.c, r["id"], "roku")[0], cp)
        self.assertTrue(os.path.isfile(saved) and os.path.isfile(hindi_only))        # nothing moved or deleted
        self.assertLess(abs(tone_hz_guess(hindi_only) - 300), 60)

    def test_no_saved_original_means_no_copy_and_no_error(self):
        lone = f"{self.root}/Movies/Lone Film (2012).mp4"
        two_tracks(lone, "hin", "hin")
        library.scan(self.c, self.root)
        self.settle()
        r = self.row(lone)
        self.assertIsNone(prepare.copy_path(self.c, r["id"], r["size"]))
        self.assertEqual(prepare.delivery(self.c, r["id"], "browser")[0], os.path.normpath(lone))

    def test_converting_keeps_every_language_with_english_first(self):
        from herotv import launcher
        src = f"{self.root}/Movies/Dual Film (2018).mkv"
        two_tracks(src, "hin", "eng", acodec="ac3")                      # Dolby sound: always converted
        res, final = launcher._convert_one_locked(src, FF)
        self.assertEqual(res, "converted")
        tracks = library.audio_tracks(final)
        self.assertEqual([t["lang"] for t in tracks], ["eng", "hin"])
        self.assertEqual([t["default"] for t in tracks], [True, False])
        self.assertLess(abs(tone_hz_guess(final) - 900), 60)
        self.assertTrue(os.path.isfile(f"{self.root}/Movies/.originals/Dual Film (2018).mkv"))

    def six(self, src, vcodec="libx264"):
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-f", "lavfi", "-i", "sine=frequency=300",
                        "-f", "lavfi", "-i", "sine=frequency=900", "-t", "3", "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", vcodec,
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "6", "-metadata:s:a:0", "language=hin", "-metadata:s:a:1", "language=eng",
                        "-disposition:a:0", "default", "-disposition:a:1", "0", src], check=True)

    def test_surround_sound_is_mixed_down_in_new_copies(self):
        src = f"{self.root}/Movies/Surround Film (2013).mp4"
        self.six(src)
        library.scan(self.c, self.root)
        self.settle()
        r = self.row(src)
        cp = prepare.copy_path(self.c, r["id"], r["size"])
        self.assertTrue(cp)
        self.assertEqual(library.audio_tracks(src)[1]["channels"], 6)
        self.assertEqual(library.audio_tracks(cp)[0]["channels"], 2)      # mixed down, not copied as 5.1
        self.assertEqual(self.c.execute("SELECT mix FROM prepared WHERE media_id=?", (r["id"],)).fetchone()[0], 1)

    def test_an_old_surround_copy_is_made_again_and_nothing_else_is_touched(self):
        src = f"{self.root}/Movies/Old Surround (2014).mp4"
        self.six(src)
        library.scan(self.c, self.root)
        r = self.row(src)
        old = prepare.folder() / f"{r['id']}-{r['size']}.mp4"
        prepare.folder().mkdir(parents=True, exist_ok=True)
        shutil.copy(src, old)                                            # a copy as an older version made it: 6 channels
        prepare._record(self.c, r["id"], "ready", r["size"], old.name, nbytes=old.stat().st_size, alang="eng", mix=0)
        self.c.execute("UPDATE media SET playable=1 WHERE id=?", (r["id"],))
        self.c.commit()
        self.settle()
        self.assertEqual(library.audio_tracks(str(old))[0]["channels"], 2)
        self.assertEqual(self.c.execute("SELECT mix FROM prepared WHERE media_id=?", (r["id"],)).fetchone()[0], 1)
        self.assertEqual(library.audio_tracks(src)[0]["channels"], 6)    # the original is untouched
        self.assertLess(abs(tone_hz_guess(str(old)) - 900), 60)          # and the remade copy still plays English

    def test_stereo_copies_are_not_remade(self):
        self.settle()
        a = self.row(self.anime)
        n = self.c.execute("SELECT made FROM prepared WHERE media_id=?", (a["id"],)).fetchone()[0]
        self.c.execute("UPDATE prepared SET mix=0")                      # as if made by an older version
        self.c.commit()
        self.settle()
        self.assertEqual(self.c.execute("SELECT made,mix FROM prepared WHERE media_id=?", (a["id"],)).fetchone()[1], 1)
        self.assertEqual(self.c.execute("SELECT made FROM prepared WHERE media_id=?", (a["id"],)).fetchone()[0], n)

    def test_converting_mixes_surround_down(self):
        from herotv import launcher
        src = f"{self.root}/Movies/Dolby Film (2016).mkv"
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-f", "lavfi", "-i", "sine=frequency=300",
                        "-t", "3", "-map", "0:v", "-map", "1:a", "-c:v", "mpeg4", "-c:a", "aac", "-ac", "6", src], check=True)   # picture must be redone
        res, final = launcher._convert_one_locked(src, FF)
        self.assertEqual(res, "converted")
        self.assertEqual(library.audio_tracks(final)[0]["channels"], 2)

    def test_a_cut_off_download_is_named_and_not_retried(self):
        from herotv import launcher
        src = f"{self.root}/Movies/Cut Film (2020).mkv"
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25", "-f", "lavfi", "-i", "sine=frequency=300",
                        "-t", "120", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "ac3", src], check=True)
        full = os.path.getsize(src)
        with open(src, "rb") as fh:
            data = fh.read(full // 2)
        with open(src, "wb") as fh:
            fh.write(data)                                                # the download stopped half way
        self.assertFalse(library.has_video_near_end(src, 120))
        lines = []
        with mock.patch.object(launcher, "say", lambda m="": lines.append(m)):
            res, _ = launcher._convert_one_locked(src, FF)
        self.assertEqual(res, "failed")
        self.assertTrue(any("cut off" in x for x in lines), lines)
        self.assertFalse(any("re-encoding the picture" in x for x in lines))
        self.assertTrue(os.path.isfile(src))                              # untouched
        whole = f"{self.root}/Movies/Whole Film (2020).mkv"
        two_tracks(whole, "hin", "eng", secs=70, acodec="ac3")
        self.assertTrue(library.has_video_near_end(whole, 70))

    def test_switched_off_makes_nothing_and_serves_the_original(self):
        self.settings.write_text(json.dumps({"audio_lang": ""}))
        self.settle()
        a = self.row(self.anime)
        self.assertEqual(a["atracks"], "")                              # not even read
        self.assertIsNone(prepare.copy_path(self.c, a["id"], a["size"]))
        self.assertEqual(prepare.delivery(self.c, a["id"], "browser")[0], os.path.normpath(self.anime))

    def test_other_language_choice_and_changing_it(self):
        self.settings.write_text(json.dumps({"audio_lang": "jpn"}))
        self.settle()
        d = self.row(self.dub)                                           # now the English-first one wants Japanese
        cp = prepare.copy_path(self.c, d["id"], d["size"])
        self.assertTrue(cp)
        self.assertLess(abs(tone_hz_guess(cp) - 900), 60)               # the dub's Japanese track is its second one (900 Hz)
        a = self.row(self.anime)
        self.assertIsNone(prepare.copy_path(self.c, a["id"], a["size"]))   # Japanese already plays there

    def test_changed_preference_rebuilds_without_losing_the_old_copy_on_failure(self):
        self.settle()
        a = self.row(self.anime)
        cp = prepare.copy_path(self.c, a["id"], a["size"])
        self.settings.write_text(json.dumps({"audio_lang": "jpn"}))      # Japanese already plays on this one: copy no longer wanted
        self.assertEqual(prepare.delivery(self.c, a["id"], "browser")[0], os.path.normpath(self.anime))
        self.assertTrue(os.path.isfile(cp))                              # but the copy is not thrown away
        prepare.tidy(self.c)
        self.assertTrue(os.path.isfile(cp))
        self.settings.write_text(json.dumps({"audio_lang": "eng"}))
        self.assertEqual(prepare.delivery(self.c, a["id"], "browser")[0], cp)   # back to English: the existing copy serves at once

    def test_failed_rebuild_keeps_the_working_copy(self):
        self.settings.write_text(json.dumps({"audio_lang": "spa"}))
        self.settle()
        self.settings.write_text(json.dumps({"audio_lang": "eng"}))
        self.settle()
        a = self.row(self.anime)
        cp = prepare.copy_path(self.c, a["id"], a["size"])
        self.assertTrue(cp)
        self.c.execute("UPDATE prepared SET alang='xxx' WHERE media_id=?", (a["id"],))   # pretend it was built for another language
        self.c.commit()
        bad = mock.Mock(returncode=1, errors=["boom"])
        row = self.c.execute("SELECT * FROM media WHERE id=?", (a["id"],)).fetchone()
        self.assertEqual(prepare.prepare_one(self.c, row, FF, run=lambda cmd, rt: bad), "failed")
        self.assertTrue(prepare.copy_path(self.c, a["id"], a["size"]))   # still there and still 'ready'
        self.assertEqual([r["id"] for r in prepare.todo(self.c, self.root) if r["id"] == a["id"]], [])   # and not retried at once

    def test_a_replaced_file_is_read_again(self):
        prepare.run_once(self.c, FF, self.root)
        self.assertEqual(self.row(self.anime)["atracks"], "jpn*,eng")
        two_tracks(self.anime, "eng", "jpn", secs=4)                      # new content, same name
        library.scan(self.c, self.root)
        self.assertEqual(self.row(self.anime)["atracks"], "")
        prepare.run_once(self.c, FF, self.root)
        self.assertEqual(self.row(self.anime)["atracks"], "eng*,jpn")

    def test_dolby_two_language_movie_gets_the_english_track_in_its_first_copy(self):
        dolby = f"{self.root}/Movies/Dolby Two (2018).mkv"
        two_tracks(dolby, "jpn", "eng", acodec="ac3")
        library.scan(self.c, self.root)
        self.assertEqual(self.row(dolby)["playable"], 0)                 # needs a copy anyway (Dolby sound)
        self.settle()
        r = self.row(dolby)
        cp = prepare.copy_path(self.c, r["id"], r["size"])
        self.assertTrue(cp)
        self.assertEqual(r["playable"], 1)
        self.assertLess(abs(tone_hz_guess(cp) - 900), 60)               # English, not the Japanese default

    def test_setting_is_validated_through_the_api(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        from herotv.server import App, make_handler
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(self.cfg)))
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def post(body):
            req = urllib.request.Request(base + "/api/prepare", json.dumps(body).encode(), {"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.load(r)
            except urllib.error.HTTPError as e:
                return e.code, None
        import urllib.error
        self.assertEqual(post({"lang": "klingon"})[0], 400)
        self.assertEqual(post({"lang": 5})[0], 400)
        st, j = post({"lang": "spa"})
        self.assertEqual((st, j["lang"]), (200, "spa"))
        self.assertEqual(library.pref_lang(), "spa")
        self.assertEqual(post({"lang": ""})[1]["lang"], "")


if __name__ == "__main__":
    unittest.main()
