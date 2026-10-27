"""On demand for the Roku app: your whole library as rows (Continue watching, Favorites, New, then one row per
folder), shows grouped so one tile stands for a whole series, and everything a TV needs to play one video."""
import os

PLAYABLE = "m.available=1 AND m.verified=1 AND m.playable=1"
ROW_MAX = 80
RECENT_S = 30 * 86400
COLS = ("m.id,m.title,m.year,m.franchise,m.series,m.season,m.episode,m.plot,m.runtime_s,m.added,m.ord,"
        "COALESCE(p.position,0) AS position,COALESCE(p.completed,0) AS completed,COALESCE(p.updated,0) AS updated,"
        "(f.media_id IS NOT NULL) AS favorite")
FROM = " FROM media m LEFT JOIN progress p ON p.media_id=m.id LEFT JOIN favorites f ON f.media_id=m.id WHERE " + PLAYABLE


def _mins(s):
    s = int(s or 0)
    if s <= 0:
        return ""
    h, m = divmod(round(s / 60), 60)
    return (f"{h} h {m} min" if h else f"{m} min") if m else f"{h} h"


def _ep(r):
    return f"S{r['season'] or 0} E{r['episode'] or 0}"


def video(r):
    """One tile for one video."""
    if r["series"]:
        title = f"{r['series']}  {_ep(r)}"
        line = r["title"] or ""
    else:
        title = r["title"] or "Untitled"
        line = "  -  ".join(x for x in (str(r["year"] or ""), _mins(r["runtime_s"])) if x)
    if r["position"] > 10 and not r["completed"]:
        left = _mins((r["runtime_s"] or 0) - r["position"])
        line = (line + "  -  " if line else "") + (f"{left} left" if left else "started")
    return {"type": "video", "id": r["id"], "title": title, "line": line, "plot": r["plot"] or "",
            "favorite": bool(r["favorite"]), "thumb": f"/thumb/{r['id']}"}


def next_up(eps):
    """The episode to watch next in a series (eps sorted by season/episode): the one you are part-way through,
    else the one after the last you finished, else the first."""
    started = [e for e in eps if e["position"] > 10 and not e["completed"]]
    if started:
        return max(started, key=lambda e: e["updated"])
    done = [i for i, e in enumerate(eps) if e["completed"]]
    if done:
        last = max(done, key=lambda i: eps[i]["updated"])
        if last + 1 < len(eps):
            return eps[last + 1]
    return eps[0]


def series_tile(name, eps):
    nx = next_up(eps)
    watched = sum(1 for e in eps if e["completed"])
    line = f"{len(eps)} episodes" + (f"  -  {watched} watched" if watched else "")
    return {"type": "series", "id": nx["id"], "title": name, "line": f"Next: {_ep(nx)}  -  " + line,
            "plot": nx["plot"] or "", "franchise": nx["franchise"] or "", "series": name,
            "favorite": any(e["favorite"] for e in eps), "thumb": f"/thumb/{nx['id']}"}


def _grouped(rows):
    """Videos in order, with each series folded into one tile at the place of its first episode."""
    out, series = [], {}
    for r in rows:
        if r["series"]:
            k = (r["franchise"] or "", r["series"])
            if k not in series:
                series[k] = []
                out.append(k)
            series[k].append(r)
        else:
            out.append(r)
    tiles = []
    for x in out:
        if isinstance(x, tuple):
            eps = sorted(series[x], key=lambda e: (e["season"] or 0, e["episode"] or 0, e["title"] or ""))
            tiles.append(series_tile(x[1], eps))
        else:
            tiles.append(video(x))
    return tiles


