"""Friendly start-up for desktop computers (built for Windows, works on Linux/macOS too).

  python -m herotv launch     check everything, scan the library, start the server, open the TV
  python -m herotv doctor     only check and explain problems
"""
import json
import os
import zipfile
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from . import library, samples, subtitles, tools
from . import scheduler as S
from .config import API_LEVEL, Config, IS_WIN, ROOT
from .db import connect
from .tz import get_tz

OK, BAD, WARN = "[ OK ]", "[FAIL]", "[ !! ]"


_sink = threading.local()          # set by jobs.py so the Settings screen sees the same messages


def say(msg=""):
    print(msg, flush=True)
    fn = getattr(_sink, "fn", None)
    if fn:
        fn(str(msg))


def ask(question, default=True):
    """Yes/no question; returns the default when nobody can answer (double-clicked/no console)."""
    if not sys.stdin or not sys.stdin.isatty():
        return default
    try:
        a = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    except EOFError:
        return default
    return default if not a else a.startswith("y")


def app_data_dir():
    base = os.environ.get("LOCALAPPDATA") if IS_WIN else None
    return Path(base or Path.home() / ".local" / "share") / "HeroTV"


def has_videos(folder):
    try:
        for _dp, _dn, fn in os.walk(folder):
            if any(os.path.splitext(f)[1].lower() in library.EXTS for f in fn):
                return True
    except OSError:
        pass
    return False


def health(cfg, timeout=1.5):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{cfg.port}/api/health", timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def pids_listening(netstat_text, port):
    """Process ids listening on `port`, from the text of  netstat -ano -p TCP  (Windows)."""
    pids = []
    for line in netstat_text.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[1].endswith(f":{port}") and parts[3].upper() == "LISTENING":
            if parts[4].isdigit() and int(parts[4]) not in pids:
                pids.append(int(parts[4]))
    return pids


def stop_old_server(cfg):
    """Close a HERO TV server left running from before an update (Windows). True once the port is free again."""
    if not IS_WIN:
        return False
    try:
        out = tools.run(["netstat", "-ano", "-p", "TCP"], timeout=20).stdout or ""
        for pid in pids_listening(out, cfg.port):
            tools.run(["taskkill", "/PID", str(pid), "/F"], timeout=20)
    except Exception:
        return False
    for _ in range(20):
        if port_free(cfg):
            return True
        time.sleep(0.25)
    return False


