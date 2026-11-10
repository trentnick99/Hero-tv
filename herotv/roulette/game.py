"""The game: rounds, guesses, hints, the timer, scores and history.

A round goes   pick -> guess -> (timeup) -> revealed -> closed      or -> skipped from any point.
  pick      only when players choose the moment themselves: the film is chosen, the moment is not yet
  guess     the picture is up and the clock may be running
  timeup    time ran out and the game is set to allow one last answer before the reveal
  revealed  the answer is showing; the host can still say who got it
  closed    over

What the page is sent never contains the film's name, year, poster or file until the round is revealed: the picture is
fetched by a random token. So whoever holds the keyboard can play too."""
import json
import os
import secrets
import time

from .. import art, tools
from . import answers, frames, pool, store
from .store import Bad

OPEN = ("pick", "guess", "timeup", "revealed")
CONFIG_KEYS = ("mode", "rounds", "difficulty", "timer", "hints", "hint_kinds", "points", "speed_bonus", "speed_max", "wrong_penalty",
               "answers", "spelling", "scene", "show", "clip_seconds", "effect", "after_time", "repeat", "categories", "logic",
               "skip_open", "skip_end")
SIDE_COLORS = ["#ffcf1f", "#4cc9f0", "#ff5d73", "#7bd389", "#c77dff", "#ff9f1c", "#2ec4b6", "#f15bb5", "#9be564", "#5e8bff", "#e9c46a", "#ef476f"]


def _j(text, default):
    try:
        v = json.loads(text or "")
    except (TypeError, ValueError):
        return default
    return v if isinstance(v, type(default)) else default


# ------------------------------------------------------------------ making a game

def sides_from(mode, players, teams):
    """Who scores: each player, or each team. [{id, name, players, color}]"""
    players, teams = store.names(players or [], 12), store.names(teams or [], 6)
    if mode == "solo":
        players = players[:1] or [{"name": "Player 1"}]
    if mode == "teams":
        if len(teams) < 2:
            teams = [{"name": "Team 1"}, {"name": "Team 2"}]
        out = [{"id": i + 1, "name": t["name"], "players": []} for i, t in enumerate(teams)]
        for p in players:                     # a player with no team joins the smallest one
            t = p.get("team")
            (out[t - 1] if isinstance(t, int) and 1 <= t <= len(out) else min(out, key=lambda s: len(s["players"])))["players"].append(p["name"])
    else:
        if mode != "solo" and len(players) < 2:
            players = [{"name": f"Player {i + 1}"} for i in range(2)] if not players else players + [{"name": f"Player {len(players) + 1}"}]
        out = [{"id": i + 1, "name": p["name"], "players": []} for i, p in enumerate(players)]
    for i, s in enumerate(out):
        s["color"] = SIDE_COLORS[i % len(SIDE_COLORS)]
    return out


def create(conn, cfg_app, body, now=None):
    """Start a new game from the saved settings with body's choices on top. Any game still open is put aside as unfinished."""
    now = int(now or time.time())
    if not tools.find_tool("ffmpeg"):
        raise Bad("Movie Roulette needs the video tools (ffmpeg) to take pictures from your films. Settings > Tools > Install video tools.")
    body = dict(body or {})
    players, teams = body.pop("players", None), body.pop("teams", None)
    saved = store.load(conn)
    full = store.clean({k: v for k, v in body.items() if k in CONFIG_KEYS}, saved)
    cfg = {k: full[k] for k in CONFIG_KEYS}
    sides = sides_from(cfg["mode"], players if players is not None else saved["players"], teams if teams is not None else saved["teams"])
    films = pool.movies(conn)
    if not films:
        raise Bad("There are no films in your library yet. Add some movies to HERO TV first.")
    fit = pool.members(films, cfg["categories"], cfg["logic"], pool.custom(conn))
    if not fit:
        raise Bad("No films fit the chosen categories. Pick different categories.")
    note = ""
    if cfg["repeat"] != "none" and len(fit) < cfg["rounds"]:
        cfg["rounds"] = len(fit)
        note = f"Only {len(fit)} film{'s' if len(fit) != 1 else ''} fit, so this game has {len(fit)} round{'s' if len(fit) != 1 else ''}."
    conn.execute("UPDATE rl_games SET status='abandoned', updated=? WHERE status='active'", (now,))
    gid = conn.execute("INSERT INTO rl_games(status,config,sides,created,updated) VALUES('active',?,?,?,?)",
                       (json.dumps(dict(cfg, note=note)), json.dumps(sides), now, now)).lastrowid
    remember = {"players": [{"name": n, "team": s["id"]} for s in sides for n in s["players"]] if cfg["mode"] == "teams"
                else [{"name": s["name"]} for s in sides]}
    if cfg["mode"] == "teams":
        remember["teams"] = [{"name": s["name"]} for s in sides]
    store.save(conn, remember)
    conn.commit()
    frames.tidy(cfg_app, set())
    return gid


