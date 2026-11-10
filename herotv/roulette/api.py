"""The /api/roulette/... requests (this PC only: they are not on the list a paired phone may use)."""
import os
import threading

from .. import tools
from . import frames, game, pool, store
from .store import Bad

_lock = threading.Lock()          # one change at a time: two presses of Next never deal two rounds


def home(conn, cfg_app):
    films = pool.movies(conn)
    g = game.get(conn)
    return {"settings": store.load(conn), "films": len(films), "matched": sum(1 for m in films.values() if m["matched"]),
            "tools": bool(tools.find_tool("ffmpeg")), "active": game.summary(conn, g) if g else None,
            "history": len(game.history(conn, 200)), "modes": store.MODES,
            "difficulties": {k: {"name": v["name"], "timer": v["timer"], "hints": v["hints"]} for k, v in store.DIFFICULTIES.items()},
            "hint_kinds": store.HINT_KINDS, "actions": store.ACTIONS, "lan": __import__("herotv.remote", fromlist=["x"]).enabled()}


def _join(conn, cfg_app, g):
    """How phones get into this game: the code, the address to open and its QR picture."""
    from .. import qr, remote as R
    from . import phone
    cfg = game._cfg(g)
    if not cfg.get("phones") or not cfg.get("code"):
        return None
    on = R.enabled()
    addrs = R.lan_addresses() if on else []
    url = f"http://{addrs[0]}:{R.lan_port(cfg_app)}/play" if addrs else ""
    pic = ""
    if url:
        try:
            pic = qr.svg(url + "?c=" + cfg["code"], scale=6)
        except ValueError:
            pic = ""
    return {"code": cfg["code"], "on": on, "url": url, "qr": pic, "players": phone.count(conn, g["id"])}


def _view(conn, cfg_app, g):
    v = game.view(conn, cfg_app, g)
    v["join"] = _join(conn, cfg_app, g) if g["status"] == "active" else None
    return v


def handle(conn, cfg_app, p, q, method, body=None):
    """(answer, status). p is the part after /api/roulette/."""
    store.ensure(conn)
    if method == "GET":
        if p in ("", "home"):
            return home(conn, cfg_app), 200
        if p == "categories":
            return pool.categories(conn), 200
        if p == "count":
            films = pool.movies(conn)
            keys = [k for k in q.get("keys", "").split("|") if k]
            return {"count": len(pool.members(films, keys, q.get("logic", "any"), pool.custom(conn))), "total": len(films)}, 200
        if p == "game":
            g = game.get(conn, q.get("id"))
            return ({"game": _view(conn, cfg_app, g)} if g else {"game": None}), 200
        if p == "history":
            return {"games": game.history(conn)}, 200
        if p.startswith("history/"):
            return game.detail(conn, p.split("/", 1)[1]), 200
        return {"error": "not found"}, 404
    body = body or {}
    with _lock:
        if p == "settings":
            return {"settings": store.save(conn, body)}, 200
        if p == "categories":
            cid = pool.category_op(conn, body)
            return dict(pool.categories(conn), id=cid), 200
        if p == "new":
            gid = game.create(conn, cfg_app, body)
            g = game.get(conn, gid)
            from .. import remote as R
            if not (body.get("lobby") and game._cfg(g).get("phones") and R.enabled()):       # with phones, the TV waits in the lobby for players first
                game.next_round(conn, cfg_app, g)
            return {"game": _view(conn, cfg_app, game.get(conn, gid))}, 200
        if p == "act":
            g = game.need(conn, body.get("game"))
            op = body.get("op")
            out = {}
            if op == "next":
                game.next_round(conn, cfg_app, g)
            elif op == "time":
                game.set_time(conn, cfg_app, g, body.get("seconds"))
            elif op == "timer":
                game.timer(conn, g, body.get("do"))
            elif op == "guess":
                out["verdict"] = game.guess(conn, g, body.get("text"), body.get("side"))
            elif op == "choose":
                out["verdict"] = game.choose(conn, g, body.get("choice"), body.get("side"))
            elif op == "correct":
                game.award(conn, g, body.get("side"))
            elif op == "wrong":
                game.wrong(conn, g, body.get("side"))
            elif op == "undo":
                game.unaward(conn, g)
            elif op == "hint":
                out["hint"] = game.hint(conn, cfg_app, g)
            elif op == "reveal":
                game.reveal(conn, g)
            elif op == "skip":
                game.skip(conn, g)
            elif op == "adjust":
                game.adjust(conn, g, body.get("side"), body.get("points"), body.get("nonce"))
            elif op == "finish":
                game.finish(conn, cfg_app, g, abandon=not game.played(conn, g))
            else:
                raise Bad("unknown game action")
            return dict(out, game=_view(conn, cfg_app, game.get(conn, g["id"]))), 200
    return {"error": "not found"}, 404


def frame_path(cfg_app, name):
    """The file for /roulette/frame/<token>-<n>.jpg, or None. Only names made of the token alphabet reach the disk."""
    if not name.endswith(".jpg"):
        return None
    stem = name[:-4]
    if not stem or any(not (ch.isalnum() or ch in "-_") for ch in stem):
        return None
    f = os.path.join(frames.folder(cfg_app), stem + ".jpg")
    return f if os.path.isfile(f) else None
