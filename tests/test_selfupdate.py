"""One-press updates: asking GitHub, what's new, a safe download, handing over to the updater."""
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import __version__, config, launcher, remote, selfupdate, updater  # noqa: E402

NEXT = ".".join(str(x) for x in (updater.version_tuple(__version__)[0], updater.version_tuple(__version__)[1] + 1, 0))
SRC = '''import os
os.system("echo should never run")
NOTES = {
    "%s": ["Shiny thing one.", "Shiny thing two."],
    "1.0.0": ["Old."],
}
''' % NEXT


def release(version=NEXT, zip_url=None, size=123):
    return {"tag_name": "v" + version, "html_url": "https://github.com/x/releases/tag/v" + version, "published_at": "2026-10-25",
            "assets": [{"name": f"HERO-TV-Setup-v{version}.exe", "browser_download_url": "https://github.com/a.exe", "size": 9},
                       {"name": f"HERO-TV-v{version}-windows.zip", "size": size,
                        "browser_download_url": zip_url or f"https://github.com/trentnick99/Hero-tv/releases/download/v{version}/HERO-TV-v{version}-windows.zip"}]}


def make_zip(version, app=True):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("HERO TV/herotv/__init__.py", f'__version__ = "{version}"\n')
        if app:
            z.writestr("HERO TV/HERO-TV.exe", "exe")
    return b.getvalue()


