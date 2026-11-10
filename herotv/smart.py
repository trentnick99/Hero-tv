"""Smart rows for Home: rows built from rules (not watched yet, quick watches, movies, one per genre).

Read-only. Each row is a short list of library items in the same shape /api/library returns, one tile per show
(its first unwatched episode) so a long series cannot fill a whole row."""
import json

from . import art

STATIC = {
    "unwatched": ("Not watched yet", "Things you have not started"),
    "short": ("Quick watches", "Under 30 minutes"),
    "movies": ("Movies", "Newest first"),
    "toprated": ("Top rated", "Best rated first"),
    "featured": ("Featured", "A rotating pick of what is worth watching"),
    "week": ("New this week", "Added in the last 7 days"),
}
WEEK_S = 7 * 86400
PICK_LEN = 30
GENRE = "genre:"
MIN_ITEMS = 3
ROW_LEN = 14
FEATURED_LEN = 6


def _about(conn, cfg, d):
    """The description, rating and genres for a featured tile (from TMDB when known)."""
    try:
        i = art.info(conn, cfg, d)
    except Exception:
        return {}
    return {"about": (i.get("plot") or "")[:260], "rating": i.get("rating") or 0, "genres": (i.get("genres") or [])[:3]}


def surprise(conn):
    """One random video you have not watched (a show stands for its first unwatched episode); any video when everything is seen."""
    import random
    rows = _rows(conn)
    pick = _one_per_show(sorted([d for d in rows if not _seen(d)], key=lambda d: (d["season"] or 0, d["episode"] or 0, d["ord"] or 0)))
    pick = pick or rows
    return _clean(random.choice(pick)) if pick else None


def pick_pool(conn, cfg=None):
    """For the swipe picker: up to PICK_LEN things you have not watched (a show = its first unwatched episode), shuffled,
    each with its description, rating and genres."""
    import random
    rows = _rows(conn)
    pool = _one_per_show(sorted([d for d in rows if not _seen(d)], key=lambda d: (d["season"] or 0, d["episode"] or 0, d["ord"] or 0)))
    random.shuffle(pool)
    out = []
    for d in pool[:PICK_LEN]:
        sh = art.show_of(d)
        show = sh[0] if sh else (d["franchise"] if art.folder_show(conn, d) else "")
        out.append(dict(_clean(d), show=show, **_about(conn, cfg, d)))
    return out


def valid_id(x):
    """A row id that may be saved in the Home rows setting."""
    return isinstance(x, str) and (x in STATIC or (x.startswith(GENRE) and 1 < len(x) <= 40 + len(GENRE)))


def _rows(conn):
    """Every playable video with its progress, favorite flag and TMDB genres/rating (when known)."""
    meta, in_folder = {}, {}
    for a in conn.execute("SELECT key,genres,rating FROM art WHERE miss=0"):
        try:
            g = json.loads(a["genres"] or "[]")
        except ValueError:
            g = []
        meta[a["key"]] = (g, a["rating"] or 0)
    out = []
    for r in conn.execute(
            "SELECT m.id,m.title,m.year,m.franchise,m.series,m.season,m.episode,m.plot,m.runtime_s,m.tags,m.added,m.ord,"
            "COALESCE(p.position,0) AS position,COALESCE(p.completed,0) AS completed,(f.media_id IS NOT NULL) AS favorite "
            "FROM media m LEFT JOIN progress p ON p.media_id=m.id LEFT JOIN favorites f ON f.media_id=m.id "
            "WHERE m.available=1 AND m.verified=1 AND m.playable=1"):
        d = dict(r)
        try:
            k = art.key_for(d)[0]
        except Exception:
            k = ""
        g, rating = meta.get(k, ([], 0))
        d["_genres"], d["_rating"] = g, rating
        sh = art.show_of(d)
        d["_show"] = art.norm(sh[0]) if sh else ""
        if not sh and not d.get("series"):             # an episode with no numbers in its name, sitting in a show's folder
            fr = d.get("franchise") or ""
            if fr and fr not in in_folder:
                try:
                    in_folder[fr] = bool(art.folder_show(conn, d))
                except Exception:
                    in_folder[fr] = False
            if fr and in_folder[fr]:
                d["_show"] = art.norm(fr)              # one tile per show in the rows, like its numbered episodes
                d["in_show"] = art.clean_show(fr)[0]   # and Home says which show it is from
        out.append(d)
    return out


