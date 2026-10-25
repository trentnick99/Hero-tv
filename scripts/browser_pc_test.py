"""PC-side browser test of everyday features: first-run welcome, the New row, the library's New tab, Settings >
Appearance window option, and the next episode starting by itself after an episode ends.

    python scripts/browser_pc_test.py chromium|webkit
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS, LOG = [], []


def check(ok, what):
    print(("  PASS  " if ok else "  FAIL  ") + what, flush=True)
    LOG.append(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        FAILS.append(what)


def main(engine):
    home = tempfile.mkdtemp()
    sys.path.insert(0, str(ROOT))
    from herotv import config, scheduler as S, server as SV
    from herotv.config import Config
    from herotv.db import connect
    sf = Path(home) / "settings.json"
    config.settings_file = lambda: sf
    media = Path(home) / "media" / "Invincible"; media.mkdir(parents=True)
    fixture = "sample.webm" if engine == "chromium" else "sample.mp4"
    codecs = ("vp9", "opus") if engine == "chromium" else ("h264", "aac")
    cfg = Config(media_dir=media.parent, db_path=os.path.join(home, "t.sqlite3"), channels_file=str(ROOT / "config" / "channels.json"))
    cfg.tz = "UTC"
    c = connect(cfg.db_path)
    now = int(time.time())
    for ep in (1, 2, 3):
        f = media / f"Invincible S01E0{ep}.{fixture.rsplit('.', 1)[1]}"
        shutil.copy(ROOT / "tests" / "fixtures" / fixture, f)
        c.execute("INSERT INTO media(path,title,series,season,episode,franchise,verified,playable,available,runtime_s,vcodec,acodec,vfmt,ord,added) "
                  "VALUES(?,?,?,?,?,?,1,1,1,12,?,?,'yuv420p|Main',?,?)", (str(f), f"Episode {ep}", "Invincible", 1, ep, "Invincible", *codecs, ep, now - ep))
    c.commit()
    S.sync_channels(c, json.load(open(cfg.channels_file, encoding="utf-8-sig"))["channels"], tz="UTC")
    S.extend_all(c, time.time(), 6 * 3600, tz="UTC")
    c.close()
    srv = SV._TVServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = getattr(p, engine).launch()
        pg = b.new_context(viewport={"width": 1280, "height": 720}).new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base + "/"); pg.wait_for_timeout(3500)
        if pg.evaluate("document.querySelector('#tapgo').classList.contains('on')"):
            pg.click("#tapgo")
        check(pg.evaluate("document.querySelector('#news').classList.contains('on')") and "Welcome" in pg.inner_text("#nw-h"),
              "a first start shows the Welcome card")
        pg.click("#nw-ok"); pg.wait_for_timeout(400)
        pg.keyboard.press("h"); pg.wait_for_timeout(1500)
        tiles = pg.inner_text("#tiles")
        check("New in your library" in tiles and "3 new" in tiles, "Home shows 'New in your library'")
        pg.click("#tiles >> text=New in your library"); pg.wait_for_timeout(1200)
        tabs = pg.inner_text("#l-tabs")
        cards = pg.locator("#list .card").all_inner_texts()
        check("New 3" in tabs.replace("\n", " ") and cards and "S1E1" in cards[0], f"the library's New tab lists the newest first ({cards[:1]!r})")
        pg.locator("#list .card").nth(0).dblclick(); pg.wait_for_timeout(2500)
        check(pg.evaluate("!document.querySelector('#v').paused"), "an episode plays on demand")
        pg.evaluate("document.querySelector('#v').currentTime = document.querySelector('#v').duration - 0.3")
        pg.wait_for_timeout(2000)
        check(pg.evaluate("document.querySelector('#nextep').classList.contains('on')"), "when it ends, the next-episode card appears")
        check("S1E2" in pg.inner_text("#ne-t"), f"it offers the next episode (S1E2): {pg.inner_text('#ne-t')!r}")
        pg.keyboard.press("Enter"); pg.wait_for_timeout(2500)
        check(pg.evaluate("!document.querySelector('#nextep').classList.contains('on')") and "S1E2" in (pg.inner_text("#o-title") + pg.inner_text("#o-sub")),
              "Enter plays the next episode at once")
        pg.keyboard.press("o"); pg.wait_for_timeout(800)
        pg.click("#st-main >> text=Open in a window instead of full screen"); pg.wait_for_timeout(800)
        check(json.loads(sf.read_text()).get("windowed") is True, "Settings > Appearance saves 'open in a window'")
        pg.select_option("#cue-style select[data-k=size]", "xl"); pg.wait_for_timeout(800)
        pg.select_option("#cue-style select[data-k=color]", "yellow"); pg.wait_for_timeout(800)
        st = json.loads(sf.read_text()).get("subs_style", {})
        check(st.get("size") == "xl" and st.get("color") == "yellow", f"subtitle size and colour are saved ({st})")
        check(pg.evaluate("document.body.classList.contains('cue-xl') && document.body.classList.contains('cue-yellow')"),
              "the new subtitle style applies at once")
        pg.goto(base + "/"); pg.wait_for_timeout(3000)
        check(not pg.evaluate("document.querySelector('#news').classList.contains('on')"), "the Welcome card does not come back")
        check(pg.evaluate("document.body.classList.contains('cue-xl')"), "the subtitle style is remembered after a restart")
        check(not errors, "no script errors" + (": " + "; ".join(errors[:3]) if errors else ""))
        b.close()
    srv.shutdown()
    print(f"\n{len(FAILS)} failure(s)")
    if os.environ.get("GITHUB_ACTIONS"):
        for f in FAILS:
            print(f"::error title=PC test ({engine})::{f}")
        print(f"::notice title=PC test ({engine})::{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    engine = sys.argv[1] if len(sys.argv) > 1 else "chromium"
    try:
        code = main(engine)
    except Exception:
        import traceback
        tb = "\n".join(LOG + ["--- crash ---"] + traceback.format_exc().strip().splitlines()[-8:])
        print(tb)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title=PC test ({engine}) crashed::" + tb.replace("%", "%25").replace("\n", "%0A"))
        code = 2
    sys.exit(code)
