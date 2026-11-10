"""Playing from a phone: open the address on the TV, type the game's 4-letter code and a name.

A phone that joins is a player in that one game and nothing else: it gets the picture of the round being played, its
own answer box and the scores. It is not a paired HERO TV device and cannot browse or watch the library. The phone
keeps a long random key that links it to its player; the keys are thrown away when a new game starts. Phones are sent exactly what the TV page is sent, so the film's name is never there before the reveal."""
import json
import secrets
import threading
import time

from . import game
from .store import Bad

MAX_SIDES = 12
_tries = {}                     # ip -> [times of wrong codes]: ten wrong codes in five minutes and that phone waits
_lock = threading.Lock()


def _slow(ip, now):
    with _lock:
        t = [x for x in _tries.get(ip, []) if now - x < 300]
        _tries[ip] = t
        return len(t) >= 10


def _miss(ip, now):
    with _lock:
        _tries.setdefault(ip, []).append(now)


def find(conn, code):
    code = "".join(ch for ch in str(code or "").upper() if ch.isalpha())[:8]
    if not code:
        return None
    g = game.get(conn)
    if g is None:
        return None
    cfg = game._cfg(g)
    return g if cfg.get("phones") and cfg.get("code") and secrets.compare_digest(cfg["code"], code) else None


def join(conn, body, ip="", now=None):
    """{code, name, team?} -> {token, side}. A name already in the game takes that player's place; a new name is a new player."""
    now = now or time.time()
    if _slow(ip, now):
        raise Bad("Too many wrong codes. Wait a few minutes and try again.")
    g = find(conn, body.get("code"))
    if g is None:
        _miss(ip, now)
        raise Bad("That code does not match a game. Check the four letters on the TV.")
    name = " ".join(str(body.get("name") or "").split())[:24]
    if not name:
        raise Bad("Type your name.")
    cfg, sides = game._cfg(g), game._j(g["sides"], [])
    taken = {r["side"]: r["name"] for r in conn.execute("SELECT side,name FROM rl_players WHERE game_id=?", (g["id"],))}
    if cfg["mode"] == "teams":
        try:
            side = next(s for s in sides if s["id"] == int(body.get("team") or 0))
        except (StopIteration, TypeError, ValueError):
            return {"teams": [{"id": s["id"], "name": s["name"]} for s in sides]}           # the phone asks which team next
        if name.casefold() not in [p.casefold() for p in side["players"]]:
            for s in sides:
                s["players"] = [p for p in s["players"] if p.casefold() != name.casefold()]
            side["players"].append(name)
    else:
        side = next((s for s in sides if s["name"].casefold() == name.casefold()), None)
        if side is not None and side["id"] in taken:
            raise Bad(f"Someone is already playing as {side['name']}. Pick another name.")
        if side is None:
            free = next((s for s in sides if s["id"] not in taken and s["name"].casefold().startswith("player ")), None)
            if free is not None:                       # an unnamed seat made on the TV: take it over
                free["name"], side = name, free
            elif len(sides) >= MAX_SIDES:
                raise Bad("This game is full.")
            else:
                side = {"id": max(s["id"] for s in sides) + 1, "name": name, "players": [],
                        "color": game.SIDE_COLORS[len(sides) % len(game.SIDE_COLORS)]}
                sides.append(side)
    token = secrets.token_urlsafe(24)
    conn.execute("UPDATE rl_games SET sides=?, updated=? WHERE id=?", (json.dumps(sides), int(now), g["id"]))
    conn.execute("INSERT INTO rl_players(token,game_id,side,name,joined) VALUES(?,?,?,?,?)", (token, g["id"], side["id"], name, int(now)))
    conn.commit()
    return {"token": token, "side": side["id"], "name": name}


def player(conn, token):
    """(game row, player row) for a phone's key, or raises. A key from an earlier game no longer works."""
    p = conn.execute("SELECT * FROM rl_players WHERE token=?", (str(token or "")[:80],)).fetchone() if token else None
    g = game.get(conn, p["game_id"]) if p else None
    if p is None or g is None:
        raise Bad("That game is over. Ask for the new code.")
    return g, p


def state(conn, cfg_app, token, now=None):
    """What the phone shows: the round (as the TV sees it), the scores and what this player may do."""
    g, p = player(conn, token)
    v = game.view(conn, cfg_app, g, now)
    cfg, r = v["config"], v["round"]
    me = next((s for s in v["sides"] if s["id"] == p["side"]), None)
    out = {"status": v["status"], "name": p["name"], "side": p["side"], "side_name": me["name"] if me else p["name"],
           "color": me["color"] if me else "#ffcf1f", "board": v["board"], "played": v["played"], "rounds": v["rounds"],
           "answers": cfg["answers"], "mode": cfg["mode"], "winners": [w["name"] for w in v.get("winners", [])], "round": None}
    if r:
        turn = r["turn"]
        can = r["status"] in ("guess", "timeup") and cfg["answers"] != "host" and (turn is None or turn == p["side"]) and p["side"] not in r["out"]
        out["round"] = {"number": r["number"], "status": r["status"], "hints": r["hints"], "timer": r["timer"],
                        "frames": ["/play/frame/" + f.rsplit("/", 1)[1] for f in r["frames"]], "choices": r.get("choices"),
                        "turn": next((s["name"] for s in v["sides"] if s["id"] == turn), None), "my_turn": turn is None or turn == p["side"],
                        "can": can, "out": p["side"] in r["out"], "win": r["win"], "won_by": next((s["name"] for s in v["sides"] if s["id"] == r["win"].get("side")), ""),
                        "answer": {k: r["answer"][k] for k in ("title", "year", "genres")} if r.get("answer") else None}
    return out


def answer(conn, cfg_app, body):
    g, p = player(conn, body.get("token"))
    if g["status"] != "active":
        raise Bad("That game is over.")
    if "choice" in body:
        verdict = game.choose(conn, g, body.get("choice"), p["side"], strict=True)
    else:
        verdict = game.guess(conn, g, body.get("text"), p["side"], strict=True)
    return {"verdict": verdict, "state": state(conn, cfg_app, body.get("token"))}


def frame_path(conn, cfg_app, name, token):
    """A round's picture for a phone in that game (the name must belong to the round being played)."""
    from . import api
    try:
        g, _p = player(conn, token)
    except Bad:
        return None
    r = game.current(conn, g)
    if r is None or not name.startswith(r["token"] + "-"):
        return None
    return api.frame_path(cfg_app, name)


def count(conn, gid):
    return [{"side": r["side"], "name": r["name"]} for r in conn.execute("SELECT side,name FROM rl_players WHERE game_id=? ORDER BY joined", (gid,))]


def handle(conn, cfg_app, p, q, method, body=None, ip=""):
    """/api/party/...: join, state, answer. Open to the home network; everything needs the game's code or a player's key."""
    from . import store
    store.ensure(conn)
    if method == "GET" and p == "state":
        return state(conn, cfg_app, q.get("t")), 200
    if method == "POST" and p == "join":
        return join(conn, body or {}, ip), 200
    if method == "POST" and p == "answer":
        from .api import _lock as L
        with L:
            return answer(conn, cfg_app, body or {}), 200
    return {"error": "not found"}, 404
