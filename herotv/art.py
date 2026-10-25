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


def key_for(row):
    """(art key, kind, search title, year) for a media row: a show is looked up by its series name, a movie by title + year."""
    if row["series"]:
        return "s:" + norm(row["series"]), "tv", row["series"], None
    return f"m:{norm(row['title'])}:{row['year'] or ''}", "movie", row["title"], row["year"]


def poster_dir(cfg):
    return os.path.splitext(cfg.db_path)[0] + "-posters"


def poster_file(cfg, key):
    return os.path.join(poster_dir(cfg), hashlib.md5(key.encode("utf-8", "replace")).hexdigest()[:16] + ".jpg")


# ---------- lookup ----------
def _pick(results, title, year, kind):
    want = norm(title)
    date_key = "release_date" if kind == "movie" else "first_air_date"
    best = None
    for r in results or []:
        name = r.get("title") if kind == "movie" else r.get("name")
        names = {norm(name), norm(r.get("original_title" if kind == "movie" else "original_name"))}
        if want not in names:
            continue
        y = int((r.get(date_key) or "0000")[:4] or 0)
        if year and y and abs(y - year) > 1:
            continue
        if best is None:
            best = r
    return best


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
        for r in conn.execute("SELECT id,title,year,series,ord FROM media WHERE series=''").fetchall():
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
    have = {r["key"]: r for r in conn.execute("SELECT key,miss,fetched FROM art")}
    out, seen = [], set()
    for r in conn.execute("SELECT title,year,series FROM media WHERE available=1 AND verified=1 ORDER BY series,title"):
        k, kind, title, year = key_for(r)
        if k in seen:
            continue
        seen.add(k)
        h = have.get(k)
        if h is None or (h["miss"] and time.time() - (h["fetched"] or 0) > RETRY_MISS_S):
            out.append((k, kind, title, year))
    return out


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


def info(conn, cfg, row):
    """What the details screen shows for one video."""
    k, kind, title, year = key_for(row)
    a = conn.execute("SELECT * FROM art WHERE key=?", (k,)).fetchone()
    got = bool(a and not a["miss"])
    out = {"title": row["title"], "series": row["series"], "year": row["year"], "plot": row["plot"] or "",
           "tagline": "", "genres": [], "cast": [], "rating": 0, "runtime_min": round((row["runtime_s"] or 0) / 60),
           "has_key": bool(api_key()), "poster": bool(local_picture(row)) or (got and os.path.isfile(poster_file(cfg, k))),
           "source": "", "searched": bool(a)}
    if got:
        out.update(tagline=a["tagline"] or "", genres=json.loads(a["genres"] or "[]"), cast=json.loads(a["cast"] or "[]"),
                   rating=a["rating"] or 0, source="TMDB")
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
