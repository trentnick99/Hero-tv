"""Free-to-use movies and shows from the Internet Archive (archive.org).

Only items that the Internet Archive itself marks as public domain (a "public domain mark" or CC0 licence on the
item) are downloaded. Nothing is streamed from here: files are saved into the "Free Movies" folder inside your
media folder and then play like any other video you own - on their own channel (and on Hero Marathon).

The network calls are small and in one place (`fetch_json`, `download`) so tests can replace them.
"""
import json
import os
import re
import shutil
import time
import urllib.parse
import urllib.request

from . import library, net

UA = "HeroTV/1.0 (personal home media player)"
SEARCH_URL = "https://archive.org/advancedsearch.php"
META_URL = "https://archive.org/metadata/"
DOWNLOAD_URL = "https://archive.org/download/"
DETAILS_URL = "https://archive.org/details/"
FOLDER = "Free Movies"
LOG_NAME = ".free-log.json"
RESERVE_BYTES = 2 * 1024 ** 3            # always leave 2 GB free on the drive
LICENSE_WORDS = ("publicdomain", "/zero/")

_LICENSES = ('licenseurl:"http://creativecommons.org/publicdomain/mark/1.0/" OR '
             'licenseurl:"https://creativecommons.org/publicdomain/mark/1.0/" OR '
             'licenseurl:"http://creativecommons.org/publicdomain/zero/1.0/" OR '
             'licenseurl:"https://creativecommons.org/publicdomain/zero/1.0/"')

# What the menu offers. Editable: config/free-sources.json replaces this list.
DEFAULT_SOURCES = [
    {"name": "Classic cartoons", "query": "collection:classic_cartoons", "tags": ["cartoon", "free"]},
    {"name": "Superhero-era cartoons (Superman, Popeye, Mighty Mouse...)",
     "query": 'title:(superman OR popeye OR "mighty mouse" OR "captain marvel" OR batman) AND collection:classic_cartoons',
     "tags": ["cartoon", "classic", "free"]},
    {"name": "Old sci-fi and horror movies", "query": "collection:SciFi_Horror", "tags": ["scifi", "free"]},
    {"name": "Silent films", "query": "collection:silent_films", "tags": ["silent", "classic", "free"]},
    {"name": "Classic feature films", "query": "collection:feature_films", "tags": ["classic", "free"]},
    {"name": "Classic TV", "query": "collection:classic_tv", "tags": ["tv", "free"]},
]


# ---------- the only two functions that touch the network ----------
def fetch_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with net.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def download(url, dest, expected=0, progress=None, timeout=60):
    """Save url to dest (via dest.part, resuming a partly finished download). Returns the final size."""
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    if expected and have > expected:
        os.remove(part)
        have = 0
    headers = {"User-Agent": UA}
    if have:
        headers["Range"] = f"bytes={have}-"
    req = urllib.request.Request(url, headers=headers)
    with net.urlopen(req, timeout=timeout) as r:
        if have and getattr(r, "status", 200) != 206:       # server ignored the resume request: start again
            have = 0
        with open(part, "ab" if have else "wb") as fh:
            done = have
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, expected)
    size = os.path.getsize(part)
    if expected and size != expected:
        raise IOError(f"download incomplete ({size} of {expected} bytes) - run it again to continue")
    os.replace(part, dest)
    return size


# ---------- helpers ----------
def load_sources(path=None):
    """The menu list: config/free-sources.json when it exists and is valid, else the built-in one."""
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
        out = []
        for i, s in enumerate(data.get("sources", []), 1):
            if not isinstance(s, dict) or not s.get("query"):
                raise ValueError(f"free-sources.json: source {i} needs a \"name\" and a \"query\"")
            out.append({"name": str(s.get("name") or f"Source {i}"), "query": str(s["query"]),
                        "tags": [str(t) for t in s.get("tags", ["free"])]})
        if out:
            return out
    return [dict(s) for s in DEFAULT_SOURCES]


def license_ok(value):
    """True only for an explicit public-domain / CC0 licence url."""
    v = value[0] if isinstance(value, list) and value else value
    return isinstance(v, str) and any(w in v.lower() for w in LICENSE_WORDS)


def build_query(source):
    return f"({source['query']}) AND mediatype:movies AND ({_LICENSES})"


def search(source, rows=40):
    params = [("q", build_query(source)), ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "year"),
              ("fl[]", "licenseurl"), ("fl[]", "downloads"), ("sort[]", "downloads desc"),
              ("rows", str(rows)), ("page", "1"), ("output", "json")]
    j = fetch_json(SEARCH_URL + "?" + urllib.parse.urlencode(params))
    docs = (j.get("response") or {}).get("docs") or []
    return [d for d in docs if d.get("identifier") and license_ok(d.get("licenseurl"))]


_BAD_NAME = re.compile(r"(_thumb|sample|trailer|_cut\b|\.ia\.mp4$)", re.I)


