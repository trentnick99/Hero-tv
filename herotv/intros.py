"""Finds the intro (theme song) and the credits of TV episodes by themselves - the way Jellyfin's Intro Skipper does:
the stretch of sound that two episodes of the same show have in common near the start is the intro, and near the
end the credits. Then on demand (PC, phones, Roku) the intro is skipped and the credits go straight on to the next
episode - unless you set your own points for the show with J / E, which always win.

How: ffmpeg reads the first minutes and the last minutes of the sound, split into four pitch bands, a level per
quarter second. Each moment becomes a small code (which band is louder than the next, which got louder than a
moment ago). Two episodes are compared code by code; a long run of matching codes (15 seconds or more) is the theme.
Runs in the background at low priority, a few episodes at a time; results are kept in the database."""
import os
import re
import subprocess
import threading
import time

FRAME_S = 0.256                      # one code per quarter second (2048 samples at 8 kHz)
RATE = 8000
INTRO_WINDOW_S = 600                 # look for the intro in the first 10 minutes (at most 40% of the episode)
CREDITS_WINDOW_S = 300               # and for the credits in the last 5 minutes
MIN_MATCH_S = 15
MAX_INTRO_S = 150
GAP_FRAMES = 8                       # small differences (two seconds) inside a match are allowed
WINDOW_FRAMES = 16                   # matching is judged over 4-second stretches...
MATCH_RATE = 0.85                    # ...of which this much has to match
CHANGE_MASK = 0xFF                   # the low 8 bits of a code: which bands got louder (all 0 = a steady sound)
SILENT_DB = -55.0
RECHECK_S = 7 * 86400                # episodes where nothing was found are tried again after a week

SCHEMA = """CREATE TABLE IF NOT EXISTS intros(media_id INTEGER PRIMARY KEY, intro_start REAL DEFAULT 0,
            intro_end REAL DEFAULT 0, credits REAL DEFAULT 0, checked INTEGER DEFAULT 0)"""
_lock = threading.Lock()
_state = {"running": False, "done": 0, "found": 0}


def ensure(conn):
    conn.execute(SCHEMA)


# ---------- sound -> codes ----------
BANDS = (150, 300, 500, 800, 1200, 1800, 2600, 3400)   # centre of each pitch band (Hz)


def _cmd(exe, path, start, length):
    mono = "aformat=sample_fmts=fltp:channel_layouts=mono"
    n = len(BANDS)
    parts = [f"[0:a:0]{mono},aresample=8000,asplit={n}" + "".join(f"[s{i}]" for i in range(n))]
    for i, f in enumerate(BANDS):
        parts.append(f"[s{i}]bandpass=f={f}:width_type=q:width=2.5,{mono}[b{i}]")
    parts.append("".join(f"[b{i}]" for i in range(n)) + f"amerge=inputs={n},asetnsamples=n=2048:p=0,"
                 "astats=metadata=1:reset=1:measure_perchannel=RMS_level:measure_overall=none,ametadata=mode=print:file=-")
    return [exe, "-hide_banner", "-v", "error", "-nostdin", "-ss", f"{max(0.0, start):.2f}", "-t", f"{length:.2f}",
            "-i", path, "-vn", "-filter_complex", ";".join(parts), "-f", "null", "-"]


_LINE = re.compile(r"lavfi\.astats\.(\d+)\.RMS_level=(-?[\d.]+|-?inf)")


def parse_levels(text):
    """ffmpeg's printout -> [[band levels in dB] per frame]."""
    n = len(BANDS)
    frames, cur = [], {}
    for line in text.splitlines():
        if line.startswith("frame:"):
            if len(cur) == n:
                frames.append([cur[i] for i in range(1, n + 1)])
            cur = {}
            continue
        m = _LINE.search(line)
        if m:
            v = m.group(2)
            cur[int(m.group(1))] = -120.0 if "inf" in v else float(v)
    if len(cur) == n:
        frames.append([cur[i] for i in range(1, n + 1)])
    return frames


def codes(levels):
    """[[dB per band]] -> list of 15-bit codes (None for silence, which never counts as a match)."""
    out, prev = [], None
    for lv in levels:
        if max(lv) < SILENT_DB:
            out.append(None)
            prev = lv
            continue
        c = 0
        for i in range(len(lv) - 1):                     # the shape of the sound: which band is louder
            c = (c << 1) | (lv[i] > lv[i + 1])
        for i in range(len(lv)):                         # and how it moves: which band got louder
            c = (c << 1) | (prev is not None and lv[i] > prev[i] + 1.0)
        out.append(c)
        prev = lv
    return out


def read_codes(exe, path, start, length, run=None, low_priority=True):
    from . import tools
    flags = dict(tools.HIDE)
    if low_priority and os.name == "nt":
        flags["creationflags"] = flags.get("creationflags", 0) | 0x00004000   # BELOW_NORMAL_PRIORITY_CLASS
    try:
        r = (run or subprocess.run)(_cmd(exe, path, start, length), capture_output=True, text=True, timeout=600, **flags)
    except (OSError, subprocess.SubprocessError):
        return None
    if getattr(r, "returncode", 0) != 0 and not r.stdout:
        return None
    return codes(parse_levels(r.stdout))


