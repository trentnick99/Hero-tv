"""Live TV in other apps: your HERO TV channels as live TV channels for Plex, Jellyfin, Emby, Channels and IPTV
player apps (TiviMate, IPTV Smarters, VLC...) on Fire TV, Apple TV, Android TV, phones and smart TVs.

HERO TV offers what those apps understand:
- a channel list (M3U) and a TV guide (XMLTV) at addresses with a private key in them, and
- an HDHomeRun TV tuner look-alike (Plex / Jellyfin / Emby: "add a tuner", type this PC's address).
Each channel is one continuous live stream (MPEG-TS) that follows the schedule, made by ffmpeg from your files
(copied as they are when the format allows, converted on the fly otherwise).

Watch-only and off by default. Like the TV media server, it has no pairing - any app on your home network that
knows the address can watch - so it has its own switch with a warning (Settings > Other devices), and it only
works while "Let other devices watch" is on."""
import json
import os
import secrets
import subprocess
import time
from xml.sax.saxutils import escape

from . import scheduler as S

TS_VIDEO = {"h264", "hevc", "mpeg2video"}
TS_AUDIO = {"aac", "mp3", "ac3", "eac3", "mp2"}
HDHR_OPEN = ("/discover.json", "/lineup.json", "/lineup_status.json", "/device.xml", "/tv.m3u", "/tv.xml")   # easy to type on a TV


# ---------- the switch (settings.json "iptv", "iptv_key") ----------
def _settings():
    from . import settings_api
    return settings_api._load()


def enabled(d=None):
    d = _settings() if d is None else d
    return bool(d.get("iptv")) and isinstance(d.get("iptv_key"), str) and len(d["iptv_key"]) >= 16


def key(d=None):
    d = _settings() if d is None else d
    return d.get("iptv_key") if enabled(d) else ""


def set_enabled(on, new_key=False):
    from . import settings_api
    d = settings_api._load()
    d["iptv"] = bool(on)
    if on and (new_key or not isinstance(d.get("iptv_key"), str) or len(d.get("iptv_key", "")) < 16):
        d["iptv_key"] = secrets.token_urlsafe(18)
    settings_api._save(d)
    return d


def base_url(server, k):
    return f"{server}/iptv/{k}"


# ---------- what the apps read ----------
def channels(conn):
    """Channels that can be watched as live TV (not the Weather channel), in number order."""
    from .server import empty_channel_ids
    empty = empty_channel_ids(conn)
    return [ch for ch in S.channels(conn) if (ch["kind"] or "tv") in ("tv", "foryou") and ch["id"] not in empty]


def m3u(conn, base):
    out = [f'#EXTM3U url-tvg="{base}/guide.xml" x-tvg-url="{base}/guide.xml"']
    for ch in channels(conn):
        name = str(ch["name"]).replace(",", " ")
        out.append(f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-chno="{ch["number"]}" tvg-name="{name}" '
                   f'group-title="HERO TV" channel-number="{ch["number"]}",{name}')
        out.append(f"{base}/ch/{ch['id']}.ts")
    return "\n".join(out) + "\n"


def _xt(t):
    return time.strftime("%Y%m%d%H%M%S +0000", time.gmtime(t))


def xmltv(conn, now, hours=48, tz="UTC"):
    """The guide for the next two days (and the last hour), shows with breaks listed once, cards left out."""
    t0, t1 = int(now) - 3600, int(now) + hours * 3600
    chans = channels(conn)
    ids = {ch["id"] for ch in chans}
    by = {}
    for r in S.window(conn, t0, t1):
        if r["channel_id"] in ids:
            by.setdefault(r["channel_id"], []).append(S.slot_dict(r, tz))
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv generator-info-name="HERO TV">']
    for ch in chans:
        out.append(f'<channel id="{escape(ch["id"])}"><display-name>{escape(ch["name"])}</display-name>'
                   f'<display-name>{ch["number"]}</display-name></channel>')
    for ch in chans:
        for d in S.merge_breaks(by.get(ch["id"], [])):
            if d.get("card"):
                continue
            sub, ep = "", ""
            if d.get("series"):
                ep = f"S{d.get('season') or 0}E{d.get('episode') or 0}"
                sub = d.get("title") or ""
                title = d["series"]
            else:
                title = d.get("title") or "Untitled"
            parts = [f'<programme start="{_xt(d["start"])}" stop="{_xt(d["end"])}" channel="{escape(ch["id"])}">',
                     f"<title>{escape(title)}</title>"]
            if sub:
                parts.append(f"<sub-title>{escape(sub)}</sub-title>")
            if d.get("plot"):
                parts.append(f"<desc>{escape(d['plot'])}</desc>")
            if d.get("year") and not d.get("series"):
                parts.append(f"<date>{d['year']}</date>")
            if ep:
                parts.append(f'<episode-num system="onscreen">{ep}</episode-num>')
            parts.append(f"<category>{'Series' if d.get('series') else 'Movie'}</category></programme>")
            out.append("".join(parts))
    out.append("</tv>")
    return "\n".join(out) + "\n"


def device_id(k):
    import hashlib
    return hashlib.sha256(("herotv-hdhr" + k).encode()).hexdigest()[:8].upper()