def pick_file(meta, max_bytes):
    """Best browser-playable video file of an item: (name, size) or None. Prefers the Archive's standard H.264
    version, then the biggest one that fits under max_bytes."""
    best = None
    for f in meta.get("files") or []:
        name = f.get("name") or ""
        if not name.lower().endswith((".mp4", ".m4v")) or _BAD_NAME.search(name) or "/" in name:
            continue
        try:
            size = int(f.get("size") or 0)
        except (TypeError, ValueError):
            continue
        if size <= 0 or size > max_bytes:
            continue
        fmt = (f.get("format") or "").lower()
        rank = 0 if fmt == "h.264" else 1 if "mpeg4" in fmt or fmt == "h.264 hd" else 2
        key = (rank, -size)
        if best is None or key < best[0]:
            best = (key, name, size)
    return (best[1], best[2]) if best else None


def clean_description(text):
    if isinstance(text, list):
        text = " ".join(str(x) for x in text)
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    text = re.sub(r"&nbsp;", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:400]


_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(title, year=None):
    t = _ILLEGAL.sub(" ", str(title or "Untitled"))
    t = re.sub(r"\s+", " ", t).strip(" .") or "Untitled"
    t = t[:80].strip(" .")
    if year:
        t = f"{t} ({year})"
    return t


def _year(doc, meta):
    for v in (doc.get("year"), (meta.get("metadata") or {}).get("year"), (meta.get("metadata") or {}).get("date")):
        m = re.search(r"(1[89]\d\d|20\d\d)", str(v or ""))
        if m:
            return int(m.group(1))
    return None


def read_log(folder):
    try:
        with open(os.path.join(folder, LOG_NAME), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write_log(folder, log):
    tmp = os.path.join(folder, LOG_NAME + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=1)
    os.replace(tmp, os.path.join(folder, LOG_NAME))


def fetch(sources, media_dir, count=3, max_gb=1.5, say=print, progress=None):
    """Download up to `count` new items from each source into <media_dir>/Free Movies.
    Returns {"got": [...titles], "skipped": n, "errors": [...]}. Safe to run again: anything already downloaded is skipped."""
    folder = os.path.join(str(media_dir), FOLDER)
    os.makedirs(folder, exist_ok=True)
    log = read_log(folder)
    max_bytes = int(max_gb * 1024 ** 3)
    out = {"got": [], "skipped": 0, "errors": []}
    for src in sources:
        say(f"\n{src['name']}: looking for titles...")
        try:
            docs = search(src)
        except Exception as e:
            out["errors"].append(f"{src['name']}: could not search the Internet Archive ({e})")
            say("  Could not reach the Internet Archive: " + str(e))
            if "CERTIFICATE" in str(e).upper():
                say("  A security certificate was refused. Antivirus 'web shield' / HTTPS scanning is the usual cause:\n"
                    "  turn that option off for a minute (or allow python.exe), then run this again.")
            continue
        if not docs:
            say("  Nothing found that is clearly marked public domain.")
            continue
        taken = 0
        for d in docs:
            if taken >= count:
                break
            ident = d["identifier"]
            if ident in log and os.path.isfile(os.path.join(folder, log[ident])):
                out["skipped"] += 1
                continue
            try:
                meta = fetch_json(META_URL + urllib.parse.quote(ident))
                if not license_ok((meta.get("metadata") or {}).get("licenseurl")):
                    out["skipped"] += 1          # never trust the search alone
                    continue
                pick = pick_file(meta, max_bytes)
                if not pick:
                    out["skipped"] += 1
                    continue
                fname, size = pick
                free = shutil.disk_usage(folder).free
                if free - size < RESERVE_BYTES:
                    msg = f"Stopped: not enough free disk space for the next file ({size // 1024 ** 2} MB)."
                    out["errors"].append(msg)
                    say("  " + msg)
                    return out
                title = d.get("title") or (meta.get("metadata") or {}).get("title") or ident
                title = title[0] if isinstance(title, list) else title
                year = _year(d, meta)
                dest = os.path.join(folder, safe_name(title, year) + os.path.splitext(fname)[1].lower())
                n = 2
                while os.path.exists(dest) and log.get(ident) != os.path.basename(dest):
                    dest = os.path.join(folder, f"{safe_name(title, year)} {n}" + os.path.splitext(fname)[1].lower())
                    n += 1
                say(f"  Downloading: {title} ({size // 1024 ** 2} MB)")
                download(DOWNLOAD_URL + urllib.parse.quote(ident) + "/" + urllib.parse.quote(fname), dest, size, progress)
                desc = clean_description((meta.get("metadata") or {}).get("description"))
                library.write_sidecar(dest, {"title": safe_name(title), "year": year, "franchise": FOLDER,
                                             "tags": src.get("tags", ["free"]), "plot": desc,
                                             "source": DETAILS_URL + ident})
                log[ident] = os.path.basename(dest)
                write_log(folder, log)
                out["got"].append(title)
                taken += 1
            except Exception as e:
                out["errors"].append(f"{ident}: {e}")
                say(f"  Skipped {ident}: {e}")
            time.sleep(0.2)                       # be polite to the Archive
    return out
