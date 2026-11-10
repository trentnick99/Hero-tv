"""Which films can come up, and the categories they fall into.

A film is what HERO TV's library calls a film: not an episode, long enough, on the disk. Two copies of one film (1080p
and 4K, say) are one film here, known by the same key HERO TV uses for its poster and details, so nothing is stored
twice. Categories are worked out from that film list each time, so they are always current and an empty one never
shows."""
import json
import random
import re
import time

from .. import art, scheduler
from .store import Bad

MIN_MATCHED_S = 20 * 60        # a matched film shorter than this is an extra or a short
MIN_UNMATCHED_S = 60 * 60      # with no TMDB match, only a full-length file is taken for a film
PEOPLE_MIN = 2                 # an actor, director or studio becomes a category with this many films
KINDS = [("channel", "Channels"), ("genre", "Genres"), ("decade", "Decades"), ("collection", "Film series"),
         ("studio", "Studios"), ("director", "Directors"), ("actor", "Actors")]
_rng = random.SystemRandom()


def _json(text, default):
    try:
        v = json.loads(text or "")
    except (TypeError, ValueError):
        return default
    return v if isinstance(v, type(default)) else default


def movies(conn):
    """Every film that can be played, one entry per film, best copy first."""
    arts = {r["key"]: r for r in conn.execute("SELECT * FROM art WHERE miss=0 AND kind='movie'")}
    shows = {r["key"] for r in conn.execute("SELECT key FROM art WHERE miss=0 AND kind='tv'")}
    chans = []
    for ch in conn.execute("SELECT id,name,number,rules,kind FROM channels ORDER BY number"):
        rules = _json(ch["rules"], {})
        if (ch["kind"] or "tv") == "tv" and (rules.get("franchise") or rules.get("tags") or rules.get("_also")):
            chans.append((ch["id"], ch["name"], rules))
    out = {}
    for r in conn.execute("SELECT id,path,title,year,franchise,series,season,episode,tags,runtime_s,playable,height,size "
                          "FROM media WHERE available=1 AND verified=1 AND runtime_s>0 ORDER BY id"):
        if art.show_of(r):
            continue
        k, _kind, title, year = art.key_for(r)
        a = arts.get(k)
        run = r["runtime_s"] or 0
        if a is None:
            if run < MIN_UNMATCHED_S or ("s:" + art.norm(art._alias(art.clean_show(r["franchise"] or "")[0]))) in shows:
                continue              # an unnumbered episode in a show's folder, or something too short to call a film
        elif run < MIN_MATCHED_S:
            continue
        m = out.get(k)
        if m is None:
            facts = _json(a["facts"], {}) if a else {}
            m = out[k] = {"key": k, "title": (a["title"] if a else "") or title, "year": (a["year"] if a else None) or year,
                          "matched": bool(a), "genres": _json(a["genres"], []) if a else [], "cast": _json(a["cast"], []) if a else [],
                          "directors": [d for d in facts.get("directors") or [] if d], "companies": [c for c in facts.get("companies") or [] if c],
                          "collection": facts.get("collection") or "", "tagline": (a["tagline"] if a else "") or "",
                          "rating": (a["rating"] if a else 0) or 0, "channels": [], "files": []}
        m["files"].append({"id": r["id"], "path": r["path"], "runtime": run, "playable": bool(r["playable"]), "height": r["height"] or 0})
        for cid, name, rules in chans:
            if (cid, name) not in m["channels"] and scheduler.matches(rules, r):
                m["channels"].append((cid, name))
    for m in out.values():
        m["files"].sort(key=lambda f: (-f["playable"], -f["height"], f["id"]))
        m["id"], m["runtime"] = m["files"][0]["id"], m["files"][0]["runtime"]
    return out