def get(conn, gid=None):
    if gid:
        g = conn.execute("SELECT * FROM rl_games WHERE id=?", (int(gid),)).fetchone()
    else:
        g = conn.execute("SELECT * FROM rl_games WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
    return g


def need(conn, gid):
    g = get(conn, gid)
    if not g:
        raise Bad("That game is no longer there.")
    if g["status"] != "active":
        raise Bad("That game is over.")
    return g


def _cfg(g):
    return _j(g["config"], {})


def _rounds(conn, g):
    return conn.execute("SELECT * FROM rl_rounds WHERE game_id=? ORDER BY id", (g["id"],)).fetchall()


def current(conn, g):
    r = conn.execute("SELECT * FROM rl_rounds WHERE game_id=? ORDER BY id DESC LIMIT 1", (g["id"],)).fetchone()
    return r if r and r["status"] in OPEN else None


def played(conn, g):
    return conn.execute("SELECT COUNT(*) FROM rl_rounds WHERE game_id=? AND status<>'skipped'", (g["id"],)).fetchone()[0]


# ------------------------------------------------------------------ rounds

def _film_file(m):
    for f in m["files"]:
        if os.path.isfile(f["path"]):
            return f
    return None


def _credits(conn, media_id):
    try:
        r = conn.execute("SELECT credits FROM intros WHERE media_id=?", (media_id,)).fetchone()
    except Exception:
        return 0.0
    return float(r["credits"] or 0) if r else 0.0


def next_round(conn, cfg_app, g, now=None, rng=None, measure_fn=None, grab_fn=None):
    """Close the round that is showing its answer and deal the next one. Ends the game after the last round."""
    now = now or time.time()
    cfg = _cfg(g)
    cur = current(conn, g)
    if cur is not None:
        if cur["status"] != "revealed":
            raise Bad("Finish this round first: reveal the answer or skip the film.")
        conn.execute("UPDATE rl_rounds SET status='closed' WHERE id=?", (cur["id"],))
    if played(conn, g) >= cfg["rounds"]:
        return finish(conn, cfg_app, g, now)
    films = pool.movies(conn)
    sides = _j(g["sides"], [])
    turn = -1 if cfg["mode"] == "party" else played(conn, g) % max(1, len(sides))
    preset = store.preset(cfg)
    for _ in range(6):                       # a film whose file cannot be read is set aside and another is dealt
        try:
            m = pool.pick(conn, films, cfg, g["id"], rng, now)
        except pool.Exhausted as e:
            if e.why == "played" and played(conn, g):
                return finish(conn, cfg_app, g, now, note="The game ended early: every film in these categories has come up.")
            raise
        f = _film_file(m)
        token = secrets.token_urlsafe(18)
        base = (g["id"], played(conn, g) + 1, token, f["id"] if f else m["id"], m["key"], m["title"], m["year"])
        if f is None:
            _put(conn, base, 0, "skipped", turn, 0, {"error": "file missing"}, now)
            continue
        win = frames.window(f["runtime"], cfg, preset, _credits(conn, f["id"]))
        extra = {"win": list(win), "runtime": f["runtime"], "path_id": f["id"], "playable": f["playable"]}
        if cfg["scene"] == "choose":
            rid = _put(conn, base, 0, "pick", turn, preset["timer"], extra, now)
            conn.commit()
            return rid
        t, checked = frames.choose(f["path"], win, preset["choose"], (), rng, measure_fn)
        if (grab_fn or frames.grab)(f["path"], t, frames.file_for(cfg_app, token, 0)):
            extra["checked"] = checked
            rid = _put(conn, base, t, "guess", turn, preset["timer"], extra, now)
            conn.commit()
            return rid
        _put(conn, base, t, "skipped", turn, 0, {"error": "no picture could be read"}, now)
    conn.commit()
    raise Bad("HERO TV could not read a picture from several films in a row. Check that the drive with your movies is connected.")


def _put(conn, base, ts, status, turn, limit, extra, now):
    return conn.execute("INSERT INTO rl_rounds(game_id,number,token,media_id,mkey,title,year,ts,status,turn,time_left,extra,created) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", base + (ts, status, turn, float(limit or 0), json.dumps(extra), int(now))).lastrowid


def _need_round(conn, g, statuses):
    r = current(conn, g)
    if r is None or r["status"] not in statuses:
        raise Bad("That cannot be done at this point in the round.")
    return r


def _file_of(conn, r):
    x = _j(r["extra"], {})
    m = conn.execute("SELECT id,path,runtime_s FROM media WHERE id=?", (x.get("path_id") or r["media_id"],)).fetchone()
    if not m or not os.path.isfile(m["path"]):
        raise Bad("This film's file is no longer there. Skip the film.")
    return m, x


def set_time(conn, cfg_app, g, seconds=None, rng=None, measure_fn=None, grab_fn=None):
    """The chosen moment for a 'pick' round (seconds), or a random one (None)."""
    r = _need_round(conn, g, ("pick",))
    m, x = _file_of(conn, r)
    win = tuple(x.get("win") or (0, 0))
    preset = store.preset(_cfg(g))
    if seconds is None:
        t, _ok = frames.choose(m["path"], win, preset["choose"], (), rng, measure_fn)
    else:
        t = frames.valid(seconds, win, x.get("runtime") or m["runtime_s"] or 0)
    if not (grab_fn or frames.grab)(m["path"], t, frames.file_for(cfg_app, r["token"], 0)):
        raise Bad("No picture could be read at that moment. Try another time, or skip the film.")
    conn.execute("UPDATE rl_rounds SET ts=?, status='guess' WHERE id=?", (t, r["id"]))
    conn.commit()


def left(r, now=None):
    """Seconds still on the clock (None when the round has no time limit)."""
    cfg_limit = r["time_left"]
    if not cfg_limit and not r["running_since"]:
        return None
    if r["running_since"]:
        return max(0.0, r["time_left"] - ((now or time.time()) - r["running_since"]))
    return float(r["time_left"])


def timer(conn, g, action, now=None):
    now = now or time.time()
    r = _need_round(conn, g, ("guess",))
    limit = store.preset(_cfg(g))["timer"]
    if not limit:
        return
    if action in ("start", "resume") and not r["running_since"]:
        conn.execute("UPDATE rl_rounds SET running_since=? WHERE id=?", (now, r["id"]))
    elif action == "pause" and r["running_since"]:
        conn.execute("UPDATE rl_rounds SET time_left=?, running_since=0 WHERE id=?", (left(r, now), r["id"]))
    elif action == "up":
        _settle(conn, g, r, now, force=True)
    conn.commit()


def _settle(conn, g, r, now, force=False):
    """Time ran out: close the guessing (and reveal, unless a last answer is allowed)."""
    if r["status"] != "guess" or not r["running_since"]:
        return False
    rem = left(r, now)
    if rem is None or (rem > (1.0 if force else 0.0)):
        return False
    cfg = _cfg(g)
    status = "timeup" if cfg["after_time"] == "last" else "revealed"
    conn.execute("UPDATE rl_rounds SET status=?, time_left=0.0001, running_since=0 WHERE id=?", (status, r["id"]))
    return True


def _side(g, side):
    sides = _j(g["sides"], [])
    try:
        side = int(side)
    except (TypeError, ValueError):
        raise Bad("Choose who is answering.") from None
    if not any(s["id"] == side for s in sides):
        raise Bad("That player is not in this game.")
    return side


def _points(cfg, r, at_left):
    used = len(_j(r["hints"], []))
    base = cfg["points"][min(used, 3)]
    speed = 0
    limit = store.preset(cfg)["timer"]
    if cfg["speed_bonus"] and limit and at_left:
        speed = int(round(cfg["speed_max"] * max(0.0, min(1.0, at_left / limit))))
    return base, speed, used


def award(conn, g, side, now=None):
    """Give this round to a side. Only once per round: a second press, a retried request or two screens change nothing."""
    now = now or time.time()
    r = _need_round(conn, g, ("guess", "timeup", "revealed"))
    side = _side(g, side)
    if _j(r["win"], {}).get("side"):
        raise Bad("This round has already been given. Undo it first to change who got it.")
    cfg = _cfg(g)
    x = _j(r["extra"], {})
    at_left = left(r, now) if r["status"] == "guess" else x.get("left_at_reveal", 0)
    base, speed, used = _points(cfg, r, at_left or 0)
    try:
        conn.execute("INSERT INTO rl_events(game_id,round_id,side,points,reason,note,key,at) VALUES(?,?,?,?,?,?,?,?)",
                     (g["id"], r["id"], side, base + speed, "correct", f"{used} hint(s)" + (f", +{speed} speed" if speed else ""),
                      f"r{r['id']}:correct", int(now)))
    except Exception:
        conn.rollback()
        raise Bad("This round has already been given.") from None
    conn.execute("UPDATE rl_rounds SET win=? WHERE id=?", (json.dumps({"side": side, "points": base + speed, "base": base, "speed": speed, "hints": used}), r["id"]))
    if r["status"] != "revealed":
        _reveal(conn, r, now)
    conn.commit()


def unaward(conn, g):
    r = _need_round(conn, g, ("revealed",))
    conn.execute("DELETE FROM rl_events WHERE key=?", (f"r{r['id']}:correct",))
    conn.execute("UPDATE rl_rounds SET win='{}' WHERE id=?", (r["id"],))
    conn.commit()


def _others(conn):
    return [m["title"] for m in pool.movies(conn).values()]


def guess(conn, g, text, side=None, now=None):
    """A typed answer. Returns 'correct', 'close' or 'wrong'."""
    now = now or time.time()
    r = _need_round(conn, g, ("guess", "timeup"))
    cfg = _cfg(g)
    if cfg["answers"] == "host":
        raise Bad("This game is set to answers said out loud. The host marks them.")
    sides = _j(g["sides"], [])
    if cfg["mode"] in ("turns", "teams"):
        side = sides[r["turn"] % len(sides)]["id"]
    elif cfg["mode"] == "solo":
        side = sides[0]["id"]
    side = _side(g, side)
    text = " ".join(str(text or "").split())[:120]
    if not text:
        raise Bad("Type the film's name first.")
    alt = conn.execute("SELECT title,year FROM media WHERE id=?", (r["media_id"],)).fetchone()
    alts = [art.clean_movie(alt["title"], alt["year"])[0]] if alt else []
    verdict = answers.check(text, r["title"], _others(conn), cfg["spelling"], alts)
    conn.execute("INSERT INTO rl_guesses(round_id,side,text,verdict,at) VALUES(?,?,?,?,?)", (r["id"], side, text, verdict, int(now)))
    if verdict == "correct":
        conn.commit()
        award(conn, g, side, now)
        return verdict
    if verdict == "wrong":
        _penalty(conn, g, r, side, now)
    if r["status"] == "timeup":               # that was the last answer
        _reveal(conn, r, now)
    conn.commit()
    return verdict


def _penalty(conn, g, r, side, now):
    pen = _cfg(g)["wrong_penalty"]
    if pen:
        n = conn.execute("SELECT COUNT(*) FROM rl_events WHERE round_id=? AND reason='wrong'", (r["id"],)).fetchone()[0]
        conn.execute("INSERT INTO rl_events(game_id,round_id,side,points,reason,note,key,at) VALUES(?,?,?,?,?,?,?,?)",
                     (g["id"], r["id"], side, -pen, "wrong", "", f"r{r['id']}:wrong:{n + 1}", int(now)))


def wrong(conn, g, side, now=None):
    """The host marks an answer said out loud as wrong."""
    now = now or time.time()
    r = _need_round(conn, g, ("guess", "timeup"))
    side = _side(g, side)
    conn.execute("INSERT INTO rl_guesses(round_id,side,text,verdict,at) VALUES(?,?,?,?,?)", (r["id"], side, "", "wrong", int(now)))
    _penalty(conn, g, r, side, now)
    if r["status"] == "timeup":
        _reveal(conn, r, now)
    conn.commit()


def _reveal(conn, r, now):
    x = _j(r["extra"], {})
    x["left_at_reveal"] = left(r, now) or 0
    conn.execute("UPDATE rl_rounds SET status='revealed', running_since=0, time_left=?, extra=? WHERE id=?",
                 (x["left_at_reveal"] or 0.0001, json.dumps(x), r["id"]))


def reveal(conn, g, now=None):
    r = _need_round(conn, g, ("pick", "guess", "timeup"))
    _reveal(conn, r, now or time.time())
    conn.commit()


def skip(conn, g):
    """Throw this film back (a bad picture, a film nobody has seen). It does not count as a round."""
    r = _need_round(conn, g, ("pick", "guess", "timeup"))
    conn.execute("DELETE FROM rl_events WHERE round_id=?", (r["id"],))
    conn.execute("UPDATE rl_rounds SET status='skipped', running_since=0 WHERE id=?", (r["id"],))
    conn.commit()


# ------------------------------------------------------------------ hints

def _safe_series(title, collection):
    words = {w for w in answers.norm(title).split() if len(w) > 2}
    return bool(collection) and not words & set(answers.norm(collection).split())


def hint_ladder(m, kinds, title):
    """The hints this film can give, mildest first: [(kind, text)]. 'frame' has no text (a second picture)."""
    out = []
    words = answers.norm(title).split() if title else []
    for k in kinds:
        if k == "decade" and m and m.get("year"):
            out.append((k, f"It came out in the {pool.decade(m['year'])}s"))
        elif k == "genre" and m and m.get("genres"):
            out.append((k, "Genre: " + ", ".join(m["genres"][:3])))
        elif k == "frame":
            out.append((k, ""))
        elif k == "actor" and m and m.get("cast"):
            out.append((k, "Starring " + m["cast"][0]))
        elif k == "words" and words:
            n = len(str(title).split())
            out.append((k, f"The title has {n} word{'s' if n != 1 else ''}"))
        elif k == "director" and m and m.get("directors"):
            out.append((k, "Directed by " + m["directors"][0]))
        elif k == "letter" and title:
            first = next((ch for ch in str(title) if ch.isalnum()), "")
            if first:
                out.append((k, f"The title starts with {first.upper()}"))
        elif k == "franchise" and m and _safe_series(title, m.get("collection")):
            out.append((k, "Part of: " + m["collection"]))
    return out


def hint(conn, cfg_app, g, rng=None, measure_fn=None, grab_fn=None):
    """Show the next hint. Returns it, or raises when there is none left."""
    r = _need_round(conn, g, ("guess", "timeup"))
    cfg = _cfg(g)
    used = _j(r["hints"], [])
    allowed = store.preset(cfg)["hints"]
    if len(used) >= allowed:
        raise Bad("No hints left in this round." if allowed else "Hints are off in this game.")
    m = pool.movies(conn).get(r["mkey"])
    ladder = [h for h in hint_ladder(m, cfg["hint_kinds"], r["title"]) if h[0] not in {u["kind"] for u in used}]
    while ladder:
        kind, text = ladder.pop(0)
        if kind == "frame":
            try:
                fm, x = _file_of(conn, r)
            except Bad:
                continue
            taken = [r["ts"]] + [u.get("ts", 0) for u in used if u["kind"] == "frame"]
            t, _ok = frames.choose(fm["path"], tuple(x.get("win") or (0, 0)), "any", taken, rng, measure_fn)
            n = 1 + sum(1 for u in used if u["kind"] == "frame")
            if not (grab_fn or frames.grab)(fm["path"], t, frames.file_for(cfg_app, r["token"], n)):
                continue
            used.append({"kind": kind, "text": "Another moment from the film", "ts": t, "n": n})
        else:
            used.append({"kind": kind, "text": text})
        conn.execute("UPDATE rl_rounds SET hints=? WHERE id=?", (json.dumps(used), r["id"]))
        conn.commit()
        return used[-1]
    raise Bad("There are no more hints for this film.")


# ------------------------------------------------------------------ scores

def adjust(conn, g, side, points, nonce, now=None):
    side = _side(g, side)
    try:
        points = int(points)
    except (TypeError, ValueError):
        raise Bad("Points must be a number.") from None
    if not points or abs(points) > 10000:
        raise Bad("Points must be between -10000 and 10000, and not zero.")
    key = f"g{g['id']}:adj:{str(nonce or secrets.token_hex(6))[:40]}"
    try:
        conn.execute("INSERT INTO rl_events(game_id,round_id,side,points,reason,note,key,at) VALUES(?,?,?,?,?,?,?,?)",
                     (g["id"], None, side, points, "adjust", "changed by the host", key, int(now or time.time())))
    except Exception:
        conn.rollback()                       # the same press arriving twice
        return
    conn.commit()


def board(conn, g):
    """Standings, best first. Equal points share a place."""
    sides = _j(g["sides"], [])
    pts, cor = {}, {}
    for e in conn.execute("SELECT side,points,reason FROM rl_events WHERE game_id=?", (g["id"],)):
        pts[e["side"]] = pts.get(e["side"], 0) + e["points"]
        if e["reason"] == "correct":
            cor[e["side"]] = cor.get(e["side"], 0) + 1
    rows = [dict(s, points=int(pts.get(s["id"], 0)), correct=cor.get(s["id"], 0)) for s in sides]
    rows.sort(key=lambda r: (-r["points"], -r["correct"], r["name"].casefold()))
    rank, prev = 0, None
    for i, r in enumerate(rows):
        if prev is None or r["points"] != prev:
            rank, prev = i + 1, r["points"]
        r["rank"] = rank
    for r in rows:
        r["tied"] = sum(1 for o in rows if o["rank"] == r["rank"]) > 1
    return rows


def finish(conn, cfg_app, g, now=None, note="", abandon=False):
    now = int(now or time.time())
    cur = current(conn, g)
    if cur is not None:
        conn.execute("UPDATE rl_rounds SET status=? WHERE id=?", ("closed" if cur["status"] == "revealed" else "skipped", cur["id"]))
    cfg = _cfg(g)
    if note:
        cfg["note"] = note
    conn.execute("UPDATE rl_games SET status=?, finished=?, updated=?, config=? WHERE id=?",
                 ("abandoned" if abandon else "finished", now, now, json.dumps(cfg), g["id"]))
    conn.commit()
    frames.tidy(cfg_app, set())
    return None


# ------------------------------------------------------------------ what the page is sent

def _answer(conn, cfg_app, r):
    m = pool.movies(conn).get(r["mkey"]) or {}
    row = conn.execute("SELECT m.id,m.title,m.year,m.series,m.season,m.episode,m.franchise,m.runtime_s,m.height,m.playable,"
                       "COALESCE(p.position,0) AS position,COALESCE(p.completed,0) AS completed FROM media m "
                       "LEFT JOIN progress p ON p.media_id=m.id WHERE m.id=?", (r["media_id"],)).fetchone()
    out = {"title": r["title"], "year": r["year"], "genres": m.get("genres", [])[:3], "directors": m.get("directors", [])[:2],
           "cast": m.get("cast", [])[:4], "tagline": m.get("tagline", ""), "rating": m.get("rating", 0),
           "minutes": round((row["runtime_s"] if row else 0) / 60), "at": r["ts"], "media_id": r["media_id"] if row else None}
    if row and row["playable"]:
        out["item"] = {k: row[k] for k in ("id", "title", "year", "series", "season", "episode", "franchise", "runtime_s", "height", "position", "completed")}
        out["item"]["title"] = r["title"]
    return out


def view(conn, cfg_app, g, now=None):
    """Everything the game screen needs. The answer is only in here once the round is revealed (or skipped)."""
    now = now or time.time()
    cfg = _cfg(g)
    cur = current(conn, g)
    if cur is not None and g["status"] == "active" and _settle(conn, g, cur, now):
        conn.commit()
        cur = current(conn, g)
    last = conn.execute("SELECT * FROM rl_rounds WHERE game_id=? ORDER BY id DESC LIMIT 1", (g["id"],)).fetchone()
    sides = _j(g["sides"], [])
    preset = store.preset(cfg)
    out = {"id": g["id"], "status": g["status"], "config": cfg, "difficulty": preset, "sides": sides, "board": board(conn, g),
           "played": played(conn, g), "rounds": cfg["rounds"], "note": cfg.get("note", ""), "round": None}
    r = cur or (last if last is not None and last["status"] == "skipped" and g["status"] == "active" else None)
    if r is not None:
        used = _j(r["hints"], [])
        x = _j(r["extra"], {})
        rem = left(r, now)
        rv = {"token": r["token"], "number": r["number"], "status": r["status"],
              "turn": sides[r["turn"] % len(sides)]["id"] if r["turn"] >= 0 and sides else None,
              "frames": ([f"/roulette/frame/{r['token']}-0.jpg"] if r["status"] != "pick" else [])
              + [f"/roulette/frame/{r['token']}-{u['n']}.jpg" for u in used if u["kind"] == "frame"],
              "hints": [u["text"] for u in used], "hints_left": max(0, preset["hints"] - len(used)),
              "timer": {"limit": preset["timer"], "left": rem, "running": bool(r["running_since"])},
              "effect": preset["effect"], "checked": x.get("checked", True),
              "guesses": [{"side": q["side"], "text": q["text"], "verdict": q["verdict"]}
                          for q in conn.execute("SELECT side,text,verdict FROM rl_guesses WHERE round_id=? ORDER BY id", (r["id"],))],
              "win": _j(r["win"], {}), "would_score": _points(cfg, r, rem or 0)[0] if r["status"] in ("guess", "timeup") else 0}
        if r["status"] == "pick":
            rv["pick"] = {"min": (x.get("win") or [0, 0])[0], "max": (x.get("win") or [0, 0])[1], "runtime": x.get("runtime", 0)}
        if cfg["show"] == "clip" and x.get("playable") and r["status"] != "pick":
            rv["clip"] = {"src": f"/media/{x.get('path_id') or r['media_id']}", "start": r["ts"], "seconds": cfg["clip_seconds"]}
        if r["status"] in ("revealed", "skipped"):
            rv["answer"] = _answer(conn, cfg_app, r)
        out["round"] = rv
    out["last_round"] = played(conn, g) >= cfg["rounds"] and (cur is None or cur["status"] == "revealed")
    if g["status"] != "active":
        b = out["board"]
        out["winners"] = [s for s in b if s["rank"] == 1] if b and b[0]["points"] > 0 else []
    return out


def summary(conn, g):
    cfg = _cfg(g)
    b = board(conn, g)
    return {"id": g["id"], "status": g["status"], "mode": cfg.get("mode"), "difficulty": cfg.get("difficulty"), "created": g["created"],
            "finished": g["finished"], "played": played(conn, g), "rounds": cfg.get("rounds"), "board": b,
            "winners": [s["name"] for s in b if s["rank"] == 1 and s["points"] > 0]}


def history(conn, limit=40):
    return [summary(conn, g) for g in conn.execute("SELECT * FROM rl_games WHERE status<>'active' ORDER BY id DESC LIMIT ?", (limit,))
            if played(conn, g)]


def detail(conn, gid):
    g = get(conn, gid)
    if not g:
        raise Bad("That game is no longer there.")
    sides = {s["id"]: s["name"] for s in _j(g["sides"], [])}
    rounds = []
    for r in _rounds(conn, g):
        if r["status"] in OPEN and g["status"] == "active":
            continue                                  # never give away a round that is still being played
        w = _j(r["win"], {})
        rounds.append({"number": r["number"], "title": r["title"], "year": r["year"], "at": r["ts"], "status": r["status"],
                       "winner": sides.get(w.get("side"), ""), "points": w.get("points", 0), "hints": len(_j(r["hints"], []))})
    return dict(summary(conn, g), rounds_list=rounds)