def rescan_running(cfg):
    """Ask an already-running HERO TV to rescan the media folder. Returns the scan stats or None."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{cfg.port}/api/rescan", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r).get("scan")
    except Exception:
        return None


def port_free(cfg):
    import socket
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", cfg.port)) != 0


def find_browser():
    """A Chromium-family browser (Edge, Chrome, Brave, Chromium) - these honour the kiosk/autoplay flags."""
    env = os.environ.get("HEROTV_BROWSER")
    if env and os.path.isfile(env):
        return env
    if IS_WIN:
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        la = os.environ.get("LOCALAPPDATA", "")
        for p in (rf"{pf86}\Microsoft\Edge\Application\msedge.exe", rf"{pf}\Microsoft\Edge\Application\msedge.exe",
                  rf"{pf}\Google\Chrome\Application\chrome.exe", rf"{pf86}\Google\Chrome\Application\chrome.exe",
                  rf"{la}\Google\Chrome\Application\chrome.exe",
                  rf"{pf}\BraveSoftware\Brave-Browser\Application\brave.exe"):
            if os.path.isfile(p):
                return p
        return None
    for n in ("chromium", "chromium-browser", "google-chrome", "microsoft-edge", "brave-browser"):
        p = shutil.which(n)
        if p:
            return p
    return None


def open_tv(cfg, fullscreen=True):
    url = f"http://127.0.0.1:{cfg.port}/"
    browser = find_browser()
    if not browser:
        say(f"{WARN} No Edge/Chrome found, opening your default browser. Click the page once and press F for fullscreen.")
        webbrowser.open(url)
        return
    profile = app_data_dir() / "browser-profile"      # own profile: flags always apply, your normal browser is untouched
    profile.mkdir(parents=True, exist_ok=True)
    args = [browser, f"--app={url}", "--autoplay-policy=no-user-gesture-required", f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check", "--disable-features=Translate", "--disable-session-crashed-bubble"]
    if fullscreen:
        args.append("--start-fullscreen")
    subprocess.Popen(args, **tools.HIDE)


def install_ffmpeg():
    """Offer to install ffmpeg with winget (built into Windows 10/11). Returns True when ffprobe is now found."""
    winget = shutil.which("winget")
    if IS_WIN and winget:
        say("HERO TV needs ffmpeg (a free video tool) to measure how long each video is.")
        if ask("Install it now with Windows' built-in installer (winget)? This is safe and takes about a minute."):
            subprocess.run([winget, "install", "--id", "Gyan.FFmpeg", "-e", "--accept-source-agreements",
                            "--accept-package-agreements"])
            tools.forget()
            if tools.find_tool("ffprobe"):
                return True
            say(f"{WARN} Installed, but Windows has not shown it to this window yet. Close this window and double-click HERO-TV.bat again.")
            return False
    say("Manual install of ffmpeg:")
    say("  1. Download the 'release essentials' zip from  https://www.gyan.dev/ffmpeg/builds/")
    say(f"  2. Unzip it and rename the folder to 'ffmpeg', then put it inside:  {ROOT}")
    say(f"     so that this file exists:  {ROOT / 'ffmpeg' / 'bin' / 'ffprobe.exe'}")
    return False


def check_config_files(cfg):
    """Friendly errors for typos in the files people edit in Notepad. Returns a list of problems."""
    problems = []
    cdir = os.path.dirname(cfg.channels_file)
    data = {}
    for name in (os.path.basename(cfg.channels_file), "auto-sort.json"):
        path = os.path.join(cdir, name)
        try:
            with open(path, encoding="utf-8-sig") as f:
                data[name] = json.load(f)
        except OSError:
            say(f"{BAD} Cannot open {path}")
            problems.append(name)
        except ValueError as e:
            say(f"{BAD} {name} has a typo: {e}")
            say("       (usually a missing/extra comma, a missing quote, or a missing bracket just before that spot)")
            problems.append(name)
    chans = data.get(os.path.basename(cfg.channels_file), {}).get("channels")
    if isinstance(chans, list):
        try:
            ids, nums = [c["id"] for c in chans], [c["number"] for c in chans]
            for c in chans:
                c["name"]
            if len(set(ids)) != len(ids) or len(set(nums)) != len(nums):
                say(f"{BAD} channels.json: two channels share the same id or the same number - each must be unique")
                problems.append("dup")
        except (KeyError, TypeError):
            say(f"{BAD} channels.json: every channel needs an  \"id\",  \"number\"  and  \"name\"")
            problems.append("fields")
        from . import scheduler as _S
        for c in chans:
            try:
                _S.parse_blocks(c)
            except (ValueError, TypeError, AttributeError) as e:
                say(f"{BAD} channels.json: {e}")
                problems.append("blocks")
        try:
            for c in _S.with_seasonal(chans):
                _S.parse_blocks(c)
        except (ValueError, TypeError, AttributeError) as e:
            say(f"{BAD} seasonal.json: {e}")
            problems.append("seasonal")
        if not problems:
            nb = sum(len(c.get("blocks") or []) for c in chans)
            say(f"{OK} Channels: {len(chans)} (config/channels.json)" + (f", {nb} scheduled block(s)" if nb else ""))
            rules = data.get("auto-sort.json")
            if isinstance(rules, dict):
                ids = {c["id"] for c in chans} | {str(c["number"]) for c in chans} | {c["number"] for c in chans}
                unknown = sorted({str(x) for key in ("rules", "year_rules") for r in rules.get(key, []) if isinstance(r, dict)
                                  for x in r.get("channels", []) if x not in ids})
                if unknown:
                    say(f"{WARN} auto-sort.json names channel(s) that do not exist: {', '.join(unknown)} (those keywords do nothing)")
    elif "channels.json" in data:
        say(f"{BAD} channels.json must contain a list called \"channels\"")
        problems.append("shape")
    return problems


def doctor(cfg=None, quiet_ok=False):
    """Print a checklist. Returns a list of blocking problems (empty = ready to run)."""
    cfg = cfg or Config()
    problems = []

    def line(flag, text):
        if flag != OK or not quiet_ok:
            say(f"{flag} {text}")

    line(OK if tools.python_ok() else BAD, f"Python {sys.version.split()[0]}" + ("" if tools.python_ok() else " - version 3.9 or newer is needed"))
    if not tools.python_ok():
        problems.append("python")
    for t in ("ffprobe", "ffmpeg"):
        p = tools.find_tool(t)
        line(OK if p else (BAD if t == "ffprobe" else WARN), f"{t}: {p or 'not found'}")
        if not p and t == "ffprobe":
            problems.append("ffprobe")
    try:
        get_tz(cfg.tz)
        line(OK, f"Timezone: {'this computer' if cfg.tz == 'local' else cfg.tz}")
    except ValueError as e:
        line(BAD, str(e))
        problems.append("tz")
    from . import weather
    wl = weather.location()
    line(OK if wl else WARN, f"Weather channel: {wl['name']}" if wl else "Weather channel: no location yet (double-click Set-Weather-Location.bat)")
    line(OK if find_browser() else WARN, f"Browser: {find_browser() or 'no Edge/Chrome found (default browser will be used)'}")
    media = Path(cfg.media_dir)
    if media.is_dir():
        line(OK if has_videos(media) else WARN, f"Media folder: {media}" + ("" if has_videos(media) else "  (no videos in it yet - demo clips will be used)"))
    else:
        line(WARN, f"Media folder: {media}  (does not exist yet - it will be created)")
    try:
        Path(cfg.db_path).parent.mkdir(parents=True, exist_ok=True)
        probe = Path(cfg.db_path).parent / ".write-test"
        probe.write_text("x")
        probe.unlink()
        line(OK, f"Data folder: {Path(cfg.db_path).parent}")
    except OSError as e:
        line(BAD, f"Cannot write to the data folder {Path(cfg.db_path).parent}: {e}")
        problems.append("data")
    problems += check_config_files(cfg)
    if "Temp" in str(ROOT) and ("Temp1_" in str(ROOT) or "7zO" in str(ROOT)):
        line(BAD, "HERO TV is running from inside the zip file. Right-click the zip > Extract All..., then start it from the new folder.")
        problems.append("zip")
    return problems


def _prepare_media(cfg):
    """Pick the library to play. Returns True when running on demo clips."""
    media = Path(cfg.media_dir)
    if not media.exists():
        try:
            media.mkdir(parents=True, exist_ok=True)
            say(f"Created your media folder: {media}")
        except OSError:
            pass
    ensure_folders(cfg)
    if has_videos(media):
        return False
    say()
    say("=" * 64)
    say(" No videos found yet, so HERO TV will start in DEMO MODE")
    say(" (made-up test clips so you can try the guide and channels).")
    say(f" Put your own videos in:  {media}")
    say(" Folder = channel (see README_WINDOWS.txt), then start HERO TV again.")
    say("=" * 64)
    demo = ROOT / "data" / "sample-media"
    if not has_videos(demo):
        if not tools.find_tool("ffmpeg"):
            raise SystemExit("Demo clips need ffmpeg - see the message above, install it and start again.")
        say("Creating demo clips (about 30 seconds)...")
        samples.make(str(demo), log=lambda m: None)
    cfg.media_dir = demo
    cfg.db_path = str(Path(cfg.db_path).with_name("demo.sqlite3"))
    return True


def _popup(text):
    """Message box for the windowless (quiet) start, where nobody can see the console."""
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, text, "HERO TV", 0x10)
            return
        except Exception:
            pass
    say(text)


def _go_quiet():
    """No console window (pythonw / desktop shortcut): send all output to a log file and let the TV
    switch itself off when its window is closed."""
    os.environ["HEROTV_QUIET"] = "1"
    if getattr(sys, "frozen", False) and os.name == "nt":     # the built exe has a console: hide it
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass
    log = app_data_dir() / "herotv.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists() and log.stat().st_size > 512_000:
        log.replace(log.with_suffix(".old.log"))
    f = open(log, "a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = sys.stderr = f
    say(f"\n=== HERO TV quiet start {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    return log


def launch(no_browser=False, windowed=False, quiet=False):
    log = _go_quiet() if quiet else None
    try:
        from . import settings_api
        windowed = windowed or bool(settings_api._load().get("windowed"))   # Settings > Appearance > open in a window
    except Exception:
        pass
    try:
        from . import updater
        updater.clean_stage(ROOT)           # leftovers of a finished update
        updater.apply_deferred(ROOT)
    except Exception:
        pass
    cfg = Config()
    say("HERO TV - starting checks")
    say("-" * 64)
    if not tools.find_tool("ffprobe") and not quiet:
        install_ffmpeg()
    if getattr(sys, "frozen", False):
        from . import updater
        if updater.app_is_stale():
            msg = ("The HERO TV application is older than the program files next to it (an update was installed but the "
                   "application was not rebuilt). Close HERO TV and double-click Build-App.bat in the HERO TV folder.")
            say(f"{WARN} {msg}")
            if quiet:
                _popup(msg)
    problems = doctor(cfg)
    say("-" * 64)
    if problems:
        say("HERO TV cannot start yet. Fix the [FAIL] line(s) above and start it again.")
        if quiet:
            _popup("HERO TV cannot start yet.\n\nDouble-click HERO-TV.bat (in the HERO TV folder) once - it will explain "
                   f"and fix what is missing.\n\nDetails: {log}")
        return 1
    running = health(cfg)
    if running is not None and running.get("api") != API_LEVEL:
        say("The HERO TV that is running is an older version - closing it so the updated one can start...")
        if not stop_old_server(cfg):
            say("[FAIL] Could not close the older HERO TV. Close its window (or end 'python' in Task Manager), then start HERO TV again.")
            if quiet:
                _popup("An older HERO TV is still running and could not be closed automatically.\n\nClose all HERO TV windows (or end "
                       "'Python' in Task Manager), then start HERO TV again.")
            return 1
        running = None
    if running is not None:
        say("HERO TV is already running - checking for new videos...")
        st = rescan_running(cfg)
        if st is not None:
            say(f"Rescanned: {st.get('added', 0)} new, {st.get('updated', 0)} changed, {st.get('missing', 0)} missing.")
        else:
            say("[FAIL] The HERO TV that is running is an OLD copy and cannot rescan.")
            say("       Close its black window (or press Ctrl+C in it), then double-click HERO-TV.bat again.")
            return 1
        if not no_browser:
            open_tv(cfg, not windowed)
        return 0
    if not port_free(cfg):
        say(f"[FAIL] Port {cfg.port} is being used by another program. Close it, or set HEROTV_PORT to another number (e.g. 8788).")
        if quiet:
            _popup(f"Port {cfg.port} is used by another program, so HERO TV cannot start.\n\nDetails: {log}")
        return 1

    demo = _prepare_media(cfg)
    c = connect(cfg.db_path)
    with open(cfg.channels_file, encoding="utf-8-sig") as f:
        S.sync_channels(c, json.load(f)["channels"], tz=cfg.tz)
    say("Scanning your videos (the first scan can take a while with a big library)...")
    st = library.scan(c, cfg.media_dir)
    S.extend_all(c, time.time(), cfg.horizon_h * 3600, rebuild=True, tz=cfg.tz)
    ready = c.execute("SELECT COUNT(*) FROM media WHERE available=1 AND verified=1 AND playable=1").fetchone()[0]
    skipped = c.execute("SELECT COUNT(*) FROM media WHERE available=1 AND (verified=0 OR playable=0)").fetchone()[0]
    c.close()
    say(f"Library: {ready} video(s) ready" + (f", {skipped} skipped (unreadable, or audio/video format browsers cannot play - see README_WINDOWS.txt)" if skipped else "") + (" [demo clips]" if demo else ""))
    if ready == 0:
        say("[FAIL] Nothing playable was found, so every channel would be empty.")
        say("       Videos should be .mp4/.mkv/.webm/.mov with H.264 video and AAC/MP3 audio.")
        if quiet:
            _popup("Nothing playable was found in your media folder.\n\nRun Why-Isnt-It-Showing.bat to see why.")
        return 1

    from .server import serve
    if not no_browser:
        def opener():
            for _ in range(60):
                if health(cfg) is not None:
                    open_tv(cfg, not windowed)
                    return
                time.sleep(0.5)
        threading.Thread(target=opener, daemon=True).start()
    say()
    say("HERO TV is ON.  Leave this window open while you watch; close it (or press Ctrl+C) to turn the TV off.")
    say("Keys: Up/Down = channel, G = guide, L = library, F = fullscreen, M = mute, Esc = exit fullscreen / back")
    try:
        serve(cfg)
    except KeyboardInterrupt:
        say("HERO TV stopped.")
    except Exception:
        import traceback
        traceback.print_exc()
        if quiet:
            _popup(f"HERO TV stopped unexpectedly.\n\nDetails: {log}")
        return 1
    return 0


CONVERTIBLE = {".avi", ".wmv", ".flv", ".ts", ".m2ts", ".mts", ".mpg", ".mpeg", ".divx", ".ogv", ".3gp"}   # need a remux/re-encode first


def _keep_original(src):
    """Move src into the hidden '.originals' folder next to it, never overwriting an earlier saved original."""
    keep = os.path.join(os.path.dirname(src), ".originals")
    os.makedirs(keep, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(src))
    dest, n = os.path.join(keep, stem + ext), 2
    while os.path.exists(dest):
        dest, n = os.path.join(keep, f"{stem} ({n}){ext}"), n + 1
    shutil.move(src, dest)
    return dest


def _convert_one(src, ffmpeg, phone=False):
    """Make one file browser-playable. Returns (status, path): 'fine' | 'converted' | 'failed'.
    Video already in a playable codec is copied untouched; only the sound (AC-3/DTS -> AAC) is converted.
    The original is kept in a hidden '.originals' folder next to it."""
    p = library.probe(src)
    if not p:
        say("  [FAIL] cannot read this file as a video")
        return "failed", src
    v_ok = library.video_ok(p["vcodec"], p.get("vfmt", ""))
    a_ok = (not p["acodec"]) or p["acodec"] in library.PLAY_A
    ext = os.path.splitext(src)[1].lower()
    if phone:                                  # iPhone-friendly: .mp4 with H.264/HEVC picture and AAC-type sound
        v_ok = v_ok and p["vcodec"] in ("h264", "hevc")
        a_ok = (not p["acodec"]) or p["acodec"] in library.PLAY_A & library.PHONE_A
        if v_ok and a_ok and ext in library.PHONE_EXTS:
            return "fine", src
    elif v_ok and a_ok and ext in library.EXTS:
        return "fine", src
    folder, stem = os.path.split(src)[0], os.path.splitext(os.path.basename(src))[0]
    tmp, final = os.path.join(folder, stem + ".converting.tmp"), os.path.join(folder, stem + ".mp4")
    if os.path.exists(final) and os.path.abspath(final) != src:
        say("  [skip] a .mp4 with this name already exists")
        return "failed", src
    vopt = ["-c:v", "copy"] if v_ok else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    if v_ok and p["vcodec"] == "hevc":
        vopt += ["-tag:v", "hvc1"]               # Apple devices only play HEVC tagged this way
    aopt = ["-c:a", "copy"] if a_ok else ["-c:a", "aac", "-b:a", "192k", "-ac", "2"]
    say(("  making an iPhone-friendly copy:" if phone else "  fixing for the TV:") + " video " + ("kept as is" if v_ok else f"re-encoding {p['vcodec']} -> standard H.264 (slow: a movie can take 15-40 minutes)") +
        ", audio " + ("kept as is" if a_ok else f"converting {p['acodec']} -> AAC"))
    cmd = [ffmpeg, "-v", "error", "-stats", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0?", *vopt, *aopt,
           "-sn", "-movflags", "+faststart", "-f", "mp4", tmp]
    r = subprocess.run(cmd, **tools.HIDE)
    if r.returncode != 0 or not os.path.isfile(tmp):
        say("  [FAIL] ffmpeg could not convert this file")
        if os.path.isfile(tmp):
            os.remove(tmp)
        return "failed", src
    kept = subtitles.save_embedded(src, folder, stem)
    _keep_original(src)
    os.replace(tmp, final)
    say(f"  [ OK ] created {os.path.basename(final)}  (original kept in .originals)")
    if kept:
        say(f"         {kept} subtitle track(s) saved next to it as .srt files")
    return "converted", final


def _describe_track(t, playing):
    ch = {1: "mono", 2: "stereo", 6: "5.1"}.get(t["channels"], f"{t['channels']} ch" if t["channels"] else "")
    bits = ", ".join(x for x in (t["codec"].upper(), ch, t["title"]) if x)
    return f"{t['n'] + 1}. {t['language']}" + (f" ({bits})" if bits else "") + ("   <- plays now" if t["n"] == playing else "")


def fix_audio(paths, lang=None, track=None):
    """Choose which sound track (language) a video plays. Browsers cannot switch tracks, so this makes a copy that
    contains only the chosen one (the picture is not re-encoded, so it is fast). The original is kept in .originals."""
    ffmpeg = tools.find_tool("ffmpeg")
    if not ffmpeg or not tools.find_tool("ffprobe"):
        say("[FAIL] ffmpeg is missing - run Check-Setup.bat and follow its instructions.")
        return 1
    interactive = bool(sys.stdin and sys.stdin.isatty())
    bad = 0
    for src in paths:
        src = os.path.abspath(src)
        say(f"\n{os.path.basename(src)}")
        tracks = library.audio_tracks(src)
        if not tracks:
            say("  [FAIL] no sound found in this file (or it cannot be read)")
            bad += 1
            continue
        playing = library.playing_track(tracks)
        if len(tracks) == 1:
            say(f"  Only one sound track ({tracks[0]['language']}) - nothing to choose.")
            continue
        for t in tracks:
            say("   " + _describe_track(t, playing))
        want = lang or "eng"
        guess = next((t["n"] for t in tracks if t["lang"] == want[:3].lower() or t["language"].lower() == want.lower()), playing)
        if lang and track is None and not any(t["n"] == guess and (t["lang"] == want[:3].lower() or t["language"].lower() == want.lower()) for t in tracks):
            say(f"  [FAIL] no '{lang}' track in this file")
            bad += 1
            continue
        pick = guess
        if track is not None:                       # chosen on the Settings screen
            if not 0 <= int(track) < len(tracks):
                say("  [FAIL] that sound track is not in this file")
                bad += 1
                continue
            pick = int(track)
        elif interactive and not lang:
            a = input(f"  Which one should it play? Type its number [{guess + 1}]: ").strip()
            if a:
                if not (a.isdigit() and 1 <= int(a) <= len(tracks)):
                    say("  [skip] not a number on the list")
                    bad += 1
                    continue
                pick = int(a) - 1
        if pick == playing:
            say("  That track already plays - nothing to change.")
            continue
        p = library.probe(src)
        if not p:
            say("  [FAIL] cannot read this file as a video")
            bad += 1
            continue
        t = tracks[pick]
        v_ok = library.video_ok(p["vcodec"], p.get("vfmt", ""))
        a_ok = t["codec"] in library.PLAY_A
        folder, stem = os.path.split(src)[0], os.path.splitext(os.path.basename(src))[0]
        tmp, final = os.path.join(folder, stem + ".converting.tmp"), os.path.join(folder, stem + ".mp4")
        if os.path.exists(final) and os.path.abspath(final) != src:
            say("  [skip] a .mp4 with this name already exists")
            bad += 1
            continue
        vopt = ["-c:v", "copy"] if v_ok else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
        aopt = ["-c:a", "copy"] if a_ok else ["-c:a", "aac", "-b:a", "192k", "-ac", "2"]
        say(f"  making a copy that plays: {t['language']}" + ("" if v_ok else "  (this video also needs re-encoding: slow)"))
        cmd = [ffmpeg, "-v", "error", "-stats", "-y", "-i", src, "-map", "0:v:0", "-map", f"0:a:{pick}", *vopt, *aopt,
               "-disposition:a:0", "default", "-sn", "-movflags", "+faststart", "-f", "mp4", tmp]
        r = subprocess.run(cmd, **tools.HIDE)
        if r.returncode != 0 or not os.path.isfile(tmp):
            say("  [FAIL] ffmpeg could not make the copy")
            if os.path.isfile(tmp):
                os.remove(tmp)
            bad += 1
            continue
        kept = subtitles.save_embedded(src, folder, stem)
        _keep_original(src)
        os.replace(tmp, final)
        say(f"  [ OK ] {os.path.basename(final)} now plays {t['language']}  (original kept in .originals)")
        if kept:
            say(f"         {kept} subtitle track(s) saved next to it as .srt files (press C while watching)")
    if len(paths):
        _after_change(Config(), bad)
    return 1 if bad else 0


def ensure_folders(cfg):
    """Make the media folder self-explanatory: an Inbox, one folder per channel, and a plain 'where things go' note.
    Empty folders change nothing about what plays; existing files are never touched."""
    media = Path(cfg.media_dir)
    try:
        media.mkdir(parents=True, exist_ok=True)
        (media / "Inbox").mkdir(exist_ok=True)
        with open(cfg.channels_file, encoding="utf-8-sig") as f:
            chans = json.load(f)["channels"]
        names = []
        for c in chans:
            fr = (c.get("match") or {}).get("franchise") or []
            if len(fr) == 1 and c.get("kind", "tv") == "tv":
                names.append(fr[0])
        have = {d.name.lower() for d in media.iterdir() if d.is_dir()}
        for n in names:
            if n.lower() not in have and not any(ch in n for ch in '<>:"/\\|?*'):
                (media / n).mkdir(exist_ok=True)
        note = media / "WHERE THINGS GO.txt"
        if not note.exists():
            note.write_text(
                "WHERE THINGS GO  (your HERO TV media folder)\r\n"
                "============================================\r\n\r\n"
                "Not sure where a movie goes?  Drop it in the  Inbox  folder, then double-click  Sort-Movies.bat\r\n"
                "(in the HERO TV program folder). It files each one onto the right channel by its title.\r\n\r\n"
                "Know the channel?  Put it straight in that channel's folder:\r\n"
                + "".join(f"    {n}\r\n" for n in names) +
                "\r\n    Free Movies   <- filled by Get-Free-Movies.bat, you do not need to touch it\r\n\r\n"
                "A TV show?  Make a folder for the show inside the channel folder and put its episodes in it:\r\n"
                "    Dragon Ball\\Dragon Ball Z\\Dragon Ball Z S01E01.mkv\r\n\r\n"
                "The hidden  .originals  folders are safe copies made when HERO TV fixes a video. Clean-Originals.bat\r\n"
                "deletes them once you are happy. Everything else in here is yours - HERO TV only reads it.\r\n",
                encoding="utf-8")
    except OSError:
        pass


def import_folder(paths, cfg=None, sort=True, assume_yes=False):
    """Bring in everything from a folder, USB stick or drive: copies every video (your originals stay where they are)
    into the Inbox, then offers to sort them onto channels."""
    cfg = cfg or Config()
    media = os.path.abspath(str(cfg.media_dir))
    inbox = os.path.join(media, "Inbox")
    if not paths and sys.stdin and sys.stdin.isatty():
        a = input("Type or drag in the folder (or drive, like E:\\) that has your videos, then press Enter: ").strip().strip('"')
        paths = [a] if a else []
    if not paths:
        say("Drag a folder (or a USB stick / drive) onto Import-Folder.bat.")
        return 1
    found, bad = [], 0
    for root in paths:
        root = os.path.abspath(root)
        if os.path.isfile(root):
            if os.path.splitext(root)[1].lower() in library.EXTS | CONVERTIBLE:
                found.append((root, os.path.basename(root)))
            continue
        if not os.path.isdir(root):
            say(f"[FAIL] cannot find: {root}")
            bad += 1
            continue
        if _under(root, media) or _under(media, root) and os.path.normcase(root) == os.path.normcase(media):
            say(f"[skip] {root} is already your HERO TV media folder.")
            continue
        base = os.path.basename(root.rstrip("\\/")) or "Imported"
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if not d.startswith(".") and d.lower() not in ("$recycle.bin", "system volume information")]
            for f in sorted(fn):
                if os.path.splitext(f)[1].lower() in library.EXTS | CONVERTIBLE and not f.startswith("."):
                    found.append((os.path.join(dp, f), os.path.join(base, os.path.relpath(os.path.join(dp, f), root))))
    if not found:
        say("No videos (.mp4 .mkv .m4v .webm .mov .avi ...) found there.")
        return 1 if bad else 0
    total = sum(os.path.getsize(src) for src, _ in found)
    say(f"Found {len(found)} video(s), {_gb(total)}. They will be COPIED into your Inbox; the originals are not touched.")
    free = shutil.disk_usage(media if os.path.isdir(media) else os.path.dirname(media)).free
    if free - total < 2 * 1024 ** 3:
        say(f"[FAIL] not enough free space on this drive ({_gb(free)} free). Free some space, or use Choose-Media-Folder.bat to use a bigger drive.")
        return 1
    if not assume_yes and not ask("Copy them now?"):
        say("Nothing changed.")
        return 0
    n = 0
    for src, rel in found:
        dest = os.path.join(inbox, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        stem, ext = os.path.splitext(dest)
        k = 2
        while os.path.exists(dest):
            if os.path.exists(dest) and os.path.getsize(dest) == os.path.getsize(src):
                break                      # already imported earlier: skip
            dest, k = f"{stem} ({k}){ext}", k + 1
        if os.path.exists(dest):
            say(f"  already have: {os.path.basename(dest)}")
            continue
        say(f"  copying {os.path.basename(src)}")
        try:
            shutil.copy2(src, dest + ".part")
            os.replace(dest + ".part", dest)
            n += 1
        except OSError as e:
            say(f"  [FAIL] {e}")
            bad += 1
            try:
                os.remove(dest + ".part")
            except OSError:
                pass
    say(f"\n[ OK ] copied {n} video(s) into  {inbox}")
    if sort and n:
        say("\nNow filing them onto channels by title...")
        return sort_movies(assume_yes) or (1 if bad else 0)
    return 1 if bad else 0


def convert(paths):
    """Make videos playable in a browser (see _convert_one)."""
    ffmpeg = tools.find_tool("ffmpeg")
    if not ffmpeg or not tools.find_tool("ffprobe"):
        say("[FAIL] ffmpeg is missing - run Check-Setup.bat and follow its instructions.")
        return 1
    bad = 0
    for src in paths:
        src = os.path.abspath(src)
        say(f"\n{os.path.basename(src)}")
        st, _ = _convert_one(src, ffmpeg)
        if st == "fine":
            say("  already fine - nothing to do")
        bad += st == "failed"
    return 1 if bad else 0


def _under(path, root):
    a, b = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
    return a == b or a.startswith(b.rstrip("\\/") + os.sep)


def add_to_channels(paths, choice=None):
    """Put videos on one or more channels: folder channels get the file moved into their folder, tag channels get a
    .hero.json tag file written next to it. `choice` = '4,8' skips the menu."""
    cfg = Config()
    with open(cfg.channels_file, encoding="utf-8-sig") as f:
        chans = [c for c in json.load(f)["channels"] if c.get("match")]   # the match-everything channel needs nothing
    media = os.path.abspath(str(cfg.media_dir))
    say("Which channel(s) should these go on?")
    for c in chans:
        m = c["match"]
        how = "folder: " + m["franchise"][0] if m.get("franchise") else "tag: " + m["tags"][0]
        say(f"  {c['number']:>2}  {c['name']:<20} ({how})")
    if choice is None:
        if not sys.stdin or not sys.stdin.isatty():
            say("[FAIL] no console to ask in")
            return 1
        choice = input("Type channel number(s), e.g. 4 or 4,8 : ")
    want = {int(x) for x in choice.replace(" ", "").split(",") if x.isdigit()}
    picked = [c for c in chans if c["number"] in want]
    if not picked:
        say("[FAIL] none of those are channel numbers from the list above.")
        return 1
    bad = 0
    for src in paths:
        if not _place(os.path.abspath(src), picked, media):
            bad += 1
    return _after_change(cfg, bad)


def _place(src, picked, media, force_move=False):
    """Put one video on the picked channels. Returns True on success."""
    stem, ext = os.path.splitext(os.path.basename(src))
    if ext.lower() not in library.EXTS | CONVERTIBLE or not os.path.isfile(src):
        say(f"\n{os.path.basename(src)}\n  [FAIL] not a video file HERO TV can use")
        return False
    say(f"\n{os.path.basename(src)}")
    ffmpeg = tools.find_tool("ffmpeg")
    if ffmpeg and tools.find_tool("ffprobe"):       # fix AC-3/DTS sound, .avi etc. on the way in
        st, src = _convert_one(src, ffmpeg)
        if st == "failed":
            return False
        stem = os.path.splitext(os.path.basename(src))[0]
    elif ext.lower() in CONVERTIBLE:
        say("  [FAIL] needs ffmpeg to convert - run Check-Setup.bat")
        return False
    tags = [c["match"]["tags"][0] for c in picked if c["match"].get("tags")]
    folders = [c["match"]["franchise"][0] for c in picked if c["match"].get("franchise")]
    dest = src
    if folders or force_move or not _under(src, media):
        target = os.path.join(media, folders[0] if folders else picked[0]["name"])
        if not _under(src, target):
            os.makedirs(target, exist_ok=True)
            dest = os.path.join(target, os.path.basename(src))
            if os.path.exists(dest) and os.path.normcase(dest) != os.path.normcase(src):
                say("  [skip] a file with this name is already in " + target)
                return False
            for old, new in ((src, dest), (os.path.join(os.path.dirname(src), stem + ".hero.json"), os.path.join(target, stem + ".hero.json"))):
                if os.path.isfile(old) and old != new:
                    shutil.move(old, new)
            say(f"  moved into  {os.path.relpath(target, media)}")
    if tags:
        side = os.path.join(os.path.dirname(dest), stem + ".hero.json")
        data = {}
        if os.path.isfile(side):
            try:
                with open(side, encoding="utf-8-sig") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                data = {}
        have = data.get("tags", [])
        data["tags"] = have + [t for t in tags if t.lower() not in (x.lower() for x in have)]
        with open(side, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        say("  tagged: " + ", ".join(data["tags"]))
    say("  [ OK ] on: " + ", ".join(c["name"] for c in picked))
    return True


def _after_change(cfg, bad):
    if health(cfg) is not None:
        if rescan_running(cfg) is not None:
            say("\nHERO TV was running and has already picked up the change - press F5 in the TV window to refresh it.")
        else:
            say("\n[!!] HERO TV is running but is an OLD copy. Close its black window and start HERO-TV.bat again.")
    else:
        say("\nNow start HERO TV (or close and start it again) so it rescans.")
    if bad:
        say("Some files were not added - see above.")
    return 1 if bad else 0


def _norm(text):
    import re
    return " ".join(re.sub(r"[._\-:'\u2019,!&]+", " ", text.lower()).split())


def plan_sort(stem, rules):
    """Channel ids (or, in an old file, numbers) a title belongs on, from the keyword rules (pure function)."""
    import re
    t, nums = _norm(stem), set()
    m = re.search(r"\((\d{4})\)", stem)
    year = int(m[1]) if m else None
    for r in rules.get("rules", []):
        if any(re.search(r"(?<![a-z0-9])" + re.escape(_norm(k)) + r"(?![a-z0-9])", t) for k in r.get("keywords", [])):
            nums.update(r.get("channels", []))
    for r in rules.get("year_rules", []):
        if year is not None and r.get("year_max") is not None and year <= r["year_max"]:
            nums.update(r.get("channels", []))
    return nums


def sort_movies(assume_yes=False, cfg=None):
    """File new movies onto channels by title keywords (config/auto-sort.json).
    Looks at videos loose in the media folder and in its 'Inbox' folder; anything already in a channel folder is left alone."""
    cfg = cfg or Config()
    media = os.path.abspath(str(cfg.media_dir))
    inbox = os.path.join(media, "Inbox")
    os.makedirs(inbox, exist_ok=True)
    from . import sortrules
    rules_file = os.path.join(os.path.dirname(cfg.channels_file), "auto-sort.json")
    rules, channels = sortrules.load(cfg)
    todo = []
    for dp, dn, fn in os.walk(media):
        if os.path.abspath(dp) != media and not _under(dp, inbox):
            dn[:] = []          # only the top level and the Inbox are sorted
            continue
        dn[:] = [d for d in dn if not d.startswith(".")]      # never touch .originals
        for f in sorted(fn):
            if os.path.splitext(f)[1].lower() in library.EXTS | CONVERTIBLE:
                todo.append(os.path.join(dp, f))
    if not todo:
        say(f"Nothing to sort. Put new movies in:  {inbox}")
        return 0
    plan, left = [], []
    for src in todo:
        picked = sortrules.targets(os.path.splitext(os.path.basename(src))[0], rules, channels)
        (plan if picked else left).append((src, picked))
    say(f"Found {len(todo)} movie(s) to sort:\n")
    for src, picked in plan:
        say(f"  {os.path.basename(src)}\n      -> " + ", ".join(f"{c['number']} {c['name']}" for c in picked))
    for src, _ in left:
        say(f"  {os.path.basename(src)}\n      -> (no keyword matched - left where it is)")
    if not plan:
        say(f"\nNothing matched. Add keywords in:  {rules_file}  (or use Add-Movies.bat to choose channels yourself)")
        return 0
    if not assume_yes and not ask("\nMove/tag these now?"):
        say("Nothing changed.")
        return 0
    bad = sum(0 if _place(src, picked, media, force_move=True) else 1 for src, picked in plan)
    return _after_change(cfg, bad)


def show_library():
    """Explain, per video, whether it is usable and which channels it lands on (answers "why is X not on channel Y?")."""
    cfg = Config()
    media = Path(cfg.media_dir)
    c = connect(cfg.db_path)
    with open(cfg.channels_file, encoding="utf-8-sig") as f:
        chans = json.load(f)["channels"]
    S.sync_channels(c, chans, tz=cfg.tz)
    say(f"Media folder: {media}")
    if not tools.find_tool("ffprobe"):
        say("[FAIL] ffprobe not found - nothing can be measured. Run Check-Setup.bat.")
    library.scan(c, media)
    rows = c.execute("SELECT * FROM media WHERE available=1 ORDER BY franchise,series,ord,title").fetchall()
    if not rows:
        say("No videos found in that folder (.mp4 .m4v .mkv .webm .mov).")
    for r in rows:
        rel = os.path.relpath(r["path"], media) if _under(r["path"], media) else r["path"]
        if not r["verified"]:
            status = "NOT READABLE as a video (damaged, or ffprobe missing)"
        elif not r["playable"]:
            status = "SKIPPED - " + (library.why_not_playable(r["vcodec"], r["acodec"], r["vfmt"]) or "format not supported") + ": drag it onto Convert-Video.bat"
        else:
            status = "OK"
            tr = library.audio_tracks(r["path"])
            if len(tr) > 1:
                status += f" - but it has {len(tr)} sound tracks and plays '{tr[library.playing_track(tr)]['language']}'. Drag it onto Fix-Audio.bat to choose the language"
        tags = ", ".join(json.loads(r["tags"] or "[]")) or "(none)"
        on = [f"{ch['number']} {ch['name']}" for ch in chans if status == "OK" and ch.get("kind", "tv") == "tv" and S.matches(S.config_rules(ch), r)]
        say(f"\n{r['title']}\n   file:   {rel}\n   format: video {r['vcodec']} {r['vfmt'].replace('|', ' ')} / audio {r['acodec'] or 'none'}\n   status: {status}\n   folder/franchise: {r['franchise'] or '(none - file is loose in the media folder)'}   tags: {tags}")
        say("   on channels: " + (", ".join(on) if on else "none"))
    total = sum(r["size"] or 0 for r in rows)
    orig = 0
    for dp, dn, _fn in os.walk(media):
        if ".originals" in dn:
            orig += _dir_size(os.path.join(dp, ".originals"))
        dn[:] = [x for x in dn if x != ".originals"]
    say(f"\n--- storage ---\n  Library: {len(rows)} video(s), {_gb(total)}")
    if orig:
        say(f"  Saved originals (.originals folders): {_gb(orig)}  <- Clean-Originals.bat frees this once you are happy with the new versions")
    say("  Shrink-Library.bat re-encodes everything efficiently to save space (shows the estimate before it starts).")
    say("\n--- channel summary ---")
    for ch in chans:
        if ch.get("kind", "tv") != "tv":
            say(f"  {ch['number']:>2} {ch['name']:<20} (live {ch['kind']} channel)")
            continue
        n = sum(1 for r in rows if r["verified"] and r["playable"] and S.matches(S.config_rules(ch), r))
        say(f"  {ch['number']:>2} {ch['name']:<20} {n} video(s)" + ("" if n else "   <- empty: shows 'No programming'"))
    c.close()
    return 0


def make_shortcut():
    """Desktop shortcut 'HERO TV' (with icon) that starts the TV without a console window."""
    if not IS_WIN:
        say("Desktop shortcuts are only made on Windows.")
        return 1
    from . import icon
    ico = ROOT / "assets" / "hero-tv.ico"
    if not ico.is_file():
        ico.parent.mkdir(exist_ok=True)
        icon.make_ico(str(ico))
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    frozen = bool(getattr(sys, "frozen", False))          # running as the built HERO-TV.exe
    target = str(exe if frozen else pyw if pyw.is_file() else exe)
    arguments = "launch --quiet" if frozen else "-m herotv launch --quiet"
    ps = ('$d=[Environment]::GetFolderPath("Desktop");$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d "HERO TV.lnk"));'
          '$s.TargetPath=$env:HT_TARGET;$s.Arguments=$env:HT_ARGS;$s.WorkingDirectory=$env:HT_DIR;'
          '$s.IconLocation=$env:HT_ICON;$s.Description="HERO TV";$s.Save();Write-Output (Join-Path $d "HERO TV.lnk")')
    env = dict(os.environ, HT_TARGET=target, HT_ARGS=arguments, HT_DIR=str(ROOT), HT_ICON=str(ico))
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, text=True, env=env, **tools.HIDE)
    if r.returncode != 0:
        say("[FAIL] Could not create the shortcut: " + (r.stderr or r.stdout).strip()[-300:])
        return 1
    say(f"[ OK ] Shortcut created on your Desktop:  {r.stdout.strip()}")
    say("       Double-click it to start HERO TV with no black window. Closing the TV window turns HERO TV off.")
    say("       Problems? A log is kept in  " + str(app_data_dir() / "herotv.log"))
    return 0


# ---------------------------------------------------------------- storage tools
SHRUNK_TAG = "HERO TV shrink v1"     # written into every shrunk file so it is never shrunk twice (no stacking quality loss)
ANIMATION_HINTS = ("dragon ball", "south park", "animation", "anime", "cartoon", "spider-verse", "what if", "x-men 97")


def _gb(n):
    return f"{n / 1e9:.1f} GB" if n >= 1e8 else f"{n / 1e6:.0f} MB"


def _dir_size(path):
    total = 0
    for dp, _dn, fn in os.walk(path):
        for f in fn:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def _shrink_plan(p, path, cap_height=None):
    """Settings and a size estimate for one probed file (pure function; used by tests)."""
    dur = p["runtime_s"]
    movie = dur >= 4200
    cap = cap_height or (1080 if movie else 720)
    h = p.get("height") or 0
    out_h = min(h, cap) if h else cap
    anim = any(k in path.replace("\\", "/").lower() for k in ANIMATION_HINTS)
    base = 3200 if out_h >= 900 else 1500 if out_h >= 620 else 800 if out_h >= 420 else 500     # kbit/s, CRF-23ish
    kbps = base * (0.6 if anim else 1.0)
    est = int((kbps + 128) * 1000 / 8 * dur)
    cur = p.get("bitrate") or 0
    already = bool(cur) and cur <= (kbps + 128) * 1000 * 1.2 and library.video_ok(p["vcodec"], p.get("vfmt", "")) \
        and p["vcodec"] == "h264" and (not p["acodec"] or p["acodec"] in library.PLAY_A)
    return dict(crf=(24 if anim else 23) if movie else (25 if anim else 24), tune_animation=anim, scale_to=out_h if h and h > out_h else None,
                est_bytes=est, already_small=already)


def _find_videos(paths):
    out = []
    for raw in paths:
        raw = os.path.abspath(raw)
        if os.path.isfile(raw):
            out.append(raw)
            continue
        for dp, dn, fn in os.walk(raw):
            dn[:] = sorted(d for d in dn if not d.startswith("."))
            out += [os.path.join(dp, f) for f in sorted(fn) if os.path.splitext(f)[1].lower() in library.EXTS | CONVERTIBLE]
    return out


def shrink(paths, delete_originals=None, fast=False, yes=False, keep_resolution=False):
    """Re-encode videos to efficient standard H.264 to save disk space. Each result is verified (same length, really
    smaller) before it replaces anything; the original goes to '.originals' (or is deleted when asked)."""
    ffmpeg = tools.find_tool("ffmpeg")
    if not ffmpeg or not tools.find_tool("ffprobe"):
        say("[FAIL] ffmpeg is missing - run Check-Setup.bat and follow its instructions.")
        return 1
    files = _find_videos(paths)
    if not files:
        say("No videos found there.")
        return 0
    say(f"Looking at {len(files)} video(s)...")
    plan = []
    for f in files:
        p = library.probe(f)
        if not p:
            continue
        pl = _shrink_plan(p, f, 1080 if keep_resolution else None)
        cur = os.path.getsize(f)
        if SHRUNK_TAG in p.get("comment", "") or pl["already_small"] or pl["est_bytes"] >= cur * 0.85:
            continue
        plan.append((f, p, pl, cur))
    if not plan:
        say("Nothing worth shrinking - these are already compact.")
        return 0
    before, after = sum(x[3] for x in plan), sum(x[2]["est_bytes"] for x in plan)
    say(f"\n{len(plan)} of {len(files)} file(s) can be shrunk: about {_gb(before)} -> {_gb(after)}  (saves ~{_gb(before - after)}).")
    say("This re-encodes every picture, so it is SLOW (roughly 15-40 min per movie, a few min per episode)."
        " You can leave it running overnight - already finished files are never redone.")
    if not yes and not ask("Start?"):
        say("Nothing changed.")
        return 0
    if delete_originals is None:
        delete_originals = ask("Delete each original once its smaller copy is checked? (no = keep originals in a hidden .originals folder)", False) if not yes else False
    saved, done, failed = 0, 0, 0
    for n, (src, p, pl, cur) in enumerate(plan, 1):
        say(f"\n[{n}/{len(plan)}] {os.path.basename(src)}   ({_gb(cur)}" + (f", {p['height']}p" if p.get("height") else "") + ")")
        folder, stem = os.path.split(src)[0], os.path.splitext(os.path.basename(src))[0]
        tmp, final = os.path.join(folder, stem + ".shrinking.tmp"), os.path.join(folder, stem + ".mp4")
        if os.path.exists(final) and os.path.abspath(final) != src:
            say("  [skip] a .mp4 with this name already exists")
            failed += 1
            continue
        vf = ["-vf", f"scale=-2:{pl['scale_to']}"] if pl["scale_to"] else []
        cmd = [ffmpeg, "-v", "error", "-stats", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0?", "-sn",
               "-c:v", "libx264", "-preset", "veryfast" if fast else "medium", "-crf", str(pl["crf"] + (2 if fast else 0)),
               "-pix_fmt", "yuv420p", *(["-tune", "animation"] if pl["tune_animation"] else []), *vf,
               "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-metadata", f"comment={SHRUNK_TAG}", "-movflags", "+faststart", "-f", "mp4", tmp]
        r = subprocess.run(cmd, **tools.HIDE)
        q = library.probe(tmp) if r.returncode == 0 and os.path.isfile(tmp) else None
        new = os.path.getsize(tmp) if q else 0
        if not q or abs(q["runtime_s"] - p["runtime_s"]) > max(2.0, p["runtime_s"] * 0.01) or new >= cur * 0.9 \
                or not library.video_ok(q["vcodec"], q.get("vfmt", "")):
            say("  [skip] the smaller copy did not pass the checks (length/size/format) - original untouched")
            if os.path.isfile(tmp):
                os.remove(tmp)
            failed += 1
            continue
        if delete_originals:
            os.remove(src)
        else:
            _keep_original(src)
        os.replace(tmp, final)
        saved += cur - new
        done += 1
        say(f"  [ OK ] {_gb(cur)} -> {_gb(new)}   (saved {_gb(cur - new)}; total so far {_gb(saved)})")
    say(f"\nDone: {done} shrunk, {failed} left as they were, {_gb(saved)} saved" + ("" if delete_originals or not done else
        " once you clear the originals (run Clean-Originals.bat)."))
    return 0


def cleanup_originals(yes=False, cfg=None):
    """Delete the hidden '.originals' folders (left by Convert/Sort/Shrink) to get the disk space back."""
    media = os.path.abspath(str((cfg or Config()).media_dir))
    found = []
    for dp, dn, _fn in os.walk(media):
        if ".originals" in dn:
            d = os.path.join(dp, ".originals")
            found.append((d, _dir_size(d)))
        dn[:] = [x for x in dn if x != ".originals"]
    if not found:
        say("No saved originals found - nothing to clean.")
        return 0
    total = sum(s for _d, s in found)
    say(f"Saved originals: {len(found)} folder(s), {_gb(total)} in total:")
    for d, s in sorted(found, key=lambda x: -x[1])[:15]:
        say(f"  {_gb(s):>9}  {os.path.relpath(d, media)}")
    say("\nThese are the ORIGINAL files from before converting/shrinking. Deleting them is permanent (not the Recycle Bin).")
    say("Only do this once you have watched the new versions and are happy with them.")
    if not yes and not ask(f"Delete them all and free {_gb(total)}?", False):
        say("Nothing deleted.")
        return 0
    for d, _s in found:
        if _under(d, media) and os.path.basename(d) == ".originals":
            shutil.rmtree(d, ignore_errors=True)
    say(f"[ OK ] Freed about {_gb(total)}.")
    return 0


def set_media_folder(path=None):
    """Remember which folder holds the videos (e.g. on an external drive). No Windows settings needed."""
    from .config import settings_file
    if not path:
        try:
            import tkinter
            from tkinter import filedialog
            root = tkinter.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askdirectory(title="Choose the folder that holds your videos (one folder per franchise)")
            root.destroy()
        except Exception:
            path = None
        if not path:
            if not sys.stdin or not sys.stdin.isatty():
                say("No folder chosen.")
                return 1
            path = input("Type the full path of the folder with your videos (e.g. E:\\Videos): ").strip().strip('"')
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        say(f"[FAIL] That folder does not exist: {path}")
        return 1
    f = settings_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(f.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        data = {}
    data["media_dir"] = path
    f.write_text(json.dumps(data, indent=1), encoding="utf-8")
    say(f"[ OK ] HERO TV will now read your videos from:\n       {path}")
    say("       (Inside it: one folder per channel, e.g. MCU, DC, Dragon Ball, South Park. If HERO TV is open, restart it.)")
    if os.environ.get("HEROTV_MEDIA"):
        say("[ !! ] A Windows environment variable HEROTV_MEDIA is also set and wins over this choice - remove it.")
    return 0


def set_weather_location(query=None):
    """Choose the town for the Weather channel (search by city name, or type 'lat,lon')."""
    from . import weather
    interactive = sys.stdin and sys.stdin.isatty()
    if not query:
        if not interactive:
            say("Usage: python -m herotv weather \"Chicago\"")
            return 1
        query = input("Your town or city (e.g. Chicago, or Springfield Illinois): ").strip()
    if not query:
        return 1
    parts = [x.strip() for x in query.split(",")]
    if len(parts) == 2 and all(x.replace(".", "", 1).replace("-", "", 1).isdigit() for x in parts):
        cc = input("Country code (US for alerts): ").strip().upper() if interactive else "US"
        choice = {"name": f"{float(parts[0]):.3f}, {float(parts[1]):.3f}", "lat": float(parts[0]), "lon": float(parts[1]), "country_code": cc}
    else:
        try:
            found = weather.geocode(query)
        except Exception as exc:
            say(f"[FAIL] Could not look that up (internet connection?): {exc}")
            return 1
        if not found:
            say("[FAIL] No place found with that name. Try just the city name (no state), or type  latitude,longitude")
            return 1
        for i, f in enumerate(found, 1):
            say(f"  {i}) {f['label']}")
        pick = input("Which one? [1] ").strip() if interactive and len(found) > 1 else "1"
        try:
            choice = found[int(pick or 1) - 1]
        except (ValueError, IndexError):
            say("[FAIL] Not one of the numbers above.")
            return 1
    choice["units"] = "us" if choice.get("country_code") in ("US", "LR", "MM") else "metric"
    weather.save_location({k: choice[k] for k in ("name", "lat", "lon", "country_code", "units")})
    say(f"[ OK ] Weather channel set to: {choice['name']}  ({'°F, mph' if choice['units'] == 'us' else '°C, km/h'})")
    if choice.get("country_code") != "US":
        say("       Live alerts come from the US National Weather Service, so they are only shown for US locations.")
    say("       Restart HERO TV (or press F5 in the TV window) and tune to the Weather channel.")
    return 0


def get_free_movies(count=None, pick=None, assume_yes=False, cfg=None):
    """Download free (public-domain) movies and shows from the Internet Archive into the 'Free Movies' folder."""
    from . import freecontent as F
    cfg = cfg or Config()
    srcfile = os.path.join(os.path.dirname(cfg.channels_file), "free-sources.json")
    try:
        sources = F.load_sources(srcfile)
    except (OSError, ValueError) as e:
        say(f"{BAD} config\\free-sources.json is not valid: {e}")
        return 1
    say("FREE MOVIES AND SHOWS")
    say("---------------------")
    say("This downloads films and cartoons that the Internet Archive marks as PUBLIC DOMAIN (free for anyone to watch).")
    say("They are saved as normal video files in your media folder, in a folder called 'Free Movies', and play on the")
    say("Free Movies channel. Nothing else is downloaded, and you can delete any of them whenever you like.")
    say()
    for i, s in enumerate(sources, 1):
        say(f"  {i}. {s['name']}")
    say(f"  {len(sources) + 1}. All of the above")
    chosen = None
    if pick:
        chosen = pick
    elif sys.stdin and sys.stdin.isatty():
        try:
            chosen = input("\nType a number (or several, like 1,3) and press Enter [all]: ").strip()
        except EOFError:
            chosen = ""
    picked = []
    if not chosen or str(len(sources) + 1) in str(chosen).replace(" ", "").split(","):
        picked = sources
    else:
        for part in str(chosen).replace(" ", "").split(","):
            if part.isdigit() and 1 <= int(part) <= len(sources) and sources[int(part) - 1] not in picked:
                picked.append(sources[int(part) - 1])
        if not picked:
            say(f"{BAD} Those numbers are not on the list.")
            return 1
    if count is None:
        count = 3
        if sys.stdin and sys.stdin.isatty() and not assume_yes:
            try:
                a = input("How many titles from each list? Each is roughly 100-700 MB [3]: ").strip()
                count = int(a) if a.isdigit() and int(a) > 0 else 3
            except EOFError:
                pass
    count = max(1, min(int(count), 50))
    say(f"\nDownloading up to {count} from each of {len(picked)} list(s) - this can take a while. You can close this window and run it again later to continue.")
    last = [0.0]

    def progress(done, total):
        if time.time() - last[0] > 2 and total:
            last[0] = time.time()
            print(f"\r    {done * 100 // total}% of {total // 1024 ** 2} MB   ", end="", flush=True)

    res = F.fetch(picked, cfg.media_dir, count=count, say=say, progress=progress)
    say()
    if res["got"]:
        say(f"{OK} Downloaded {len(res['got'])} title(s):")
        for t in res["got"]:
            say("       " + t)
    elif not res["errors"]:
        say(f"{WARN} Nothing new to download (you may already have everything on the list).")
    for e in res["errors"]:
        say(f"{WARN} {e}")
    if res["errors"] and not res["got"]:
        say("If every list failed, check your internet connection, or that archive.org opens in your browser.")
    if res["got"]:
        return _after_change(cfg, False)
    return 1 if res["errors"] else 0


def show_checklist(cfg=None):
    """Print what you have and what is still missing for each wish list, and save it as 'Shopping list.txt' in your media folder."""
    from . import checklist as CL
    cfg = cfg or Config()
    path = os.path.join(os.path.dirname(cfg.channels_file), "checklist.json")
    try:
        lists = CL.load(path)
    except (OSError, ValueError) as e:
        say(f"{BAD} config\\checklist.json cannot be read: {e}")
        return 1
    c = connect(cfg.db_path)
    with open(cfg.channels_file, encoding="utf-8-sig") as f:
        S.sync_channels(c, json.load(f)["channels"], tz=cfg.tz)
    library.scan(c, cfg.media_dir)
    rows = c.execute("SELECT title,year,franchise,series,season,episode,playable FROM media WHERE available=1 AND verified=1").fetchall()
    text = CL.to_text(CL.build(rows, lists))
    say(text)
    try:
        out = Path(cfg.media_dir) / "Shopping list.txt"
        out.write_text(text.replace("\n", "\r\n"), encoding="utf-8")
        say(f"\n(Saved as  {out}  - take it with you.)")
    except OSError:
        pass
    return 0


COLOR_CHOICES = [("Gold", "#ffcf1f"), ("Red", "#ff3b3b"), ("Blue", "#3d6bff"), ("Green", "#3ddc84"), ("Purple", "#b06bff"),
                 ("Orange", "#ff8c00"), ("Pink", "#ff2e88"), ("Teal", "#1fd1b4")]


def personalize(name=None, color=None, tagline=None):
    """Make the TV yours: its name, main colour and greeting."""
    from .config import settings_file
    import re
    interactive = bool(sys.stdin and sys.stdin.isatty()) and name is None and color is None and tagline is None
    from .config import station
    cur = station()
    if interactive:
        say("MAKE IT YOURS")
        say("-------------")
        a = input(f"Name of your TV station [{cur['name']}]  (for example: Nick's Hero TV): ").strip()
        name = a or None
        say("\nPick a main colour:")
        for i, (n, _h) in enumerate(COLOR_CHOICES, 1):
            say(f"  {i}. {n}")
        a = input(f"Number, or a colour like #ff3b3b [keep {cur['color']}]: ").strip()
        color = a or None
        a = input(f"The line under the name [{cur['tagline']}]: ").strip()
        tagline = a or None
    new = {}
    if name:
        new["name"] = name.strip()[:40]
    if color:
        color = color.strip()
        if color.isdigit() and 1 <= int(color) <= len(COLOR_CHOICES):
            color = COLOR_CHOICES[int(color) - 1][1]
        elif color.lower() in {n.lower() for n, _ in COLOR_CHOICES}:
            color = next(h for n, h in COLOR_CHOICES if n.lower() == color.lower())
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            say(f"{BAD} '{color}' is not a colour I understand. Use a number from the list or something like #ff3b3b.")
            return 1
        new["color"] = color
    if tagline:
        new["tagline"] = tagline.strip()[:80]
    if not new:
        say("Nothing changed.")
        return 0
    f = settings_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(f.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        data = {}
    st = data.get("station") if isinstance(data.get("station"), dict) else {}
    st.update(new)
    data["station"] = st
    f.write_text(json.dumps(data, indent=1), encoding="utf-8")
    say(f"{OK} Saved. Press F5 in the TV window (or restart HERO TV) to see it.")
    return 0


def backup_now(dest=None):
    """Save your HERO TV setup (not your videos) into one zip file in Documents\\HERO TV Backups."""
    from . import backup
    cfg = Config()
    c = connect(cfg.db_path)
    path = backup.make(cfg, c, dest)
    say(f"{OK} Backup saved:\n       {path}")
    say("       It holds your channels and lists, name and colours, favorites, resume points and watch history.")
    say("       Copy it somewhere safe (USB stick, cloud folder). Your videos are not in it.")
    return 0


def restore_backup(path=None, assume_yes=False):
    from . import backup
    cfg = Config()
    path = path or backup.latest()
    if not path:
        say(f"No backup found in {backup.default_dir()}. Drag a backup .zip onto Restore.bat, or run Backup.bat first.")
        return 1
    say(f"Restoring from:\n   {path}")
    say("Your current channel files are kept next to the new ones as  *.before-restore .")
    if not assume_yes and not ask("Restore now?"):
        say("Nothing changed.")
        return 0
    c = connect(cfg.db_path)
    try:
        r = backup.restore(cfg, c, path)
    except ValueError as e:
        say(f"{BAD} {e}")
        return 1
    say(f"{OK} Restored: {r['config']} settings file(s), {r['favorites']} favorites, {r['progress']} resume points, {r['seen']} watched marks.")
    if r["not_found"]:
        say(f"{WARN} {r['not_found']} favorite(s) are for videos not in your media folder yet - add them and restore again.")
    say("Close HERO TV completely and start it again to use the restored setup.")
    return 0


def set_poster_key(key=None):
    """Save your free TMDB key so HERO TV can show cover art, plots, cast and ratings."""
    from . import art
    from .config import settings_file
    if not key:
        say("COVER ART AND DESCRIPTIONS")
        say("-------------------------")
        say("HERO TV can show a poster, plot, cast and rating for every title, using TMDB (themoviedb.org). It is free for")
        say("personal use but needs a free key:")
        say("  1. Make a free account at  https://www.themoviedb.org/signup")
        say("  2. Open  https://www.themoviedb.org/settings/api  and request an API key (choose personal / non-commercial).")
        say("  3. Copy the long 'API Read Access Token' (or the short 'API Key') and paste it below.")
        say("Only each video's title and year are sent to TMDB. Nothing else leaves this PC.")
        say()
        if not (sys.stdin and sys.stdin.isatty()):
            return 1
        key = input("Paste your key here and press Enter (empty = cancel): ").strip()
    key = (key or "").strip().strip('"')
    if not key:
        say("Nothing changed.")
        return 0
    f = settings_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(f.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        data = {}
    data["tmdb_key"] = key
    f.write_text(json.dumps(data, indent=1), encoding="utf-8")
    try:
        art.fetch_json("/configuration", {}, key, timeout=15)
        say(f"{OK} Key saved and accepted by TMDB.")
    except Exception as e:
        say(f"{WARN} Key saved, but TMDB did not accept it just now ({e}). Check you copied all of it, or that you are online.")
    say("Restart HERO TV. Pictures and descriptions fill in by themselves in the background (a big library takes a few minutes).")
    say("Press D on any video to see them. This product uses the TMDB API but is not endorsed or certified by TMDB.")
    return 0


def update(zip_arg=None, assume_yes=False):
    """Install a newer HERO TV from the downloaded zip (newest one in Downloads unless one is given)."""
    from . import updater
    z = updater.find_zip(zip_arg)
    if z is None:
        say("[FAIL] Could not find a downloaded HERO TV zip." if not zip_arg else f"[FAIL] No such file: {zip_arg}")
        say("       Download the new  hero-tv-windows.zip  (it lands in your Downloads folder), then run this again -")
        say("       or drag the zip file onto  Update-HERO-TV.bat.")
        return 1
    from . import __version__
    try:
        info = updater.zip_info(z)
        items = updater.plan(z, ROOT)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as e:
        say(f"[FAIL] {z.name}: {e}")
        return 1
    newv = info["version"] or "?"
    say(f"You have HERO TV {__version__}. This zip is HERO TV {newv}" + (" (with the ready-made application)." if info["app"] else "."))
    if info["version"] and updater.version_tuple(info["version"]) < updater.version_tuple(__version__):
        say(f"{WARN} That is an OLDER version than the one you have.")
        if not ask("Install the older version anyway?", False):
            say("Nothing changed.")
            return 0
    n_new = sum(1 for _, _, a in items if a == "new")
    n_rep = sum(1 for _, _, a in items if a == "replace")
    n_mine = sum(1 for _, _, a in items if a == "keep-mine")
    n_app = sum(1 for _, _, a in items if a == "app")
    n_rep += n_app + sum(1 for _, _, a in items if a == "deferred")
    say(f"Update file:  {z}")
    say(f"  {n_rep} program file(s) will be replaced, {n_new} added, {n_mine} of your settings files differ (kept as they are).")
    if not (n_new or n_rep or n_mine):
        say("\nYou already have this version - nothing to do.")
        return 0
    if not assume_yes and not ask("\nInstall it now? (your videos, favorites and settings are not touched)"):
        say("Nothing changed.")
        return 0
    cfg = Config()
    if health(cfg) is not None:
        say("Closing the running HERO TV first...")
        stop_old_server(cfg)
        time.sleep(1.5)
    res = updater.apply(z, ROOT)
    say(f"\n{OK} Updated: {res['replaced']} replaced, {res['new']} added.")
    if res["backup"]:
        say("       The old files are kept in  " + res["backup"])
    for name in res["kept"]:
        say(f"{WARN} config\\{name} was changed by you, so it was left alone. The new standard version is next to it as {name}.new")
        say("       (open both if you want the new channels/keywords; delete the .new file if you do not)")
    if res["staged"]:
        if getattr(sys, "frozen", False):
            helper = ROOT / updater.STAGE / "HERO-TV.exe"
            say("\nFinishing: this window closes, the new HERO-TV.exe is put in place, and HERO TV starts again by itself.")
            subprocess.Popen([str(helper), "finish-update", "--root", str(ROOT), "--pid", str(os.getpid())],
                             cwd=str(ROOT / updater.STAGE), close_fds=True,
                             creationflags=(0x00000008 | 0x00000200) if IS_WIN else 0)      # detached, own process group
            return 0
        n = updater.finish_swap(ROOT)
        updater.clean_stage(ROOT)
        say(f"{OK} The ready-made application was installed ({n} files). No rebuilding needed.")
        say("Start HERO TV as usual.")
        return 0
    if (ROOT / "HERO-TV.exe").exists():
        say("\nThe application (HERO-TV.exe) still has the OLD program inside. Rebuilding it now...")
        return 2          # Update-HERO-TV.bat sees this and runs Build-App.bat
    say("Start HERO TV as usual.")
    return 0


def finish_update(root, pid=None, start=True):
    """Run by the NEW exe from the staging folder after the old one has closed: swap it in, then start HERO TV."""
    from . import updater
    root = Path(root)
    try:
        n = updater.finish_swap(root, wait_pid=pid)
    except OSError as e:
        _popup(f"HERO TV could not finish updating: {e}")
        return 1
    say(f"{OK} Installed {n} application file(s).")
    if start and os.environ.get("HEROTV_UPDATE_NO_START") != "1" and (root / "HERO-TV.exe").is_file():
        subprocess.Popen([str(root / "HERO-TV.exe"), "launch", "--quiet"], cwd=str(root), close_fds=True,
                         creationflags=0x00000008 if IS_WIN else 0)
    return 0


def make_phone_ready(paths, cfg=None):
    """Make iPhone-friendly .mp4 copies (picture copied as is, so usually quick). Originals go to .originals."""
    ffmpeg = tools.find_tool("ffmpeg")
    if not ffmpeg or not tools.find_tool("ffprobe"):
        say(f"{BAD} ffmpeg is missing - Settings > Tools > Install video tools.")
        return 1
    bad = done = 0
    for i, src in enumerate(paths, 1):
        say(f"\n[{i} of {len(paths)}] {os.path.basename(src)}")
        st, _ = _convert_one(os.path.abspath(src), ffmpeg, phone=True)
        bad += st == "failed"
        done += st == "converted"
        if st == "fine":
            say("  already iPhone-friendly")
    say(f"\n{OK if not bad else WARN} {done} copied, {bad} failed.")
    if done:
        _after_change(cfg or Config(), bad)
    return 1 if bad else 0