def decade(year):
    return (int(year) // 10) * 10 if year else None


def keys_of(m):
    """Every automatic category this film belongs to."""
    out = [f"channel:{cid}" for cid, _ in m["channels"]]
    out += [f"genre:{g}" for g in m["genres"]]
    if m["year"]:
        out.append(f"decade:{decade(m['year'])}")
    if m["collection"]:
        out.append(f"collection:{m['collection']}")
    out += [f"studio:{c}" for c in m["companies"]]
    out += [f"director:{d}" for d in m["directors"]]
    out += [f"actor:{a}" for a in m["cast"]]
    return out


def _label(key, m):
    kind, name = key.split(":", 1)
    if kind == "channel":
        return next((n for cid, n in m["channels"] if cid == name), name)
    if kind == "decade":
        return name + "s"
    if kind == "collection":
        return re.sub(r"\s+Collection$", "", name)
    return name


def custom(conn):
    out = []
    for r in conn.execute("SELECT id,name,rules FROM rl_categories ORDER BY name COLLATE NOCASE"):
        rules = _json(r["rules"], {})
        out.append({"id": r["id"], "key": f"custom:{r['id']}", "name": r["name"],
                    "keys": [k for k in rules.get("keys") or [] if isinstance(k, str) and not k.startswith("custom:")],
                    "logic": "all" if rules.get("logic") == "all" else "any"})
    return out


def members(films, keys, logic="any", customs=()):
    """The film keys that fit the chosen categories (any = in at least one, all = in every one). No categories = every film."""
    keys = [k for k in keys or [] if isinstance(k, str)]
    if not keys:
        return set(films)
    by = {}
    for m in films.values():
        for k in keys_of(m):
            by.setdefault(k, set()).add(m["key"])
    cust = {c["key"]: c for c in customs}
    sets = []
    for k in keys:
        if k in cust:
            sets.append(members(films, cust[k]["keys"], cust[k]["logic"]) if cust[k]["keys"] else set())
        else:
            sets.append(by.get(k, set()))
    return set.intersection(*sets) if logic == "all" else set.union(*sets)


def categories(conn, films=None):
    """The category picker: groups of {key, name, count}, most films first, empty ones left out."""
    films = movies(conn) if films is None else films
    count, label = {}, {}
    for m in films.values():
        for k in keys_of(m):
            count[k] = count.get(k, 0) + 1
            label.setdefault(k, _label(k, m))
    groups = []
    for kind, title in KINDS:
        least = PEOPLE_MIN if kind in ("studio", "director", "actor") else 1
        items = [{"key": k, "name": label[k], "count": n} for k, n in count.items() if k.startswith(kind + ":") and n >= least]
        items.sort(key=(lambda x: x["name"]) if kind == "decade" else (lambda x: (-x["count"], x["name"].casefold())))
        if items:
            groups.append({"kind": kind, "title": title, "items": items})
    customs = custom(conn)
    mine = [dict(c, count=len(members(films, [c["key"]], "any", customs))) for c in customs]
    return {"total": len(films), "groups": groups, "custom": mine}


def category_op(conn, body):
    """Make, rename, change or delete one of your own categories."""
    op = body.get("op")
    name = " ".join(str(body.get("name") or "").split())[:40]
    rules = {"keys": [str(k)[:120] for k in body.get("keys") or [] if isinstance(k, str) and not str(k).startswith("custom:")][:60],
             "logic": "all" if body.get("logic") == "all" else "any"}
    try:
        cid = int(body.get("id") or 0)
    except (TypeError, ValueError):
        raise Bad("that category does not exist") from None
    if op in ("rename", "update", "delete") and not conn.execute("SELECT 1 FROM rl_categories WHERE id=?", (cid,)).fetchone():
        raise Bad("that category does not exist")
    if op in ("create", "rename") or (op == "update" and name):
        if not name:
            raise Bad("give the category a name")
        if conn.execute("SELECT 1 FROM rl_categories WHERE name=? COLLATE NOCASE AND id<>?", (name, cid)).fetchone():
            raise Bad(f"there is already a category called {name}")
    if op == "create":
        if not rules["keys"]:
            raise Bad("choose at least one category to put in it")
        cid = conn.execute("INSERT INTO rl_categories(name,rules,created) VALUES(?,?,?)", (name, json.dumps(rules), int(time.time()))).lastrowid
    elif op == "rename":
        conn.execute("UPDATE rl_categories SET name=? WHERE id=?", (name, cid))
    elif op == "update":
        if not rules["keys"]:
            raise Bad("choose at least one category to put in it")
        conn.execute("UPDATE rl_categories SET rules=? WHERE id=?", (json.dumps(rules), cid))
        if name:
            conn.execute("UPDATE rl_categories SET name=? WHERE id=?", (name, cid))
    elif op == "delete":
        conn.execute("DELETE FROM rl_categories WHERE id=?", (cid,))
    else:
        raise Bad("unknown category action")
    conn.commit()
    return cid


def blocked(conn, game_id, policy, now=None):
    """Film keys the repeat rule keeps out. A film never comes up twice in one game, whatever the wider rule."""
    out = {r[0] for r in conn.execute("SELECT mkey FROM rl_rounds WHERE game_id=?", (game_id,))}
    if policy == "days30":
        since = int((now or time.time()) - 30 * 86400)
        out |= {r[0] for r in conn.execute("SELECT mkey FROM rl_rounds WHERE created>=? AND status<>'skipped'", (since,))}
    return out


class Exhausted(Bad):
    def __init__(self, message, why):
        super().__init__(message)
        self.why = why


def pick(conn, films, cfg, game_id, rng=None, now=None):
    """One film, every eligible film equally likely. Raises Exhausted with the reason when none is left."""
    fit = members(films, cfg["categories"], cfg["logic"], custom(conn))
    if not fit:
        raise Exhausted("No films fit the chosen categories.", "empty")
    in_game = {r[0] for r in conn.execute("SELECT mkey FROM rl_rounds WHERE game_id=?", (game_id,))}
    left = sorted(fit - blocked(conn, game_id, cfg["repeat"], now))
    if not left:                                   # the 30-day rule ran dry: fall back to "not in this game" before giving up
        left = sorted(fit - in_game)
    if not left:
        if cfg["repeat"] == "none":                # repeats are allowed: start round the list again
            left = sorted(fit)
        else:
            raise Exhausted(f"All {len(fit)} films in these categories have come up in this game.", "played")
    return films[(rng or _rng).choice(left)]
