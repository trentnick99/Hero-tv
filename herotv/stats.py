"""Your watching: hours watched, what you watch most, favourite genres, and this week at a glance (Home > More).

Read-only, from what HERO TV already keeps: on-demand progress, live-TV seconds watched, favorites and the TMDB genres."""
import time

from . import art, smart

WEEK_S = 7 * 86400
TOP = 6


def _watched_s(d, live):
    """Seconds of this video you have watched: the live-TV seconds plus how far you got on demand."""
    od = (d["runtime_s"] or 0) if d["completed"] else min(d["position"] or 0, d["runtime_s"] or d["position"] or 0)
    return (live.get(d["id"], 0) or 0) + od


def build(conn, now=None):
    now = now or time.time()
    live = {r[0]: r[1] or 0 for r in conn.execute("SELECT media_id,secs FROM seen")}
    recent = {r[0] for r in conn.execute("SELECT media_id FROM progress WHERE updated>?", (int(now - WEEK_S),))}
    recent |= {r[0] for r in conn.execute("SELECT media_id FROM seen WHERE last>?", (int(now - WEEK_S),))}
    rows = smart._rows(conn)
    total = week = 0.0
    shows, genres = {}, {}
    finished = started = 0
    for d in rows:
        s = _watched_s(d, live)
        if s < 60:                       # a peek of under a minute does not count
            continue
        total += s
        if d["id"] in recent:
            week += s
        finished += 1 if d["completed"] else 0
        started += 1
        if d["_show"]:
            sh = art.show_of(d)
            name = sh[0] if sh else (d["series"] or d["franchise"] or d["title"])
        else:
            name = d["title"] + (f" ({d['year']})" if d["year"] else "")
        e = shows.setdefault(name, {"name": name, "secs": 0.0, "id": d["id"], "kind": "show" if d["_show"] else "film"})
        e["secs"] += s
        for g in d["_genres"]:
            genres[g] = genres.get(g, 0) + s
    added = conn.execute("SELECT COUNT(*) FROM media WHERE available=1 AND playable=1 AND added>?", (int(now - WEEK_S),)).fetchone()[0]
    favs = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
    top = sorted(shows.values(), key=lambda e: -e["secs"])[:TOP]
    gtot = sum(genres.values()) or 1
    return {"hours": round(total / 3600, 1), "week_hours": round(week / 3600, 1), "finished": finished, "started": started,
            "favorites": favs, "added_week": added,
            "top": [{"name": e["name"], "hours": round(e["secs"] / 3600, 1), "id": e["id"], "kind": e["kind"]} for e in top],
            "genres": [{"name": g, "share": round(v * 100 / gtot)} for g, v in sorted(genres.items(), key=lambda x: -x[1])[:TOP]]}
