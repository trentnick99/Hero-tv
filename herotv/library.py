"""Library scanner: ffprobe-verified runtimes + sidecar/filename metadata."""
import json
import os
import time
import shutil
import re
import subprocess

from . import tools

EXTS = {".mp4", ".m4v", ".mkv", ".webm", ".mov"}
PLAY_V = {"h264", "hevc", "vp8", "vp9", "av1"}                  # codecs a browser may decode - see video_ok() for the details
IS_WIN = os.name == "nt"
PLAY_A = {"aac", "mp3", "opus", "vorbis", "flac", "pcm_s16le"}  # no ac3/eac3/dts: transcode (see README)


PHONE_EXTS = {".mp4", ".m4v", ".mov"}          # Safari (iPhone/iPad/Mac) cannot open .mkv or .webm files
PHONE_A = {"aac", "mp3", "ac3", "eac3", "alac"}


def phone_ok(path, vcodec, acodec, vfmt=""):
    """Will Safari on an iPhone play this file as it is? (Used for 'iPhone-friendly copies'.)"""
    return (os.path.splitext(str(path))[1].lower() in PHONE_EXTS and vcodec in ("h264", "hevc")
            and video_ok(vcodec, vfmt) and (not acodec or acodec in PHONE_A))


# What the TV screen on this PC has been seen to play (settings.json "browser_caps", filled in by the TV page's own
# test): H.265 (8-bit and 10-bit, in .mp4 and .mkv) and Dolby sound (AC-3, E-AC-3). Unknown = not assumed.
CAP_KEYS = ("hevc", "hevc10", "hevc_mkv", "ac3", "eac3")
_caps = {"mtime": None, "caps": {}}


def caps():
    from . import config
    try:
        f = config.settings_file()
        mt = os.path.getmtime(f)
    except (OSError, AttributeError):
        return {}
    if _caps["mtime"] != mt:
        try:
            d = json.loads(f.read_text(encoding="utf-8-sig"))
            c = d.get("browser_caps") if isinstance(d, dict) else None
            _caps["caps"] = dict({k: bool(c.get(k)) for k in CAP_KEYS}, checked=int(c.get("checked") or 0)) if isinstance(c, dict) else {}
        except (OSError, ValueError):
            _caps["caps"] = {}
        _caps["mtime"] = mt
    return _caps["caps"]


def audio_ok(acodec, ext=""):
    """Can the TV screen play this sound? Dolby (AC-3 / E-AC-3) is always converted to AAC: a browser can say it
    supports Dolby and still play it as static (seen in 1.29.0), and converting only the sound is quick. Raw PCM is
    fine in .mkv/.webm but not inside an .mp4 / .mov (see mp4_audio_ok)."""
    if str(ext).lower() in (".mp4", ".m4v", ".mov") and str(acodec or "").startswith("pcm"):
        return False
    return not acodec or acodec in PLAY_A


def mp4_audio_ok(acodec):
    """Sound that may be copied as is into an .mp4. Raw PCM (DVD rips) becomes 'ipcm' there, which TVs and many
    browsers play as noise or not at all - it is converted to AAC."""
    return audio_ok(acodec) and not str(acodec or "").startswith("pcm")


def video_ok(vcodec, vfmt="", ext=""):
    """Can a browser really SHOW this picture? (audio-but-black-screen is what you get when it cannot).
    vfmt is "pix_fmt|profile" from ffprobe. 10-bit / 4:2:2 / 4:4:4 H.264 (common in anime rips) is not decodable by
    Edge/Chrome. HEVC plays on Windows PCs that have H.265 support (graphics card + Microsoft's HEVC Video Extensions):
    the TV page tests that once (caps())."""
    if vcodec not in PLAY_V:
        return False
    pix, _, prof = (vfmt or "").partition("|")
    if vcodec == "h264":
        return not any(x in pix for x in ("10", "12", "422", "444", "gbr")) and not any(x in prof for x in ("10", "4:2:2", "4:4:4"))
    if vcodec == "hevc":
        if not IS_WIN or os.environ.get("HEROTV_ALLOW_HEVC") == "1":
            return True
        c = caps()
        if not c.get("hevc") or any(x in pix for x in ("422", "444", "12")):
            return False
        if ("10" in pix or "10" in prof) and not c.get("hevc10"):
            return False
        return str(ext).lower() != ".mkv" or c.get("hevc_mkv", False)
    return True


