"""Movie Roulette: the film pool and categories, answer matching, picking the moment, and a whole game."""
import json
import os
import random
import tempfile
from pathlib import Path

try:
    import pytest
except ImportError:                      # the plain unittest run skips this file; CI runs it with pytest in its own step
    import unittest
    raise unittest.SkipTest("needs pytest")

from herotv import tools
from herotv.config import Config
from herotv.db import connect
from herotv.roulette import answers, api, frames, game, pool, store
from herotv.roulette.store import Bad

FILMS = [  # title, year, folder, genres, cast, directors, studio, series
    ("Iron Man", 2008, "MCU", ["Action", "Science Fiction"], ["Robert Downey Jr.", "Gwyneth Paltrow"], ["Jon Favreau"], "Marvel Studios", "Iron Man Collection"),
    ("Iron Man 2", 2010, "MCU", ["Action"], ["Robert Downey Jr.", "Mickey Rourke"], ["Jon Favreau"], "Marvel Studios", "Iron Man Collection"),
    ("Thor: Ragnarok", 2017, "MCU", ["Action", "Comedy"], ["Chris Hemsworth"], ["Taika Waititi"], "Marvel Studios", "Thor Collection"),
    ("The Dark Knight", 2008, "DC", ["Action", "Crime"], ["Christian Bale", "Heath Ledger"], ["Christopher Nolan"], "Warner Bros. Pictures", "The Dark Knight Collection"),
    ("The Dark Knight Rises", 2012, "DC", ["Action"], ["Christian Bale", "Tom Hardy"], ["Christopher Nolan"], "Warner Bros. Pictures", "The Dark Knight Collection"),
    ("Anchorman: The Legend of Ron Burgundy", 2004, "Comedy", ["Comedy"], ["Will Ferrell"], ["Adam McKay"], "DreamWorks Pictures", ""),
]


def _setup(films=FILMS, files=True):
    d = tempfile.mkdtemp()
    cfg = Config(media_dir=Path(d), db_path=os.path.join(d, "t.sqlite3"), channels_file=os.path.join(d, "channels.json"))
    c = connect(cfg.db_path)
    store.ensure(c)
    c.execute("CREATE TABLE IF NOT EXISTS intros(media_id INTEGER PRIMARY KEY, intro_start REAL, intro_end REAL, credits REAL, checked INTEGER)")
    for i, (t, y, fr, g, cast, dr, st, col) in enumerate(films, 1):
        p = os.path.join(d, f"{i}.mkv")
        if files:
            open(p, "wb").write(b"x")
        c.execute("INSERT INTO media(id,path,title,year,franchise,verified,playable,available,runtime_s,height) VALUES(?,?,?,?,?,1,1,1,7200,1080)",
                  (i, p, t.replace(":", " -"), y, fr))
        k = __import__("herotv.art", fromlist=["x"]).key_for(c.execute("SELECT * FROM media WHERE id=?", (i,)).fetchone())[0]
        c.execute("INSERT INTO art(key,tmdb_id,kind,title,year,genres,\"cast\",rating,miss,facts,tagline) VALUES(?,?,?,?,?,?,?,7.5,0,?,'A tagline')",
                  (k, i, "movie", t, y, json.dumps(g), json.dumps(cast),
                   json.dumps({"type": "movie", "companies": [st], "genres": g, "collection": col, "directors": dr, "year": y})))
    c.execute("INSERT INTO channels(id,number,name,rules,kind) VALUES('mcu',1,'Marvel Movies',?, 'tv')", (json.dumps({"franchise": ["MCU"]}),))
    c.execute("INSERT INTO channels(id,number,name,rules,kind) VALUES('all',2,'Everything','{}','tv')")
    c.commit()
    return c, cfg


@pytest.fixture
def fake_ffmpeg(monkeypatch):
    monkeypatch.setattr(tools, "find_tool", lambda n: "/bin/true")


def _grab(path, t, out, **kw):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "wb").write(b"jpg")
    return True


def _play(c, cfg, **body):
    gid = game.create(c, cfg, body)
    game.next_round(c, cfg, game.get(c, gid), rng=random.Random(1), measure_fn=lambda p, t: (120.0, 40.0), grab_fn=_grab)
    return gid


def _next(c, cfg, gid):
    return game.next_round(c, cfg, game.get(c, gid), rng=random.Random(2), measure_fn=lambda p, t: (120.0, 40.0), grab_fn=_grab)


# ---------------------------------------------------------------- pool and categories

