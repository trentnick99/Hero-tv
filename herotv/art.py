"""Cover art and descriptions (poster, plot, cast, rating) for your titles, from TMDB (themoviedb.org).

Needs a free TMDB key (Set-Poster-Key.bat). Only the TITLE and YEAR of each video are sent to TMDB, one at a time, in the
background. Results are saved on this PC (poster pictures in a folder beside the database), so each title is looked up once.
Your own picture always wins: put  <video name>.jpg  or .png next to a video (for a show: poster.jpg in its folder).

This product uses the TMDB API but is not endorsed or certified by TMDB."""
import hashlib
import json
import os
import re
import threading
import time
import urllib.parse

from . import config, net

API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w342"
UA = "HeroTV/1.0 (personal home media player)"
RETRY_MISS_S = 7 * 86400
_worker = {"thread": None, "kick": threading.Event(), "lock": threading.Lock()}


# ---------- the only functions that touch the network (tests replace them) ----------
def fetch_json(path, params, key, timeout=20):
    import urllib.request
    params = dict(params)
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if len(key) > 40:                      # the long "read access token"
        headers["Authorization"] = "Bearer " + key
    else:                                  # the short "API key"
        params["api_key"] = key
    req = urllib.request.Request(API + path + "?" + urllib.parse.urlencode(params), headers=headers)
    with net.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_bytes(url, timeout=30):
    import urllib.request
    with net.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
        return r.read()


# ---------- settings ----------
def api_key():
    try:
        k = json.loads(config.settings_file().read_text(encoding="utf-8-sig")).get("tmdb_key")
        return k.strip() if isinstance(k, str) and k.strip() else ""
    except (OSError, ValueError, AttributeError):
        return ""


def norm(text):
    t = re.sub(r"[^a-z0-9]+", " ", str(text or "").lower().replace("&", " and ")).strip()
    return re.sub(r"^(the|a|an) ", "", t)


_JUNK = (r"complete|seasons?\s*\d+(?:\s*(?:to|-)\s*\d+)?|s\d{1,2}(?:e\d{1,3})?|ep\.?\s*\d+(?:\s*-\s*\d+)?|\d{3,4}p|blu-?ray|web-?dl|webrip|tvrip|hdtv|x26[45]|"
         r"h\.?26[45]|hevc|10\s*bit|dual audio|hindi|english|vegamovies\S*|60\s*fps|uncut|esub|dvdrip|brrip")
_JUNK_RE = re.compile(r"\b(?:" + _JUNK + r")\b.*$", re.I)
# a folder that is named for a show but is really another one (the lookup only; the folder and the library stay as they are)
ALIASES = {"dragon ball": "Dragon Ball Super"}
NOT_SHOW_FOLDERS = {"inbox", "movies", "films", "tv", "shows", "videos", "downloads", ""}


def _g(row, name):
    try:
        return row[name]
    except (KeyError, IndexError):
        return ""


def clean_show(name):
    """'Invincible season 1' -> ('Invincible', None); 'Spider-Man The Animated Series 1994 Complete Seasons 1 to 5 TVRip x264 [i_c]' ->
    ('Spider-Man The Animated Series', 1994): release leftovers cut off, a year kept as a hint."""
    t = re.sub(r"\[[^\]]*\]", " ", str(name or ""))
    t = _JUNK_RE.sub(" ", t)
    year = None
    m = re.search(r"[\s.(]((?:19|20)\d{2})\)?\s*$", t)
    if m and len(t[:m.start()].split()) >= 2:
        year, t = int(m.group(1)), t[:m.start()]
    t = re.sub(r"\s+", " ", t).strip(" -._(")
    return (t or str(name or "").strip()), year


def clean_movie(title, year):
    """'[60FPS] Spider-Man Into the Spider-Verse' -> that without the tag; 'Avengers Endgame 2019 Hindi English' -> ('Avengers Endgame', 2019)."""
    t = re.sub(r"\[[^\]]*\]", " ", str(title or ""))
    m = re.match(r"^(.*?)\s+((?:19|20)\d{2})\s+(?:" + _JUNK + r")\b.*$", t, re.I)
    if m:
        t, year = m.group(1), year or int(m.group(2))
    else:
        t = _JUNK_RE.sub(" ", t) if re.search(r"\b(?:hindi|english|dual audio|vegamovies)\b", t, re.I) else t
    t = re.sub(r"\s+", " ", t).strip(" -._")
    return (t or str(title or "").strip()), year


