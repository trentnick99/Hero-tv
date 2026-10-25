"""Things HERO TV can tell you about your library: episodes you are missing (from TMDB's season lists), videos you
have twice, and which channel a new episode belongs on because you already have that show."""
import json
import os
import re
import time

from . import art, library

SEASONS_MAX_AGE = 7 * 86400          # shows keep airing: refresh TMDB's season list weekly


# ---------- new episodes follow their show ----------
def series_channels(conn, channels, stem):
    """Channels a new episode belongs on because earlier episodes of the same show are already on them."""
    g = library._guess([stem], stem)
    if not g["series"] or not g["episode"]:
        return []
    want = _n(g["series"])
    folders = set()
    for r in conn.execute("SELECT DISTINCT series,franchise FROM media WHERE available=1 AND series<>'' AND franchise<>''"):
        if _n(r["series"]) == want:
            folders.add(r["franchise"].lower())
    if not folders:
        return []
    return [c for c in sorted(channels, key=lambda x: x.get("number", 0)) if not c.get("off") and
            any(f.lower() in folders for f in (c.get("match") or {}).get("franchise", []))]


def _n(s):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).split())


# ---------- missing episodes ----------
def _season_list(conn, cfg, series, key=None, fj=None, now=None):
    """{season: aired episode count} for a show, from TMDB (remembered for a week). None = unknown/no key/offline."""
    now = now or time.time()
    k = "s:" + art.norm(series)
    a = conn.execute("SELECT tmdb_id,miss,facts FROM art WHERE key=?", (k,)).fetchone()
    if a and a["miss"]:
        return None
    facts = json.loads(a["facts"] or "{}") if a else {}
    if facts.get("seasons") and now - facts.get("seasons_at", 0) < SEASONS_MAX_AGE:
        return {int(s): n for s, n in facts["seasons"].items()}
    key = key or art.api_key()
    if not key:
        return {int(s): n for s, n in facts["seasons"].items()} if facts.get("seasons") else None
    fj = fj or art.fetch_json
    try:
        if not a or not a["tmdb_id"]:
            data = art.lookup("tv", series, None, key, fj)
            art.save(conn, k, data, cfg)
            if not data:
                return None
            tid, facts = data["tmdb_id"], dict(data.get("facts") or {})
        else:
            tid = a["tmdb_id"]
        d = fj(f"/tv/{tid}", {"language": "en-US"}, key)
    except Exception:
        return {int(s): n for s, n in facts["seasons"].items()} if facts.get("seasons") else None
    last = d.get("last_episode_to_air") or {}
    ls, le = int(last.get("season_number") or 0), int(last.get("episode_number") or 0)
    seasons = {}
    for s in d.get("seasons") or []:
        n, cnt = int(s.get("season_number") or 0), int(s.get("episode_count") or 0)
        if n <= 0 or cnt <= 0:
            continue                                  # season 0 = specials: not expected
        if ls and n > ls:
            continue                                  # not on air yet
        if ls and n == ls and le:
            cnt = min(cnt, le)                        # the season that is airing now: only what has aired
        seasons[n] = cnt
    facts.update(seasons={str(s): n for s, n in seasons.items()}, seasons_at=int(now))
    conn.execute("UPDATE art SET facts=? WHERE key=?", (json.dumps(facts), k))
    conn.commit()
    return seasons


def missing(conn, cfg, series, key=None, fj=None, now=None):
    """What you have of a show against what has aired. None when TMDB does not know it (or no key/offline)."""
    seasons = _season_list(conn, cfg, series, key, fj, now)
    if not seasons:
        return None
    want = _n(series)
    have = set()
    for r in conn.execute("SELECT series,season,episode FROM media WHERE available=1 AND series<>''"):
        if _n(r["series"]) == want and r["episode"]:
            have.add((r["season"] or 0, r["episode"]))
    out = []
    if have and all(s == 0 for s, _e in have):                  # numbered 1, 2, 3... across the whole show
        eps = {e for _s, e in have}
        total = sum(seasons.values())
        gone = [e for e in range(1, total + 1) if e not in eps]
        out.append({"season": 0, "aired": total, "have": total - len(gone), "missing": gone})
    else:
        for s in sorted(seasons):
            gone = [e for e in range(1, seasons[s] + 1) if (s, e) not in have]
            out.append({"season": s, "aired": seasons[s], "have": seasons[s] - len(gone), "missing": gone})
    return {"series": series, "seasons": out, "missing": sum(len(x["missing"]) for x in out),
            "aired": sum(x["aired"] for x in out)}


