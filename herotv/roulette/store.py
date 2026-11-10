"""Tables and settings for Movie Roulette. Everything lives in HERO TV's own database; nothing here touches the
media, art or progress tables."""
import copy
import json

SCHEMA = """
CREATE TABLE IF NOT EXISTS rl_games(id INTEGER PRIMARY KEY, status TEXT DEFAULT 'active', config TEXT DEFAULT '{}',
 sides TEXT DEFAULT '[]', created INTEGER, updated INTEGER, finished INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS rl_rounds(id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL, number INTEGER NOT NULL, token TEXT UNIQUE NOT NULL,
 media_id INTEGER, mkey TEXT DEFAULT '', title TEXT DEFAULT '', year INTEGER, ts REAL DEFAULT 0, status TEXT DEFAULT 'guess',
 turn INTEGER DEFAULT 0, hints TEXT DEFAULT '[]', time_left REAL DEFAULT 0, running_since REAL DEFAULT 0, win TEXT DEFAULT '{}',
 extra TEXT DEFAULT '{}', created INTEGER);
CREATE INDEX IF NOT EXISTS rl_rounds_game ON rl_rounds(game_id, number);
CREATE TABLE IF NOT EXISTS rl_guesses(id INTEGER PRIMARY KEY, round_id INTEGER NOT NULL, side INTEGER, text TEXT DEFAULT '',
 verdict TEXT DEFAULT '', at INTEGER);
CREATE TABLE IF NOT EXISTS rl_events(id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL, round_id INTEGER, side INTEGER NOT NULL,
 points REAL NOT NULL, reason TEXT DEFAULT '', note TEXT DEFAULT '', key TEXT UNIQUE NOT NULL, at INTEGER);
CREATE TABLE IF NOT EXISTS rl_players(token TEXT PRIMARY KEY, game_id INTEGER NOT NULL, side INTEGER NOT NULL, name TEXT DEFAULT '', joined INTEGER);
CREATE TABLE IF NOT EXISTS rl_categories(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, rules TEXT DEFAULT '{}', created INTEGER);
"""

MODES = {"solo": "Solo", "turns": "Take turns", "teams": "Teams", "party": "Party"}
DIFFICULTIES = {
    # seconds to guess, hints allowed, the part of the film scenes come from, how the picture is chosen, picture effect
    "easy": {"name": "Easy", "timer": 60, "hints": 3, "from": 15, "to": 85, "choose": "clear", "effect": "none"},
    "normal": {"name": "Normal", "timer": 45, "hints": 3, "from": 5, "to": 95, "choose": "any", "effect": "none"},
    "hard": {"name": "Hard", "timer": 30, "hints": 2, "from": 0, "to": 100, "choose": "plain", "effect": "none"},
    "expert": {"name": "Expert", "timer": 20, "hints": 1, "from": 0, "to": 100, "choose": "plain", "effect": "zoom"},
}
HINT_KINDS = ["decade", "genre", "frame", "actor", "words", "director", "letter", "franchise"]
ACTIONS = {"timer": " ", "reveal": "r", "next": "n", "hint": "h", "correct": "c", "wrong": "x", "skip": "s"}

DEFAULTS = {
    "mode": "solo", "rounds": 10, "difficulty": "normal",
    "timer": "auto",                 # "auto" = from the difficulty, 0 = no limit, or seconds
    "hints": True, "hint_kinds": list(HINT_KINDS),
    "points": [100, 75, 50, 25],     # correct with 0, 1, 2, 3 (or more) hints
    "speed_bonus": False, "speed_max": 50, "wrong_penalty": 0,
    "answers": "both",               # both | typed | host | choice (pick one of four titles)
    "phones": True,                  # players may join on their phones with the game's code (needs Settings > Other devices on)
    "spelling": True,                # small spelling mistakes still count
    "scene": "random",               # random | choose (pick the moment yourself, without seeing it)
    "show": "still", "clip_seconds": 15,
    "effect": "auto",                # auto (from the difficulty) | none | blur | zoom
    "after_time": "reveal",          # reveal | last (one last answer, then the host reveals)
    "repeat": "days30",              # game | days30 | none
    "categories": [], "logic": "any",
    "skip_open": 180, "skip_end": 600,
    "sounds": True, "animations": True, "fullscreen": False,
    "keys": dict(ACTIONS),
    "players": [], "teams": [],      # who played last, offered again
}


class Bad(ValueError):
    """A request that cannot be done; the message is shown to the player as it is."""


def ensure(conn):
    conn.executescript(SCHEMA)


def _int(v, lo, hi, what):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise Bad(f"{what} must be a number") from None
    if not lo <= n <= hi:
        raise Bad(f"{what} must be between {lo} and {hi}")
    return n


def _one(v, allowed, what):
    if v not in allowed:
        raise Bad(f"{what} must be one of: {', '.join(str(a) for a in allowed)}")
    return v


