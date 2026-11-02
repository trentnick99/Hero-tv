"""HERO TV's own window: opt-in setting, and Edge is the backup when it cannot open."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from herotv import config, launcher, nativewin, settings_api


class NativeWindow(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.sf = Path(self.d) / "settings.json"
        self.sf.write_text("{}")
        p = mock.patch.object(config, "settings_file", return_value=self.sf)
        p.start(); self.addCleanup(p.stop)
        self.cfg = config.Config()

    def test_off_by_default_and_saved(self):
        self.assertFalse(settings_api.read(self.cfg)["native_window"])
        settings_api.update({"native_window": True})
        self.assertTrue(settings_api.read(self.cfg)["native_window"])
        with self.assertRaises(ValueError):
            settings_api.update({"native_window": "yes"})

    def test_the_command_for_the_window(self):
        with mock.patch.object(launcher.sys, "frozen", True, create=True), mock.patch.object(launcher.sys, "executable", "C:/HERO-TV.exe"):
            self.assertEqual(launcher._native_cmd("http://x/", True), ["C:/HERO-TV.exe", "window", "http://x/"])
            self.assertEqual(launcher._native_cmd("http://x/", False)[-1], "--windowed")
        with mock.patch.object(launcher.sys, "frozen", False, create=True):
            self.assertEqual(launcher._native_cmd("http://x/", True)[1:3], ["-m", "herotv"])

    def test_edge_is_the_backup(self):
        self.sf.write_text(json.dumps({"native_window": True}))
        with mock.patch.object(launcher, "open_native", return_value=False) as nat, \
             mock.patch.object(launcher, "find_browser", return_value="edge.exe"), mock.patch.object(launcher.subprocess, "Popen") as po:
            launcher.open_tv(self.cfg, True)
        nat.assert_called_once()
        self.assertIn("--app=http://127.0.0.1:%d/" % self.cfg.port, po.call_args[0][0])

    def test_when_it_opens_edge_is_not_started(self):
        self.sf.write_text(json.dumps({"native_window": True}))
        with mock.patch.object(launcher, "open_native", return_value=True), mock.patch.object(launcher.subprocess, "Popen") as po:
            launcher.open_tv(self.cfg, True)
        po.assert_not_called()

    def test_not_asked_for_means_edge(self):
        with mock.patch.object(launcher, "open_native") as nat, mock.patch.object(launcher, "find_browser", return_value="edge.exe"), \
             mock.patch.object(launcher.subprocess, "Popen"):
            launcher.open_tv(self.cfg, True)
        nat.assert_not_called()

    def test_only_on_windows(self):
        with mock.patch.object(nativewin, "IS_WIN", False):
            self.assertFalse(nativewin.available())
            self.assertEqual(nativewin.run("http://x/"), nativewin.FAILED)


class FromBackup(unittest.TestCase):
    def test_an_old_exe_in_the_backup_folder_starts_the_real_one(self):
        from herotv import __main__ as M
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        (Path(d) / "HERO-TV.exe").write_bytes(b"x")
        old = Path(d) / ".update-backup" / "2026-11-02-002533-app" / "HERO-TV.exe"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"x")
        with mock.patch.object(M.sys, "frozen", True, create=True), mock.patch.object(M.sys, "executable", str(old)), \
             mock.patch.object(M.sys, "argv", [str(old), "launch", "--quiet"]), mock.patch("subprocess.Popen") as po:
            self.assertEqual(M._from_backup(), 0)
        self.assertEqual(po.call_args[0][0], [os.path.join(d, "HERO-TV.exe"), "launch", "--quiet"])

    def test_the_normal_exe_carries_on(self):
        from herotv import __main__ as M
        with mock.patch.object(M.sys, "frozen", True, create=True), mock.patch.object(M.sys, "executable", "/app/HERO-TV.exe"):
            self.assertIsNone(M._from_backup())


class StayHome(unittest.TestCase):
    def test_a_window_that_opened_a_dropped_file_goes_back(self):
        win = mock.Mock()
        win.get_current_url.return_value = "file:///D:/movies/New%20Movie.mp4"
        nativewin.stay_home(win, "http://127.0.0.1:8787/")
        win.load_url.assert_called_once_with("http://127.0.0.1:8787/")

    def test_a_window_showing_hero_tv_is_left_alone(self):
        win = mock.Mock()
        win.get_current_url.return_value = "http://127.0.0.1:8787/"
        nativewin.stay_home(win, "http://127.0.0.1:8787/")
        win.load_url.assert_not_called()


class UpdateFreesTheFiles(unittest.TestCase):
    def test_other_hero_tv_processes_are_closed_before_the_swap(self):
        from herotv import updater
        with mock.patch.object(updater.os, "name", "nt"), mock.patch.object(updater.subprocess, "run") as run, mock.patch.object(updater.time, "sleep"):
            updater._stop_others()
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[:4], ["taskkill", "/F", "/IM", "HERO-TV.exe"])
        self.assertIn(f"PID ne {os.getpid()}", cmd)                          # never itself

    def test_nothing_happens_off_windows(self):
        from herotv import updater
        with mock.patch.object(updater.os, "name", "posix"), mock.patch.object(updater.subprocess, "run") as run:
            updater._stop_others()
        run.assert_not_called()


class ShortcutsAndSwap(unittest.TestCase):
    def test_shortcuts_pointing_into_the_backup_are_repaired_on_windows_only(self):
        with mock.patch.object(launcher, "IS_WIN", False):
            self.assertEqual(launcher.repair_shortcuts(), 0)
        fake = mock.Mock(stdout="2\n")
        with mock.patch.object(launcher, "IS_WIN", True), mock.patch.object(launcher.sys, "frozen", True, create=True), \
             mock.patch.object(launcher.subprocess, "run", return_value=fake) as run:
            self.assertEqual(launcher.repair_shortcuts(), 2)
        self.assertIn("update-backup", run.call_args[0][0][-1])
        self.assertEqual(run.call_args[1]["env"]["HT_ROOT"], str(launcher.ROOT))

    def test_the_old_exe_is_copied_to_the_backup_not_moved(self):
        from herotv import updater
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        root = Path(d)
        (root / "HERO-TV.exe").write_bytes(b"old")
        (root / "_internal").mkdir()
        (root / "_internal" / "a.dll").write_bytes(b"old")
        st = root / updater.STAGE
        (st / "_internal").mkdir(parents=True)
        (st / "HERO-TV.exe").write_bytes(b"new")
        (st / "_internal" / "a.dll").write_bytes(b"new")
        with mock.patch.object(updater, "_stop_others"):
            updater.finish_swap(root, now=1000)
        self.assertEqual((root / "HERO-TV.exe").read_bytes(), b"new")
        b = next((root / ".update-backup").iterdir())
        self.assertEqual((b / "HERO-TV.exe").read_bytes(), b"old")
        self.assertEqual((b / "_internal" / "a.dll").read_bytes(), b"old")
        self.assertEqual((root / "_internal" / "a.dll").read_bytes(), b"new")


class DroppedFiles(unittest.TestCase):
    def test_dropped_videos_land_in_the_inbox_and_others_do_not(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        media = Path(d) / "media"
        media.mkdir()
        cfg = config.Config(media_dir=media, db_path=os.path.join(d, "t.sqlite3"))
        film = Path(d) / "New Film (2021).mp4"
        film.write_bytes(b"v" * 5000)
        junk = Path(d) / "notes.txt"
        junk.write_text("x")
        said = []
        with mock.patch("shutil.disk_usage", return_value=mock.Mock(free=10 * 1024 ** 4)), mock.patch.object(nativewin.time, "sleep"):
            n = nativewin.add_dropped([str(film), str(junk), str(Path(d) / "missing.mp4")], said.append, cfg)
        self.assertEqual(n, 1)
        self.assertIn("1 video added", said[0])
        self.assertIn("2 could not be added", said[0])
        self.assertEqual(film.read_bytes(), b"v" * 5000)                                  # the original stays where it was
        got = [p for p in media.rglob("New Film*") if p.is_file()]
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].read_bytes(), b"v" * 5000)


class RestartAfterUpdate(unittest.TestCase):
    def _run(self, own):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        (Path(d) / "HERO-TV.exe").write_bytes(b"x")
        with mock.patch.dict(os.environ, {"HEROTV_RESTART_NO_BROWSER": "1"}), \
             mock.patch.object(launcher, "_own_window_on", return_value=own), \
             mock.patch.object(launcher.updater if hasattr(launcher, "updater") else __import__("herotv.updater", fromlist=["x"]), "finish_swap", return_value=3), \
             mock.patch.object(launcher.subprocess, "Popen") as po:
            launcher.finish_update(d, None, True)
        return po.call_args[0][0]

    def test_an_edge_window_reconnects_so_no_new_window(self):
        self.assertIn("--no-browser", self._run(False))

    def test_the_own_window_is_closed_by_the_update_so_a_new_one_opens(self):
        self.assertNotIn("--no-browser", self._run(True))

    def test_a_program_that_cannot_be_overwritten_is_renamed_aside(self):
        from herotv import updater
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        root = Path(d)
        (root / "HERO-TV.exe").write_bytes(b"old")
        st = root / updater.STAGE
        st.mkdir()
        (st / "HERO-TV.exe").write_bytes(b"new")
        real = shutil.copy2

        def busy(src, dst, *a, **k):
            if str(dst) == str(root / "HERO-TV.exe") and (root / "HERO-TV.exe").exists():
                raise PermissionError("in use")
            return real(src, dst, *a, **k)
        with mock.patch.object(updater, "_stop_others"), mock.patch.object(updater.shutil, "copy2", side_effect=busy), mock.patch.object(updater.time, "sleep"):
            updater.finish_swap(root, now=1000)
        self.assertEqual((root / "HERO-TV.exe").read_bytes(), b"new")
        left = list(root.glob("HERO-TV.exe.old*"))
        self.assertEqual(len(left), 1)
        updater.clean_old_exes(root)
        self.assertEqual(list(root.glob("HERO-TV.exe.old*")), [])
