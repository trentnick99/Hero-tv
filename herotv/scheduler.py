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
# Clean start times: a channel can start its shows on the quarter hour, half hour or hour (channels.json "starts":
# 15, 30 or 60). The gap is filled with whole short cartoons from the Shorts folder that fit, and whatever is left
# with an "Up next" card for the next show.
SHORTS = "~short"
CARD = "~card"
SHORTS_FOLDER = "shorts"
SHORT_MAX_S = 15 * 60          # longer videos are never used as filler
LATE_OK_S = 60                 # a show that runs up to a minute past the hour: the next one simply starts then
CARD_MIN_S = 5                 # a smaller leftover is added to the last item instead
ALIGN_CHOICES = (15, 30, 60)
BREAK_MIN_SHOW_S = 15 * 60     # breaks inside shows: only shows at least this long get one
BREAK_MIN_GAP_S = 120          # ...and only when there are at least two minutes to share out
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
            if c.get("starts") in ALIGN_CHOICES:
                rules["_align"] = int(c["starts"])        # shows start on the quarter/half hour or the hour
                if c.get("breaks"):
                    rules["_breaks"] = True               # ...with breaks of shorts inside the shows
            if isinstance(c.get("filler"), list) and c["filler"]:
                rules["_filler"] = [str(x) for x in c["filler"]]   # only these Shorts subfolders / tags
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


# ---------- clean start times ----------
def is_short(m):
    """Filler: anything in the Shorts folder, and free classic cartoons, up to 15 minutes."""
    if not 0 < (m["runtime_s"] or 0) <= SHORT_MAX_S:
        return False
    f = str(m["franchise"] or "").lower()
    if f == SHORTS_FOLDER:
        return True
    return f == "free movies" and "cartoon" in {str(t).lower() for t in json.loads(m["tags"] or "[]")}


def shorts_pool(conn, only=None):
    """The shorts a channel may use, in a fixed order. `only`: names of Shorts subfolders or tags to keep to."""
    rows = [r for r in conn.execute("SELECT * FROM media WHERE available=1 AND verified=1 AND playable=1 ORDER BY id")
            if is_short(r)]
    if only:
        want = {str(x).lower() for x in only}
        rows = [r for r in rows if str(r["series"] or "").lower() in want
                or want & {str(t).lower() for t in json.loads(r["tags"] or "[]")}] or rows
    return rows


def next_start(t, minutes, z):
    """The first quarter/half/whole hour (local time) at or after t - or t itself when that is under a minute late."""
    step = minutes * 60
    off = int(dt.datetime.fromtimestamp(t, z).utcoffset().total_seconds())
    late = (t + off) % step
    if late == 0 or late <= LATE_OK_S:
        return t
    return t + step - late


def chapter_marks(conn, m):
    """Chapter starts of a video (cached in the database; read with ffprobe the first time)."""
    r = conn.execute("SELECT marks FROM chapters WHERE media_id=?", (m["id"],)).fetchone()
    if r is not None:
        try:
            return json.loads(r["marks"] or "[]")
        except ValueError:
            return []
    from . import library
    marks = library.chapter_starts(m["path"]) if m["path"] else None
    if marks is None:
        return []                               # no ffprobe / unreadable: midpoints are used, nothing is cached
    conn.execute("INSERT OR REPLACE INTO chapters(media_id,marks) VALUES(?,?)", (m["id"], json.dumps(marks)))
    return marks


def break_points(runtime, marks):
    """Where the breaks go inside a show: one in the middle (two for shows of 50 minutes or more), moved to the
    nearest chapter start when there is one close by, never in the first or last 10%."""
    n = 2 if runtime >= 50 * 60 else 1
    out = []
    for k in range(1, n + 1):
        want = runtime * k / (n + 1)
        near = [c for c in marks if runtime * 0.1 <= c <= runtime * 0.9 and abs(c - want) <= runtime * 0.15]
        t = min(near, key=lambda c: abs(c - want)) if near else want
        t = int(round(t))
        if not out or t - out[-1] >= 120:
            out.append(t)
    return out


def pick_shorts(pool, budget, after):
    """Whole shorts (going round the pool after `after`) that fit in `budget` seconds: (list, last id used)."""
    if not pool or budget <= 0:
        return [], after
    ids = [r["id"] for r in pool]
    first = ids.index(after) + 1 if after in ids else 0
    got = []
    for k in range(len(pool)):
        m = pool[(first + k) % len(pool)]
        d = max(1, math.ceil(m["runtime_s"]))
        if d <= budget:
            got.append(m)
            budget -= d
            after = m["id"]
        if budget < CARD_MIN_S:
            break
    return got, after