def test_films_are_the_librarys_films_once_each():
    c, cfg = _setup()
    c.execute("INSERT INTO media(id,path,title,year,franchise,verified,playable,available,runtime_s,height) VALUES(50,'/x/im4k.mkv','Iron Man',2008,'MCU',1,0,1,7200,2160)")
    c.execute("INSERT INTO media(id,path,title,series,season,episode,franchise,verified,playable,available,runtime_s) VALUES(51,'/x/e.mkv','Pilot','Loki',1,1,'Marvel TV',1,1,1,3000)")
    c.execute("INSERT INTO media(id,path,title,franchise,verified,playable,available,runtime_s) VALUES(52,'/x/clip.mkv','Some Clip','Inbox',1,1,1,1500)")
    c.execute("INSERT INTO media(id,path,title,franchise,verified,playable,available,runtime_s) VALUES(53,'/x/home.mkv','Home Video','Inbox',1,1,1,5400)")
    films = pool.movies(c)
    titles = sorted(m["title"] for m in films.values())
    assert "Pilot" not in titles and "Some Clip" not in titles           # an episode; an unmatched short file
    assert "Home Video" in titles                                         # unmatched but full length: still a film
    im = next(m for m in films.values() if m["title"] == "Iron Man")
    assert len(im["files"]) == 2 and im["id"] == 1                        # two copies, one film; the playable copy stands for it


def test_categories_come_from_the_films_and_empty_ones_do_not_show():
    c, cfg = _setup()
    cats = pool.categories(c)
    by = {g["kind"]: {i["name"]: i["count"] for i in g["items"]} for g in cats["groups"]}
    assert by["channel"] == {"Marvel Movies": 3}                          # the catch-all channel is not a category
    assert by["genre"]["Action"] == 5 and by["genre"]["Comedy"] == 2
    assert by["decade"] == {"2000s": 3, "2010s": 3}
    assert by["collection"]["Iron Man"] == 2 and by["collection"]["The Dark Knight"] == 2
    assert by["director"] == {"Christopher Nolan": 2, "Jon Favreau": 2}   # one-film directors are left out
    assert by["actor"] == {"Christian Bale": 2, "Robert Downey Jr.": 2}
    assert cats["total"] == 6


def test_choosing_several_categories_any_and_all():
    c, cfg = _setup()
    films = pool.movies(c)
    t = lambda keys, logic: sorted(films[k]["title"] for k in pool.members(films, keys, logic))
    assert t(["genre:Comedy", "director:Christopher Nolan"], "any") == ["Anchorman: The Legend of Ron Burgundy", "The Dark Knight", "The Dark Knight Rises", "Thor: Ragnarok"]
    assert t(["genre:Comedy", "channel:mcu"], "all") == ["Thor: Ragnarok"]
    assert t(["genre:Western"], "any") == []
    assert len(t([], "any")) == 6


def test_your_own_categories_make_rename_change_delete():
    c, cfg = _setup()
    cid = pool.category_op(c, {"op": "create", "name": "Bat and Iron", "keys": ["collection:Iron Man Collection", "director:Christopher Nolan"]})
    cats = pool.categories(c)
    assert cats["custom"][0]["name"] == "Bat and Iron" and cats["custom"][0]["count"] == 4
    with pytest.raises(Bad):
        pool.category_op(c, {"op": "create", "name": "bat and iron", "keys": ["genre:Action"]})          # same name
    with pytest.raises(Bad):
        pool.category_op(c, {"op": "create", "name": "Empty", "keys": []})
    pool.category_op(c, {"op": "rename", "id": cid, "name": "Heroes"})
    pool.category_op(c, {"op": "update", "id": cid, "keys": ["genre:Comedy"], "logic": "any"})
    cu = pool.categories(c)["custom"][0]
    assert (cu["name"], cu["count"]) == ("Heroes", 2)
    films = pool.movies(c)
    assert len(pool.members(films, [f"custom:{cid}", "channel:mcu"], "all", pool.custom(c))) == 1       # mixes with the others
    pool.category_op(c, {"op": "delete", "id": cid})
    assert pool.categories(c)["custom"] == []
    with pytest.raises(Bad):
        pool.category_op(c, {"op": "delete", "id": cid})


# ---------------------------------------------------------------- answers

@pytest.mark.parametrize("guess,title,want", [
    ("iron man", "Iron Man", "correct"), ("IRON-MAN!", "Iron Man", "correct"), ("iorn man", "Iron Man", "correct"),
    ("iron man", "Iron Man 2", "close"), ("iron man two", "Iron Man 2", "correct"), ("iron man ii", "Iron Man 2", "correct"),
    ("iron man 3", "Iron Man 2", "wrong"), ("ragnarok", "Thor: Ragnarok", "correct"), ("thor ragnorok", "Thor: Ragnarok", "correct"),
    ("dark knight", "The Dark Knight", "correct"), ("dark knight", "The Dark Knight Rises", "close"),
    ("the dark night rises", "The Dark Knight Rises", "correct"), ("anchorman", "Anchorman: The Legend of Ron Burgundy", "correct"),
    ("man", "Iron Man", "wrong"), ("the", "The Dark Knight", "wrong"), ("", "Iron Man", "wrong"), ("batman", "The Dark Knight", "wrong"),
])
def test_typed_answers(guess, title, want):
    assert answers.check(guess, title, [f[0] for f in FILMS]) == want


