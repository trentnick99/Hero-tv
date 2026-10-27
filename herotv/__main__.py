import argparse
import os
import json
import sys
import time

from . import library, scheduler as S
from .config import Config
from .db import connect


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):   # Windows consoles/pipes may not be UTF-8: never crash on a movie title
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="herotv")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="scan media dir, verify runtimes, rebuild future schedule")
    s = sub.add_parser("serve", help="run server (scans first with --scan)")
    s.add_argument("--scan", action="store_true")
    g = sub.add_parser("schedule", help="print generated schedule")
    g.add_argument("--hours", type=float, default=6)
    g.add_argument("--channel")
    sub.add_parser("doctor", help="check this computer is ready (python, ffmpeg, folders, browser)")
    lc = sub.add_parser("launch", help="check, scan, start the server and open the TV (the easy way)")
    lc.add_argument("--no-browser", action="store_true")
    lc.add_argument("--quiet", action="store_true", help="no console output; log to a file; stop when the TV window closes")
    lc.add_argument("--window", action="store_true", help="open in a normal window instead of fullscreen")
    cv = sub.add_parser("convert", help="make videos browser-playable (e.g. AC-3/DTS audio -> AAC); keeps originals")
    cv.add_argument("files", nargs="+")
    ad = sub.add_parser("add", help="put video files on channels (moves into folder / writes tag file)")
    ad.add_argument("files", nargs="+")
    ad.add_argument("--channel", help="channel number(s), e.g. 4,8 (skips the menu)")
    sub.add_parser("library", help="list every video, whether it is usable and which channels it is on")
    so = sub.add_parser("sort", help="file new movies onto channels by title keywords (config/auto-sort.json)")
    so.add_argument("--yes", action="store_true")
    sub.add_parser("shortcut", help="put a HERO TV icon on the Desktop (starts with no black window)")
    sh = sub.add_parser("shrink", help="re-encode videos to save disk space (files or folders)")
    sh.add_argument("paths", nargs="*", help="files or folders (none = your whole media folder)")
    sh.add_argument("--delete-originals", action="store_true", default=None)
    sh.add_argument("--fast", action="store_true", help="quicker, slightly bigger files")
    sh.add_argument("--keep-resolution", action="store_true", help="allow 1080p for episodes too")
    sh.add_argument("--yes", action="store_true")
    cl = sub.add_parser("cleanup", help="delete the saved .originals folders to free disk space")
    cl.add_argument("--yes", action="store_true")
    sm = sub.add_parser("setmedia", help="choose the folder that holds your videos")
    sm.add_argument("path", nargs="?")
    wx = sub.add_parser("weather", help="choose the town for the Weather channel")
    wx.add_argument("query", nargs="?")
    au = sub.add_parser("audio", help="choose which sound track (language) a video plays")
    au.add_argument("files", nargs="+")
    au.add_argument("--lang", help="language to use, e.g. eng or English (skips the question)")
    im = sub.add_parser("import", help="copy all videos from a folder / USB stick / drive into your Inbox and sort them")
    im.add_argument("paths", nargs="*")
    im.add_argument("--yes", action="store_true")
    sub.add_parser("checklist", help="show which movies/shows on your wish lists you have and which are missing")
    pz = sub.add_parser("personalize", help="set your TV station name, color and greeting")
    pz.add_argument("--name"); pz.add_argument("--color"); pz.add_argument("--tagline")
    bk = sub.add_parser("backup", help="save your channels, lists, favorites and watch history to one zip file")
    bk.add_argument("--to", help="folder to save into (default: Documents\\HERO TV Backups)")
    rs = sub.add_parser("restore", help="restore a backup made by the backup command")
    rs.add_argument("file", nargs="?", help="the backup .zip (default: the newest one)")
    rs.add_argument("--yes", action="store_true")
    fu = sub.add_parser("finish-update", help=argparse.SUPPRESS)
    fu.add_argument("--root", required=True)
    fu.add_argument("--pid", type=int)
    fu.add_argument("--no-start", action="store_true")
    su = sub.add_parser("self-update", help=argparse.SUPPRESS)
    su.add_argument("zip")
    up = sub.add_parser("update", help="install a newer HERO TV from the downloaded zip")
    up.add_argument("zip", nargs="?")
    up.add_argument("--yes", action="store_true")
    pk = sub.add_parser("posterkey", help="save your free TMDB key for cover art and descriptions")
    pk.add_argument("key", nargs="?")
    fo = sub.add_parser("folders", help="create the Inbox and channel folders inside your media folder")
    fo.add_argument("--open", action="store_true", help="then open the media folder in Explorer")
    fr = sub.add_parser("free", help="download free public-domain movies and shows from the Internet Archive")
    fr.add_argument("--count", type=int, help="titles per list (default 3)")
    fr.add_argument("--pick", help="list numbers, e.g. 1,3 (default: ask / all)")
    fr.add_argument("--yes", action="store_true")
    sub.add_parser("samples", help="create demo clips in HEROTV_MEDIA (needs ffmpeg)")
    a = ap.parse_args(argv)
    if a.cmd in ("doctor", "launch", "samples", "convert", "add", "library", "sort", "shortcut", "shrink", "cleanup", "setmedia", "weather", "free", "audio", "folders", "import", "checklist", "personalize", "backup", "restore", "posterkey", "update", "finish-update", "self-update"):
        from . import launcher
        if a.cmd == "doctor":
            return 1 if launcher.doctor() else 0
        if a.cmd == "launch":
            return launcher.launch(no_browser=a.no_browser, windowed=a.window, quiet=a.quiet)
        if a.cmd == "shrink":
            return launcher.shrink(a.paths or [str(Config().media_dir)], a.delete_originals, a.fast, a.yes, a.keep_resolution)
        if a.cmd == "finish-update":
            return launcher.finish_update(a.root, a.pid, start=not a.no_start)
        if a.cmd == "update":
            return launcher.update(a.zip, a.yes)
        if a.cmd == "self-update":
            return launcher.self_update(a.zip)
        if a.cmd == "posterkey":
            return launcher.set_poster_key(a.key)
        if a.cmd == "backup":
            return launcher.backup_now(a.to)
        if a.cmd == "restore":
            return launcher.restore_backup(a.file, a.yes)
        if a.cmd == "checklist":
            return launcher.show_checklist()
        if a.cmd == "personalize":
            return launcher.personalize(a.name, a.color, a.tagline)
        if a.cmd == "import":
            return launcher.import_folder(a.paths, assume_yes=a.yes)
        if a.cmd == "audio":
            return launcher.fix_audio(a.files, a.lang)
        if a.cmd == "folders":
            launcher.ensure_folders(Config())
            print(f"Your media folder is ready: {Config().media_dir}")
            if a.open and os.name == "nt":
                os.startfile(str(Config().media_dir))      # the folder chosen in Settings, not a guess
            return 0
        if a.cmd == "free":
            return launcher.get_free_movies(a.count, a.pick, a.yes)
        if a.cmd == "cleanup":
            return launcher.cleanup_originals(a.yes)
        if a.cmd == "weather":
            return launcher.set_weather_location(a.query)
        if a.cmd == "setmedia":
            return launcher.set_media_folder(a.path)
        if a.cmd == "shortcut":
            return launcher.make_shortcut()
        if a.cmd == "sort":
            return launcher.sort_movies(a.yes)
        if a.cmd == "library":
            return launcher.show_library()
        if a.cmd == "add":
            return launcher.add_to_channels(a.files, a.channel)
        if a.cmd == "convert":
            return launcher.convert(a.files)
        from . import samples
        n = samples.make(str(Config().media_dir))
        print(f"Created {n} demo clip(s) in {Config().media_dir}")
        return 0
    cfg = Config()
    c = connect(cfg.db_path)
    with open(cfg.channels_file, encoding="utf-8-sig") as f:
        S.sync_channels(c, json.load(f)["channels"], tz=cfg.tz)
    if a.cmd in ("scan",) or (a.cmd == "serve" and a.scan):
        st = library.scan(c, cfg.media_dir)
        S.extend_all(c, time.time(), cfg.horizon_h * 3600, rebuild=True, tz=cfg.tz)
        print("scan:", st, flush=True)
        from . import tools
        if not tools.find_tool("ffprobe"):
            print("WARNING: ffprobe (part of ffmpeg) was not found, so no video can be measured and every channel will be empty. Run: python -m herotv doctor", flush=True)
        if st.get("offline"):
            print("WARNING: no media files found in", cfg.media_dir, "- keeping the existing library (drive not mounted?)", flush=True)
    if a.cmd == "serve":
        c.close()
        from .server import serve
        serve(cfg)
    elif a.cmd == "schedule":
        now = time.time()
        S.extend_all(c, now, cfg.horizon_h * 3600, tz=cfg.tz)
        for ch in S.channels(c):
            if a.channel and ch["id"] != a.channel:
                continue
            print(f"\n{ch['number']:>3} {ch['name']}  (generated, tz {cfg.tz})")
            for r in S.window(c, now, now + a.hours * 3600):
                if r["channel_id"] == ch["id"]:
                    d = S.slot_dict(r, cfg.tz)
                    print("   ", d["start_local"][11:16], "-", d["end_local"][11:16], r["title"])


if __name__ == "__main__":
    sys.exit(main())