def _alias(name):
    extra = {}
    try:
        extra = json.loads(config.settings_file().read_text(encoding="utf-8-sig")).get("art_aliases") or {}
    except (OSError, ValueError, AttributeError):
        pass
    k = norm(name)
    for src in (extra, ALIASES):
        for a, b in (src or {}).items():
            if norm(a) == k:
                return str(b)
    return name


def show_of(row):
    """The show a video belongs to for the lookup: its series, or - for loose numbered episodes in a folder named for the show -
    that folder. None for a movie."""
    if _g(row, "series"):
        return clean_show(row["series"])
    ep, fr = _g(row, "episode"), str(_g(row, "franchise") or "").strip()
    if ep and int(ep) > 0 and not _g(row, "season") and norm(fr) not in NOT_SHOW_FOLDERS:
        name, year = clean_show(fr)
        return _alias(name), year
    return None


def key_for(row):
    """(art key, kind, search title, year) for a media row: a show is looked up by its show name, a movie by title + year."""
    sh = show_of(row)
    if sh:
        return "s:" + norm(sh[0]), "tv", sh[0], sh[1]
    t, y = clean_movie(row["title"], row["year"])
    return f"m:{norm(t)}:{y or ''}", "movie", t, y


def poster_dir(cfg):
    return os.path.splitext(cfg.db_path)[0] + "-posters"


def poster_file(cfg, key):
    return os.path.join(poster_dir(cfg), hashlib.md5(key.encode("utf-8", "replace")).hexdigest()[:16] + ".jpg")


# ---------- lookup ----------
MATCH_VERSION = 3                    # older misses are tried again once after the matching got better


def _close(a, b):
    """Two normalised titles that are the same apart from small differences: 'spider man 3' / 'spiderman 3',
    'x men origins wolverine' / 'x men origins   wolverine', 'the dark knight rises' / 'dark knight rises'."""
    if a == b:
        return True
    if a.replace(" ", "") == b.replace(" ", ""):
        return True
    if not a or not b or re.findall(r"\d+", a) != re.findall(r"\d+", b):   # sequel numbers must agree
        return False
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio() >= 0.88


def _pick(results, title, year, kind):
    """TMDB's best result that is really this title: the same name (small differences allowed, sequel numbers must
    match) and, when the file says a year, within a year of it. TMDB lists the likeliest first."""
    want = norm(title)
    date_key = "release_date" if kind == "movie" else "first_air_date"
    exact = close = None
    for r in results or []:
        name = r.get("title") if kind == "movie" else r.get("name")
        names = {norm(name), norm(r.get("original_title" if kind == "movie" else "original_name"))}
        y = int((r.get(date_key) or "0000")[:4] or 0)
        if year and y and abs(y - year) > 1:
            continue
        subs = {norm(x) for nm in (name, r.get("original_title" if kind == "movie" else "original_name")) for x in re.split(r"\s*[:\u2013-]\s+", str(nm or ""))[1:]}
        if want in names:
            exact = exact or r
        elif close is None and any(_close(want, n) for n in names if n):
            close = r
        elif close is None and want in subs and len(want.split()) >= 3:       # 'Bigger Longer and Uncut' = 'South Park: Bigger, Longer & Uncut'
            close = r
        elif close is None and kind == "tv" and year and y == year and any(n and len(n.split()) >= 2 and want.startswith(n + " ") for n in names):
            close = r                                                          # '1994' 'Spider-Man The Animated Series' = TMDB's 'Spider-Man' (1994)
    return exact or close