def test_spelling_help_can_be_switched_off_and_the_file_name_counts():
    others = [f[0] for f in FILMS]
    assert answers.check("iorn man", "Iron Man", others, spelling=False) == "wrong"
    assert answers.check("x men 2 united", "X2", others, alts=["X-Men 2 United"]) == "correct"


# ---------------------------------------------------------------- the moment and the picture

def test_the_window_skips_the_credits_and_follows_the_difficulty():
    cfg = dict(store.DEFAULTS)
    lo, hi = frames.window(7200, cfg, store.DIFFICULTIES["hard"])
    assert (lo, hi) == (180.0, 6600.0)                       # 3 minutes in, 10 minutes before the end
    lo, hi = frames.window(7200, cfg, store.DIFFICULTIES["easy"])
    assert (lo, hi) == (1080.0, 6120.0)                      # the middle 15% to 85%
    assert frames.window(7200, cfg, store.DIFFICULTIES["hard"], credits=6300)[1] == 6300      # HERO TV found the credits
    lo, hi = frames.window(90, cfg, store.DIFFICULTIES["normal"])
    assert 0 <= lo < hi <= 88                                # a short file still gives a usable window
    with pytest.raises(Bad):
        frames.window(0, cfg, store.DIFFICULTIES["normal"])
    assert frames.valid(99999 if False else 7000, (180, 6600), 7200) == 6600                  # pulled back inside the window
    with pytest.raises(Bad):
        frames.valid(9000, (180, 6600), 7200)


def test_dark_and_flat_pictures_are_thrown_back():
    seen = []

    def measure(path, t):
        seen.append(t)
        return [(3.0, 1.0), (250.0, 2.0), (120.0, 4.0), (110.0, 35.0)][len(seen) - 1]       # black, white, flat grey, a real picture
    t, ok = frames.choose("f", (100, 5000), "any", (), random.Random(3), measure)
    assert ok and t == seen[3] and len(seen) == 4
    t, ok = frames.choose("f", (100, 5000), "any", (), random.Random(3), lambda p, t: (2.0, 1.0))
    assert not ok and 100 <= t <= 5000                       # nothing usable: a plain random moment, and it says so
    t, ok = frames.choose("f", (100, 5000), "any", (), random.Random(3), lambda p, t: None)
    assert not ok and 100 <= t <= 5000                       # ffmpeg cannot read it: same


def test_clear_takes_the_most_detailed_and_plain_the_least():
    vals = iter([(120, 20.0), (120, 60.0), (120, 35.0)])
    ts = []

    def measure(path, t):
        ts.append(t)
        return next(vals)
    t, _ = frames.choose("f", (100, 5000), "clear", (), random.Random(1), measure)
    assert t == ts[1]
    vals = iter([(120, 20.0), (120, 60.0), (120, 35.0)])
    ts.clear()
    t, _ = frames.choose("f", (100, 5000), "plain", (), random.Random(1), measure)
    assert t == ts[0]


def test_moments_in_one_film_keep_apart():
    rng = random.Random(5)
    used = []
    for _ in range(20):
        t = frames.random_time((0, 3000), used, rng)
        assert all(abs(t - u) >= 45 for u in used)
        used.append(t)


@pytest.mark.skipif(not tools.find_tool("ffmpeg"), reason="needs ffmpeg")
def test_a_real_file_is_measured_and_grabbed():
    d = tempfile.mkdtemp()
    f = os.path.join(d, "film.mkv")
    exe = tools.find_tool("ffmpeg")
    r = tools.run([exe, "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=320x180:d=4", "-f", "lavfi", "-i", "testsrc=s=320x180:d=6",
                   "-filter_complex", "[0:v][1:v]concat=n=2:v=1", "-pix_fmt", "yuv420p", f], timeout=120)
    assert r.returncode == 0, r.stderr
    dark, pic = frames.measure(f, 1.0), frames.measure(f, 7.0)
    assert dark and dark[0] < frames.DARK and not frames.good(dark)
    assert pic and frames.good(pic)
    t, ok = frames.choose(f, (0.0, 9.0), "any", (), random.Random(2))
    assert ok and t >= 4                                      # never the black part
    out = os.path.join(d, "o", "x-0.jpg")
    assert frames.grab(f, t, out) and open(out, "rb").read(3) == b"\xff\xd8\xff"
    assert frames.measure(os.path.join(d, "nothing.mkv"), 1.0) is None


