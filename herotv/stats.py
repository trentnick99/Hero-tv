"""Your watching: hours watched, what you watch most, favourite genres, and this week at a glance (Home > More).

Read-only, from what HERO TV already keeps: on-demand progress, live-TV seconds watched, favorites and the TMDB genres."""
import time

from . import art, smart

WEEK_S = 7 * 86400
TOP = 6


LOG = "CREATE TABLE IF NOT EXISTS watch_log(day TEXT PRIMARY KEY, secs REAL DEFAULT 0)"


def _day(t):
    return time.strftime("%Y-%m-%d", time.localtime(t))


def log(conn, secs, now=None):
    """Add watched seconds to today's total (live TV every 30 s; on demand as the position moves on)."""
    if not 0 < secs <= 120:
        return
    conn.execute(LOG)
    conn.execute("INSERT INTO watch_log(day,secs) VALUES(?,?) ON CONFLICT(day) DO UPDATE SET secs=secs+excluded.secs",
                 (_day(now or time.time()), secs))


def _week(conn, now):
    conn.execute(LOG)
    r = conn.execute("SELECT COALESCE(SUM(secs),0),MIN(day) FROM watch_log WHERE day>=?", (_day(now - 6 * 86400),)).fetchone()
    first = conn.execute("SELECT MIN(day) FROM watch_log").fetchone()[0]
    return r[0], first


def _watched_s(d, live):
    """Seconds of this video you have watched: the live-TV seconds or how far you got, whichever is more (live TV saves a
    position too, so adding them would count it twice)."""
    od = (d["runtime_s"] or 0) if d["completed"] else min(d["position"] or 0, d["runtime_s"] or d["position"] or 0)
    return max(live.get(d["id"], 0) or 0, od)


def build(conn, now=None):
    now = now or time.time()
    live = {r[0]: r[1] or 0 for r in conn.execute("SELECT media_id,secs FROM seen")}
    rows = smart._rows(conn)
    total = 0.0
    shows, genres = {}, {}
    finished = started = 0
    for d in rows:
        s = _watched_s(d, live)
        if s < 60:                       # a peek of under a minute does not count
            continue
        total += s
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
    week, since = _week(conn, now)
    added = conn.execute("SELECT COUNT(*) FROM media WHERE available=1 AND playable=1 AND added>?", (int(now - WEEK_S),)).fetchone()[0]
    favs = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
    top = sorted(shows.values(), key=lambda e: -e["secs"])[:TOP]
    gtot = sum(genres.values()) or 1
    return {"hours": round(total / 3600, 1), "week_hours": round(week / 3600, 1), "finished": finished, "started": started,
            "favorites": favs, "added_week": added, "week_since": since,
            "top": [{"name": e["name"], "hours": round(e["secs"] / 3600, 1), "id": e["id"], "kind": e["kind"]} for e in top],
            "genres": [{"name": g, "share": round(v * 100 / gtot)} for g, v in sorted(genres.items(), key=lambda x: -x[1])[:TOP]]}
