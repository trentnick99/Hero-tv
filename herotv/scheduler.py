"""Persistent virtual-channel scheduler.

Times are integer UTC epoch seconds. A slot lasts ceil(verified runtime) seconds and slots are
contiguous. Playout order is a pure function of (channel rules, library, last stored slot), so the
schedule survives restarts: new slots are always appended after the last stored slot.
"""
import datetime as dt
import json
import math
import random
import threading
import time
from .tz import get_tz

MAX_CATCHUP_S = 7 * 86400   # after a longer outage the channel resumes "now" instead of replaying it
MAX_SLOTS_PER_RUN = 200000
_lock = threading.RLock()


def load_channels(conn, channels):
    """Upsert channel definitions (list of dicts from channels.json)."""
    with _lock:
        for c in channels:
            rules = config_rules(c)
            if c.get("blocks"):
                rules["_blocks"] = parse_blocks(c)
            if c.get("smart") is False:
                rules["_smart"] = False                   # opt out of "prefer what you have not seen"
            conn.execute(
                "INSERT INTO channels(id,number,name,mode,rules,description,color,kind) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET number=excluded.number,name=excluded.name,mode=excluded.mode,"
                "rules=excluded.rules,description=excluded.description,color=excluded.color,kind=excluded.kind",
                (c["id"], c["number"], c["name"], c.get("mode", "sequential"),
                 json.dumps(rules), c.get("description", ""), c.get("color", ""), c.get("kind", "tv")))
        conn.commit()


DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DAY_WORDS = {"weekday": DAYS[:5], "weekdays": DAYS[:5], "weekend": DAYS[5:], "weekends": DAYS[5:],
              "daily": DAYS, "everyday": DAYS, "all": DAYS}


def _hhmm(v, what):
    try:
        h, m = str(v).strip().split(":")
        h, m = int(h), int(m)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return h * 60 + m
    except ValueError:
        raise ValueError(f'{what} must look like "07:30" (24-hour clock), not {v!r}')


def parse_blocks(ch):
    """Validate and normalise a channel's "blocks" (scheduled programming such as Saturday morning cartoons).
    Returns a list of {name, days(set of 0-6, Monday=0), start, end (minutes), match, mode}. Raises ValueError
    with a plain-English message."""
    out, names = [], set()
    where = f'channel "{ch.get("name", ch.get("id"))}"'
    for i, b in enumerate(ch.get("blocks") or [], 1):
        if not isinstance(b, dict):
            raise ValueError(f"{where}: block {i} must be a {{ ... }} group")
        name = str(b.get("name") or f"Block {i}")
        if name.lower() in names:
            raise ValueError(f'{where}: two blocks are both called "{name}" - give each its own name')
        names.add(name.lower())
        raw = b.get("days", "daily")
        raw = [raw] if isinstance(raw, str) else list(raw)
        days = set()
        for d in raw:
            d = str(d).strip().lower()
            if d in _DAY_WORDS:
                days |= {DAYS.index(x) for x in _DAY_WORDS[d]}
            elif d[:3] in DAYS:
                days.add(DAYS.index(d[:3]))
            else:
                raise ValueError(f'{where}, block "{name}": "{d}" is not a day. Use mon tue wed thu fri sat sun, '
                                 f'or "weekdays", "weekends", "daily"')
        if "from" not in b or "to" not in b:
            raise ValueError(f'{where}, block "{name}": needs both  "from"  and  "to"  times, e.g. "from": "07:00", "to": "12:00"')
        a, z = _hhmm(b["from"], f'{where}, block "{name}": "from"'), _hhmm(b["to"], f'{where}, block "{name}": "to"')
        if a == z:
            raise ValueError(f'{where}, block "{name}": "from" and "to" are the same time')
        dates = None
        if b.get("dates"):
            try:
                x, y = [p.strip() for p in str(b["dates"]).split("..")]
                (m1, d1), (m2, d2) = [tuple(int(v) for v in q.split("-")) for q in (x, y)]
                dt.date(2000, m1, d1), dt.date(2000, m2, d2)           # checks the month/day exist
                dates = (m1, d1, m2, d2)
            except (ValueError, TypeError):
                raise ValueError(f'{where}, block "{name}": "dates" must look like "10-24..10-31" (month-day..month-day)')
        out.append({"name": name, "days": sorted(days), "start": a, "end": z, "dates": dates,
                    "match": dict(b.get("match") or {}), "mode": b.get("mode")})
    return out