# ---------------------------------------------------------------- settings

def test_settings_are_checked_and_kept():
    c, cfg = _setup()
    assert store.load(c)["rounds"] == 10
    s = store.save(c, {"rounds": 5, "difficulty": "hard", "points": [200, 150, 100, 50], "keys": {"reveal": "v"}})
    assert store.load(c) == s and s["keys"]["reveal"] == "v" and s["keys"]["hint"] == "h"
    for bad in ({"rounds": 0}, {"difficulty": "silly"}, {"nope": 1}, {"points": [1, 2]}, {"keys": {"reveal": "h"}}, {"timer": 9999}):
        with pytest.raises(Bad):
            store.save(c, bad)
    c.execute("UPDATE prefs SET value=? WHERE key='rl_settings'", (json.dumps({"rounds": 7, "difficulty": "from an older version"}),))
    assert store.load(c)["rounds"] == 7 and store.load(c)["difficulty"] == "normal"      # one bad stored value loses nothing else


# ---------------------------------------------------------------- a game

def test_solo_game_typed_answers_hints_and_scores(fake_ffmpeg):
    c, cfg = _setup()
    gid = _play(c, cfg, mode="solo", rounds=3, players=["Nick"])
    v = game.view(c, cfg, game.get(c, gid))
    r = v["round"]
    assert v["status"] == "active" and r["number"] == 1 and r["status"] == "guess" and len(r["frames"]) == 1
    blob = json.dumps(v)
    title = c.execute("SELECT title FROM rl_rounds WHERE game_id=?", (gid,)).fetchone()[0]
    assert title not in blob and "answer" not in r and "media_id" not in blob        # nothing gives the film away
    assert os.path.isfile(api.frame_path(cfg, r["frames"][0].rsplit("/", 1)[1]))
    assert game.guess(c, game.get(c, gid), "definitely not a film") == "wrong"
    h = game.hint(c, cfg, game.get(c, gid), grab_fn=_grab)
    assert h["kind"] == "decade" and "0s" in h["text"]
    assert game.guess(c, game.get(c, gid), title.upper()) == "correct"
    v = game.view(c, cfg, game.get(c, gid))
    assert v["round"]["status"] == "revealed" and v["round"]["answer"]["title"] == title
    assert v["round"]["win"]["points"] == 75 and v["board"][0]["points"] == 75           # one hint used
    with pytest.raises(Bad):
        game.award(c, game.get(c, gid), 1)                                               # never twice
    _next(c, cfg, gid)
    t2 = c.execute("SELECT title FROM rl_rounds WHERE game_id=? ORDER BY id DESC", (gid,)).fetchone()[0]
    assert t2 != title                                                                    # no film twice in a game
    game.reveal(c, game.get(c, gid))
    _next(c, cfg, gid)
    game.award(c, game.get(c, gid), 1)
    assert _next(c, cfg, gid) is None                                                     # that was round 3 of 3
    g = game.get(c, gid)
    v = game.view(c, cfg, g)
    assert g["status"] == "finished" and v["board"][0]["points"] == 175 and v["winners"][0]["name"] == "Nick"
    assert game.history(c)[0]["winners"] == ["Nick"]
    d = game.detail(c, gid)
    assert [x["points"] for x in d["rounds_list"]] == [75, 0, 100]
    assert not os.listdir(frames.folder(cfg))                                             # the pictures are cleared away