def recheck_playable(conn):
    """After the H.265 / Dolby test result changed: re-decide only the videos it affects. Returns how many changed."""
    n = 0
    for r in conn.execute("SELECT id,path,vcodec,acodec,vfmt,playable FROM media WHERE verified=1 AND "
                          "(vcodec='hevc' OR acodec IN ('ac3','eac3') OR acodec LIKE 'pcm%')").fetchall():
        ok = 1 if video_ok(r["vcodec"], r["vfmt"] or "", os.path.splitext(r["path"])[1]) and \
            audio_ok(r["acodec"], os.path.splitext(r["path"])[1]) else 0
        if ok != r["playable"]:
            conn.execute("UPDATE media SET playable=? WHERE id=?", (ok, r["id"]))
            n += 1
    conn.commit()
    return n


def why_not_playable(vcodec, acodec, vfmt="", ext=""):
    """Plain-English reason a file is skipped (None when it is fine)."""
    if not video_ok(vcodec, vfmt, ext):
        if vcodec == "hevc":
            c = caps()
            if c.get("hevc") and str(ext).lower() == ".mkv" and not c.get("hevc_mkv"):
                return "its video is HEVC/H.265 in an .mkv file - this PC plays H.265 only in .mp4 files (Fix repackages it in seconds)"
            if c.get("hevc") and not c.get("hevc10"):
                return "its video is 10-bit HEVC/H.265, which this PC cannot show (it plays 8-bit H.265)"
            return "its video is HEVC/H.265, which this PC's TV screen cannot show yet (sound only) - see Settings > Tools > H.265"
        if vcodec == "h264":
            return f"its video is 10-bit/high-profile H.264 ({vfmt.replace('|', ', ')}), which browsers cannot show (sound only)"
        return f"its video format '{vcodec}' cannot be shown by a browser"
    if not audio_ok(acodec, ext):
        return f"its sound ({acodec}) cannot be played by the TV screen (Fix converts just the sound - quick)"
    return None


def probe(path):
    """dict(runtime_s, vcodec, acodec, title) or None if ffprobe is missing / file unreadable."""
    exe = tools.find_tool("ffprobe")
    if not exe:
        return None
    try:
        out = tools.run([exe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path], timeout=90)
        j = json.loads(out.stdout or "{}")
        dur = float(j["format"]["duration"])
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None
    streams = j.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v is None or dur <= 0:
        return None
    return {"runtime_s": dur, "vcodec": v.get("codec_name", ""), "acodec": (a or {}).get("codec_name", ""),
            "vfmt": f"{v.get('pix_fmt', '')}|{v.get('profile', '')}".lower(),
            "title": (j["format"].get("tags") or {}).get("title", ""),
            "width": int(v.get("width") or 0), "height": int(v.get("height") or 0),
            "bitrate": int(float(j["format"].get("bit_rate") or 0)),
            "comment": str((j["format"].get("tags") or {}).get("comment", "") or (j["format"].get("tags") or {}).get("COMMENT", ""))}


def chapter_starts(path):
    """Start times (seconds) of the chapters inside a video - natural places for a break. [] when there are none or
    ffprobe is missing; None when the file could not be read."""
    exe = tools.find_tool("ffprobe")
    if not exe:
        return None
    try:
        out = tools.run([exe, "-v", "error", "-print_format", "json", "-show_chapters", path], timeout=60)
        j = json.loads(out.stdout or "{}")
        return sorted(float(c["start_time"]) for c in j.get("chapters", []) if float(c.get("start_time", 0)) > 0)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None


LANG_NAMES = {"eng": "English", "jpn": "Japanese", "spa": "Spanish", "fre": "French", "fra": "French", "ger": "German", "deu": "German",
              "ita": "Italian", "por": "Portuguese", "kor": "Korean", "chi": "Chinese", "zho": "Chinese", "rus": "Russian",
              "hin": "Hindi", "ara": "Arabic", "und": "Unknown language", "": "Unknown language"}