def fill_gap(conn, ch_id, start, until, pool, after, card_media):
    """Fill [start, until) with whole shorts that fit (going round the pool, starting after `after`), then an
    "Up next" card for `card_media`. Returns the id of the last short used (or `after`)."""
    gap = until - start
    if gap <= 0:
        return after
    ids = [r["id"] for r in pool]
    first = ids.index(after) + 1 if after in ids else 0
    last_start = None
    for k in range(len(pool)):
        if gap < CARD_MIN_S:
            break
        m = pool[(first + k) % len(pool)]
        d = max(1, math.ceil(m["runtime_s"]))
        if d <= gap:
            conn.execute("INSERT INTO slots(channel_id,start,end,media_id,cycle,pl) VALUES(?,?,?,?,0,?)",
                         (ch_id, start, start + d, m["id"], SHORTS))
            last_start, after = start, m["id"]
            start, gap = start + d, gap - d
    if gap >= CARD_MIN_S or (gap > 0 and last_start is None and card_media is not None):
        conn.execute("INSERT INTO slots(channel_id,start,end,media_id,cycle,pl) VALUES(?,?,?,?,0,?)",
                     (ch_id, start, until, card_media if card_media is not None else after, CARD))
    elif gap > 0 and last_start is not None:
        conn.execute("UPDATE slots SET end=? WHERE channel_id=? AND start=?", (until, ch_id, last_start))
    return after


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
    rng = random.Random(f"{ch['id']}:{key}:{cycle}")              # deterministic per (channel, block, cycle)
    if mode == "shuffle":
        rng.shuffle(rows)
    elif mode in ("mixed", "balanced"):
        rows = mix_shows(rows, rng, cycle, balanced=mode == "balanced")
    cache[(key, cycle)] = (rows, [r["id"] for r in rows])
    return cache[(key, cycle)]