def _in_dates(b, day):
    """Is this calendar day inside the block's yearly "dates" range (if it has one)? Ranges may wrap the new year."""
    r = b.get("dates")
    if not r:
        return True
    a, z, d = (r[0], r[1]), (r[2], r[3]), (day.month, day.day)
    return a <= d <= z if a <= z else (d >= a or d <= z)


def block_at(blocks, local):
    """The block on air at a local datetime, or None. Blocks may run past midnight (22:00 -> 02:00); the
    after-midnight part belongs to the day the block started on."""
    mins = local.hour * 60 + local.minute
    wd = local.weekday()
    today, yesterday = local.date(), local.date() - dt.timedelta(days=1)
    for b in blocks:
        if b["start"] < b["end"]:
            if wd in b["days"] and b["start"] <= mins < b["end"] and _in_dates(b, today):
                return b
        else:
            if (wd in b["days"] and mins >= b["start"] and _in_dates(b, today)) or \
                    ((wd - 1) % 7 in b["days"] and mins < b["end"] and _in_dates(b, yesterday)):
                return b
    return None


SEASONAL_FILE = None          # set by with_seasonal() callers/tests; default is config/seasonal.json


DAYPARTS_FILE = None          # tests may point this elsewhere; default is config/dayparts.json


def _extra_blocks(setting, path):
    """Blocks from a config file, unless switched off in Settings (settings.json key `setting`)."""
    import json as _json
    from . import config as _config
    try:
        if _json.loads(_config.settings_file().read_text(encoding="utf-8-sig")).get(setting, True) is False:
            return []
    except (OSError, ValueError, AttributeError):
        pass
    try:
        with open(path, encoding="utf-8-sig") as f:
            blocks = _json.load(f).get("blocks", [])
    except (OSError, ValueError):
        return []
    return [b for b in blocks if isinstance(b, dict)]


def with_seasonal(channels, path=None, dayparts_path=None):
    """Add the seasonal specials (config/seasonal.json, e.g. Halloween week) and the time-of-day programming
    (config/dayparts.json, e.g. late-night horror) to their channels. Order of precedence: seasonal specials, then
    blocks you put in channels.json yourself, then the time-of-day blocks. Each is switched off in Settings > Channels."""
    from . import config as _config
    seasonal = _extra_blocks("seasonal", path or SEASONAL_FILE or str(_config.ROOT / "config" / "seasonal.json"))
    dayparts = _extra_blocks("dayparts", dayparts_path or DAYPARTS_FILE or str(_config.ROOT / "config" / "dayparts.json"))
    if not seasonal and not dayparts:
        return channels
    out = []
    for c in channels:
        own = list(c.get("blocks") or [])
        have = {str(b.get("name", "")).lower() for b in own}

        def mine(extra):
            got = []
            for b in extra:
                if b.get("channel") == c.get("id") and str(b.get("name", "")).lower() not in have:
                    have.add(str(b.get("name", "")).lower())
                    got.append({k: v for k, v in b.items() if k != "channel"})
            return got
        first, last = mine(seasonal), mine(dayparts)
        out.append(dict(c, blocks=first + own + last) if first or last else c)
    return out


def _block_start_within(blocks, start, end, z):
    """First minute in (start, end) at which a block begins, else None - so a movie can be cut at 7:00 sharp."""
    t = start - start % 60 + 60
    while t < end:
        if block_at(blocks, dt.datetime.fromtimestamp(t, z)):
            return t
        t += 60
    return None