# ---------- comparing two episodes ----------
def _bits(x):
    return bin(x).count("1")


def best_match(a, b, min_frames=None):
    """The longest stretch the two code lists have in common: (a_start, a_end, b_start, b_end) in frames, or None.
    Candidate alignments come from runs of three identical codes; each is then followed with some tolerance."""
    min_frames = min_frames or int(MIN_MATCH_S / FRAME_S)
    index = {}
    for j in range(len(b) - 2):
        k = (b[j], b[j + 1], b[j + 2])
        if None not in k:
            index.setdefault(k, []).append(j)
    votes = {}
    for i in range(len(a) - 2):
        k = (a[i], a[i + 1], a[i + 2])
        if None in k:
            continue
        for j in index.get(k, ()):
            votes[i - j] = votes.get(i - j, 0) + 1
    best = None
    for d, n in sorted(votes.items(), key=lambda x: -x[1])[:12]:
        if n < min_frames // 6:
            break
        lo, hi = max(0, d), min(len(a), len(b) + d)
        # per moment: 1 = the same, 0 = different, None = says nothing (silence, or a steady sound that does not
        # change - steady hum or noise looks alike everywhere, so it neither proves nor breaks a match)
        ok = []
        for i in range(lo, hi):
            x, y = a[i], b[i - d]
            if x is None or y is None or not (x & CHANGE_MASK or y & CHANGE_MASK):
                ok.append(None)
            else:                                      # the same, and moving the same way (not just both steady)
                ok.append(1 if _bits(x ^ y) <= 2 and x & y & CHANGE_MASK else 0)
        # a real match keeps matching: in every 4-second stretch at least half the moments say something, and 85% of
        # those are the same (ordinary sound matches now and then by chance)
        w = WINDOW_FRAMES
        good = [False] * len(ok)
        said = [0] * (len(ok) + 1)
        same = [0] * (len(ok) + 1)
        for q, v in enumerate(ok):
            said[q + 1] = said[q] + (v is not None)
            same[q + 1] = same[q] + (v == 1)
        for k in range(len(ok) - w + 1):
            n_said = said[k + w] - said[k]
            if n_said >= w // 2 and same[k + w] - same[k] >= MATCH_RATE * n_said:
                for q in range(k, k + w):
                    good[q] = True
        k = 0
        while k < len(good):
            if not good[k]:
                k += 1
                continue
            e, miss = k, 0
            while e + 1 < len(good) and (good[e + 1] or miss < GAP_FRAMES):
                miss = 0 if good[e + 1] else miss + 1
                e += 1
            while e > k and ok[e] != 1:                 # the match starts and ends on moments that really match
                e -= 1
            while k < e and ok[k] != 1:
                k += 1
            if e + 1 - k >= min_frames and (best is None or e + 1 - k > best[1] - best[0]):
                best = (lo + k, lo + e + 1, lo + k - d, lo + e + 1 - d)
            k = e + 1
    return best


def find_pair(exe, ep_a, ep_b, run=None):
    """Intro and credits of two episodes of one show: {id: {"intro_start","intro_end","credits"}} (zeros = none)."""
    res = {ep_a["id"]: {"intro_start": 0.0, "intro_end": 0.0, "credits": 0.0},
           ep_b["id"]: {"intro_start": 0.0, "intro_end": 0.0, "credits": 0.0}}
    wa = min(INTRO_WINDOW_S, (ep_a["runtime_s"] or 0) * 0.4)
    wb = min(INTRO_WINDOW_S, (ep_b["runtime_s"] or 0) * 0.4)
    if wa >= MIN_MATCH_S and wb >= MIN_MATCH_S:
        ca, cb = read_codes(exe, ep_a["path"], 0, wa, run), read_codes(exe, ep_b["path"], 0, wb, run)
        m = best_match(ca, cb) if ca and cb else None
        if m and (m[1] - m[0]) * FRAME_S <= MAX_INTRO_S:
            res[ep_a["id"]].update(intro_start=round(m[0] * FRAME_S, 1), intro_end=round(m[1] * FRAME_S, 1))
            res[ep_b["id"]].update(intro_start=round(m[2] * FRAME_S, 1), intro_end=round(m[3] * FRAME_S, 1))
    sa = max(0.0, (ep_a["runtime_s"] or 0) - CREDITS_WINDOW_S)
    sb = max(0.0, (ep_b["runtime_s"] or 0) - CREDITS_WINDOW_S)
    if (ep_a["runtime_s"] or 0) > 4 * CREDITS_WINDOW_S and (ep_b["runtime_s"] or 0) > 4 * CREDITS_WINDOW_S:
        ca = read_codes(exe, ep_a["path"], sa, CREDITS_WINDOW_S, run)
        cb = read_codes(exe, ep_b["path"], sb, CREDITS_WINDOW_S, run)
        m = best_match(ca, cb) if ca and cb else None
        if m:
            res[ep_a["id"]]["credits"] = round(sa + m[0] * FRAME_S, 1)
            res[ep_b["id"]]["credits"] = round(sb + m[2] * FRAME_S, 1)
    return res