def _seen(d):
    return d["completed"] or d["position"] > 10


def _one_per_show(items):
    """Keep the first item of each show (items are already in the wanted order); movies all stay."""
    seen, out = set(), []
    for d in items:
        s = d["_show"]
        if s:
            if s in seen:
                continue
            seen.add(s)
        out.append(d)
    return out


def _clean(d):
    return {k: v for k, v in d.items() if not k.startswith("_")}


def catalog(conn):
    """The rows that can be added on Home: the fixed ones plus one per genre with enough videos."""
    rows = _rows(conn)
    cat = [{"id": k, "title": v[0], "sub": v[1]} for k, v in STATIC.items()]
    count = {}
    for s in _one_per_show(sorted(rows, key=lambda d: d["ord"] or 0)):
        for g in s["_genres"]:
            count[g] = count.get(g, 0) + 1
    for g, n in sorted(count.items(), key=lambda x: (-x[1], x[0])):
        if n >= MIN_ITEMS:
            cat.append({"id": GENRE + g, "title": g, "sub": f"{n} titles"})
    return cat


def build(conn, ids, cfg=None):
    """{id: {title, sub, items}} for the wanted row ids; rows with fewer than MIN_ITEMS tiles are left out."""
    rows = _rows(conn)
    newest = sorted(rows, key=lambda d: (-(d["added"] or 0), -d["id"]))
    out = {}
    for rid in ids:
        if rid == "unwatched":
            pick = [d for d in sorted(rows, key=lambda d: (d["season"] or 0, d["episode"] or 0, d["ord"] or 0)) if not _seen(d)]
            pick = _one_per_show(pick)
            pick.sort(key=lambda d: (-(d["added"] or 0), -d["id"]))
        elif rid == "short":
            pick = _one_per_show([d for d in newest if 60 <= (d["runtime_s"] or 0) <= 1800 and not _seen(d)])
        elif rid == "featured":
            pick = _one_per_show(sorted([d for d in rows if not _seen(d) and d["_rating"] >= 6.5],
                                        key=lambda d: (-(d["_rating"]), -(d["added"] or 0))))[:FEATURED_LEN]
            if len(pick) < 2:                                   # too few good ones: fall back to the newest unwatched
                pick = _one_per_show([d for d in newest if not _seen(d)])[:FEATURED_LEN]
            out[rid] = {"title": "Featured", "sub": "", "items": [dict(_clean(d), **_about(conn, cfg, d)) for d in pick]} if pick else None
            if not pick:
                del out[rid]
            continue
        elif rid == "week":
            import time
            fresh = [d for d in newest if (d["added"] or 0) > time.time() - WEEK_S]
            pick = _one_per_show(sorted(fresh, key=lambda d: (d["season"] or 0, d["episode"] or 0, d["ord"] or 0)))
            pick.sort(key=lambda d: (-(d["added"] or 0), -d["id"]))
            if pick:
                films = sum(1 for d in fresh if not d["_show"])
                eps = len(fresh) - films
                bits = [f"{films} {'film' if films == 1 else 'films'}" if films else "", f"{eps} {'episode' if eps == 1 else 'episodes'}" if eps else ""]
                out[rid] = {"title": "New this week", "sub": " and ".join(b for b in bits if b) + " added",
                            "items": [_clean(d) for d in pick[:ROW_LEN]]}
            continue
        elif rid == "movies":
            pick = [d for d in newest if not d["_show"]]
        elif rid == "toprated":
            pick = _one_per_show(sorted([d for d in rows if d["_rating"]], key=lambda d: (-d["_rating"], d["ord"] or 0)))
        elif isinstance(rid, str) and rid.startswith(GENRE):
            g = rid[len(GENRE):]
            pick = _one_per_show([d for d in newest if g in d["_genres"]])
        else:
            continue
        if len(pick) < MIN_ITEMS:
            continue
        title, sub = STATIC.get(rid, (rid[len(GENRE):], "")) if rid in STATIC else (rid[len(GENRE):], "")
        out[rid] = {"title": title, "sub": sub or (f"{len(pick)} titles" if rid.startswith(GENRE) else ""),
                    "items": [_clean(d) for d in pick[:ROW_LEN]]}
    return out