def sync_channels(conn, channels, now=None, tz="local"):
    """Make the database match channels.json exactly: edits apply, removed channels disappear (with their
    schedule), and renumbering/swapping numbers cannot trip the UNIQUE number constraint."""
    channels = [c for c in with_seasonal(channels) if not c.get("off")]     # switched off in "Your channels"
    with _lock:
        ids = [c["id"] for c in channels]
        if len(set(ids)) != len(ids) or len({c["number"] for c in channels}) != len(channels):
            raise ValueError("channels.json: every channel needs its own id and its own number")
        for c in channels:
            parse_blocks(c)                       # fail early with a readable message
        old = {r["id"]: (r["rules"], r["mode"]) for r in conn.execute("SELECT id,rules,mode FROM channels")}
        keep = ",".join("?" * len(ids)) or "''"
        conn.execute(f"DELETE FROM slots WHERE channel_id NOT IN ({keep})", ids)
        conn.execute(f"DELETE FROM channels WHERE id NOT IN ({keep})", ids)
        conn.execute("UPDATE channels SET number=-rowid")      # free every number, then assign the new ones
        conn.commit()
        load_channels(conn, channels)
        new = {r["id"]: (r["rules"], r["mode"]) for r in conn.execute("SELECT id,rules,mode FROM channels")}
        changed = [i for i in new if i in old and old[i] != new[i]]
        for i in changed:                         # edited rules/blocks: replan what has not aired yet
            ch = conn.execute("SELECT * FROM channels WHERE id=?", (i,)).fetchone()
            rebuild_future(conn, ch, now if now is not None else time.time(), tz=tz)


def _kind(ch):
    try:
        return ch["kind"] or "tv"
    except (KeyError, IndexError):
        return "tv"


def config_rules(c):
    """A channel's rules as stored: its "match", plus any "also" groups (extra videos that belong too, e.g. the
    Spider-Man TV shows on Marvel Television). A video belongs if it fits "match" OR any "also" group."""
    rules = dict(c.get("match", {}))
    also = c.get("also")
    also = [also] if isinstance(also, dict) else [a for a in (also or []) if isinstance(a, dict)]
    if also:
        rules["_also"] = also
    return rules


def matches(rules, m):
    return _fits(rules, m) or any(_fits(a, m) for a in rules.get("_also", []))


def _fits(rules, m):
    low = lambda x: str(x).lower()
    if rules.get("franchise") and low(m["franchise"]) not in [low(x) for x in rules["franchise"]]:
        return False
    tags = {low(t) for t in json.loads(m["tags"] or "[]")}
    if rules.get("tags") and not tags & {low(t) for t in rules["tags"]}:
        return False
    if rules.get("series") and low(m["series"]) not in [low(x) for x in rules["series"]]:
        return False
    mins = (m["runtime_s"] or 0) / 60
    if rules.get("min_minutes") and mins < rules["min_minutes"]:
        return False
    if rules.get("max_minutes") and mins > rules["max_minutes"]:
        return False
    kind = str(rules.get("type") or "").lower()
    if kind in ("movie", "episode"):
        is_ep = bool(m["episode"] or m["series"])
        if is_ep != (kind == "episode"):
            return False
    if rules.get("year_min") and (m["year"] or 0) < rules["year_min"]:
        return False
    if rules.get("year_max") and (m["year"] or 9999) > rules["year_max"]:
        return False
    return True


def seen_ids(conn):
    """Videos you have effectively watched: at least half of it live, played to the end / past 90% from the library."""
    return {r[0] for r in conn.execute(
        "SELECT m.id FROM media m LEFT JOIN seen s ON s.media_id=m.id LEFT JOIN progress p ON p.media_id=m.id "
        "WHERE m.runtime_s>0 AND (s.secs>=0.5*m.runtime_s OR p.completed=1 OR p.position>=0.9*m.runtime_s)")}


def _spec(ch):
    """(base rules, blocks) for a channel row."""
    rules = json.loads(ch["rules"] or "{}")
    blocks = rules.pop("_blocks", [])
    return rules, blocks