# ---------- which episodes, and keeping the results ----------
def todo(conn, now=None, limit=6):
    """Episodes to check next: in shows with at least two episodes, not checked yet (or nothing found a week ago)."""
    now = int(now or time.time())
    ensure(conn)
    return conn.execute(
        "SELECT m.* FROM media m LEFT JOIN intros i ON i.media_id=m.id WHERE m.available=1 AND m.verified=1 "
        "AND m.series<>'' AND m.runtime_s>=300 AND (i.media_id IS NULL OR (i.intro_end=0 AND i.credits=0 AND i.checked<?)) "
        "AND (SELECT COUNT(*) FROM media x WHERE x.series=m.series AND COALESCE(x.franchise,'')=COALESCE(m.franchise,'') "
        "AND x.available=1 AND x.id<>m.id)>0 ORDER BY m.franchise,m.series,m.season,m.episode LIMIT ?",
        (now - RECHECK_S, limit)).fetchall()


def partner(conn, ep):
    """The episode to compare with: the next one in the show, else the one before."""
    q = ("SELECT * FROM media WHERE available=1 AND verified=1 AND series=? AND COALESCE(franchise,'')=? AND id<>? "
         "AND runtime_s>=300 ")
    args = (ep["series"], ep["franchise"] or "", ep["id"])
    key = (ep["season"] or 0, ep["episode"] or 0)
    nxt = conn.execute(q + "AND (COALESCE(season,0),COALESCE(episode,0))>(?,?) ORDER BY season,episode LIMIT 1", args + key).fetchone()
    return nxt or conn.execute(q + "ORDER BY season DESC,episode DESC LIMIT 1", args).fetchone()


def save(conn, results, now=None):
    now = int(now or time.time())
    ensure(conn)
    for mid, r in results.items():
        old = conn.execute("SELECT intro_end,credits FROM intros WHERE media_id=?", (mid,)).fetchone()
        if old and (old["intro_end"] or old["credits"]) and not (r["intro_end"] or r["credits"]):
            continue                                       # keep an earlier find over an empty retry
        conn.execute("INSERT OR REPLACE INTO intros(media_id,intro_start,intro_end,credits,checked) VALUES(?,?,?,?,?)",
                     (mid, r["intro_start"], r["intro_end"], r["credits"], now))
    conn.commit()


def for_media(conn, mid):
    ensure(conn)
    r = conn.execute("SELECT intro_start,intro_end,credits FROM intros WHERE media_id=?", (mid,)).fetchone()
    return dict(r) if r and (r["intro_end"] or r["credits"]) else None


def run_once(conn, exe, limit=6, run=None):
    """Check a few episodes. Returns how many were checked."""
    n = 0
    for ep in todo(conn, limit=limit):
        other = partner(conn, ep)
        if other is None or not os.path.isfile(ep["path"] or "") or not os.path.isfile(other["path"] or ""):
            save(conn, {ep["id"]: {"intro_start": 0, "intro_end": 0, "credits": 0}})
            n += 1
            continue
        res = find_pair(exe, ep, other, run)
        save(conn, res)
        n += 1
        with _lock:
            _state["done"] += 1
            _state["found"] += 1 if res[ep["id"]]["intro_end"] or res[ep["id"]]["credits"] else 0
    return n


def enabled():
    from . import settings_api
    return settings_api._load().get("auto_intros", True) is not False


def status(conn):
    ensure(conn)
    total = conn.execute("SELECT COUNT(*) FROM media m WHERE m.available=1 AND m.series<>'' AND m.runtime_s>=300").fetchone()[0]
    checked = conn.execute("SELECT COUNT(*) FROM intros i JOIN media m ON m.id=i.media_id WHERE m.available=1").fetchone()[0]
    found = conn.execute("SELECT COUNT(*) FROM intros i JOIN media m ON m.id=i.media_id WHERE m.available=1 "
                         "AND (i.intro_end>0 OR i.credits>0)").fetchone()[0]
    return {"on": enabled(), "episodes": total, "checked": min(checked, total), "found": found, "running": _state["running"]}


def start_background(cfg, connect, every=20, idle=900):
    """Check episodes a few at a time while HERO TV runs (low priority, pauses between batches)."""
    from . import tools

    def loop():
        time.sleep(120)                                   # let HERO TV start up first
        while True:
            pause = idle
            try:
                exe = tools.find_tool("ffmpeg")
                if exe and enabled():
                    c = connect(cfg.db_path)
                    try:
                        _state["running"] = True
                        if run_once(c, exe, limit=4):
                            pause = every
                    finally:
                        _state["running"] = False
                        c.close()
            except Exception:
                pass
            time.sleep(pause)
    threading.Thread(target=loop, name="herotv-intros", daemon=True).start()