def test_turns_teams_and_party(fake_ffmpeg):
    c, cfg = _setup()
    gid = _play(c, cfg, mode="turns", rounds=4, players=["Ann", "Bo"])
    v = game.view(c, cfg, game.get(c, gid))
    assert [s["name"] for s in v["sides"]] == ["Ann", "Bo"] and v["round"]["turn"] == 1
    title = c.execute("SELECT title FROM rl_rounds WHERE game_id=?", (gid,)).fetchone()[0]
    game.guess(c, game.get(c, gid), title, side=2)                    # typed answers belong to whoever's turn it is
    assert game.view(c, cfg, game.get(c, gid))["round"]["win"]["side"] == 1
    _next(c, cfg, gid)
    assert game.view(c, cfg, game.get(c, gid))["round"]["turn"] == 2
    game.wrong(c, game.get(c, gid), 2)
    game.award(c, game.get(c, gid), 1)                                # a steal, given by the host
    b = game.view(c, cfg, game.get(c, gid))["board"]
    assert (b[0]["name"], b[0]["points"], b[0]["rank"]) == ("Ann", 200, 1) and b[1]["rank"] == 2

    gid = _play(c, cfg, mode="teams", rounds=2, teams=["Reds", "Blues"], players=[{"name": "Ann", "team": 2}, {"name": "Bo", "team": 1}, {"name": "Cy"}])
    v = game.view(c, cfg, game.get(c, gid))
    assert [(s["name"], s["players"]) for s in v["sides"]] == [("Reds", ["Bo", "Cy"]), ("Blues", ["Ann"])]
    assert game.get(c, gid - 1)["status"] == "abandoned"               # the earlier game was put aside, not lost
    assert store.load(c)["teams"] == [{"name": "Reds"}, {"name": "Blues"}]

    gid = _play(c, cfg, mode="party", rounds=2, players=["Ann", "Bo", "Cy"])
    v = game.view(c, cfg, game.get(c, gid))
    assert v["round"]["turn"] is None
    with pytest.raises(Bad):
        game.guess(c, game.get(c, gid), "x")                           # in a party game, say who is answering
    game.reveal(c, game.get(c, gid))
    game.award(c, game.get(c, gid), 3)                                 # someone shouted it: given after the reveal
    game.unaward(c, game.get(c, gid))
    game.award(c, game.get(c, gid), 2)                                 # the host pressed the wrong name
    b = game.view(c, cfg, game.get(c, gid))["board"]
    assert [(s["name"], s["points"]) for s in b] == [("Bo", 100), ("Ann", 0), ("Cy", 0)] and b[1]["tied"] and not b[0]["tied"]
    game.adjust(c, game.get(c, gid), 1, 30, "n1")
    game.adjust(c, game.get(c, gid), 1, 30, "n1")                      # the same press twice counts once
    assert next(s for s in game.board(c, game.get(c, gid)) if s["name"] == "Ann")["points"] == 30


def test_timer_speed_bonus_and_time_up(fake_ffmpeg):
    c, cfg = _setup()
    gid = _play(c, cfg, mode="solo", rounds=2, timer=30, speed_bonus=True, speed_max=50)
    g = game.get(c, gid)
    assert game.view(c, cfg, g, now=1000)["round"]["timer"] == {"limit": 30, "left": 30.0, "running": False}
    game.timer(c, g, "start", now=1000)
    assert game.view(c, cfg, g, now=1012)["round"]["timer"]["left"] == 18.0
    game.timer(c, g, "pause", now=1012)
    assert game.view(c, cfg, g, now=5000)["round"]["timer"] == {"limit": 30, "left": 18.0, "running": False}
    game.timer(c, g, "resume", now=5000)
    game.award(c, g, 1, now=5003)                                      # 15 of 30 seconds left: half the bonus
    assert game.view(c, cfg, game.get(c, gid))["round"]["win"] == {"side": 1, "points": 125, "base": 100, "speed": 25, "hints": 0}
    _next(c, cfg, gid)
    g = game.get(c, gid)
    game.timer(c, g, "start", now=100)
    v = game.view(c, cfg, g, now=131)                                  # nobody answered: the game reveals by itself
    assert v["round"]["status"] == "revealed" and "answer" in v["round"]

    gid = _play(c, cfg, mode="solo", rounds=1, timer=15, after_time="last")
    g = game.get(c, gid)
    game.timer(c, g, "start", now=100)
    assert game.view(c, cfg, g, now=120)["round"]["status"] == "timeup"
    assert game.guess(c, g, "nope") == "wrong"                         # the last answer, then the reveal
    assert game.view(c, cfg, game.get(c, gid))["round"]["status"] == "revealed"


def test_hints_follow_the_difficulty_and_never_give_the_title(fake_ffmpeg):
    c, cfg = _setup()
    gid = _play(c, cfg, mode="solo", rounds=1, difficulty="easy", categories=["collection:Iron Man Collection"])
    g = game.get(c, gid)
    got = [game.hint(c, cfg, g, measure_fn=lambda p, t: (120.0, 40.0), grab_fn=_grab) for _ in range(3)]
    assert [h["kind"] for h in got] == ["decade", "genre", "frame"]
    v = game.view(c, cfg, game.get(c, gid))
    assert len(v["round"]["frames"]) == 2 and v["round"]["hints_left"] == 0 and v["round"]["would_score"] == 25
    with pytest.raises(Bad):
        game.hint(c, cfg, game.get(c, gid))
    m = pool.movies(c)
    im = next(x for x in m.values() if x["title"] == "Iron Man")
    kinds = [k for k, _ in game.hint_ladder(im, store.HINT_KINDS, "Iron Man")]
    assert "franchise" not in kinds                                    # "Iron Man Collection" would give it away
    assert all("iron" not in t.lower() for _, t in game.hint_ladder(im, store.HINT_KINDS, "Iron Man"))

    gid = _play(c, cfg, mode="solo", rounds=1, hints=False)
    with pytest.raises(Bad):
        game.hint(c, cfg, game.get(c, gid))