def rows(c, now, q=""):
    """{"rows": [{"title", "items": [tile...]}]} - with q, a single row of search results."""
    q = (q or "").strip()[:80]
    if q:
        like = f"%{q}%"
        found = c.execute("SELECT " + COLS + FROM + " AND (m.title LIKE ? OR m.series LIKE ? OR m.franchise LIKE ? OR "
                          "m.tags LIKE ?) ORDER BY m.franchise,m.ord,m.series,m.season,m.episode,m.title LIMIT 400",
                          (like,) * 4).fetchall()
        tiles = _grouped(found)[:ROW_MAX]
        return {"rows": [{"title": f"Results for \"{q}\"" if tiles else f"Nothing found for \"{q}\"", "items": tiles}]}
    out = []
    cont = c.execute("SELECT " + COLS + FROM + " AND p.position>10 AND p.completed=0 ORDER BY p.updated DESC LIMIT ?",
                     (ROW_MAX,)).fetchall()
    if cont:
        out.append({"title": "Continue watching", "items": [video(r) for r in cont]})
    fav = c.execute("SELECT " + COLS + FROM + " AND f.media_id IS NOT NULL ORDER BY f.added DESC LIMIT 400").fetchall()
    if fav:
        out.append({"title": "Favorites", "items": _grouped(fav)[:ROW_MAX]})
    new = c.execute("SELECT " + COLS + FROM + " AND m.added>? ORDER BY m.added DESC,m.id DESC LIMIT 400",
                    (int(now) - RECENT_S,)).fetchall()
    if new:
        out.append({"title": "New in your library", "items": _grouped(new)[:ROW_MAX]})
    allr = c.execute("SELECT " + COLS + FROM + " ORDER BY m.franchise,m.ord,m.year,m.series,m.season,m.episode,m.title").fetchall()
    by = {}
    for r in allr:
        by.setdefault(r["franchise"] or "Other videos", []).append(r)
    for name in sorted(by, key=lambda n: (n.lower() == "inbox", n.lower())):
        out.append({"title": name, "items": _grouped(by[name])[:ROW_MAX * 3]})
    return {"rows": out}


def episodes(c, franchise, series):
    """Every episode of a show, in order, and which one is next."""
    eps = c.execute("SELECT " + COLS + FROM + " AND m.series=? AND COALESCE(m.franchise,'')=? "
                    "ORDER BY m.season,m.episode,m.title", (series, franchise or "")).fetchall()
    if not eps:
        return {"series": series, "items": [], "next": None}
    nx = next_up(list(eps))
    items = []
    for e in eps:
        t = video(e)
        t["title"] = f"{_ep(e)}  {e['title'] or ''}".strip()
        if e["completed"]:
            t["line"] = (t["line"] + "  -  " if t["line"] else "") + "watched"
        items.append(t)
    return {"series": series, "items": items, "next": nx["id"]}


def extras(c, mid):
    """File type and subtitle tracks the TV needs to play a video ("" / [] when unknown)."""
    m = c.execute("SELECT path FROM media WHERE id=?", (mid,)).fetchone()
    ext = os.path.splitext(m["path"])[1].lstrip(".").lower() if m else ""
    subs = []
    if m and os.path.isfile(m["path"]):
        from . import subtitles
        try:
            subs = [{"url": f"/sub/{mid}/{t['key']}.vtt", "language": t.get("language") or "",
                     "label": t.get("label") or "Subtitles"} for t in subtitles.tracks(m["path"])["tracks"]]
        except Exception:
            subs = []
    return ext, subs


def play(c, mid):
    """What the Roku needs to start one video on demand: file type, subtitles, where you left off, what is next."""
    r = c.execute("SELECT " + COLS + FROM + " AND m.id=?", (mid,)).fetchone()
    if r is None:
        return None
    ext, subs = extras(c, mid)
    nxt = None
    if r["series"]:
        n = c.execute("SELECT m.id,m.title,m.season,m.episode FROM media m WHERE " + PLAYABLE + " AND m.series=? AND "
                      "COALESCE(m.franchise,'')=? AND (COALESCE(m.season,0),COALESCE(m.episode,0))>(?,?) "
                      "ORDER BY m.season,m.episode LIMIT 1",
                      (r["series"], r["franchise"] or "", r["season"] or 0, r["episode"] or 0)).fetchone()
        if n:
            nxt = {"id": n["id"], "title": f"{r['series']}  {_ep(n)}" + (f"  {n['title']}" if n["title"] else "")}
    t = video(r)
    resume = int(r["position"]) if r["position"] > 30 and not r["completed"] else 0
    if r["runtime_s"] and resume > r["runtime_s"] - 60:
        resume = 0                                     # practically finished: start again
    return {"id": r["id"], "title": t["title"], "line": t["line"], "ext": ext, "subs": subs, "resume": resume,
            "runtime": int(r["runtime_s"] or 0), "favorite": bool(r["favorite"]), "next": nxt}