def mix_shows(rows, rng, cycle=0, balanced=False):
    """Shows in a random mix, but each show's episodes still in order (films count as a show of their own).
    balanced: every show gets about the same number of turns per round - a big show plays its next few episodes
    each round (as many as a typical show on the channel has, at least 3) instead of swamping the small ones."""
    groups, order = {}, []
    for r in rows:
        k = ("s", str(r["franchise"] or "").lower(), str(r["series"]).lower()) if r["series"] else ("m", r["id"])
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(r)
    lists = [groups[k] for k in order]
    if balanced and lists:
        sizes = sorted(len(g) for g in lists)
        share = max(3, sizes[len(sizes) // 2])
        cut = []
        for g in lists:
            if len(g) <= share:
                cut.append(g)
            else:                              # this round's part of a big show, carrying on round after round
                a = (cycle * share) % len(g)
                cut.append([g[(a + i) % len(g)] for i in range(share)])
        lists = cut
    out, pos = [], [0] * len(lists)
    left = sum(len(g) for g in lists)
    while left:                                # pick a show at random, weighted by what it has left: an even spread
        x = rng.randrange(left)
        for i, g in enumerate(lists):
            n = len(g) - pos[i]
            if x < n:
                out.append(g[pos[i]])
                pos[i] += 1
                break
            x -= n
        left -= 1
    return out


def _month_of(r):
    """The month a seasonal video belongs to (folder "December", "Halloween"...), else 0."""
    for t in json.loads(r["tags"] or "[]"):
        if str(t).startswith("month:"):
            try:
                return int(str(t)[6:])
            except ValueError:
                return 0
    return 0


def _next(conn, ch, plan, key, last_media, cycle, cache, skip=frozenset(), month=0):
    """Next item after `last_media`, passing over anything in `skip` (already watched) while something else is left.
    Seasonal videos (in a "December" or "Halloween" folder) are passed over outside their month."""
    rows, ids = _playlist(conn, ch, plan, key, cycle, cache)
    if not rows:
        return None
    off = {r["id"] for r in rows if _month_of(r) not in (0, month)} if month else set()
    if off:
        if len(off) == len(rows):                         # only out-of-season videos: nothing to show now
            return None
        skip = set(skip) | off
    idx = 0 if last_media is None or last_media not in ids else ids.index(last_media) + 1
    cyc = cycle
    for _ in range(2):
        rows, ids = _playlist(conn, ch, plan, key, cyc, cache)
        for i in range(idx, len(rows)):
            if rows[i]["id"] not in skip:
                return rows[i], cyc
        cyc, idx = cyc + 1, 0
    if skip and skip != off:                   # everything has been seen: just carry on in order (still in season)
        return _next(conn, ch, plan, key, last_media, cycle, cache, frozenset(off))
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
        align = plan[0].get("_align") if plan[0].get("_align") in ALIGN_CHOICES else None
        breaks = bool(plan[0].get("_breaks"))
        fill_state = {"pool": None, "last": None}

        def load_pool():
            if fill_state["pool"] is None:
                fill_state["pool"] = shorts_pool(conn, plan[0].get("_filler"))
                r0 = conn.execute("SELECT media_id FROM slots WHERE channel_id=? AND pl=? ORDER BY start DESC LIMIT 1",
                                  (ch["id"], SHORTS)).fetchone()
                fill_state["last"] = r0["media_id"] if r0 else None
            return fill_state["pool"]

        def split_for_breaks(s0, e0, m):
            """The show cut into parts with shorts in between, using part of the time up to the clean start
            (the rest stays for the shorts and card after it). None when no break fits."""
            dur = e0 - s0
            gap = next_start(e0, align, z) - e0
            if dur < BREAK_MIN_SHOW_S or gap < BREAK_MIN_GAP_S:
                return None
            pool = load_pool()
            if not pool:
                return None
            cuts = break_points(dur, chapter_marks(conn, m))
            share = gap // (len(cuts) + 1)          # each break gets an equal share; what is left goes after the show
            parts, t, seek, last = [], s0, 0, fill_state["last"]
            for c in cuts:
                shorts, last2 = pick_shorts(pool, share, last)
                if not shorts:
                    continue
                parts.append((t, t + (c - seek), seek, ""))
                t += c - seek
                for sm in shorts:
                    d = max(1, math.ceil(sm["runtime_s"]))
                    parts.append((t, t + d, sm["id"], SHORTS))   # for a short, the 3rd value is its media id
                    t += d
                seek, last = c, last2
            if not parts:
                return None
            parts.append((t, t + (dur - seek), seek, ""))
            fill_state["last"] = last
            return parts

        def pad(t, fallback_media):
            """Fill from t to the next clean start time; returns that time."""
            b = next_start(t, align, z)
            if b <= t:
                return t
            bw = dt.datetime.fromtimestamp(b, z)
            nb = block_at(blocks, bw) if blocks else None
            nkey = nb["name"] if nb else ""
            peek = _next(conn, ch, plan, nkey, *where_was(nkey), cache, skip, bw.month) or \
                _next(conn, ch, plan, "", *where_was(""), cache, skip, bw.month)
            load_pool()
            fill_state["last"] = fill_gap(conn, ch["id"], t, b, fill_state["pool"], fill_state["last"],
                                          peek[0]["id"] if peek else fallback_media)
            return b

        def where_was(key):                       # (last media, cycle) for a playlist, from what is already stored
            if key not in pos:
                r = conn.execute("SELECT media_id,cycle FROM slots WHERE channel_id=? AND pl=? ORDER BY start DESC LIMIT 1",
                                 (ch["id"], key)).fetchone()
                pos[key] = (r["media_id"], r["cycle"]) if r else (None, 0)
                mode = next((b["mode"] for b in blocks if b["name"] == key), None) or ch["mode"] if key else ch["mode"]
                if resume and smart and mode not in ("shuffle", "mixed", "balanced"):   # back to the first unwatched episode
                    pos[key] = (None, pos[key][1])
            return pos[key]

        if align and last is not None and start == last["end"] and start < now + horizon_s:
            start = pad(start, last["media_id"])      # e.g. carrying on after a short, or the setting was just switched on
        while start < now + horizon_s and added < MAX_SLOTS_PER_RUN:
            when = dt.datetime.fromtimestamp(start, z)
            b = block_at(blocks, when) if blocks else None
            key = b["name"] if b else ""
            r = _next(conn, ch, plan, key, *where_was(key), cache, skip, when.month)
            if r is None and key:                 # a block with nothing to show falls back to normal programming
                key = ""
                r = _next(conn, ch, plan, key, *where_was(key), cache, skip, when.month)
            if r is None:
                # nothing this channel can show right now (e.g. only Christmas videos in March): shorts instead of
                # dead air, while there are any; the channel's own videos come back as soon as there is something
                pool = load_pool() if conn.execute("SELECT 1 FROM slots WHERE channel_id=? LIMIT 1", (ch["id"],)).fetchone() \
                    or _playlist(conn, ch, plan, "", 0, cache)[0] else []
                if not pool:
                    break
                ids = [p["id"] for p in pool]
                sm = pool[(ids.index(fill_state["last"]) + 1) % len(pool) if fill_state["last"] in ids else 0]
                end = start + max(1, math.ceil(sm["runtime_s"]))
                conn.execute("INSERT INTO slots(channel_id,start,end,media_id,cycle,pl) VALUES(?,?,?,?,0,?)",
                             (ch["id"], start, end, sm["id"], SHORTS))
                fill_state["last"], start, added = sm["id"], end, added + 1
                continue
            m, cycle = r
            dur = max(1, math.ceil(m["runtime_s"]))
            end = start + dur
            if blocks and not key:                # cut regular programming where a block begins
                cut = _block_start_within(blocks, start, end, z)
                if cut:
                    end = cut
            parts = split_for_breaks(start, end, m) if align and breaks and end - start == dur else None
            if parts:
                for p_start, p_end, p_seek, p_pl in parts:
                    conn.execute("INSERT INTO slots(channel_id,start,end,media_id,cycle,pl,seek) VALUES(?,?,?,?,?,?,?)",
                                 (ch["id"], p_start, p_end, p_seek if p_pl == SHORTS else m["id"],
                                  0 if p_pl == SHORTS else cycle, key if p_pl != SHORTS else SHORTS, 0 if p_pl == SHORTS else p_seek))
                end = parts[-1][1]
            else:
                conn.execute("INSERT INTO slots(channel_id,start,end,media_id,cycle,pl) VALUES(?,?,?,?,?,?)",
                             (ch["id"], start, end, m["id"], cycle, key))
            pos[key] = (m["id"], cycle)
            if smart:
                skip.add(m["id"])
            if align:
                end = pad(end, m["id"])
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
        "m.plot,m.runtime_s,s.pl,s.seek FROM slots s JOIN media m ON m.id=s.media_id ")


def slot_dict(row, tz):
    if row is None:
        return None
    z = get_tz(tz)
    d = dict(row)
    d["start_local"] = dt.datetime.fromtimestamp(d["start"], z).isoformat()
    d["end_local"] = dt.datetime.fromtimestamp(d["end"], z).isoformat()
    pl = d.get("pl") or ""
    d["block"] = "" if pl.startswith("~") else pl   # "~filler" = slots made by an older version
    d["filler"] = "short" if pl == SHORTS else "card" if pl == CARD else ""
    d["seek"] = int(d.get("seek") or 0)                 # a part after a break starts this far into the video
    # the slot ends before the video does (a break follows): players must switch over at the end of the slot
    d["cut"] = bool(d["seek"]) or (not pl.startswith("~") and (d["end"] - d["start"]) < (d.get("runtime_s") or 0) - 2)
    if pl == CARD:                       # an "Up next" card: no video, a picture and the name of what is next
        d["card"] = True
        nl = d.get("title") or ""
        if d.get("series"):
            nl = f"{d['series']} S{d.get('season') or 0}E{d.get('episode') or 0}" + (f" - {d['title']}" if d.get("title") else "")
        d["next_title"] = nl
        d["title"] = "Up next"
        d["series"], d["season"], d["episode"] = "", 0, 0
    d["source"] = "generated"   # virtual-channel schedule, never an official broadcast listing
    return d


def merge_breaks(slots):
    """For the guide: a show cut by breaks is listed once, from its first part to its last (the shorts in between
    are inside it), like a real TV guide. `slots` are slot dicts of one channel in time order."""
    out = []
    for d in slots:
        if d.get("seek"):
            i = len(out) - 1
            while i >= 0 and out[i].get("filler") == "short":
                i -= 1
            if i >= 0 and out[i]["media_id"] == d["media_id"] and not out[i].get("filler"):
                show = dict(out[i], end=d["end"], end_local=d["end_local"], cut=False)
                out[i:] = [show]
                continue
        out.append(d)
    return out


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
