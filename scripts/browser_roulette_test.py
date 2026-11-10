"""Browser test of Movie Roulette inside HERO TV: Home tile -> landing -> a whole solo game with real pictures taken by
ffmpeg -> winner screen -> back to live TV; then a party game, the categories, the settings and the history.

    python scripts/browser_roulette_test.py chromium [folder for screenshots]
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
FILMS = [("Iron Man", 2008, "MCU", "testsrc2", ["Action", "Science Fiction"], ["Robert Downey Jr."], ["Jon Favreau"], "Iron Man Collection"),
         ("Iron Man 2", 2010, "MCU", "smptebars", ["Action"], ["Robert Downey Jr."], ["Jon Favreau"], "Iron Man Collection"),
         ("Thor: Ragnarok", 2017, "MCU", "rgbtestsrc", ["Action", "Comedy"], ["Chris Hemsworth"], ["Taika Waititi"], ""),
         ("The Dark Knight", 2008, "DC", "testsrc", ["Action", "Crime"], ["Christian Bale"], ["Christopher Nolan"], ""),
         ("Anchorman", 2004, "Comedy", "pal75bars", ["Comedy"], ["Will Ferrell"], ["Adam McKay"], ""),
         ("Ghost Rider", 2007, "Superhero Classics", "smptehdbars", ["Action", "Fantasy"], ["Nicolas Cage"], ["Mark Steven Johnson"], "")]


def check(ok, what):
    print(("  PASS  " if ok else "  FAIL  ") + what, flush=True)
    if not ok:
        FAILS.append(what)


def main(engine, shots=None):
    home = tempfile.mkdtemp()
    sys.path.insert(0, str(ROOT))
    from herotv import art, config, scheduler as S, server as SV, tools
    from herotv.config import Config
    from herotv.db import connect
    sf = Path(home) / "settings.json"
    config.settings_file = lambda: sf
    shutil.copytree(ROOT / "config", Path(home) / "config")
    cfg = Config(media_dir=Path(home) / "media", db_path=os.path.join(home, "t.sqlite3"), channels_file=str(Path(home) / "config" / "channels.json"))
    cfg.tz = "UTC"
    c = connect(cfg.db_path)
    ff = tools.find_tool("ffmpeg")
    ext, vc, codecs = ("webm", ["-c:v", "libvpx-vp9", "-b:v", "60k", "-deadline", "realtime", "-cpu-used", "8"], ("vp9", "opus")) if engine == "chromium" \
        else ("mp4", ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"], ("h264", "aac"))
    now = int(time.time())
    for i, (t, y, folder, src, genres, cast, dr, col) in enumerate(FILMS, 1):
        d = cfg.media_dir / folder
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{t.replace(':', ' -')} ({y}).{ext}"
        r = subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", f"{src}=s=320x180:r=1:d=1500", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
                            "-shortest", *vc, "-g", "30", "-c:a", "libopus" if ext == "webm" else "aac", "-b:a", "12k", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-400:]
        c.execute("INSERT INTO media(id,path,title,year,franchise,verified,playable,available,runtime_s,vcodec,acodec,vfmt,ord,added,height) "
                  "VALUES(?,?,?,?,?,1,1,1,1500,?,?,'yuv420p|Main',?,?,1080)", (i, str(f), t.replace(":", " -"), y, folder, *codecs, i, now - i))
        k = art.key_for(c.execute("SELECT * FROM media WHERE id=?", (i,)).fetchone())[0]
        c.execute("INSERT INTO art(key,tmdb_id,kind,title,year,genres,\"cast\",rating,miss,facts,tagline) VALUES(?,?,?,?,?,?,?,7.1,0,?,?)",
                  (k, i, "movie", t, y, json.dumps(genres), json.dumps(cast),
                   json.dumps({"type": "movie", "companies": ["Test Studio"], "genres": genres, "collection": col, "directors": dr, "year": y}), "A test tagline."))
    c.execute("INSERT OR REPLACE INTO prefs(key,value) VALUES('welcomed','1')")
    c.commit()
    S.sync_channels(c, json.load(open(cfg.channels_file, encoding="utf-8-sig"))["channels"], tz="UTC")
    S.extend_all(c, time.time(), 6 * 3600, tz="UTC")
    titles = {r["id"]: r["title"] for r in c.execute("SELECT m.id, a.title FROM media m JOIN art a ON a.tmdb_id=m.id")}
    srv = SV._TVServer(("127.0.0.1", 0), SV.make_handler(SV.App(cfg)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    n = [0]

    def answer():
        r = c.execute("SELECT title FROM rl_rounds ORDER BY id DESC LIMIT 1").fetchone()
        return r["title"] if r else ""

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = getattr(p, engine).launch()
        pg = b.new_context(viewport={"width": 1280, "height": 720}).new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append("console: " + m.text) if m.type == "error" and "favicon" not in m.text and "404" not in m.text else None)

        def shot(name):
            if shots:
                n[0] += 1
                pg.screenshot(path=os.path.join(shots, f"{n[0]:02d}-{name}.png"))

        class Text(str):                                          # headings are shown in capitals: compare without case
            def __contains__(self, x):
                return str.__contains__(self.lower(), x.lower())

        def text(sel="#rl"):
            return Text(pg.inner_text(sel))

        pg.goto(base + "/")
        pg.wait_for_timeout(3000)
        for _ in range(3):                                        # tap-to-start, welcome and channel picker of a first start
            if pg.evaluate("document.querySelector('#tapgo').classList.contains('on')"):
                pg.click("#tapgo")
            if pg.evaluate("document.querySelector('#news').classList.contains('on')"):
                pg.click("#nw-ok")
            pg.wait_for_timeout(900)
        pg.mouse.click(640, 300)
        pg.keyboard.press("h")
        pg.wait_for_timeout(1500)
        if not pg.evaluate("document.querySelector('#home').classList.contains('on')"):
            pg.keyboard.press("h")
            pg.wait_for_timeout(1500)
        check(pg.evaluate("document.querySelector('#home').classList.contains('on')") and "Movie Roulette" in pg.inner_text("#tiles"), "Home has a Movie Roulette tile")
        shot("home")
        pg.get_by_text("Movie Roulette", exact=True).first.click()
        pg.wait_for_timeout(1500)
        check(pg.evaluate("document.querySelector('#rl').classList.contains('landing')") and "6 films" in text(), "the landing page opens and counts the library's films")
        check(pg.evaluate("document.querySelector('#v').paused"), "the TV underneath is paused while the game is open")
        check(pg.evaluate("document.activeElement.textContent") == "Play now", "Play now is highlighted first")
        shot("landing")

        # ---- a solo game from Play now
        pg.keyboard.press("Enter")
        pg.wait_for_selector("#rl.game.guess .g-img", timeout=20000)
        pg.wait_for_timeout(1200)
        ans = answer()
        check(pg.evaluate("(()=>{const i=document.querySelector('#rl .g-img');return i.complete&&i.naturalWidth>0})()"), "a real picture from the film is on the screen")
        check(ans and ans.lower() not in pg.inner_html("#rl").lower() and "/media/" not in pg.inner_html("#rl"), "the film's name is nowhere in the game screen before the reveal")
        check("Round 1 of 6" in text(), "the game has as many rounds as there are films (6 of the usual 10)")
        check(pg.evaluate("document.activeElement.classList.contains('g-in')"), "the answer box is ready to type in")
        t0 = int(pg.inner_text("#rl .g-timer b"))
        pg.wait_for_timeout(2100)
        check(int(pg.inner_text("#rl .g-timer b")) < t0 <= 45, f"the clock started by itself and counts down (from {t0})")
        shot("guess")
        pg.keyboard.type("r")                                     # letters typed into the box are letters, not shortcuts
        check(pg.evaluate("document.querySelector('#rl').classList.contains('guess')"), "typing R in the answer box does not reveal the film")
        pg.keyboard.type("ound table")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(700)
        check("Not that one" in text() and pg.evaluate("document.querySelector('#rl').classList.contains('guess')"), "a wrong typed answer says so and the round goes on")
        pg.keyboard.press("Tab")
        pg.keyboard.press("h")
        pg.wait_for_timeout(700)
        check("HINT 1" in text() and "It came out in the" in text() and "Worth 75 points" in text(), "H gives the first hint (the decade) and the round is now worth 75")
        shot("hint")
        pg.keyboard.press(" ")
        pg.wait_for_timeout(500)
        check("paused" in pg.inner_text("#rl .g-timer"), "Space pauses the clock")
        pg.click("#rl .g-in")
        pg.keyboard.type(ans.lower().replace(":", ""))
        pg.keyboard.press("Enter")
        pg.wait_for_selector("#rl.game.revealed .g-answer", timeout=8000)
        pg.wait_for_timeout(900)
        check(ans.upper() in text().upper() and "got it: +75" in text(), "the right answer reveals the film and gives 75 points")
        check(str(FILMS[[f[0] for f in FILMS].index(ans)][1]) in text("#rl .g-answer") and "Directed by" in text(), "the reveal shows year, genre and director")
        shot("revealed")
        pg.keyboard.press("n")
        pg.wait_for_selector("#rl.game.guess .g-img", timeout=20000)
        check("Round 2 of 6" in text() and answer() != ans, "N deals round 2 with a different film")
        pg.keyboard.press("Escape")                               # focus is in the answer box: Esc opens the pause menu
        pg.wait_for_timeout(500)
        check("Paused" in text() and pg.evaluate("document.activeElement.textContent") == "Carry on", "Esc opens the pause menu (it never ends the game by accident)")
        shot("paused")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
        check("Paused" not in text(), "Esc again carries on")
        pg.keyboard.press("Tab")
        pg.keyboard.press("s")
        pg.wait_for_selector("#rl.game.skipped", timeout=8000)
        check("does not count" in text(), "S skips the film and shows what it was")
        pg.keyboard.press("n")
        pg.wait_for_selector("#rl.game.guess .g-img", timeout=20000)
        check("Round 2 of 6" in text(), "a skipped film does not use up a round")
        for _ in range(5):                                        # reveal and move on through the rest
            pg.keyboard.press("Tab")
            pg.keyboard.press("r")
            pg.wait_for_selector("#rl.game.revealed", timeout=8000)
            pg.keyboard.press("n")
            pg.wait_for_timeout(2500)
            if pg.evaluate("document.querySelector('#rl').classList.contains('final')"):
                break
        pg.wait_for_selector("#rl.final", timeout=20000)
        check("THE WINNER IS" in text() and "75 points" in text(), "after the last round the winner screen shows")
        shot("winner")
        pg.keyboard.press("ArrowRight")
        pg.keyboard.press("ArrowRight")
        pg.keyboard.press("Enter")                                # See the rounds
        pg.wait_for_timeout(900)
        check(ans in text() and "+75" in text(), "the game's rounds are in the history")
        shot("history-detail")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(900)

        # ---- create a party game
        check(pg.evaluate("document.querySelector('#rl').classList.contains('landing')"), "Esc goes back to the landing page")
        pg.locator("#rl button", has_text="Create game").click()
        pg.wait_for_timeout(700)
        pg.locator("#rl .rl-row button", has_text="Party").click()
        pg.wait_for_timeout(500)
        pg.locator("#rl button", has_text="+ Player").click()
        pg.wait_for_timeout(400)
        boxes = pg.locator("#rl .names input")
        check(boxes.count() == 3, "a party game starts with players to name, and + Player adds one")
        for i, nm in enumerate(["Ann", "Bo", "Cy"]):
            boxes.nth(i).fill(nm)
        pg.locator("#rl .rl-row button", has_text="5").first.click()
        shot("create")
        pg.locator("#rl button", has_text="Choose categories").click()
        pg.wait_for_timeout(900)
        check("Genres" in text() and "Directors" in text() and "Marvel Movies" in text(), "categories come from HERO TV: channels, genres, decades, directors")
        pg.locator("#rl .chip", has_text="Action").first.click()
        pg.wait_for_timeout(600)
        check("5 films can come up" in text(), "choosing Action counts 5 films")
        shot("categories")
        pg.locator("#rl button", has_text="Save as my category").click()
        pg.wait_for_timeout(300)
        pg.keyboard.type("Punchy films")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(900)
        check("Your categories" in text() and "Punchy films" in text(), "a selection can be saved as your own category")
        pg.locator("#rl button", has_text="Done").click()
        pg.wait_for_timeout(700)
        check("5 of 6 films" in text(), "the game form shows how many films can come up")
        pg.locator("#rl button", has_text="Start the game").click()
        pg.wait_for_selector("#rl.game.guess .g-img", timeout=20000)
        pg.wait_for_timeout(800)
        check("Who knows it? Press their number." in text() and "Ann" in pg.inner_text("#rl .g-board"), "the party game asks who knows it and lists the players")
        pg.keyboard.press("2")
        pg.wait_for_timeout(400)
        check("Bo is answering" in text(), "pressing 2 chooses Bo")
        shot("party")
        pg.keyboard.press("Tab")
        pg.keyboard.press("x")
        pg.wait_for_timeout(600)
        check("Not that one" in text(), "X marks Bo's answer wrong")
        pg.keyboard.press("r")
        pg.wait_for_selector("#rl.game.revealed", timeout=8000)
        pg.wait_for_timeout(600)
        pg.keyboard.press("3")
        pg.wait_for_timeout(700)
        check("Cy got it: +100" in text(), "after the reveal, pressing 3 gives the round to Cy")
        shot("party-revealed")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
        pg.locator("#rl .rl-modal button", has_text="Leave and come back later").click()
        pg.wait_for_timeout(1500)
        check(not pg.evaluate("window.Roulette.isOpen()") and pg.evaluate("document.querySelector('#home').classList.contains('on')"), "leaving the game goes back to HERO TV's Home")
        pg.wait_for_timeout(2500)
        check(not pg.evaluate("document.querySelector('#v').paused"), "live TV plays again after the game")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(500)
        pg.keyboard.press("ArrowUp")                              # channel change still works: HERO TV's own keys are back
        pg.wait_for_timeout(1500)
        pg.evaluate("window.Roulette.open()")
        pg.wait_for_timeout(1200)
        check(pg.evaluate("document.activeElement.textContent") == "Continue game" and "A game is waiting" in text(), "the landing page offers Continue game")
        pg.keyboard.press("Enter")
        pg.wait_for_selector("#rl.game.revealed", timeout=8000)
        check("Cy got it" in text(), "Continue game picks up exactly where it stopped")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        pg.locator("#rl .rl-modal button", has_text="End the game now").click()
        pg.wait_for_timeout(300)
        pg.locator("#rl .rl-modal button", has_text="End the game").last.click()
        pg.wait_for_selector("#rl.final", timeout=8000)
        check("Cy" in pg.inner_text("#rl .rl-hero h1"), "ending the game early still names the winner")
        pg.locator("#rl button", has_text="Back to").click()
        pg.wait_for_timeout(1000)

        # ---- teams, choosing the moment yourself, and a clip
        pg.evaluate("window.Roulette.open()")
        pg.wait_for_timeout(1000)
        pg.locator("#rl button", has_text="Create game").click()
        pg.wait_for_timeout(700)
        pg.locator("#rl .rl-row button", has_text="Teams").click()
        pg.wait_for_timeout(500)
        check(pg.locator("#rl .rl-row", has_text="Teams").locator("input").count() == 2, "a team game starts with two teams to name")
        pg.locator("#rl .rl-row", has_text="All films").locator("button", has_text="All films").click() if pg.locator("#rl button", has_text="All films").count() else None
        pg.wait_for_timeout(400)
        pg.locator("#rl .rl-row button", has_text="The guesser picks where").click()
        pg.locator("#rl .rl-row button", has_text="A short clip").click()
        pg.locator("#rl .rl-row button", has_text="Expert").click()
        pg.locator("#rl button", has_text="Start the game").click()
        pg.wait_for_selector("#rl.game.pick .g-pick", timeout=20000)
        check("where in the film" in text() and pg.locator("#rl .g-img").count() == 0, "the guesser is asked where in the film to look, before any picture shows")
        shot("pick")
        pg.keyboard.press("ArrowLeft")                            # focus is on 'Show this moment'; go up to the slider and move it
        pg.keyboard.press("ArrowUp")
        for _ in range(6):
            pg.keyboard.press("ArrowRight")
        pg.keyboard.press("Enter")
        pg.wait_for_selector("#rl.game.guess .g-img", timeout=20000)
        pg.wait_for_timeout(700)
        check(pg.locator("#rl video.rl-clip").count() == 1, "a short clip of the film plays first")
        check(pg.evaluate("document.querySelector('#v').paused"), "the TV's own video stays paused during the clip")
        check("Team 1's turn" in text() and "close-up" not in text(), "it is Team 1's turn")
        shot("clip")
        pg.keyboard.press("Tab")
        pg.keyboard.press("r")
        pg.wait_for_selector("#rl.game.revealed", timeout=8000)
        check(pg.locator("#rl video.rl-clip").count() == 0, "the clip stops when the answer is revealed")
        pg.keyboard.press("2")
        pg.wait_for_timeout(600)
        check("Team 2 got it" in text(), "the other team can be given the round (a steal)")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        pg.locator("#rl .rl-modal button", has_text="Change the scores").click()
        pg.wait_for_timeout(300)
        pg.locator("#rl .adj", has_text="Team 1").locator("button", has_text="+25").click()
        pg.wait_for_timeout(600)
        check("25" in pg.inner_text("#rl .adj >> nth=0"), "the host can change a score by hand")
        pg.locator("#rl .rl-modal button", has_text="Done").click()
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        pg.locator("#rl .rl-modal button", has_text="Leave and come back later").click()
        pg.wait_for_timeout(1200)

        # ---- settings and how to play
        pg.evaluate("window.Roulette.open()")
        pg.wait_for_timeout(1000)
        pg.locator("#rl button", has_text="Game settings").click()
        pg.wait_for_timeout(700)
        pg.locator("#rl .rl-row", has_text="Difficulty").locator("button", has_text="Hard").click()
        pg.wait_for_timeout(500)
        check(json.loads(c.execute("SELECT value FROM prefs WHERE key='rl_settings'").fetchone()[0])["difficulty"] == "hard", "a setting is saved the moment it is changed")
        shot("settings")
        pg.locator("#rl .rl-row", has_text="Reveal the answer").locator("button").click()
        pg.wait_for_timeout(200)
        pg.keyboard.press("v")
        pg.wait_for_timeout(700)
        check(json.loads(c.execute("SELECT value FROM prefs WHERE key='rl_settings'").fetchone()[0])["keys"]["reveal"] == "v", "the Reveal key can be changed")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(600)
        pg.locator("#rl button", has_text="How to play").click()
        pg.wait_for_timeout(500)
        check("Name the film" in text() and "V" in pg.inner_text("#rl .rl-keys"), "How to play explains the game with your own keys")
        shot("how")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(500)
        pg.locator("#rl button", has_text="History").click()
        pg.wait_for_timeout(700)
        check(pg.locator("#rl .rl-table .tr").count() >= 2, "the finished games are in the history")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(500)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(1200)
        check(not pg.evaluate("window.Roulette.isOpen()"), "Esc on the landing page goes back to HERO TV")
        check(not errors, "no script errors on the page" + (": " + " | ".join(errors[:3]) if errors else ""))
        b.close()
    srv.shutdown()
    print("\n" + ("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "chromium", sys.argv[2] if len(sys.argv) > 2 else None))
