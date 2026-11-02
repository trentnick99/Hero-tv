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