def test_skip_does_not_use_up_a_round_and_running_out_ends_the_game(fake_ffmpeg):
    c, cfg = _setup()
    gid = _play(c, cfg, mode="solo", rounds=10, categories=["director:Christopher Nolan"], repeat="game")
    v = game.view(c, cfg, game.get(c, gid))
    assert v["rounds"] == 2 and "Only 2 films" in v["note"]            # two films fit, so two rounds
    game.skip(c, game.get(c, gid))
    v = game.view(c, cfg, game.get(c, gid))
    assert v["round"]["status"] == "skipped" and "answer" in v["round"] and v["played"] == 0
    _next(c, cfg, gid)
    assert game.view(c, cfg, game.get(c, gid))["round"]["number"] == 1
    game.reveal(c, game.get(c, gid))
    _next(c, cfg, gid)                                                 # both films have come up: the game ends rather than repeat
    assert game.get(c, gid)["status"] == "finished"
    with pytest.raises(Bad):
        game.create(c, cfg, {"categories": ["genre:Western"]})


def test_choosing_the_moment_yourself(fake_ffmpeg):
    c, cfg = _setup()
    gid = _play(c, cfg, mode="solo", rounds=1, scene="choose")
    g = game.get(c, gid)
    v = game.view(c, cfg, g)
    assert v["round"]["status"] == "pick" and v["round"]["frames"] == [] and v["round"]["pick"]["min"] == 360.0
    with pytest.raises(Bad):
        game.guess(c, g, "x")
    game.set_time(c, cfg, g, 3600, grab_fn=_grab)
    v = game.view(c, cfg, game.get(c, gid))
    assert v["round"]["status"] == "guess" and c.execute("SELECT ts FROM rl_rounds WHERE game_id=?", (gid,)).fetchone()[0] == 3600


def test_missing_files_and_unreadable_pictures(fake_ffmpeg):
    c, cfg = _setup(files=False)
    with pytest.raises(Bad, match="could not read"):
        _play(c, cfg, mode="solo")
    c, cfg = _setup()
    gid = game.create(c, cfg, {"mode": "solo"})
    with pytest.raises(Bad):
        game.next_round(c, cfg, game.get(c, gid), measure_fn=lambda p, t: None, grab_fn=lambda *a, **k: False)
    assert game.view(c, cfg, game.get(c, gid))["status"] == "active"   # the game is still there to carry on or leave


def test_no_ffmpeg_and_empty_library(monkeypatch):
    c, cfg = _setup()
    monkeypatch.setattr(tools, "find_tool", lambda n: None)
    with pytest.raises(Bad, match="video tools"):
        game.create(c, cfg, {})
    monkeypatch.setattr(tools, "find_tool", lambda n: "/bin/true")
    c, cfg = _setup(films=[])
    with pytest.raises(Bad, match="no films"):
        game.create(c, cfg, {})
    assert api.home(c, cfg)["films"] == 0


def test_the_requests(fake_ffmpeg, monkeypatch):
    c, cfg = _setup()
    monkeypatch.setattr(frames, "grab", _grab)
    monkeypatch.setattr(frames, "measure", lambda p, t, run=None: (120.0, 40.0))
    h, code = api.handle(c, cfg, "home", {}, "GET")
    assert code == 200 and h["films"] == 6 and h["active"] is None and h["tools"]
    assert api.handle(c, cfg, "count", {"keys": "genre:Comedy|channel:mcu", "logic": "all"}, "GET")[0] == {"count": 1, "total": 6}
    v, _ = api.handle(c, cfg, "new", {}, "POST", {"mode": "party", "rounds": 2, "players": ["Ann", "Bo"]})
    gid = v["game"]["id"]
    assert v["game"]["round"]["status"] == "guess"
    assert api.handle(c, cfg, "home", {}, "GET")[0]["active"]["id"] == gid          # Continue Game finds it
    v, _ = api.handle(c, cfg, "act", {}, "POST", {"game": gid, "op": "hint"})
    assert v["hint"]["kind"] == "decade"
    v, _ = api.handle(c, cfg, "act", {}, "POST", {"game": gid, "op": "guess", "text": "wrong film", "side": 2})
    assert v["verdict"] == "wrong"
    for op in ("reveal", "next", "reveal", "next"):
        v, _ = api.handle(c, cfg, "act", {}, "POST", {"game": gid, "op": op})
    assert v["game"]["status"] == "finished"
    with pytest.raises(Bad):
        api.handle(c, cfg, "act", {}, "POST", {"game": gid, "op": "next"})
    assert api.handle(c, cfg, "history", {}, "GET")[0]["games"][0]["id"] == gid
    assert api.handle(c, cfg, "game", {}, "GET")[0] == {"game": None}
    assert api.frame_path(cfg, "../../t.sqlite3") is None and api.frame_path(cfg, "x.png") is None
    s, _ = api.handle(c, cfg, "settings", {}, "POST", {"rounds": 6})
    assert s["settings"]["rounds"] == 6