def audio_tracks(path):
    """Every sound track of a video: [{n, lang, language, title, codec, channels, default}] (n counts from 0), or []."""
    exe = tools.find_tool("ffprobe")
    if not exe:
        return []
    try:
        out = tools.run([exe, "-v", "error", "-print_format", "json", "-show_streams", "-select_streams", "a", path], timeout=90)
        streams = json.loads(out.stdout or "{}").get("streams", [])
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return []
    tracks = []
    for i, st in enumerate(streams):
        tags = {k.lower(): v for k, v in (st.get("tags") or {}).items()}
        lang = str(tags.get("language", "")).lower()
        tracks.append({"n": i, "lang": lang, "language": LANG_NAMES.get(lang, lang.upper() or "Unknown language"),
                       "title": str(tags.get("title", "")), "codec": st.get("codec_name", ""), "channels": int(st.get("channels") or 0),
                       "default": bool((st.get("disposition") or {}).get("default"))})
    return tracks


def playing_track(tracks):
    """The track a browser plays on its own: the one flagged default, else the first."""
    return next((t["n"] for t in tracks if t["default"]), 0) if tracks else 0


_JUNK = re.compile(r"\[[^\]]*\]|\([^)]*\)")        # [fansub group] [720p] (1080p) ...


def _clean(text):
    return re.sub(r"\s+", " ", _JUNK.sub(" ", text)).strip(" ._-")


_RELEASE = re.compile(r"(?i)[ ._\-\[(]+(?:(?:480|576|720|1080|2160)[pi]|4k|uhd|blu-?ray|bdrip|brrip|web-?dl|web-?rip|hdtv|"
                      r"dvdrip|hdrip|remux|x26[45]|h\.?26[45]|hevc|xvid|aac\d*|dts|ddp?\d|10bit|hdr10?|yts|rarbg)(?![A-Za-z]).*$")


_LANGS = (r"hindi|english|eng|tamil|telugu|malayalam|kannada|bengali|punjabi|marathi|urdu|spanish|latino|castellano|"
          r"french|german|italian|russian|japanese|korean|chinese|mandarin|portuguese|arabic|turkish|polish|dutch|thai")
_RJUNK = r"dual|multi|audio|dubbed|dub|subbed|esubs?|subs?|org|proper|repack|unrated|extended|hq|hc|line|hd|tc|cam|hdcam|hdts"
_TAG = rf"(?:{_LANGS}|{_RJUNK})"
_SEP = r"[\s\[\]()+&,/|-]"
_BRACKET_LANG = re.compile(rf"(?i)\s*[\[(]\s*{_TAG}(?:{_SEP}+{_TAG})*\s*[\])]")
_YEAR_LANG = re.compile(rf"(?i)^(.*?\S)\s+\(?((?:19|20)\d{{2}})\)?(?:{_SEP}*{_TAG}\b)+{_SEP}*$")
_TAIL_JUNK = re.compile(rf"(?i)(?:\s+{_TAG})*\s+(?:dual|multi)\s+audio(?:{_SEP}+{_TAG})*{_SEP}*$|(?:{_SEP}+(?:{_RJUNK}))+{_SEP}*$")


def _drop_languages(cut):
    """'Avengers Endgame 2019 Hindi-English' -> 'Avengers Endgame 2019'; '... [Hindi + English]' -> '...'.
    A language word is only dropped after a year, inside brackets or next to 'Dual Audio', so 'Johnny English' stays."""
    c = _BRACKET_LANG.sub("", cut).strip()
    m = _YEAR_LANG.match(c)
    if m:
        c = f"{m[1]} {m[2]}"
    c2 = _TAIL_JUNK.sub("", c).strip(" ._-")
    if c2 and re.search(r"(?i)\b(?:dual|multi)\s+audio\b", c[len(c2):]):
        c = c2
    return c


def tidy(text, year=None, dotted_name=False):
    """Turn a download-style name into a readable one: 'Iron.Man.2008.1080p.BluRay.x264-GRP' -> ('Iron Man', 2008)."""
    t = text.strip()
    cut = _RELEASE.sub("", t)
    dotted = " " not in cut and bool(re.search(r"[._]", cut))
    if dotted:
        cut = re.sub(r"[._]+", " ", cut)
    cut = re.sub(r"\s+", " ", cut).strip(" ._-")
    cut = _drop_languages(cut) or cut
    if (dotted or dotted_name or cut != t) and year is None:            # 'Iron Man 2008' -> title + year (only for download-style names)
        m = re.match(r"^(.*\S)\s+\(?((?:19|20)\d{2})\)?$", cut)
        if m and int(m[2]) <= 2030:
            cut, year = m[1].strip(" ._-"), int(m[2])
    return (cut or t), year