def _playlist(conn, ch, plan, key, cycle, cache):
    """Ordered media for one playlist ("" = the channel's normal programming, else a block name) and cycle."""
    if (key, cycle) in cache:
        return cache[(key, cycle)]
    if ("base", key) not in cache:
        rules, blocks = plan
        match, mode = rules, ch["mode"]
        if key:
            b = next(x for x in blocks if x["name"] == key)
            match, mode = b["match"] or rules, b["mode"] or ch["mode"]
        if _kind(ch) == "foryou" and not key:          # picked from what you have been watching
            from . import insights
            rows, mode = insights.for_you(conn, limit=80), "sequential"
        else:
            rows = [r for r in conn.execute(
                "SELECT * FROM media WHERE available=1 AND verified=1 AND playable=1 "
                "ORDER BY ord,series,season,episode,title,id") if matches(match, r)]
        cache[("base", key)] = (rows, mode)
    rows, mode = cache[("base", key)]
    rows = list(rows)
    if mode == "shuffle":
        random.Random(f"{ch['id']}:{key}:{cycle}").shuffle(rows)   # deterministic per (channel, block, cycle)
    cache[(key, cycle)] = (rows, [r["id"] for r in rows])
    return cache[(key, cycle)]


def _next(conn, ch, plan, key, last_media, cycle, cache, skip=frozenset()):
    """Next item after `last_media`, passing over anything in `skip` (already watched) while something else is left."""
    rows, ids = _playlist(conn, ch, plan, key, cycle, cache)
    if not rows:
        return None
    idx = 0 if last_media is None or last_media not in ids else ids.index(last_media) + 1
    cyc = cycle
    for _ in range(2):
        rows, ids = _playlist(conn, ch, plan, key, cyc, cache)
        for i in range(idx, len(rows)):
            if rows[i]["id"] not in skip:
                return rows[i], cyc
        cyc, idx = cyc + 1, 0
    if skip:                                   # everything has been seen: just carry on in order
        return _next(conn, ch, plan, key, last_media, cycle, cache)
    return None


def extend(conn, ch, now, horizon_s=48 * 3600, tz="local", resume=False, avoid=()):
    """Append slots until the schedule covers now+horizon. Idempotent and restart-safe.

    Programming blocks (see parse_blocks) pick from their own playlist while they are on air; each playlist
    remembers where it stopped, so Saturday's cartoons carry on with next Saturday's episodes. A block starts on
    the dot: normal programming that would run into it is cut off at its start.

    Smart programming: videos you have already watched are passed over while anything unwatched is left, so
    shuffle channels do not repeat and sequential channels carry on with what you have not seen. `resume`
    (used when HERO TV starts) makes sequential channels go back to the first unwatched episode; `avoid` keeps
    the video that is on air from being scheduled again straight after itself."""
    now = int(now)
    if _kind(ch) not in ("tv", "foryou"):   # e.g. the Weather channel: live data, nothing to schedule
        return 0
    plan = _spec(ch)
    blocks = plan[1]
    z = get_tz(tz)
    with _lock:
        smart = plan[0].get("_smart", True)
        skip = (seen_ids(conn) if smart else set()) | set(avoid)      # grows with what this pass schedules, so a lone unwatched video is not repeated
        last = conn.execute("SELECT end,media_id,cycle FROM slots WHERE channel_id=? ORDER BY start DESC LIMIT 1",
                            (ch["id"],)).fetchone()
        if last is None:
            start = now
        elif now - last["end"] > MAX_CATCHUP_S:
            start = now
        else:
            start = last["end"]
        cache, added, pos = {}, 0, {}

        def where_was(key):                       # (last media, cycle) for a playlist, from what is already stored
            if key not in pos:
                r = conn.execute("SELECT media_id,cycle FROM slots WHERE channel_id=? AND pl=? ORDER BY start DESC LIMIT 1",
                                 (ch["id"], key)).fetchone()
                pos[key] = (r["media_id"], r["cycle"]) if r else (None, 0)
                mode = next((b["mode"] for b in blocks if b["name"] == key), None) or ch["mode"] if key else ch["mode"]
                if resume and smart and mode != "shuffle":      # start over at the first unwatched episode
                    pos[key] = (None, pos[key][1])
            return pos[key]

        while start < now + horizon_s and added < MAX_SLOTS_PER_RUN:
            b = block_at(blocks, dt.datetime.fromtimestamp(start, z)) if blocks else None
            key = b["name"] if b else ""
            r = _next(conn, ch, plan, key, *where_was(key), cache, skip)
            if r is None and key:                 # a block with nothing to show falls back to normal programming
                key = ""
                r = _next(conn, ch, plan, key, *where_was(key), cache, skip)
            if r is None:
                break
            m, cycle = r
            dur = max(1, math.ceil(m["runtime_s"]))
            end = start + dur
            if blocks and not key:                # cut regular programming where a block begins
                cut = _block_start_within(blocks, start, end, z)
                if cut:
                    end = cut
            conn.execute("INSERT INTO slots(channel_id,start,end,media_id,cycle,pl) VALUES(?,?,?,?,?,?)",
                         (ch["id"], start, end, m["id"], cycle, key))
            pos[key] = (m["id"], cycle)
            if smart:
                skip.add(m["id"])
            start = end
            added += 1
        conn.commit()
        return added