def clean(patch, base=None):
    """base with the valid parts of patch applied. Unknown names are refused, so a typing mistake never passes silently."""
    out = copy.deepcopy(base if base is not None else DEFAULTS)
    if not isinstance(patch, dict):
        raise Bad("settings must be a set of names and values")
    for k, v in patch.items():
        if k not in DEFAULTS:
            raise Bad(f"unknown setting: {k}")
        if k == "mode":
            out[k] = _one(v, MODES, "mode")
        elif k == "rounds":
            out[k] = _int(v, 1, 50, "rounds")
        elif k == "difficulty":
            out[k] = _one(v, DIFFICULTIES, "difficulty")
        elif k == "timer":
            out[k] = "auto" if v == "auto" else _int(v, 0, 600, "timer")
        elif k in ("hints", "speed_bonus", "spelling", "sounds", "animations", "fullscreen", "phones"):
            out[k] = bool(v)
        elif k == "hint_kinds":
            if not isinstance(v, list):
                raise Bad("hint_kinds must be a list")
            out[k] = [h for h in HINT_KINDS if h in v]
        elif k == "points":
            if not isinstance(v, list) or len(v) != 4:
                raise Bad("points needs four numbers: no hints, one, two, three hints")
            out[k] = [_int(x, 0, 10000, "points") for x in v]
        elif k == "speed_max":
            out[k] = _int(v, 0, 10000, "speed bonus")
        elif k == "wrong_penalty":
            out[k] = _int(v, 0, 10000, "wrong-answer penalty")
        elif k == "answers":
            out[k] = _one(v, ("both", "typed", "host", "choice"), "answers")
        elif k == "scene":
            out[k] = _one(v, ("random", "choose"), "scene")
        elif k == "show":
            out[k] = _one(v, ("still", "clip"), "show")
        elif k == "clip_seconds":
            out[k] = _int(v, 5, 120, "clip length")
        elif k == "effect":
            out[k] = _one(v, ("auto", "none", "blur", "zoom"), "effect")
        elif k == "after_time":
            out[k] = _one(v, ("reveal", "last"), "after_time")
        elif k == "repeat":
            out[k] = _one(v, ("game", "days30", "none"), "repeat")
        elif k == "categories":
            if not isinstance(v, list):
                raise Bad("categories must be a list")
            out[k] = [str(x)[:120] for x in v][:60]
        elif k == "logic":
            out[k] = _one(v, ("any", "all"), "logic")
        elif k in ("skip_open", "skip_end"):
            out[k] = _int(v, 0, 3600, k)
        elif k == "keys":
            if not isinstance(v, dict):
                raise Bad("keys must be a set of names and keys")
            keys = dict(ACTIONS)
            for a, key in v.items():
                if a in ACTIONS and isinstance(key, str) and 1 <= len(key) <= 12 and key not in ("Escape", "Enter", "Tab"):
                    keys[a] = key if len(key) > 1 else key.lower()
            if len(set(keys.values())) != len(keys):
                raise Bad("two actions cannot share one key")
            out[k] = keys
        elif k in ("players", "teams"):
            out[k] = names(v, 12 if k == "players" else 6)
    return out


def names(v, most):
    """Player or team entries as given by the page: [{name, team?}] with tidy, unique, non-empty names."""
    if not isinstance(v, list):
        raise Bad("players must be a list")
    out, seen = [], set()
    for x in v[:most]:
        d = {"name": x} if isinstance(x, str) else dict(x) if isinstance(x, dict) else {}
        n = " ".join(str(d.get("name") or "").split())[:24]
        if not n or n.casefold() in seen:
            continue
        seen.add(n.casefold())
        e = {"name": n}
        if d.get("team") not in (None, ""):
            try:
                e["team"] = int(d["team"])
            except (TypeError, ValueError):
                pass
        out.append(e)
    return out


def load(conn):
    r = conn.execute("SELECT value FROM prefs WHERE key='rl_settings'").fetchone()
    try:
        saved = json.loads(r["value"]) if r else {}
    except ValueError:
        saved = {}
    out = copy.deepcopy(DEFAULTS)
    for k, v in (saved if isinstance(saved, dict) else {}).items():      # one bad stored value never loses the others
        try:
            out = clean({k: v}, out)
        except Bad:
            pass
    return out


def save(conn, patch):
    s = clean(patch, load(conn))
    conn.execute("INSERT OR REPLACE INTO prefs(key,value) VALUES('rl_settings',?)", (json.dumps(s),))
    conn.commit()
    return s


def preset(cfg):
    """The difficulty's numbers with this game's own choices applied."""
    p = dict(DIFFICULTIES[cfg["difficulty"]])
    if cfg["timer"] != "auto":
        p["timer"] = cfg["timer"]
    if cfg["effect"] != "auto":
        p["effect"] = cfg["effect"]
    if not cfg["hints"]:
        p["hints"] = 0
    return p