_SITE = re.compile(r"(?i)(?:www\.|https?://|\b[a-z0-9-]+\.(?:com|net|org|to|io|me|tv|cc|xyz|info|ws|se|ru|link|club|site|app)\b)")


def tag_title(text):
    """The title stored inside a video file, cleaned - or "" when it is only a download site's label.
    'PSArips.com | South.Park.S17E07.720p' -> 'South Park S17E07'; 'www.site.org' -> ''."""
    t = str(text or "").strip()
    if not t:
        return ""
    parts = [x for x in re.split(r"\s*[|\u2022]\s*|\s+-\s+(?=\S*(?:www\.|\.com|\.net|\.org))", t) if x.strip()]
    parts = [x for x in parts if not _SITE.search(x)]
    if not parts:
        return ""
    t = tidy(" ".join(parts))[0]
    t = _SITE.sub("", t).strip(" ._-|")
    return t if len(t) >= 2 else ""


_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"]
_HOLIDAYS = {"halloween": 10, "thanksgiving": 11, "christmas": 12, "xmas": 12, "holiday": 12, "holidays": 12,
             "valentines": 2, "valentine's day": 2, "valentines day": 2}


def season_month(rel_parts):
    """1-12 when a video sits in a folder named after a month or holiday ("December", "Halloween", "Christmas"):
    such videos only play on channels in that month. 0 otherwise. Only the folders count, not the file name."""
    for part in rel_parts[:-1]:
        p = part.strip().lower()
        if p in _MONTHS:
            return _MONTHS.index(p) + 1
        if p in _HOLIDAYS:
            return _HOLIDAYS[p]
    return 0


def tag_months(conn, root):
    """Keep the "month:N" tag in step with the folders (also for videos found by older versions)."""
    n = 0
    for r in conn.execute("SELECT id,path,tags FROM media WHERE available=1").fetchall():
        try:
            rel = os.path.relpath(r["path"], root).split(os.sep)
            tags = json.loads(r["tags"] or "[]")
        except (ValueError, TypeError):
            continue
        want = season_month(rel)
        keep = [t for t in tags if not str(t).startswith("month:")]
        new = keep + ([f"month:{want}"] if want else [])
        if new != tags:
            conn.execute("UPDATE media SET tags=? WHERE id=?", (json.dumps(new), r["id"]))
            n += 1
    return n


def fix_site_titles(conn, root):
    """Titles that are a download site's label (found inside the file by older versions) are named again from the
    file name. Videos with a title in their .hero.json keep it. Returns how many were fixed."""
    n = 0
    for r in conn.execute("SELECT id,path,title FROM media WHERE title LIKE '%.%' OR title LIKE '%|%'").fetchall():
        if not _SITE.search(r["title"] or ""):
            continue
        side = sidecar_path(r["path"])
        try:
            with open(side, encoding="utf-8-sig") as fh:
                if "title" in (json.load(fh) or {}):
                    continue
        except (OSError, ValueError, TypeError):
            pass
        try:
            rel = os.path.relpath(r["path"], root)
        except ValueError:
            continue
        stem = os.path.splitext(os.path.basename(r["path"]))[0]
        guess = _guess(rel.split(os.sep), stem)
        new = tag_title(guess["title"]) or tag_title(r["title"])          # the file name, unless that is a site label too
        if new and new != r["title"]:
            conn.execute("UPDATE media SET title=? WHERE id=?", (new, r["id"]))
            n += 1
    return n


def _guess(parts, stem):
    d = _guess_raw(parts, stem)
    d["title"], d["year"] = tidy(d["title"], d["year"], " " not in stem and bool(re.search(r"[._]", stem)))
    if d["series"] and (d["series"] != parts[1] if len(parts) > 2 else True):
        d["series"] = tidy(d["series"])[0]
    return d