def describe_missing(m):
    """'Season 1: 5, 7  ·  Season 3: all 10' - short enough for one line."""
    parts = []
    for s in m["seasons"]:
        if not s["missing"]:
            continue
        head = f"Season {s['season']}: " if s["season"] else "Episodes "
        if len(s["missing"]) == s["aired"]:
            parts.append(head + f"all {s['aired']}")
        else:
            parts.append(head + _ranges(s["missing"]))
    return "  ·  ".join(parts)


def _ranges(nums):
    out, start, prev = [], None, None
    for n in nums + [None]:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = n
    return ", ".join(out)


# ---------- the same video twice ----------
def duplicates(conn):
    """Groups of files that are the same film (title + year) or the same episode (show + season + episode).
    The best copy (plays here, then biggest) comes first and is marked keep."""
    groups = {}
    for r in conn.execute("SELECT id,path,title,year,series,season,episode,size,playable,verified,runtime_s FROM media WHERE available=1"):
        if r["series"] and r["episode"]:
            k = ("e", _n(r["series"]), r["season"] or 0, r["episode"])
            name = f"{r['series']}  S{r['season'] or 0}E{r['episode']}"
        elif not r["series"] and r["year"]:
            k = ("m", _n(r["title"]), r["year"])
            name = f"{r['title']} ({r['year']})"
        else:
            continue                                  # no year: too easy to mistake two different films
        groups.setdefault(k, {"name": name, "copies": []})["copies"].append(r)
    out = []
    for g in groups.values():
        if len(g["copies"]) < 2:
            continue
        mins = [c["runtime_s"] for c in g["copies"] if c["runtime_s"]]
        if len(mins) > 1 and max(mins) > 1.5 * min(mins):
            continue                                  # very different lengths: an extended cut or a different film
        cs = sorted(g["copies"], key=lambda c: (-(c["playable"] and c["verified"]), -(c["size"] or 0)))
        out.append({"name": g["name"], "copies": [
            {"id": c["id"], "file": os.path.basename(c["path"]), "folder": os.path.basename(os.path.dirname(c["path"])),
             "size": c["size"] or 0, "plays": bool(c["playable"] and c["verified"]), "keep": i == 0} for i, c in enumerate(cs)],
            "extra": sum(c["size"] or 0 for c in cs[1:])})
    return sorted(out, key=lambda g: -g["extra"])


# ---------- the "For You" channel ----------
FOR_YOU_DAYS = 30