def test_phones_cannot_reach_the_game():
    from herotv import remote
    assert not any(n.startswith("roulette") for n in remote.REMOTE_GET_API | remote.REMOTE_POST_API)
    assert not any(n.startswith("roulette") for n in remote.REMOTE_GET_API_PREFIX)


# ---------------------------------------------------------------- multiple choice

def test_multiple_choice(fake_ffmpeg):
    c, cfg = _setup()
    gid = _play(c, cfg, mode="party", rounds=3, answers="choice", players=["Ann", "Bo"])
    g = game.get(c, gid)
    v = game.view(c, cfg, g)
    title = c.execute("SELECT title FROM rl_rounds WHERE game_id=?", (gid,)).fetchone()[0]
    opts = v["round"]["choices"]
    assert len(opts) == 4 and len(set(opts)) == 4 and title in opts          # the film and three others, no title twice
    with pytest.raises(Bad):
        game.guess(c, g, title, 1)                                           # no typing in a multiple-choice game
    wrong = next(i for i, t in enumerate(opts) if t != title)
    assert game.choose(c, g, wrong, 1) == "wrong"
    v = game.view(c, cfg, game.get(c, gid))
    assert v["round"]["out"] == [1] and v["round"]["status"] == "guess"      # Ann is out, Bo can still pick
    with pytest.raises(Bad, match="out of this round"):
        game.choose(c, g, opts.index(title), 1)
    assert game.choose(c, g, opts.index(title), 2) == "correct"
    v = game.view(c, cfg, game.get(c, gid))
    assert v["round"]["win"]["side"] == 2 and "choices" not in v["round"]
    _next(c, cfg, gid)
    g = game.get(c, gid)
    opts = game.view(c, cfg, g)["round"]["choices"]
    title = c.execute("SELECT title FROM rl_rounds WHERE game_id=? ORDER BY id DESC", (gid,)).fetchone()[0]
    wrong = next(i for i, t in enumerate(opts) if t != title)
    game.choose(c, g, wrong, 1)
    game.choose(c, g, wrong, 2)
    assert game.view(c, cfg, game.get(c, gid))["round"]["status"] == "revealed"   # everyone is out: the answer shows
    with pytest.raises(Bad):
        game.choose(c, game.get(c, gid), 9, 1)

    gid = _play(c, cfg, mode="turns", rounds=2, answers="choice", players=["Ann", "Bo"])
    g = game.get(c, gid)
    opts = game.view(c, cfg, g)["round"]["choices"]
    title = c.execute("SELECT title FROM rl_rounds WHERE game_id=?", (gid,)).fetchone()[0]
    game.choose(c, g, next(i for i, t in enumerate(opts) if t != title))
    assert game.view(c, cfg, game.get(c, gid))["round"]["status"] == "revealed"   # a wrong pick ends the turn


def test_decoys_follow_the_difficulty():
    c, cfg = _setup()
    films = pool.movies(c)
    im = next(m for m in films.values() if m["title"] == "Iron Man")
    hard = pool.decoys(films, im, set(films), "plain", random.Random(1))
    assert hard[0] == "Iron Man 2" and "Iron Man" not in hard               # the most alike first; never the answer itself
    assert len(pool.decoys(films, im, {im["key"]}, "any", random.Random(1))) == 3     # a small category borrows from the library
    one = {im["key"]: im}
    assert pool.decoys(one, im, set(one)) == []


# ---------------------------------------------------------------- phones