def _guess_raw(parts, stem):
    title, year, season, ep, series = stem, None, 0, 0, ""
    m = re.search(r"[Ss](\d{1,2})[ ._-]?[Ee](\d{1,4})", stem)
    if not m:
        m = re.search(r"(?<!\d)(\d{1,2})x(\d{1,4})(?!\d)", stem)
    if m:
        season, ep = int(m[1]), int(m[2])
    else:   # anime-style numbering: "Episode 012", "Ep.12", "E012", "Dragon Ball Z - 012 - Title"
        for pat in (r"\b[Ee]pisode[ ._-]*(\d{1,4})\b", r"\b[Ee]p[ ._-]*(\d{1,4})\b", r"(?<![A-Za-z0-9])[Ee](\d{2,4})\b",
                    r"\s-\s(\d{1,3})(?=\s|\.|-|_|$)"):
            m = re.search(pat, _JUNK.sub(lambda x: " " * len(x[0]), stem))
            if m:
                ep = int(m[1])
                break
    if m:
        series = _clean(stem[:m.start()])
        title = _clean(stem[m.end():]) or (f"Episode {ep}" if series else stem)
    m = re.match(r"^(.*?)[ ._-]*\((\d{4})\)", stem)
    if m and not ep:
        title, year = m[1].strip(), int(m[2])
    elif m:
        year = int(m[2])
    return dict(title=title.replace("_", " ").strip() or stem, year=year, season=season, episode=ep,
                franchise=parts[0] if len(parts) > 1 else "", series=parts[1] if len(parts) > 2 else (series if ep else ""))


def sidecar_path(path):
    return os.path.splitext(path)[0] + ".hero.json"


def write_sidecar(path, updates):
    """Merge `updates` into the video's .hero.json (a value of None removes that setting). Returns the sidecar's mtime."""
    side = sidecar_path(path)
    try:
        with open(side, encoding="utf-8-sig") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    for k, v in updates.items():
        if v is None:
            data.pop(k, None)
        else:
            data[k] = v
    tmp = side + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, side)
    return os.stat(side).st_mtime


def scan(conn, root, probe_fn=probe):
    """Scan root -> dict(added, updated, missing, unverified). Safe to re-run; unchanged files are not re-probed."""
    root = os.path.abspath(str(root))
    seen, stats = set(), dict(added=0, updated=0, missing=0, unverified=0)
    added_paths = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if not d.startswith("."))
        for f in sorted(fn):
            stem, ext = os.path.splitext(f)
            if ext.lower() not in EXTS:
                continue
            path = os.path.join(dp, f)
            seen.add(path)
            st = os.stat(path)
            side = os.path.join(dp, stem + ".hero.json")
            mt = st.st_mtime + (os.stat(side).st_mtime if os.path.exists(side) else 0)
            row = conn.execute("SELECT id,mtime,size,verified,vcodec,acodec,vfmt FROM media WHERE path=?", (path,)).fetchone()
            if row and row["mtime"] == mt and row["size"] == st.st_size and row["verified"]:
                # unchanged: no re-probe, but re-evaluate playable (undoes a "marked unplayable" from transient errors)
                ok = video_ok(row["vcodec"], row["vfmt"], ext) and audio_ok(row["acodec"], ext)
                conn.execute("UPDATE media SET available=1, playable=? WHERE id=?", (1 if ok else 0, row["id"]))
                continue
            meta = _guess(os.path.relpath(path, root).split(os.sep), stem)
            sc = {}
            if os.path.exists(side):
                try:
                    with open(side, encoding="utf-8-sig") as fh:
                        sc = json.load(fh)
                except (OSError, ValueError):
                    sc = {}
            p = probe_fn(path)
            if p and tag_title(p["title"]) and meta["title"] == stem:
                meta["title"] = tag_title(p["title"])
            meta.update({k: sc[k] for k in ("title", "year", "franchise", "series", "season", "episode") if k in sc})
            # Year first; episodes of one series then follow in season/episode order (see the ORDER BY in scheduler.py).
            ordv = sc.get("order", (meta["year"] or 9999) * 10_000_000)
            if "order" not in sc and not meta["series"]:
                from . import art                  # films: TMDB's release date, once it is known
                ordv = art.release_ord(conn, meta["title"], meta["year"]) or ordv
            verified = 1 if p else 0
            playable = 1 if p and video_ok(p["vcodec"], p.get("vfmt", ""), ext) and audio_ok(p["acodec"], ext) else 0
            stats["unverified"] += 0 if verified else 1
            vals = (path, meta["title"], meta["year"], meta["franchise"], meta["series"], meta["season"], meta["episode"],
                    json.dumps(sc.get("tags", [])), sc.get("plot", ""), p["runtime_s"] if p else 0, verified, playable,
                    p["vcodec"] if p else "", p["acodec"] if p else "", ordv, mt, st.st_size, p.get("vfmt", "") if p else "",
                    int(time.time()))
            conn.execute(
                "INSERT INTO media(path,title,year,franchise,series,season,episode,tags,plot,runtime_s,verified,playable,"
                "vcodec,acodec,ord,mtime,size,vfmt,available,added) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?) "
                "ON CONFLICT(path) DO UPDATE SET title=excluded.title,year=excluded.year,franchise=excluded.franchise,"
                "series=excluded.series,season=excluded.season,episode=excluded.episode,tags=excluded.tags,"
                "plot=excluded.plot,runtime_s=excluded.runtime_s,verified=excluded.verified,playable=excluded.playable,"
                "vcodec=excluded.vcodec,acodec=excluded.acodec,vfmt=excluded.vfmt,ord=excluded.ord,mtime=excluded.mtime,"
                "size=excluded.size,available=1", vals)
            stats["updated" if row else "added"] += 1
            if not row:
                added_paths.append(path)
    if not seen and conn.execute("SELECT 1 FROM media WHERE available=1 LIMIT 1").fetchone():
        # Folder missing or empty (USB/NAS not mounted yet?): keep the library instead of wiping every channel.
        conn.commit()
        stats["offline"] = True
        return stats
    for r in conn.execute("SELECT id,path FROM media WHERE available=1").fetchall():
        if r["path"] not in seen:
            conn.execute("UPDATE media SET available=0 WHERE id=?", (r["id"],))
            stats["missing"] += 1
    stats["relinked"] = relink(conn, added_paths)
    stats["renamed"] = fix_site_titles(conn, root)
    tag_months(conn, root)
    conn.commit()
    return stats