def lookup(kind, title, year, key, fj=None):
    """Return a dict of details, or None when TMDB has no match. Raises OSError-like errors when the network fails."""
    fj = fj or fetch_json
    params = {"query": title, "include_adult": "false", "language": "en-US"}
    if year:
        params["year" if kind == "movie" else "first_air_date_year"] = year
    res = fj("/search/" + kind, params, key).get("results")
    hit = _pick(res, title, year, kind)
    if hit is None and year:
        params.pop("year", None)
        params.pop("first_air_date_year", None)
        hit = _pick(fj("/search/" + kind, params, key).get("results"), title, year, kind)
    if hit is None:
        return None
    d = fj(f"/{kind}/{hit['id']}", {"append_to_response": "credits,keywords", "language": "en-US"}, key)
    kw = d.get("keywords") or {}
    kw = kw.get("keywords") or kw.get("results") or []          # movies say "keywords", shows say "results"
    cast = [c["name"] for c in (d.get("credits") or {}).get("cast", [])[:6] if c.get("name")]
    runtime = d.get("runtime") or (d.get("episode_run_time") or [0])[0] or 0
    return {"tmdb_id": hit["id"], "kind": kind, "title": d.get("title") or d.get("name") or title,
            "year": int((d.get("release_date") or d.get("first_air_date") or "0")[:4] or 0) or None,
            "overview": d.get("overview") or "", "tagline": d.get("tagline") or "",
            "genres": [g["name"] for g in d.get("genres", [])], "cast": cast, "rating": round(float(d.get("vote_average") or 0), 1),
            "runtime": int(runtime), "poster": d.get("poster_path") or hit.get("poster_path") or "",
            "seasons": [x["season_number"] for x in d.get("seasons") or [] if x.get("season_number")],
            "facts": {"type": "tv" if kind == "tv" else "movie",
                      "companies": [c["name"] for c in d.get("production_companies") or [] if c.get("name")]
                      + [n["name"] for n in d.get("networks") or [] if n.get("name")],
                      "genres": [g["name"] for g in d.get("genres", [])],
                      "keywords": [k["name"] for k in kw if isinstance(k, dict) and k.get("name")],
                      "collection": (d.get("belongs_to_collection") or {}).get("name") or "",
                      "year": int((d.get("release_date") or d.get("first_air_date") or "0")[:4] or 0) or None,
                      "released": d.get("release_date") or d.get("first_air_date") or ""}}


def save(conn, key, data, cfg, fb=None):
    fb = fb or fetch_bytes
    if data and data.get("poster"):
        f = poster_file(cfg, key)
        try:
            os.makedirs(os.path.dirname(f), exist_ok=True)
            blob = fb(IMG + data["poster"])
            with open(f + ".tmp", "wb") as fh:
                fh.write(blob)
            os.replace(f + ".tmp", f)
        except OSError:
            pass
    if data:
        conn.execute("INSERT OR REPLACE INTO art(key,tmdb_id,kind,title,year,overview,tagline,genres,\"cast\",rating,runtime,poster,fetched,miss,facts) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)",
                     (key, data["tmdb_id"], data["kind"], data["title"], data["year"], data["overview"], data["tagline"],
                      json.dumps(data["genres"]), json.dumps(data["cast"]), data["rating"], data["runtime"], data["poster"], int(time.time()),
                      json.dumps(data.get("facts") or {})))
    else:
        conn.execute("INSERT OR REPLACE INTO art(key,kind,fetched,miss) VALUES(?,?,?,1)", (key, "", int(time.time())))
    if data and data.get("kind") == "movie":          # films now know their release date: play them in that order
        for r in conn.execute("SELECT id,title,year,series,season,episode,franchise,ord FROM media WHERE series=''").fetchall():
            if key_for(r)[0] == key and int(r["ord"] or 0) % 10_000_000 == 0:
                o = release_ord(conn, r["title"], r["year"])
                if o:
                    conn.execute("UPDATE media SET ord=? WHERE id=?", (o, r["id"]))
    conn.commit()


def release_ord(conn, title, year):
    """A film's place in its channel from TMDB's release date (Iron Man in May 2008 before The Incredible Hulk in
    June), or its TMDB year when the file name has none. None when TMDB has not been asked yet."""
    k = key_for({"series": "", "title": title, "year": year})[0]
    a = conn.execute("SELECT year,facts,miss FROM art WHERE key=?", (k,)).fetchone()
    if not a or a["miss"]:
        return None
    try:
        rel = str(json.loads(a["facts"] or "{}").get("released") or "")
    except ValueError:
        rel = ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", rel)
    if m and (not year or int(m[1]) == int(year)):
        return int(m[1]) * 10_000_000 + int(m[2]) * 100_000 + int(m[3]) * 1_000
    if not year and a["year"]:
        return int(a["year"]) * 10_000_000
    return None


def pending(conn):
    """[(key, kind, title, year)] for titles with no answer yet (or a miss older than a week)."""
    v = conn.execute("SELECT value FROM prefs WHERE key='art_match'").fetchone()
    if not v or v["value"] != str(MATCH_VERSION):          # better matching: give every earlier miss another go
        conn.execute("DELETE FROM art WHERE miss=1")
        conn.execute("INSERT OR REPLACE INTO prefs(key,value) VALUES('art_match',?)", (str(MATCH_VERSION),))
        conn.commit()
    have = {r["key"]: r for r in conn.execute("SELECT key,miss,fetched FROM art")}
    out, seen = [], set()
    for r in conn.execute("SELECT title,year,series,season,episode,franchise FROM media WHERE available=1 AND verified=1 ORDER BY series,title"):
        k, kind, title, year = key_for(r)
        if k in seen:
            continue
        seen.add(k)
        h = have.get(k)
        if h is None or (h["miss"] and time.time() - (h["fetched"] or 0) > RETRY_MISS_S):
            out.append((k, kind, title, year))
    return out