def test_phones_join_with_the_code_and_play(fake_ffmpeg, monkeypatch):
    from herotv.roulette import phone
    c, cfg = _setup()
    monkeypatch.setattr(frames, "grab", _grab)
    monkeypatch.setattr(frames, "measure", lambda p, t, run=None: (120.0, 40.0))
    gid = game.create(c, cfg, {"mode": "party", "rounds": 2, "players": []})
    code = game._cfg(game.get(c, gid))["code"]
    assert len(code) == 4 and code.isalpha()
    with pytest.raises(Bad, match="does not match"):
        phone.join(c, {"code": "ZZZZ" if code != "ZZZZ" else "YYYY", "name": "Ann"}, "10.0.0.5")
    with pytest.raises(Bad, match="name"):
        phone.join(c, {"code": code, "name": "  "}, "10.0.0.5")
    a = phone.join(c, {"code": code.lower(), "name": "Ann"}, "10.0.0.5")       # takes the first unnamed seat
    b = phone.join(c, {"code": code, "name": "Bo"}, "10.0.0.6")
    d = phone.join(c, {"code": code, "name": "Cy"}, "10.0.0.7")                # a third player is added
    assert [s["name"] for s in game._j(game.get(c, gid)["sides"], [])] == ["Ann", "Bo", "Cy"]
    with pytest.raises(Bad, match="already playing"):
        phone.join(c, {"code": code, "name": "ann"}, "10.0.0.8")
    st = phone.state(c, cfg, a["token"])
    assert st["round"] is None and st["name"] == "Ann" and st["status"] == "active"       # waiting in the lobby
    game.next_round(c, cfg, game.get(c, gid))
    title = c.execute("SELECT title FROM rl_rounds WHERE game_id=?", (gid,)).fetchone()[0]
    st = phone.state(c, cfg, b["token"])
    assert st["round"]["can"] and title not in json.dumps(st) and "media" not in json.dumps(st)
    name = st["round"]["frames"][0].rsplit("/", 1)[1]
    assert phone.frame_path(c, cfg, name, b["token"]) and not phone.frame_path(c, cfg, name, "nope")
    assert not phone.frame_path(c, cfg, "other-0.jpg", b["token"])
    assert phone.answer(c, cfg, {"token": b["token"], "text": "wrong film"})["verdict"] == "wrong"
    out = phone.answer(c, cfg, {"token": d["token"], "text": title})
    assert out["verdict"] == "correct" and out["state"]["round"]["answer"]["title"] == title
    assert phone.state(c, cfg, a["token"])["round"]["won_by"] == "Cy"
    v, _ = api.handle(c, cfg, "game", {}, "GET")
    assert v["game"]["join"]["code"] == code and len(v["game"]["join"]["players"]) == 3
    with pytest.raises(Bad):
        phone.state(c, cfg, "made-up-key")
    game.create(c, cfg, {"mode": "party"})                                      # a new game: old phone keys stop working
    with pytest.raises(Bad, match="over"):
        phone.state(c, cfg, a["token"])


def test_phones_turns_teams_and_limits(fake_ffmpeg, monkeypatch):
    from herotv.roulette import phone
    c, cfg = _setup()
    monkeypatch.setattr(frames, "grab", _grab)
    monkeypatch.setattr(frames, "measure", lambda p, t, run=None: (120.0, 40.0))
    gid = game.create(c, cfg, {"mode": "turns", "rounds": 2, "answers": "choice", "players": ["Ann", "Bo"]})
    code = game._cfg(game.get(c, gid))["code"]
    a = phone.join(c, {"code": code, "name": "Ann"})
    b = phone.join(c, {"code": code, "name": "Bo"})
    game.next_round(c, cfg, game.get(c, gid))
    sb = phone.state(c, cfg, b["token"])
    assert not sb["round"]["can"] and sb["round"]["turn"] == "Ann" and len(sb["round"]["choices"]) == 4
    with pytest.raises(Bad, match="Ann's turn"):
        phone.answer(c, cfg, {"token": b["token"], "choice": 0})
    title = c.execute("SELECT title FROM rl_rounds WHERE game_id=?", (gid,)).fetchone()[0]
    opts = phone.state(c, cfg, a["token"])["round"]["choices"]
    assert phone.answer(c, cfg, {"token": a["token"], "choice": opts.index(title)})["verdict"] == "correct"

    gid = game.create(c, cfg, {"mode": "teams", "teams": ["Reds", "Blues"], "players": []})
    code = game._cfg(game.get(c, gid))["code"]
    ask = phone.join(c, {"code": code, "name": "Dee"})
    assert [t["name"] for t in ask["teams"]] == ["Reds", "Blues"]              # a team game asks which team
    j = phone.join(c, {"code": code, "name": "Dee", "team": 2})
    assert j["side"] == 2 and game._j(game.get(c, gid)["sides"], [])[1]["players"] == ["Dee"]

    gid = game.create(c, cfg, {"mode": "solo"})
    assert not game._cfg(game.get(c, gid))["code"] and api._join(c, cfg, game.get(c, gid)) is None     # one player: no phones
    gid = game.create(c, cfg, {"mode": "party", "phones": False})
    assert phone.find(c, "ABCD") is None
    for _ in range(10):
        with pytest.raises(Bad):
            phone.join(c, {"code": "QQQQ", "name": "x"}, "10.9.9.9")
    with pytest.raises(Bad, match="Too many"):
        phone.join(c, {"code": "QQQQ", "name": "x"}, "10.9.9.9")


def test_a_paired_tv_device_still_cannot_reach_the_host_controls():
    from herotv import remote
    assert not any(n.startswith(("roulette", "party")) for n in remote.REMOTE_GET_API | remote.REMOTE_POST_API)