def rebuild_future(conn, ch, now, horizon_s=48 * 3600, tz="local", resume=False):
    """Drop not-yet-started slots (after a library change) and regenerate them. The slot on air is
    kept while its media is usable; otherwise it is replaced seamlessly from its own start time."""
    now = int(now)
    with _lock:
        cur = conn.execute("SELECT s.end, s.media_id, (m.available=1 AND m.verified=1 AND m.playable=1) AS ok FROM slots s "
                           "JOIN media m ON m.id=s.media_id WHERE channel_id=? AND start<=? AND end>?",
                           (ch["id"], now, now)).fetchone()
        if cur and cur["ok"]:
            conn.execute("DELETE FROM slots WHERE channel_id=? AND start>=?", (ch["id"], cur["end"]))
        else:
            conn.execute("DELETE FROM slots WHERE channel_id=? AND end>?", (ch["id"], now))
        conn.commit()
        return extend(conn, ch, now, horizon_s, tz, resume, avoid=(cur["media_id"],) if cur and cur["ok"] else ())


def channels(conn):
    return conn.execute("SELECT * FROM channels ORDER BY number").fetchall()


def extend_all(conn, now, horizon_s=48 * 3600, rebuild=False, tz="local", resume=False):
    for ch in channels(conn):
        if rebuild:
            rebuild_future(conn, ch, now, horizon_s, tz, resume)
        else:
            extend(conn, ch, now, horizon_s, tz)


# ---------- queries ----------
_SEL = ("SELECT s.channel_id,s.start,s.end,s.media_id,m.title,m.year,m.franchise,m.series,m.season,m.episode,"
        "m.plot,m.runtime_s,s.pl FROM slots s JOIN media m ON m.id=s.media_id ")


def slot_dict(row, tz):
    if row is None:
        return None
    z = get_tz(tz)
    d = dict(row)
    d["start_local"] = dt.datetime.fromtimestamp(d["start"], z).isoformat()
    d["end_local"] = dt.datetime.fromtimestamp(d["end"], z).isoformat()
    d["block"] = "" if d.get("pl") == "~filler" else (d.get("pl") or "")   # "~filler" = slots made by an older version
    d["source"] = "generated"   # virtual-channel schedule, never an official broadcast listing
    return d


def current(conn, ch_id, t):
    return conn.execute(_SEL + "WHERE s.channel_id=? AND s.start<=? AND s.end>?", (ch_id, int(t), int(t))).fetchone()


def following(conn, ch_id, t):
    return conn.execute(_SEL + "WHERE s.channel_id=? AND s.start>=? ORDER BY s.start LIMIT 1", (ch_id, int(t))).fetchone()


def window(conn, t0, t1):
    """Slots overlapping [t0,t1)."""
    return conn.execute(_SEL + "WHERE s.end>? AND s.start<? ORDER BY s.channel_id,s.start", (int(t0), int(t1))).fetchall()


def local_day_bounds(tz, day):
    """UTC epoch bounds of a local calendar day (23/24/25 h long around DST changes)."""
    z = get_tz(tz)
    d = dt.date.fromisoformat(day) if isinstance(day, str) else day
    a = dt.datetime.combine(d, dt.time.min, tzinfo=z)
    b = dt.datetime.combine(d + dt.timedelta(days=1), dt.time.min, tzinfo=z)
    return int(a.timestamp()), int(b.timestamp())