def fetch_episodes(conn, k, tmdb_id, seasons, key, fj=None, delay=0.25):
    """Every episode's name and description for one show (one call per season), remembered. False when the network failed (try again later)."""
    fj = fj or fetch_json
    for n in seasons:
        try:
            d = fj(f"/tv/{tmdb_id}/season/{n}", {"language": "en-US"}, key)
        except Exception:
            return False
        for e in d.get("episodes") or []:
            conn.execute("INSERT OR REPLACE INTO art_ep(key,season,episode,name,overview,air) VALUES(?,?,?,?,?,?)",
                         (k, int(n), int(e.get("episode_number") or 0), e.get("name") or "", e.get("overview") or "", e.get("air_date") or ""))
        if delay:
            time.sleep(delay)
    conn.execute("INSERT OR REPLACE INTO prefs(key,value) VALUES(?,?)", ("art_eps:" + k, str(int(time.time()))))
    conn.commit()
    return True


def episodes_pass(conn, key, fj=None, delay=0.25, stop=None):
    """Fetch the episode lists of shows that have none yet."""
    done = 0
    have = {r["key"][8:] for r in conn.execute("SELECT key FROM prefs WHERE key LIKE 'art_eps:%'")}
    for r in conn.execute("SELECT key,tmdb_id FROM art WHERE kind='tv' AND miss=0 AND tmdb_id IS NOT NULL").fetchall():
        if r["key"] in have:
            continue
        if stop and stop():
            break
        try:
            d = (fj or fetch_json)(f"/tv/{r['tmdb_id']}", {"language": "en-US"}, key)
        except Exception:
            break
        seasons = [x["season_number"] for x in d.get("seasons") or [] if x.get("season_number")]
        if not fetch_episodes(conn, r["key"], r["tmdb_id"], seasons, key, fj, delay):
            break
        done += 1
    return done


def episode_for(conn, k, row):
    """The TMDB episode a video is: by season and episode number when the file has both, else by its title. None when unknown."""
    try:
        season, ep = int(_g(row, "season") or 0), int(_g(row, "episode") or 0)
    except (TypeError, ValueError):
        season = ep = 0
    if season and ep:
        r = conn.execute("SELECT name,overview FROM art_ep WHERE key=? AND season=? AND episode=?", (k, season, ep)).fetchone()
        if r:
            return r
    want = norm(_g(row, "title"))
    if not want:
        return None
    best = None
    for r in conn.execute("SELECT name,overview FROM art_ep WHERE key=?", (k,)):
        n = norm(r["name"])
        if n == want:
            return r
        if best is None and n and _close(want, n):
            best = r
    return best


def run_pass(conn, cfg, key, fj=None, fb=None, delay=0.25, stop=None):
    """Look up everything still missing. Returns (looked_up, matched). A network failure ends the pass without recording misses."""
    done = hit = 0
    for k, kind, title, year in pending(conn):
        if stop and stop():
            break
        try:
            data = lookup(kind, title, year, key, fj)
        except Exception:
            break                          # offline, wrong key, rate limit: try again later, remember nothing
        save(conn, k, data, cfg, fb)
        done += 1
        hit += bool(data)
        if delay:
            time.sleep(delay)
    try:
        episodes_pass(conn, key, fj, delay, stop)
    except Exception:
        pass
    return done, hit


def start_background(cfg, connect):
    """Fill in art for new titles whenever the library changes (needs a key; does nothing without one)."""
    _worker["kick"].set()
    with _worker["lock"]:
        if _worker["thread"] and _worker["thread"].is_alive():
            return

        def loop():
            while True:
                _worker["kick"].wait(timeout=900)
                _worker["kick"].clear()
                key = api_key()
                if not key:
                    continue
                c = connect(cfg.db_path)
                try:
                    run_pass(c, cfg, key)
                except Exception:
                    pass
                finally:
                    c.close()

        t = threading.Thread(target=loop, daemon=True, name="art")
        _worker["thread"] = t
        t.start()


