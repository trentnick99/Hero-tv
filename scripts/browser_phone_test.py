"""Browser test of watching on a phone: a phone-sized touch browser pairs with a one-time link (no code), watches a .mkv
with Dolby sound that a phone cannot open (HERO TV converts it while it plays), switches quality, watches live TV, and
sets up its Home Screen icon.

    python scripts/browser_phone_test.py [folder for screenshots]

Needs a Chromium that plays HLS itself (recent Chromium and Edge do; so do Safari and every iPhone).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS = []


def check(ok, what):
    print(("  PASS  " if ok else "  FAIL  ") + what, flush=True)
    if not ok:
        FAILS.append(what)


def main(shots=None):
    sys.path.insert(0, str(ROOT))
    from herotv import config, remote as R, scheduler as S, server as SV, stream, tools
    from herotv.config import Config
    from herotv.db import connect
    home = tempfile.mkdtemp()
    sf = Path(home) / "settings.json"
    sf.write_text(json.dumps({"lan_share": True}), encoding="utf-8")
    config.settings_file = lambda: sf
    shutil.copytree(ROOT / "config", Path(home) / "config")
    media = Path(home) / "media"
    (media / "MCU").mkdir(parents=True)
    ff = tools.find_tool("ffmpeg")
    films = [("Iron Man (2008).mkv", "Iron Man", 2008, "ac3", "testsrc2"), ("Thor (2011).mp4", "Thor", 2011, "aac", "smptebars")]
    for name, *_rest in films:
        src, audio = _rest[3], _rest[2]
        r = subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", f"{src}=s=854x480:r=24:d=240", "-f", "lavfi", "-i", "sine=f=300:d=240",
                            "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-g", "96", "-c:a", audio, "-b:a", "128k",
                            str(media / "MCU" / name)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-400:]
    cfg = Config(media_dir=media, db_path=os.path.join(home, "t.sqlite3"), channels_file=str(Path(home) / "config" / "channels.json"))
    cfg.tz = "UTC"
    c = connect(cfg.db_path)
    now = int(time.time())
    for i, (name, title, year, audio, _s) in enumerate(films, 1):
        p = media / "MCU" / name
        c.execute("INSERT INTO media(id,path,title,year,franchise,verified,playable,available,runtime_s,vcodec,acodec,vfmt,ord,added,height,size,atracks) "
                  "VALUES(?,?,?,?,'MCU',1,1,1,240,'h264',?,'yuv420p|High',?,?,480,?,'eng*')", (i, str(p), title, year, audio, i, now - i, os.path.getsize(p)))
    c.execute("INSERT OR REPLACE INTO prefs(key,value) VALUES('welcomed','1')")
    c.commit()
    S.sync_channels(c, json.load(open(cfg.channels_file, encoding="utf-8-sig"))["channels"], tz="UTC")
    S.extend_all(c, time.time(), 6 * 3600, tz="UTC")
    app = SV.App(cfg)
    R.set_enabled(True)
    import random
    for _ in range(20):
        cfg.port = random.randrange(20000, 40000)
        try:
            app.start_lan()
            break
        except ValueError:
            continue
    lan = f"http://127.0.0.1:{R.lan_port(cfg)}"
    n = [0]

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = None
        for kw in ({"channel": "msedge"}, {}):                          # Edge where there is one (it plays H.264 and HLS, like the PC)
            try:
                b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"], **kw)
                break
            except Exception:
                continue
        ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2,
                            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        def shot(name):
            if shots:
                n[0] += 1
                pg.screenshot(path=os.path.join(shots, f"{n[0]:02d}-{name}.png"))

        hls = pg.evaluate("document.createElement('video').canPlayType('application/vnd.apple.mpegurl')")
        avc = pg.evaluate("document.createElement('video').canPlayType('video/mp4; codecs=\"avc1.640028\"')")
        if not hls or not avc:
            print(f"  SKIP  this browser cannot play HLS ({hls!r}) or H.264 ({avc!r}) itself")
            b.close()
            app.stop_lan()
            return 0

        # ---- pairing with a one-time link: no code to type
        pg.goto(lan + "/")
        pg.wait_for_timeout(800)
        check(pg.url.endswith("/pair") and "6-digit code" in pg.inner_text("body"), "an unpaired phone is sent to the pairing page")
        pg.goto(lan + "/pair?t=" + R.make_link())
        pg.wait_for_timeout(3500)
        check(pg.url.rstrip("/") == lan and pg.evaluate("document.body.classList.contains('remote')"), "a one-time link pairs the phone and opens HERO TV")
        names = [d["name"] for d in R.devices(connect(cfg.db_path))]
        check(any("iPhone" in x for x in names), f"it shows up in the PC's paired devices ({names})")

        V = "document.getElementById('v')"

        def play_from_library(title):
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(300)
            pg.keyboard.press("l")
            pg.wait_for_timeout(1200)
            pg.fill("#q", title)
            pg.wait_for_timeout(1200)
            pg.keyboard.press("ArrowDown")
            pg.wait_for_timeout(300)
            pg.keyboard.press("Enter")

        def tap_menu(name):
            pg.touchscreen.tap(195, 300)
            pg.wait_for_timeout(500)
            pg.locator("#mbar button", has_text=name).click()
            pg.wait_for_timeout(500)

        # ---- an .mkv with Dolby sound: converted while it plays
        play_from_library("Iron Man")
        pg.wait_for_timeout(9000)
        st = pg.evaluate(f"({{src:{V}.currentSrc,t:{V}.currentTime,w:{V}.videoWidth}})")
        check("/stream/1/high/index.m3u8" in st["src"] and "k=" in st["src"], f"the .mkv is sent as a converted stream ({st['src'][-60:]})")
        check(st["t"] > 1 and st["w"] > 0, f"it plays: picture {st['w']} wide, {st['t']:.1f} s in")
        shot("phone-mkv")
        pg.evaluate(f"{V}.currentTime=150")
        pg.wait_for_timeout(7000)
        t = pg.evaluate(f"{V}.currentTime")
        check(150 < t < 175, f"jumping ahead works ({t:.1f} s)")

        # ---- quality
        tap_menu("Quality")
        menu = pg.inner_text("#ctx")
        check("Data saver (360p)" in menu and "● Automatic" in menu, "Quality lists the choices, Automatic ticked")
        shot("phone-quality")
        pg.locator("#ctx div", has_text="Data saver").click()
        pg.wait_for_timeout(8000)
        st = pg.evaluate(f"({{src:{V}.currentSrc,t:{V}.currentTime,h:{V}.videoHeight}})")
        check("/stream/1/saver/" in st["src"] and st["h"] == 360, f"Data saver switches to 360p ({st['h']})")
        check(st["t"] > 140, f"...and carries on from the same place ({st['t']:.1f} s)")
        check(pg.evaluate("localStorage.getItem('quality')") == "saver", "the choice is remembered on the phone")

        # ---- an .mp4 the phone plays: sent as it is (no work for the PC) unless a smaller quality is chosen
        tap_menu("Quality")
        pg.locator("#ctx div", has_text="Automatic").click()
        pg.wait_for_timeout(3000)
        play_from_library("Thor")
        pg.wait_for_timeout(6000)
        st = pg.evaluate(f"({{src:{V}.currentSrc,t:{V}.currentTime}})")
        check("/media/2" in st["src"] and st["t"] > 0.5, f"an .mp4 that plays on phones is sent as the file itself ({st['src'][-30:]})")

        # ---- live TV on the phone
        tap_menu("Ch ▲")
        pg.wait_for_timeout(9000)
        st = pg.evaluate(f"({{src:{V}.currentSrc,t:{V}.currentTime,p:{V}.paused}})")
        check(("/stream/" in st["src"] or "/media/" in st["src"]) and st["t"] > 1 and not st["p"], f"live TV plays on the phone ({st['src'][-40:]}, {st['t']:.0f} s in)")
        shot("phone-live")

        # ---- the phone's menu: Home Screen icon
        tap_menu("Phone")
        menu = pg.inner_text("#ctx")
        check("Put HERO TV on the Home Screen" in menu and "Use away from home" in menu, "the Phone menu offers the Home Screen icon and away from home")
        shot("phone-menu")
        pg.locator("#ctx div", has_text="Use away from home").click()
        pg.wait_for_timeout(1200)
        check("Tailscale is not set up on the PC" in pg.inner_text("#toast"), "away from home says plainly when the PC has no Tailscale yet")
        tap_menu("Phone")
        pg.locator("#ctx div", has_text="Put HERO TV on the Home Screen").click()
        pg.wait_for_timeout(2500)
        check("/pair?t=" in pg.url and "home=1" in pg.url and "Add to Home Screen" in pg.inner_text("body"),
              "in Safari, the Home Screen link explains how to add the icon (and does not use the link up)")
        shot("phone-homescreen")
        url = pg.url
        icon_ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)   # its own cookies, like iOS
        ip = icon_ctx.new_page()
        ip.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true})")
        ip.goto(url)
        ip.wait_for_timeout(3500)
        check(ip.url.rstrip("/") == lan and ip.evaluate("document.body.classList.contains('remote')"), "opened from the Home Screen, the icon pairs itself and opens HERO TV")
        ip.goto(url)                                                      # every later launch opens the same address
        ip.wait_for_timeout(2500)
        check(ip.url.rstrip("/") == lan, "later launches go straight in (the used link is not asked for again)")
        check(not errors, "no script errors on the phone" + (": " + " | ".join(errors[:3]) if errors else ""))
        b.close()
    app.stop_lan()
    stream.stop_all(cfg)
    print("\n" + ("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