def for_you(conn, now=None, limit=40):
    """What the For You channel plays, best first: the next episode of shows you are watching, films you stopped
    half-way, then unwatched videos most like what you watched lately (TMDB genres, studios, keywords, film series,
    and the channel folder). With no history yet: the newest videos in your library. Never more than a few in a row
    from one channel folder, and a little day-to-day variety."""
    import random
    from .scheduler import seen_ids
    now = int(now or time.time())
    rows = conn.execute("SELECT * FROM media WHERE available=1 AND verified=1 AND playable=1").fetchall()
    if not rows:
        return []
    by_id = {r["id"]: r for r in rows}
    seen = seen_ids(conn)
    facts = {}
    for a in conn.execute("SELECT key,facts,genres FROM art WHERE miss=0"):
        try:
            f = json.loads(a["facts"] or "{}")
        except ValueError:
            f = {}
        if not f.get("genres"):
            try:
                f["genres"] = json.loads(a["genres"] or "[]")
            except ValueError:
                pass
        facts[a["key"]] = f

    def features(r):
        f = facts.get(art.key_for(r)[0], {})
        out = [("g", x) for x in f.get("genres") or []] + [("c", x) for x in (f.get("companies") or [])[:4]]
        out += [("k", x) for x in (f.get("keywords") or [])[:12]]
        if f.get("collection"):
            out.append(("col", f["collection"]))
        if r["franchise"]:
            out.append(("f", r["franchise"].lower()))
        for t in json.loads(r["tags"] or "[]"):
            out.append(("t", str(t).lower()))
        return out

    # what you watched lately, newest counting most
    since = now - FOR_YOU_DAYS * 86400
    history = {}
    for q in ("SELECT media_id, last AS t FROM seen WHERE last>=? AND secs>=120",
              "SELECT media_id, updated AS t FROM progress WHERE updated>=? AND (position>=120 OR completed=1)"):
        for h in conn.execute(q, (since,)):
            history[h["media_id"]] = max(history.get(h["media_id"], 0), h["t"] or 0)
    for f in conn.execute("SELECT media_id FROM favorites"):
        history.setdefault(f["media_id"], since)
    weight = {"g": 3, "c": 3, "k": 2, "col": 12, "f": 4, "t": 2}
    taste, watching = {}, {}
    for mid, t in history.items():
        r = by_id.get(mid)
        if r is None:
            continue
        w = 1 / (1 + max(0, now - t) / (7 * 86400))
        for feat in set(features(r)):
            taste[feat] = taste.get(feat, 0) + w * weight[feat[0]]
        if r["series"]:
            s = _n(r["series"])
            watching[s] = max(watching.get(s, 0), w)
    progress = {p["media_id"]: p for p in conn.execute("SELECT media_id,position,completed,updated FROM progress")}
    day = time.strftime("%Y-%m-%d", time.localtime(now))
    first_ep = {}
    for r in sorted(rows, key=lambda r: (r["season"] or 0, r["episode"] or 0)):
        if r["series"] and r["id"] not in seen:
            first_ep.setdefault(_n(r["series"]), r["id"])          # a show: only its next unwatched episode
    scored = []
    for r in rows:
        p = progress.get(r["id"])
        half = bool(p and not p["completed"] and (p["position"] or 0) >= 60 and (p["updated"] or 0) >= since)
        if r["id"] in seen and not half:
            continue
        if r["series"] and first_ep.get(_n(r["series"])) != r["id"] and not half:
            continue
        score = sum(taste.get(f, 0) for f in set(features(r)))
        if r["series"] and _n(r["series"]) in watching:
            score += 100 * watching[_n(r["series"])]                 # carry on with what you are watching
        if half:
            score += 80
        if (r["added"] or 0) >= now - 14 * 86400:
            score += 3                                              # new in your library
        if not taste:
            score += (r["added"] or 0) / 1e9                        # no history yet: newest first
        score += random.Random(f"{day}:{r['id']}").random() * 2     # a little variety from day to day
        scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    out, per_folder = [], {}
    for _score, r in scored:                                        # mix it up: at most 4 from one folder
        f = (r["franchise"] or "").lower()
        if per_folder.get(f, 0) >= 4:
            continue
        per_folder[f] = per_folder.get(f, 0) + 1
        out.append(r)
        if len(out) >= limit:
            break
    if len(out) < min(limit, 6):                                    # a small library: fill up rather than go quiet
        have = {r["id"] for r in out}
        out += [r for _s, r in scored if r["id"] not in have][:limit - len(out)]
    return out


def history_signature(conn):
    """Changes whenever something is watched - the For You channel is re-planned then."""
    a = conn.execute("SELECT COUNT(*), COALESCE(MAX(last),0), COALESCE(SUM(secs),0) FROM seen").fetchone()
    b = conn.execute("SELECT COUNT(*), COALESCE(MAX(updated),0) FROM progress").fetchone()
    c = conn.execute("SELECT COUNT(*) FROM media WHERE available=1").fetchone()
    return (tuple(a), tuple(b), c[0])