def _same_video(old, new):
    """Is the new library entry the old one that was moved, renamed or converted?"""
    op, np_ = old["path"], new["path"]
    if old["size"] and old["size"] == new["size"] and abs((old["runtime_s"] or 0) - (new["runtime_s"] or 0)) < 1.5:
        return True                                     # moved or renamed: same bytes, same length
    # converted by HERO TV (Fix / iPhone-friendly / sound track): the old file now sits in .originals next to the new one
    od, of = os.path.split(op)
    nd = os.path.dirname(np_)
    if (os.path.normcase(od) == os.path.normcase(nd) and os.path.splitext(of)[0] == os.path.splitext(os.path.basename(np_))[0]
            and os.path.isfile(os.path.join(nd, ".originals", of))
            and abs((old["runtime_s"] or 0) - (new["runtime_s"] or 0)) < 3):
        return True
    return False


def relink(conn, added_paths):
    """Give newly found files the favorites, resume point, watch history and schedule of the missing file they
    replace (a file moved to another folder, renamed in Windows, or converted by HERO TV). Only when exactly one
    missing file matches - otherwise nothing is touched. Returns how many were relinked."""
    if not added_paths:
        return 0
    gone = conn.execute("SELECT id,path,size,runtime_s FROM media WHERE available=0").fetchall()
    if not gone:
        return 0
    n = 0
    used = set()
    for path in added_paths:
        new = conn.execute("SELECT id,path,size,runtime_s FROM media WHERE path=?", (path,)).fetchone()
        if new is None:
            continue
        cands = [g for g in gone if g["id"] not in used and _same_video(g, new)]
        if len(cands) != 1:
            continue
        old = cands[0]
        used.add(old["id"])
        for table, cols in (("favorites", "media_id,added"), ("seen", "media_id,secs,last"),
                            ("progress", "media_id,position,completed,updated")):
            rest = cols.split(",", 1)[1]
            conn.execute(f"INSERT OR IGNORE INTO {table}({cols}) SELECT ?,{rest} FROM {table} WHERE media_id=?", (new["id"], old["id"]))
            conn.execute(f"DELETE FROM {table} WHERE media_id=?", (old["id"],))
        conn.execute("UPDATE slots SET media_id=? WHERE media_id=?", (new["id"], old["id"]))
        conn.execute("UPDATE media SET added=(SELECT added FROM media WHERE id=?) WHERE id=?", (old["id"], new["id"]))
        old_side = os.path.splitext(old["path"])[0] + ".hero.json"           # your renames/tags follow the file
        new_side = os.path.splitext(new["path"])[0] + ".hero.json"
        if os.path.isfile(old_side) and not os.path.exists(new_side):
            try:
                shutil.move(old_side, new_side)
                conn.execute("UPDATE media SET mtime=0 WHERE id=?", (new["id"],))   # re-read with the names on the next scan
            except OSError:
                pass
        conn.execute("DELETE FROM media WHERE id=?", (old["id"],))
        n += 1
    return n