# ---------- reading ----------
def local_picture(row):
    """A picture you put next to the video: <name>.jpg/.png/-poster.jpg (movies), or poster.jpg / folder.jpg in a show's folder."""
    folder, name = os.path.split(row["path"])
    stem = os.path.splitext(name)[0]
    names = [stem + e for e in (".jpg", ".jpeg", ".png", "-poster.jpg", "-poster.png", ".poster.jpg", ".poster.png")]
    if row["series"]:
        names += ["poster.jpg", "poster.png", "folder.jpg", "folder.png"]
    for n in names:
        f = os.path.join(folder, n)
        if os.path.isfile(f):
            return f
    return None


def folder_show(conn, row):
    """For a video with no number in its name inside a show's folder (Dragon Ball/"His Name is Ginyu.mp4"): that show's art key
    when HERO TV already knows the show from its numbered episodes. None otherwise."""
    fr = str(_g(row, "franchise") or "").strip()
    if not fr or _g(row, "series") or norm(fr) in NOT_SHOW_FOLDERS:
        return None
    k = "s:" + norm(_alias(clean_show(fr)[0]))
    r = conn.execute("SELECT 1 FROM art WHERE key=? AND miss=0", (k,)).fetchone()
    return k if r else None


def info(conn, cfg, row):
    """What the details screen shows for one video."""
    k, kind, title, year = key_for(row)
    a = conn.execute("SELECT * FROM art WHERE key=?", (k,)).fetchone()
    if (not a or a["miss"]) and kind == "movie":
        fk = folder_show(conn, row)                       # an unnumbered episode in a known show's folder
        if fk:
            k, a = fk, conn.execute("SELECT * FROM art WHERE key=?", (fk,)).fetchone()
    got = bool(a and not a["miss"])
    out = {"title": row["title"], "series": row["series"], "year": row["year"], "plot": row["plot"] or "",
           "tagline": "", "genres": [], "cast": [], "rating": 0, "runtime_min": round((row["runtime_s"] or 0) / 60),
           "has_key": bool(api_key()), "poster": bool(local_picture(row)) or (got and os.path.isfile(poster_file(cfg, k))),
           "source": "", "searched": bool(a)}
    if got:
        out.update(tagline=a["tagline"] or "", genres=json.loads(a["genres"] or "[]"), cast=json.loads(a["cast"] or "[]"),
                   rating=a["rating"] or 0, source="TMDB")
        if a["kind"] == "tv":
            try:
                e = episode_for(conn, k, row)
            except Exception:
                e = None
            if e and e["overview"] and not out["plot"]:
                out["plot"], out["episode_title"] = e["overview"], e["name"]
        if not out["plot"]:
            out["plot"] = a["overview"] or ""
        if a["kind"] == "tv" and a["year"]:
            out["year"] = out["year"] or a["year"]
    return out


def picture_path(conn, cfg, row):
    f = local_picture(row)
    if f:
        return f
    k = key_for(row)[0]
    f = poster_file(cfg, k)
    return f if os.path.isfile(f) else None


def stats(conn):
    n = conn.execute("SELECT COUNT(*) FROM art WHERE miss=0").fetchone()[0]
    m = conn.execute("SELECT COUNT(*) FROM art WHERE miss=1").fetchone()[0]
    return {"found": n, "not_found": m, "waiting": len(pending(conn))}



# ---------- facts for sorting new videos onto channels ----------
def facts_for(conn, cfg, stem, key=None, fj=None, fb=None, cached_only=False):
    """What TMDB knows about a video file name (studio, genres, keywords) - or None without a key, when offline, or
    when TMDB does not know the title. Remembered, so each title is looked up once (the poster comes along too)."""
    from . import library
    g = library._guess([stem], stem)
    row = {"series": g["series"], "title": g["title"], "year": g["year"]}
    k, kind, title, year = key_for(row)
    a = conn.execute("SELECT facts,miss FROM art WHERE key=?", (k,)).fetchone()
    if a and a["miss"]:
        return None
    if a and a["facts"] and a["facts"] != "{}":
        return json.loads(a["facts"])
    if cached_only:
        return None
    key = key or api_key()
    if not key:
        return None
    try:
        data = lookup(kind, title, year, key, fj)
    except Exception:
        return None                               # offline or refused: fall back to keywords this time
    save(conn, k, data, cfg, fb)
    return (data or {}).get("facts")


def describe(facts):
    """'Movie, 2016 - Action, Comedy - Marvel Studios' for the Inbox helper."""
    if not facts:
        return ""
    head = ("TV show" if facts.get("type") == "tv" else "Movie") + (f", {facts['year']}" if facts.get("year") else "")
    return "  -  ".join(x for x in (head, ", ".join((facts.get("genres") or [])[:3]), ", ".join((facts.get("companies") or [])[:2])) if x)
