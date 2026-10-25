"""Subtitles for the player: files saved next to a video (.srt / .vtt) and text subtitles stored inside it.

Browsers show WebVTT, so everything is served as WebVTT. Picture-based subtitles (Blu-ray / DVD "PGS" and "VobSub")
cannot be shown by a browser and are only counted, so the TV can say so."""
import hashlib
import json
import os
import re
import subprocess

from . import tools

TEXT_CODECS = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text"}
BITMAP_CODECS = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"}
FILE_EXT = (".srt", ".vtt")
NAMES = {"en": "English", "eng": "English", "es": "Spanish", "spa": "Spanish", "fr": "French", "fre": "French", "fra": "French",
         "de": "German", "ger": "German", "deu": "German", "it": "Italian", "ita": "Italian", "ja": "Japanese", "jpn": "Japanese",
         "ko": "Korean", "kor": "Korean", "pt": "Portuguese", "por": "Portuguese", "zh": "Chinese", "chi": "Chinese", "zho": "Chinese",
         "ru": "Russian", "rus": "Russian", "ar": "Arabic", "ara": "Arabic", "hi": "Hindi", "hin": "Hindi", "english": "English"}
NAMES.update({v.lower(): v for v in set(NAMES.values())})        # "spanish", "japanese"... as written out in a file name
_TS = re.compile(r"(\d{1,2}:\d{2}:\d{2}),(\d{3})")


def language_of(word):
    return NAMES.get(str(word or "").strip().lower(), "")


def decode(raw):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def srt_to_vtt(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    if text.lstrip().startswith("WEBVTT"):
        return text
    return "WEBVTT\n\n" + _TS.sub(r"\1.\2", text)


def external_files(path):
    """Subtitle files next to the video with the same name: Movie.srt, Movie.en.srt, Movie.English.vtt ..."""
    folder, name = os.path.split(path)
    stem = os.path.splitext(name)[0].lower()
    out = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return out
    for f in names:
        low = f.lower()
        base, ext = os.path.splitext(low)
        if ext not in FILE_EXT or not base.startswith(stem):
            continue
        rest = base[len(stem):]
        if rest and not rest.startswith("."):
            continue
        parts = [x for x in rest.split(".") if x]
        lang = next((language_of(x) for x in parts if language_of(x)), "")
        out.append({"file": os.path.join(folder, f), "language": lang, "forced": "forced" in parts})
    return out


def embedded(path):
    """(text tracks, picture track count) stored inside the video."""
    exe = tools.find_tool("ffprobe")
    if not exe:
        return [], 0
    try:
        r = tools.run([exe, "-v", "error", "-print_format", "json", "-show_streams", "-select_streams", "s", path], timeout=90)
        streams = json.loads(r.stdout or "{}").get("streams", [])
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return [], 0
    text, bitmap = [], 0
    for i, st in enumerate(streams):
        codec = st.get("codec_name", "")
        tags = {k.lower(): v for k, v in (st.get("tags") or {}).items()}
        if codec in TEXT_CODECS:
            text.append({"n": i, "language": language_of(tags.get("language")) or "", "title": str(tags.get("title", "")),
                         "forced": bool((st.get("disposition") or {}).get("forced"))})
        elif codec in BITMAP_CODECS:
            bitmap += 1
    return text, bitmap


def tracks(path):
    """{"tracks": [{key, label, language}], "picture_only": n}  - keys: x<i> = file next to the video, e<n> = inside it."""
    out = []
    for i, f in enumerate(external_files(path)):
        lang = f["language"]
        out.append({"key": f"x{i}", "language": lang, "label": (lang or "Subtitles") + (" (forced)" if f["forced"] else "") + " (file)"})
    text, bitmap = embedded(path)
    for t in text:
        label = t["language"] or t["title"] or f"Track {t['n'] + 1}"
        out.append({"key": f"e{t['n']}", "language": t["language"], "label": label + (" (forced)" if t["forced"] else "")})
    return {"tracks": out, "picture_only": bitmap}


def vtt(path, key, cache_dir, mtime=0):
    """WebVTT bytes for one track key (see tracks), or None."""
    m = re.fullmatch(r"([xe])(\d{1,3})", str(key))
    if not m:
        return None
    kind, n = m[1], int(m[2])
    if kind == "x":
        files = external_files(path)
        if n >= len(files):
            return None
        try:
            with open(files[n]["file"], "rb") as fh:
                return srt_to_vtt(decode(fh.read())).encode("utf-8")
        except OSError:
            return None
    ffmpeg = tools.find_tool("ffmpeg")
    if not ffmpeg:
        return None
    os.makedirs(cache_dir, exist_ok=True)
    out = os.path.join(cache_dir, f"{hashlib.md5(path.encode('utf-8', 'replace')).hexdigest()[:12]}-{int(mtime)}-{n}.vtt")
    if not os.path.isfile(out):
        tmp = out + ".tmp"
        try:
            r = tools.run([ffmpeg, "-v", "error", "-y", "-i", path, "-map", f"0:s:{n}", "-f", "webvtt", tmp], timeout=300)
        except (OSError, subprocess.SubprocessError):
            return None
        if r.returncode != 0 or not os.path.isfile(tmp):
            return None
        os.replace(tmp, out)
    with open(out, "rb") as fh:
        return fh.read()


def save_embedded(src, folder, stem):
    """Before a fix-up drops a video's inside subtitles: write its text subtitles next to the new file as .srt. Returns how many."""
    ffmpeg = tools.find_tool("ffmpeg")
    text, _ = embedded(src)
    if not ffmpeg or not text:
        return 0
    saved = 0
    for t in text:
        tag = (t["language"] or f"track{t['n'] + 1}").lower().replace(" ", "")
        dest = os.path.join(folder, f"{stem}.{tag}{'.forced' if t['forced'] else ''}.srt")
        k = 2
        while os.path.exists(dest):
            dest, k = os.path.join(folder, f"{stem}.{tag}{k}.srt"), k + 1
        try:
            r = tools.run([ffmpeg, "-v", "error", "-y", "-i", src, "-map", f"0:s:{t['n']}", "-f", "srt", dest], timeout=300)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0 and os.path.isfile(dest):
            saved += 1
        elif os.path.isfile(dest):
            os.remove(dest)
    return saved
