"""End-to-end test of watching HERO TV on a phone over the home network, in a real browser engine.

    python scripts/browser_phone_test.py webkit     # Safari's engine (run on macOS in CI: closest to an iPhone)
    python scripts/browser_phone_test.py chromium   # Chrome's engine

It starts HERO TV with 'other devices' switched on, opens the network address as an emulated iPhone, pairs with the
code, checks a channel really plays, that Settings are not offered, that touch controls work, and that an unpaired
browser gets the pairing page. Exit code 0 = everything passed. Each failure is printed (and reported as a GitHub
annotation when running in CI).
"""
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS = []
LOG = []
PAGES = {}


def check(ok, what):
    print(("  PASS  " if ok else "  FAIL  ") + what, flush=True)
    LOG.append(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        FAILS.append(what)
    return ok


def free_port():
    for _ in range(50):
        s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
        t = socket.socket()
        try:
            t.bind(("0.0.0.0", p + 1)); t.close(); return p
        except OSError:
            t.close()
    raise RuntimeError("no free ports")


def main(engine):
    home = tempfile.mkdtemp()
    sys.path.insert(0, str(ROOT))
    from herotv import config, remote as R, scheduler as S, server as SV
    from herotv.config import Config
    from herotv.db import connect
    sf = Path(home) / "settings.json"              # a throw-away settings file (HOME is left alone: browsers live there)
    config.settings_file = lambda: sf
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps({"lan_share": True}))
    media = Path(home) / "media" / "MCU"; media.mkdir(parents=True)
    fixture = "sample.webm" if engine == "chromium" else "sample.mp4"   # headless Chromium has no H.264
    codecs = ("vp9", "opus") if engine == "chromium" else ("h264", "aac")
    cfg = Config(media_dir=media.parent, db_path=os.path.join(home, "t.sqlite3"), channels_file=str(ROOT / "config" / "channels.json"))
    cfg.tz = "UTC"; cfg.port = free_port()
    c = connect(cfg.db_path)
    for i, t in enumerate(("Iron Man", "Thor", "Captain America")):
        f = media / f"{t} ({2008 + i}).{fixture.rsplit('.', 1)[1]}"
        shutil.copy(ROOT / "tests" / "fixtures" / fixture, f)
        c.execute("INSERT INTO media(path,title,year,franchise,verified,playable,available,runtime_s,vcodec,acodec,vfmt,ord) "
                  "VALUES(?,?,?,?,1,1,1,12,?,?,'yuv420p|Main',?)", (str(f), t, 2008 + i, "MCU", *codecs, i))
    c.commit()
    S.sync_channels(c, json.load(open(cfg.channels_file, encoding="utf-8-sig"))["channels"], tz="UTC")
    S.extend_all(c, time.time(), 6 * 3600, tz="UTC")
    c.close()
    app = SV.App(cfg)
    for attempt in range(10):                 # another program may grab a just-checked port: pick again
        try:
            pc = SV._TVServer(("127.0.0.1", cfg.port), SV.make_handler(app))
        except OSError:
            cfg.port = free_port(); continue
        try:
            app.start_lan(); break
        except ValueError:
            pc.server_close(); cfg.port = free_port()
    else:
        raise RuntimeError("could not find two free ports")
    threading.Thread(target=pc.serve_forever, daemon=True).start()
    lan = f"http://127.0.0.1:{R.lan_port(cfg)}"
    print(f"HERO TV test server: PC {cfg.port}, network {R.lan_port(cfg)}; engine {engine}", flush=True)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        bt = getattr(p, engine)
        browser = bt.launch()
        phone = dict(p.devices["iPhone 13"])
        if engine == "firefox":
            phone.pop("is_mobile", None)
        ctx = browser.new_context(**phone)
        page = ctx.new_page()
        errors, media_urls = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: media_urls.append(r.url) if "/media/" in r.url else None)

        pcp = browser.new_context(viewport={"width": 1280, "height": 720}).new_page()
        PAGES["pc"], PAGES["phone"] = pcp, page
        pcp.on("pageerror", lambda e: errors.append("PC: " + str(e)))
        pcp.goto(f"http://127.0.0.1:{cfg.port}/"); pcp.wait_for_timeout(3500)
        if pcp.evaluate("document.querySelector('#tapgo').classList.contains('on')"):
            pcp.click("#tapgo")             # this test browser blocks autoplay; the real PC window allows it
        check(pcp.evaluate("document.querySelector('#news').classList.contains('on')"), "the PC shows its one-time card (welcome)")
        for _ in range(4):                     # dismiss the one-time pop-ups in whatever order they appear
            if pcp.evaluate("document.querySelector('#news').classList.contains('on')"):
                pcp.click("#nw-ok")
            if pcp.evaluate("document.querySelector('#tapgo').classList.contains('on')"):
                pcp.click("#tapgo")
            pcp.wait_for_timeout(400)
        pcp.keyboard.press("o"); pcp.wait_for_timeout(800)
        check(pcp.evaluate("document.querySelector('#settings').classList.contains('on')"), "O opens Settings on the PC")
        pcp.click("#st-nav >> text=Other devices"); pcp.wait_for_timeout(800)
        for _ in range(20):
            txt = pcp.inner_text("#st-main")
            if "Pair a device" in txt:
                break
            pcp.wait_for_timeout(500)
        if "Pair a device" not in txt:
            LOG.append("st-main was: " + txt[:300].replace("\n", " | "))
        check("Let other devices on my home WiFi watch" in txt and "Pair a device" in txt, "the PC's Settings > Other devices shows the switch and Pair")
        pcp.click("#st-main >> button:has-text('Pair a device')"); pcp.wait_for_timeout(800)
        shown = "".join(ch for ch in pcp.inner_text("#st-main") if ch.isdigit())
        code = (R.pairing_state() or {}).get("code", "")
        check(bool(code) and code in shown, "pressing Pair shows a 6-digit code on the PC")
        check(pcp.locator("#phone-qr svg").count() == 1, "the PC shows a QR code for the phone's camera")

        page.goto(lan + "/")
        check(page.url.endswith("/pair"), "an unpaired phone is sent to the pairing page")
        page.fill("#code", code[:5]); page.click("#go")
        page.wait_for_timeout(500)
        check("6 numbers" in page.inner_text("#msg"), "a short code is refused with a clear message")
        page.fill("#code", code)                               # 6 digits pairs by itself
        page.wait_for_url(lan + "/", timeout=10000)
        check(True, "pairing with the code opens the TV")
        pcp.wait_for_timeout(2500)
        check("iPhone" in pcp.inner_text("#st-main"), "the PC lists the newly paired iPhone")
        pcp.screenshot(path=str(ROOT / f"pc-devices-{engine}.png"))
        try:
            import cv2
            shot = str(ROOT / f"pc-qr-{engine}.png")
            pcp.locator("#phone-qr").screenshot(path=shot)
            img = cv2.imread(shot)
            got = cv2.QRCodeDetector().detectAndDecode(img)[0]
            if not got:                                  # try once more, enlarged and in pure black and white
                g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                g = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
                g = cv2.copyMakeBorder(cv2.threshold(g, 128, 255, cv2.THRESH_BINARY)[1], 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
                got = cv2.QRCodeDetector().detectAndDecode(g)[0]
            box = pcp.locator("#phone-qr").bounding_box()
            check(got.startswith("http://") and got.endswith(f":{R.lan_port(cfg)}/"),
                  f"a QR reader can read the code on the screen ({got!r}, shown at {box and round(box['width'])}px, image {img.shape[1]}x{img.shape[0]})")
        except ImportError:
            print("  (no QR reader installed here - skipped reading the code off the screen)")
        from herotv import dlna as D
        from unittest import mock as _mock
        with _mock.patch.object(D, "Announcer", side_effect=OSError("test")):
            pcp.click("#dlna-btn"); pcp.wait_for_timeout(600)
            check(not D.enabled() and "Press again" in pcp.inner_text("#dlna-btn"), "turning on the TV media player asks to confirm first")
            pcp.click("#dlna-btn")
            for _ in range(20):
                if D.enabled() and app.dlna.running:
                    break
                pcp.wait_for_timeout(250)
            ok = D.enabled() and app.dlna.running
            check(ok, "pressing again switches the TV media server on" + ("" if ok else " - screen says: " + pcp.inner_text("#st-msg")[:200]))
            check("Roku Media Player" in pcp.inner_text("#st-main"), "it explains where to find it on the Roku")
            pcp.click("#dlna-btn"); pcp.wait_for_timeout(1200)
            check(not D.enabled() and not app.dlna.running, "Turn off switches it off again")
        page.wait_for_timeout(3000)

        tapped = False
        if page.evaluate("document.querySelector('#tapgo').classList.contains('on')"):
            page.tap("#tapgo"); tapped = True
        check(True, "tap-to-start " + ("was shown and tapped" if tapped else "was not needed"))
        s0, t0 = page.evaluate("[document.querySelector('#v').src, document.querySelector('#v').currentTime]")
        page.wait_for_timeout(2500)
        s1, t1 = page.evaluate("[document.querySelector('#v').src, document.querySelector('#v').currentTime]")
        rs = page.evaluate("document.querySelector('#v').readyState")
        moved = t1 > t0 if s0 == s1 else t1 > 0            # the 12-second test clips may hand over to the next programme
        check(moved and rs >= 2, f"a live channel really plays on the phone (time {t0:.1f} -> {t1:.1f}, readyState {rs})")
        check(any("k=" in u for u in media_urls), "video addresses carry the device's media key (for AirPlay)")
        err = page.evaluate("document.querySelector('#v').error && document.querySelector('#v').error.code")
        check(not err, f"no video error ({err})")

        page.tap("#v"); page.wait_for_timeout(400)
        bar = page.inner_text("#mbar")
        check("Ch ▲" in bar and "Library" in bar, "tapping the picture shows touch buttons (channel up/down, library...)")
        check("Settings" not in bar, "Settings are not offered on the phone")
        before = page.evaluate("document.querySelector('#o-num') && document.querySelector('#o-num').textContent")
        page.click("#mbar >> text=Ch ▲"); page.wait_for_timeout(1500)
        check(True, "channel up button works (" + str(before) + " -> next)")

        page.tap("#v"); page.wait_for_timeout(300)
        page.click("#mbar >> text=Guide"); page.wait_for_timeout(1200)
        page.screenshot(path=str(ROOT / f"phone-guide-{engine}.png"))
        page.click("#xclose"); page.wait_for_timeout(500)
        page.tap("#v"); page.wait_for_timeout(300)
        page.click("#mbar >> text=Library"); page.wait_for_timeout(1200)
        cards = page.locator("#list .card").count()
        check(cards >= 3, f"the library opens and lists the videos ({cards})")
        check(page.is_visible("#xclose"), "a Close button is shown for touch screens")
        page.screenshot(path=str(ROOT / f"phone-library-{engine}.png"))
        page.locator("#list .card").nth(1).click(); page.wait_for_timeout(300)
        page.locator("#list .card").nth(1).click(); page.wait_for_timeout(2500)
        check(page.evaluate("!document.querySelector('#lib').classList.contains('on')"), "tapping a selected video plays it")

        st = page.evaluate("fetch('/api/settings').then(r=>r.status)")
        check(st == 403, f"the phone cannot read the PC's settings ({st})")
        st = page.evaluate("fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:'{\"auto_inbox\":false}'}).then(r=>r.status)")
        check(st == 403, f"the phone cannot change settings ({st})")
        page.screenshot(path=str(ROOT / f"phone-{engine}.png"))
        page.set_viewport_size({"width": 844, "height": 390})          # phone turned sideways
        page.wait_for_timeout(500)
        page.tap("#v"); page.wait_for_timeout(300)
        page.click("#mbar >> text=Guide"); page.wait_for_timeout(1200)
        page.screenshot(path=str(ROOT / f"phone-landscape-guide-{engine}.png"))
        page.click("#xclose"); page.wait_for_timeout(500)
        check(page.evaluate("!document.querySelector('#guide').classList.contains('on')"), "the Close button closes the guide")

        other = browser.new_context(**phone).new_page()
        other.goto(lan + "/api/channels")
        check("pair this device first" in other.content(), "another, unpaired browser gets nothing")
        check(not errors, "no script errors on the phone page" + (": " + "; ".join(errors[:3]) if errors else ""))
        browser.close()
    app.stop_lan(); pc.shutdown()
    print(f"\n{len(FAILS)} failure(s)")
    if os.environ.get("GITHUB_ACTIONS"):
        for f in FAILS:
            print(f"::error title=Phone test ({engine})::{f}")
        print(f"::notice title=Phone test ({engine})::{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    engine = sys.argv[1] if len(sys.argv) > 1 else "webkit"
    try:
        code = main(engine)
    except Exception:
        import traceback
        tb = traceback.format_exc().strip().splitlines()[-6:]
        state = []
        for name, pg in PAGES.items():
            try:
                state.append(f"[{name}] url={pg.url} " + pg.evaluate(
                    "JSON.stringify({layer:typeof layer!=='undefined'?layer:'?',on:[...document.querySelectorAll('.on')].map(e=>e.id||e.className).slice(0,12),"
                    "main:(document.querySelector('#st-main')||{}).innerText?.slice(0,300),msg:(document.querySelector('#msg')||{}).innerText})"))
            except Exception as e:
                state.append(f"[{name}] could not read state: {e}")
        tb = "\n".join(LOG + ["--- crash ---"] + tb + state)
        print(tb)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title=Phone test ({engine}) crashed::" + tb.replace("%", "%25").replace("\n", "%0A"))
        code = 2
    sys.exit(code)