class Resp(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class SelfUpdateTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        p = mock.patch.object(config, "settings_file", return_value=Path(self.d) / "settings.json")
        p.start(); self.addCleanup(p.stop)
        saved = dict(selfupdate._state)
        self.addCleanup(lambda: (selfupdate._state.clear(), selfupdate._state.update(saved)))
        selfupdate._state.update(checked=0, info=None, error="", phase="", done=0, total=0)

    def test_notes_are_read_without_running_the_file(self):
        self.assertEqual(selfupdate.notes_from_source(SRC, NEXT), ["Shiny thing one.", "Shiny thing two."])
        self.assertEqual(selfupdate.notes_from_source("NOTES = make()", NEXT), [])
        self.assertEqual(selfupdate.notes_from_source("not python (", NEXT), [])

    def test_check_offers_a_newer_version_with_its_notes(self):
        st = selfupdate.check(gj=lambda u: release(), gt=lambda u: SRC, now=1000)
        self.assertTrue(st["available"])
        self.assertEqual((st["current"], st["latest"]), (__version__, NEXT))
        self.assertEqual(st["notes"], ["Shiny thing one.", "Shiny thing two."])
        calls = []
        selfupdate.check(gj=lambda u: calls.append(u) or release(), gt=lambda u: SRC, now=2000)
        self.assertEqual(calls, [])                                        # remembered for a few hours
        selfupdate.check(force=True, gj=lambda u: calls.append(u) or release(), gt=lambda u: SRC, now=2000)
        self.assertEqual(calls, [selfupdate.LATEST])

    def test_same_or_older_is_not_offered(self):
        self.assertFalse(selfupdate.check(gj=lambda u: release(__version__), gt=lambda u: SRC, now=1)["available"])
        self.assertFalse(selfupdate.check(force=True, gj=lambda u: release("1.0.0"), gt=lambda u: SRC, now=2)["available"])

    def test_offline_is_a_plain_message(self):
        def boom(u):
            raise OSError("down")
        st = selfupdate.check(gj=boom, now=5)
        self.assertFalse(st["available"])
        self.assertIn("Could not check GitHub", st["error"])
        self.assertIn("no connection", selfupdate._why(__import__("urllib.error").error.URLError("down")))

    def test_api_limit_falls_back_to_the_releases_page(self):
        import urllib.error
        from unittest import mock

        class R:
            def geturl(self):
                return "https://github.com/trentnick99/Hero-tv/releases/tag/v9.9.9"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        self.addCleanup(selfupdate._state.update, {"checked": 0, "info": None, "error": ""})
        limited = urllib.error.HTTPError(selfupdate.LATEST, 403, "rate limit exceeded", {}, None)
        with mock.patch.object(selfupdate, "_get_json", side_effect=limited), \
                mock.patch.object(selfupdate, "_get_text", side_effect=OSError("no notes")), \
                mock.patch.object(selfupdate.net, "urlopen", return_value=R()):
            st = selfupdate.check(force=True, now=7)
        self.assertEqual((st["latest"], st["available"], st["error"]), ("9.9.9", True, ""))
        self.assertEqual(selfupdate._state["info"]["zip_url"],
                         "https://github.com/trentnick99/Hero-tv/releases/download/v9.9.9/HERO-TV-v9.9.9-windows.zip")
        self.assertIn("limiting", selfupdate._why(limited))

    def test_setting_switches_automatic_checks_off(self):
        self.assertTrue(selfupdate.enabled())
        (Path(self.d) / "settings.json").write_text('{"auto_update": false}')
        self.assertFalse(selfupdate.enabled())

    def test_download_only_from_github_and_complete(self):
        dest = Path(self.d) / "dl" / "x.zip"
        with self.assertRaises(ValueError):
            selfupdate.download("https://evil.example/x.zip", dest, 3)
        with self.assertRaises(ValueError):                                # redirected somewhere unexpected
            selfupdate.download("https://github.com/x.zip", dest, 3, opener=lambda u: Resp(b"abc", "https://evil.example/x"))
        with self.assertRaises(ValueError):                                # cut short
            selfupdate.download("https://github.com/x.zip", dest, 10, opener=lambda u: Resp(b"abc", "https://objects.githubusercontent.com/x"))
        self.assertFalse(dest.exists())
        selfupdate.download("https://github.com/x.zip", dest, 3, opener=lambda u: Resp(b"abc", "https://release-assets.githubusercontent.com/x"))
        self.assertEqual(dest.read_bytes(), b"abc")

    def wait_phase(self):
        for _ in range(100):
            if selfupdate._state["phase"] not in ("", "downloading"):
                return selfupdate._state["phase"]
            time.sleep(0.03)
        return selfupdate._state["phase"]

    def test_install_checks_the_zip_then_hands_over(self):
        data = make_zip(NEXT)
        selfupdate.check(gj=lambda u: release(size=len(data)), gt=lambda u: SRC, now=1)
        spawned = []
        with mock.patch.dict(os.environ, {"HEROTV_SELFUPDATE_TEST": "1"}):
            selfupdate.install(root=self.d, opener=lambda u: Resp(data, u), spawn=lambda z, r: spawned.append(Path(z).name))
            self.assertEqual(self.wait_phase(), "installing")
        self.assertEqual(spawned, [f"HERO-TV-v{NEXT}-windows.zip"])

    def test_install_refuses_a_zip_of_another_version(self):
        data = make_zip("0.0.1")
        selfupdate.check(gj=lambda u: release(size=len(data)), gt=lambda u: SRC, now=1)
        spawned = []
        with mock.patch.dict(os.environ, {"HEROTV_SELFUPDATE_TEST": "1"}):
            selfupdate.install(root=self.d, opener=lambda u: Resp(data, u), spawn=lambda z, r: spawned.append(z))
            self.assertEqual(self.wait_phase(), "failed")
        self.assertEqual(spawned, [])
        self.assertIn("not " + NEXT, selfupdate.status()["error"])

    def test_install_needs_something_newer_and_the_built_app(self):
        with self.assertRaises(ValueError):
            selfupdate.install(root=self.d)                              # nothing offered
        selfupdate.check(gj=lambda u: release(), gt=lambda u: SRC, now=1)
        with mock.patch.dict(os.environ, {"HEROTV_SELFUPDATE_TEST": ""}), self.assertRaises(ValueError):
            selfupdate.install(root=self.d)                              # running from Python source

    def test_phones_cannot_update(self):
        self.assertNotIn("update", remote.REMOTE_GET_API | remote.REMOTE_POST_API)
        self.assertFalse(any("update".startswith(p) for p in remote.REMOTE_GET_API_PREFIX))

    def test_failed_update_restarts_the_old_one_and_says_why(self):
        started = []
        with mock.patch.object(launcher, "update", return_value=1), \
                mock.patch.object(launcher, "app_data_dir", return_value=Path(self.d)), \
                mock.patch.object(launcher.subprocess, "Popen", side_effect=lambda cmd, **k: started.append(cmd)):
            out, err = sys.stdout, sys.stderr
            try:
                rc = launcher.self_update(os.path.join(self.d, "x.zip"))
            finally:
                sys.stdout.close() if sys.stdout is not out else None
                sys.stdout, sys.stderr = out, err
        self.assertEqual(rc, 1)
        self.assertEqual(started[0][-3:], ["launch", "--quiet", "--no-browser"])
        msg = selfupdate.take_last_error()
        self.assertIn("could not be installed", msg)
        self.assertEqual(selfupdate.take_last_error(), "")                 # shown once


if __name__ == "__main__":
    unittest.main()