def discover(base, k, name="HERO TV"):
    return {"FriendlyName": name, "Manufacturer": "HERO TV", "ModelNumber": "HDTC-2US", "FirmwareName": "hdhomeruntc_atsc",
            "FirmwareVersion": "20200101", "DeviceID": device_id(k), "DeviceAuth": "herotv", "TunerCount": 4,
            "BaseURL": base, "LineupURL": f"{base}/lineup.json"}


def lineup(conn, base):
    return [{"GuideNumber": str(ch["number"]), "GuideName": ch["name"], "URL": f"{base}/ch/{ch['id']}.ts", "HD": 1}
            for ch in channels(conn)]


LINEUP_STATUS = {"ScanInProgress": 0, "ScanPossible": 1, "Source": "Cable", "SourceList": ["Cable"]}


def device_xml(base, k, name="HERO TV"):
    return ('<?xml version="1.0"?><root xmlns="urn:schemas-upnp-org:device-1-0"><specVersion><major>1</major>'
            f'<minor>0</minor></specVersion><URLBase>{escape(base)}</URLBase><device>'
            '<deviceType>urn:schemas-upnp-org:device:MediaServer:1</deviceType>'
            f'<friendlyName>{escape(name)}</friendlyName><manufacturer>HERO TV</manufacturer>'
            f'<modelName>HDTC-2US</modelName><modelNumber>HDTC-2US</modelNumber><serialNumber></serialNumber>'
            f'<UDN>uuid:{device_id(k).lower()}-herotv</UDN></device></root>')


# ---------- the live stream ----------
def ffmpeg_cmd(exe, slot, media, offset, length, ts_offset, still=None):
    """ffmpeg arguments for one stretch of a channel: a video from `offset` for `length` seconds, or (for an Up next
    card) a still picture with silence. Output: MPEG-TS on stdout, timestamps carrying on from earlier stretches."""
    head = [exe, "-hide_banner", "-loglevel", "error", "-nostdin"]
    out = ["-output_ts_offset", f"{ts_offset:.3f}", "-muxdelay", "0", "-f", "mpegts", "pipe:1"]
    if slot is None or media is None:
        src = (["-loop", "1", "-framerate", "25", "-i", still] if still and os.path.isfile(still)
               else ["-f", "lavfi", "-i", "color=c=0x0d1322:s=1280x720:r=25"])
        return head + ["-re"] + src + ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{length:.3f}",
                                       "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                                       "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-g", "50",
                                       "-c:a", "aac", "-b:a", "128k", "-shortest"] + out
    v = "copy" if (media["vcodec"] or "") in TS_VIDEO else None
    a = "copy" if (media["acodec"] or "") in TS_AUDIO else None
    codec = ["-c:v", v] if v else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-g", "50"]
    codec += ["-c:a", a] if a else ["-c:a", "aac", "-b:a", "192k", "-ac", "2"]
    return head + ["-re", "-ss", f"{max(0.0, offset):.3f}", "-t", f"{max(0.5, length):.3f}", "-i", media["path"],
                   "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn"] + codec + out


def stream_channel(app, cid, write, exe, still_for=None, popen=subprocess.Popen, clock=time.time, max_parts=None):
    """Send channel `cid` as one never-ending live stream, following the schedule slot by slot, until the app
    disconnects (write raises). still_for(media_row) -> picture path for Up next cards."""
    from . import tools
    ts = 0.0
    n = 0
    while max_parts is None or n < max_parts:
        n += 1
        c = app.db()
        try:
            now = clock()
            cur = S.current(c, cid, now)
            if cur is None:
                ch = c.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone()
                if ch is None:
                    return
                S.extend(c, ch, now, app.horizon(), app.tz)
                cur = S.current(c, cid, now)
            if cur is None:
                return
            d = S.slot_dict(cur, app.tz)
            media = c.execute("SELECT * FROM media WHERE id=?", (d["media_id"],)).fetchone()
        finally:
            c.close()
        length = d["end"] - now
        if length <= 0.2:
            time.sleep(0.2)
            continue
        if d.get("card") or media is None or not os.path.isfile(media["path"] or ""):
            cmd = ffmpeg_cmd(exe, None, None, 0, length, ts, still_for(media) if (still_for and media) else None)
        else:
            cmd = ffmpeg_cmd(exe, d, media, now - d["start"] + (d.get("seek") or 0), length, ts)
        started = clock()
        p = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **tools.HIDE)
        try:
            while True:
                chunk = p.stdout.read(188 * 512)
                if not chunk:
                    break
                write(chunk)
        finally:
            try:
                p.kill()
            except OSError:
                pass
            try:
                p.wait(timeout=5)
            except Exception:
                pass
            try:
                p.stdout.close()
            except Exception:
                pass
        ts += max(0.5, clock() - started)
        if clock() - started < 0.5 and length > 2:      # ffmpeg gave up at once (unreadable file): go on after this slot
            time.sleep(min(2.0, length))


def status(server, d=None):
    d = _settings() if d is None else d
    on = enabled(d)
    out = {"on": on}
    if on and server:
        b = base_url(server, d["iptv_key"])
        out.update(m3u=f"{server}/tv.m3u", xmltv=f"{server}/tv.xml", hdhr=server.split("://", 1)[-1],
                   m3u_long=f"{b}/channels.m3u", xmltv_long=f"{b}/guide.xml")
    return out


def json_bytes(x):
    return json.dumps(x).encode()
