"""Let a TV's own media player (Roku Media Player, VLC, smart-TV "Media" apps) browse and play your library.

This is a standard UPnP/DLNA media server. It is OFF until switched on in Settings > Other devices, because the
standard has no pairing: while it is on, ANY device on your WiFi can see and play your videos (read-only - nothing
can be changed, renamed, uploaded or deleted through it). It answers on port 8789 and announces itself on the
network (SSDP, UDP port 1900). Only videos in your library are served; nothing else on the PC can be reached.
"""
import html
import json
import os
import random
import re
import socket
import struct
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler
from urllib.parse import quote, unquote, urlparse

from . import __version__, config

SSDP_ADDR, SSDP_PORT = "239.255.255.250", 1900
MAX_AGE = 1800
DEVICE = "urn:schemas-upnp-org:device:MediaServer:1"
CDS = "urn:schemas-upnp-org:service:ContentDirectory:1"
CMS = "urn:schemas-upnp-org:service:ConnectionManager:1"
MIME = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".mkv": "video/x-matroska",
        ".webm": "video/webm"}
DLNA_FLAGS = "DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01700000000000000000000000000000"
MAX_SOAP = 65536


# ---------- switch and identity (settings.json) ----------
def _settings():
    try:
        d = json.loads(config.settings_file().read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def enabled():
    return bool(_settings().get("dlna_share", False))


def set_enabled(on):
    from . import settings_api
    d = settings_api._load()
    d["dlna_share"] = bool(on)
    d.setdefault("dlna_uuid", str(uuid.uuid4()))
    settings_api._save(d)


def device_uuid():
    u = _settings().get("dlna_uuid")
    if isinstance(u, str) and re.fullmatch(r"[0-9a-f-]{36}", u):
        return u
    from . import settings_api
    d = settings_api._load()
    d["dlna_uuid"] = str(uuid.uuid4())
    settings_api._save(d)
    return d["dlna_uuid"]


def port(cfg):
    return cfg.port + 2


def friendly_name():
    return f"{config.station()['name']} (HERO TV)"


# ---------- the library as folders ----------
def _x(t):
    return html.escape(str(t or ""), quote=True)


def _rows(conn):
    return conn.execute("SELECT id,path,title,year,franchise,series,season,episode,runtime_s,size,added FROM media "
                        "WHERE available=1 AND verified=1 ORDER BY franchise,ord,series,season,episode,title").fetchall()


def _label(r):
    if r["series"]:
        return f"{r['series']} S{r['season'] or 0}E{r['episode'] or 0}" + (f" - {r['title']}" if r["title"] and r["title"] != r["series"] else "")
    return r["title"] + (f" ({r['year']})" if r["year"] else "")


def children(conn, oid, now=None):
    """[(kind, id, title, row_or_count)] directly inside container oid. kind = 'c' (folder) or 'i' (video)."""
    rows = _rows(conn)
    now = now or time.time()
    if oid == "0":
        out = []
        recent = [r for r in rows if (r["added"] or 0) > now - 30 * 86400]
        if recent:
            out.append(("c", "new", "New in your library", len(recent)))
        folders = sorted({r["franchise"] or "Other" for r in rows}, key=str.lower)
        for f in folders:
            n = len({(r["series"] or f"#{r['id']}") for r in rows if (r["franchise"] or "Other") == f})
            out.append(("c", "f:" + quote(f, safe=""), f, n))
        return out
    if oid == "new":
        recent = sorted((r for r in rows if (r["added"] or 0) > now - 30 * 86400), key=lambda r: -(r["added"] or 0))
        return [("i", f"m:{r['id']}", _label(r), r) for r in recent]
    if oid.startswith("f:"):
        f = unquote(oid[2:])
        inside = [r for r in rows if (r["franchise"] or "Other") == f]
        if not inside:
            return None
        out, shows = [], {}
        for r in inside:
            if r["series"]:
                shows.setdefault(r["series"], 0)
                shows[r["series"]] += 1
        for s in sorted(shows, key=str.lower):
            out.append(("c", f"s:{quote(f, safe='')}/{quote(s, safe='')}", s, shows[s]))
        out += [("i", f"m:{r['id']}", _label(r), r) for r in inside if not r["series"]]
        return out
    if oid.startswith("s:"):
        f, _, s = oid[2:].partition("/")
        f, s = unquote(f), unquote(s)
        eps = [r for r in rows if (r["franchise"] or "Other") == f and r["series"] == s]
        if not eps:
            return None
        eps.sort(key=lambda r: (r["season"] or 0, r["episode"] or 0, r["title"]))
        return [("i", f"m:{r['id']}", _label(r), r) for r in eps]
    return None


def parent_of(oid):
    if oid in ("new",) or oid.startswith("f:"):
        return "0"
    if oid.startswith("s:"):
        return "f:" + oid[2:].partition("/")[0]
    return "0"


def subtitle_file(path):
    """The subtitle file a TV should get for this video: English (or unlabelled) first, forced-only tracks last."""
    from . import subtitles
    files = subtitles.external_files(path)
    if not files:
        return None
    rank = lambda f: (f["forced"], f["language"] not in ("English", ""), f["language"] != "English", f["file"])
    return sorted(files, key=rank)[0]["file"]


def vtt_to_srt(text):
    """WebVTT -> SubRip (what TV media players read)."""
    import re as _re
    blocks, n = [], 0
    for block in _re.split(r"\r?\n\s*\r?\n", text.replace("\ufeff", "")):
        lines = [l for l in block.strip().splitlines()]
        if not lines or lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        i = next((k for k, l in enumerate(lines) if "-->" in l), None)
        if i is None:
            continue
        a, _, b = lines[i].partition("-->")
        fix = lambda t: (("00:" + t) if t.count(":") == 1 else t).replace(".", ",")
        a, b = fix(a.strip()), fix(b.strip().split(" ")[0])
        n += 1
        blocks.append(f"{n}\n{a} --> {b}\n" + "\n".join(lines[i + 1:]))
    return "\n\n".join(blocks) + "\n"


def srt_text(path):
    from . import subtitles
    with open(path, "rb") as fh:
        text = subtitles.decode(fh.read())
    return vtt_to_srt(text) if path.lower().endswith(".vtt") else text.replace("\ufeff", "")


def _dur(s):
    s = max(0.0, float(s or 0))
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:06.3f}"


def didl(entries, parent, base):
    parts = ['<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" '
             'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/" '
             'xmlns:sec="http://www.sec.co.kr/">']
    for kind, oid, title, x in entries:
        if kind == "c":
            parts.append(f'<container id="{_x(oid)}" parentID="{_x(parent)}" restricted="1" childCount="{int(x)}" searchable="0">'
                         f'<dc:title>{_x(title)}</dc:title><upnp:class>object.container.storageFolder</upnp:class></container>')
        else:
            r = x
            ext = os.path.splitext(r["path"])[1].lower()
            mime = MIME.get(ext, "video/mp4")
            url = f"{base}/dlna/media/{r['id']}{ext}"
            sub = f"{base}/dlna/sub/{r['id']}.srt" if subtitle_file(r["path"]) else ""
            subs = (f'<sec:CaptionInfoEx sec:type="srt">{_x(sub)}</sec:CaptionInfoEx>'
                    f'<res protocolInfo="http-get:*:text/srt:*">{_x(sub)}</res>') if sub else ""
            parts.append(f'<item id="{_x(oid)}" parentID="{_x(parent)}" restricted="1"><dc:title>{_x(title)}</dc:title>'
                         f'<upnp:class>object.item.videoItem</upnp:class>'
                         + (f'<dc:date>{int(r["year"])}-01-01</dc:date>' if r["year"] else "")
                         + f'<upnp:albumArtURI dlna:profileID="JPEG_TN">{base}/dlna/thumb/{r["id"]}.jpg</upnp:albumArtURI>'
                         f'<res protocolInfo="http-get:*:{mime}:{DLNA_FLAGS}" size="{int(r["size"] or 0)}" '
                         f'duration="{_dur(r["runtime_s"])}">{_x(url)}</res>{subs}</item>')
    parts.append("</DIDL-Lite>")
    return "".join(parts)


def browse(conn, oid, flag, start, count, base):
    """(Result DIDL, NumberReturned, TotalMatches). Raises KeyError for an unknown object."""
    if flag == "BrowseMetadata":
        if oid == "0":
            return didl([("c", "0", friendly_name(), len(children(conn, "0")))], "-1", base), 1, 1
        if oid.startswith("m:"):
            r = next((r for r in _rows(conn) if f"m:{r['id']}" == oid), None)
            if r is None:
                raise KeyError(oid)
            return didl([("i", oid, _label(r), r)], "0", base), 1, 1
        kids = children(conn, oid)
        if kids is None:
            raise KeyError(oid)
        title = unquote(oid[2:].partition("/")[2]) if oid.startswith("s:") else ("New in your library" if oid == "new" else unquote(oid[2:]))
        return didl([("c", oid, title, len(kids))], parent_of(oid), base), 1, 1
    kids = children(conn, oid)
    if kids is None:
        raise KeyError(oid)
    page = kids[start:start + count] if count else kids[start:]
    return didl(page, oid, base), len(page), len(kids)


# ---------- XML documents ----------
def description(base):
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<root xmlns="urn:schemas-upnp-org:device-1-0" xmlns:dlna="urn:schemas-dlna-org:device-1-0">'
            f'<specVersion><major>1</major><minor>0</minor></specVersion><device><deviceType>{DEVICE}</deviceType>'
            f'<friendlyName>{_x(friendly_name())}</friendlyName><manufacturer>HERO TV</manufacturer>'
            f'<modelDescription>Your own videos from HERO TV</modelDescription><modelName>HERO TV</modelName>'
            f'<modelNumber>{_x(__version__)}</modelNumber><UDN>uuid:{device_uuid()}</UDN><dlna:X_DLNADOC>DMS-1.50</dlna:X_DLNADOC>'
            f'<presentationURL>{base}/</presentationURL><serviceList>'
            f'<service><serviceType>{CDS}</serviceType><serviceId>urn:upnp-org:serviceId:ContentDirectory</serviceId>'
            f'<SCPDURL>/dlna/cds.xml</SCPDURL><controlURL>/dlna/control/cds</controlURL><eventSubURL>/dlna/event/cds</eventSubURL></service>'
            f'<service><serviceType>{CMS}</serviceType><serviceId>urn:upnp-org:serviceId:ConnectionManager</serviceId>'
            f'<SCPDURL>/dlna/cms.xml</SCPDURL><controlURL>/dlna/control/cms</controlURL><eventSubURL>/dlna/event/cms</eventSubURL></service>'
            f'</serviceList></device></root>')


def _scpd(actions, variables):
    a = "".join(f"<action><name>{n}</name><argumentList>" + "".join(
        f"<argument><name>{an}</name><direction>{d}</direction><relatedStateVariable>{v}</relatedStateVariable></argument>"
        for an, d, v in args) + "</argumentList></action>" for n, args in actions)
    v = "".join(f'<stateVariable sendEvents="{"yes" if ev else "no"}"><name>{n}</name><dataType>{t}</dataType>'
                + ("".join(f"<allowedValueList>{''.join(f'<allowedValue>{x}</allowedValue>' for x in allowed)}</allowedValueList>") if allowed else "")
                + "</stateVariable>" for n, t, ev, allowed in variables)
    return ('<?xml version="1.0" encoding="utf-8"?>\n<scpd xmlns="urn:schemas-upnp-org:service-1-0"><specVersion><major>1</major>'
            f'<minor>0</minor></specVersion><actionList>{a}</actionList><serviceStateTable>{v}</serviceStateTable></scpd>')


CDS_XML = _scpd(
    [("Browse", [("ObjectID", "in", "A_ARG_TYPE_ObjectID"), ("BrowseFlag", "in", "A_ARG_TYPE_BrowseFlag"),
                 ("Filter", "in", "A_ARG_TYPE_Filter"), ("StartingIndex", "in", "A_ARG_TYPE_Index"),
                 ("RequestedCount", "in", "A_ARG_TYPE_Count"), ("SortCriteria", "in", "A_ARG_TYPE_SortCriteria"),
                 ("Result", "out", "A_ARG_TYPE_Result"), ("NumberReturned", "out", "A_ARG_TYPE_Count"),
                 ("TotalMatches", "out", "A_ARG_TYPE_Count"), ("UpdateID", "out", "A_ARG_TYPE_UpdateID")]),
     ("GetSearchCapabilities", [("SearchCaps", "out", "SearchCapabilities")]),
     ("GetSortCapabilities", [("SortCaps", "out", "SortCapabilities")]),
     ("GetSystemUpdateID", [("Id", "out", "SystemUpdateID")])],
    [("A_ARG_TYPE_ObjectID", "string", False, None), ("A_ARG_TYPE_Result", "string", False, None),
     ("A_ARG_TYPE_BrowseFlag", "string", False, ["BrowseMetadata", "BrowseDirectChildren"]),
     ("A_ARG_TYPE_Filter", "string", False, None), ("A_ARG_TYPE_SortCriteria", "string", False, None),
     ("A_ARG_TYPE_Index", "ui4", False, None), ("A_ARG_TYPE_Count", "ui4", False, None),
     ("A_ARG_TYPE_UpdateID", "ui4", False, None), ("SearchCapabilities", "string", False, None),
     ("SortCapabilities", "string", False, None), ("SystemUpdateID", "ui4", True, None)])

CMS_XML = _scpd(
    [("GetProtocolInfo", [("Source", "out", "SourceProtocolInfo"), ("Sink", "out", "SinkProtocolInfo")]),
     ("GetCurrentConnectionIDs", [("ConnectionIDs", "out", "CurrentConnectionIDs")])],
    [("SourceProtocolInfo", "string", True, None), ("SinkProtocolInfo", "string", True, None),
     ("CurrentConnectionIDs", "string", True, None)])


def soap(action, service, out):
    body = "".join(f"<{k}>{_x(v)}</{k}>" for k, v in out)
    return ('<?xml version="1.0" encoding="utf-8"?>\n<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            f's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:{action}Response xmlns:u="{service}">'
            f'{body}</u:{action}Response></s:Body></s:Envelope>')


def soap_fault(code, text):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><s:Fault><faultcode>s:Client</faultcode>'
            '<faultstring>UPnPError</faultstring><detail><UPnPError xmlns="urn:schemas-upnp-org:control-1-0">'
            f'<errorCode>{code}</errorCode><errorDescription>{_x(text)}</errorDescription></UPnPError></detail></s:Fault></s:Body></s:Envelope>')


def _arg(body, name):
    """One argument from a SOAP request (plain text match: no XML entities are ever expanded)."""
    m = re.search(rf"<(?:\w+:)?{name}(?:\s[^>]*)?>(.*?)</(?:\w+:)?{name}>", body, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


# ---------- HTTP side ----------
def make_handler(app):
    from . import thumbs

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = f"HERO-TV/{__version__} UPnP/1.0 DLNADOC/1.50"

        def log_message(self, fmt, *a):
            if os.environ.get("HEROTV_ACCESS_LOG"):
                super().log_message(fmt, *a)

        def base(self):
            host = self.headers.get("Host") or f"{self.server.server_address[0]}:{self.server.server_address[1]}"
            if not re.fullmatch(r"[0-9.]+(:\d+)?|\[[0-9a-fA-F:]+\](:\d+)?", host):
                host = f"{_local_ip_for(self.client_address[0])}:{self.server.server_address[1]}"
            return f"http://{host}"

        def send(self, code, body=b"", ctype="text/xml; charset=\"utf-8\"", extra=None):
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def guard(self):
            if not enabled():
                self.close_connection = True
                self.send(503, "switched off", "text/plain")
                return False
            return True

        def do_GET(self):
            self.get()

        def do_HEAD(self):
            self.get()

        def get(self):
            if not self.guard():
                return
            p = urlparse(self.path).path
            if p == "/dlna/description.xml":
                return self.send(200, description(self.base()))
            if p == "/dlna/cds.xml":
                return self.send(200, CDS_XML)
            if p == "/dlna/cms.xml":
                return self.send(200, CMS_XML)
            m = re.fullmatch(r"/dlna/(media|thumb|sub)/(\d+)(\.\w+)?", p)
            if m:
                c = app.db()
                try:
                    row = c.execute("SELECT * FROM media WHERE id=? AND available=1 AND verified=1", (int(m.group(2)),)).fetchone()
                finally:
                    c.close()
                if row is None:
                    return self.send(404, "not found", "text/plain")
                if m.group(1) == "sub":
                    f = subtitle_file(row["path"])
                    if not f:
                        return self.send(404, "no subtitles", "text/plain")
                    return self.send(200, srt_text(f), "text/srt; charset=utf-8")
                if m.group(1) == "thumb":
                    f = thumbs.thumb_file(app.cfg, row)
                    if not os.path.isfile(f):
                        return self.send(404, "no picture yet", "text/plain")
                    with open(f, "rb") as fh:
                        return self.send(200, fh.read(), "image/jpeg")
                extra = {}
                if self.headers.get("getcaptionInfo.sec") == "1" and subtitle_file(row["path"]):
                    extra["CaptionInfo.sec"] = f"{self.base()}/dlna/sub/{row['id']}.srt"   # Samsung-style TVs ask this way
                return self.file(row["path"], extra)
            return self.send(404, "not found", "text/plain")

        def file(self, path, extra=None):
            if not os.path.isfile(path):
                return self.send(404, "not found", "text/plain")
            size = os.path.getsize(path)
            start, end, code = 0, size - 1, 200
            rng = self.headers.get("Range", "")
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip()) if rng else None
            if rng and not m:
                return self.send(416, b"", "text/plain", {"Content-Range": f"bytes */{size}"})
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    end = min(size - 1, int(m.group(2))) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2)))
                if start > end or start >= size:
                    return self.send(416, b"", "text/plain", {"Content-Range": f"bytes */{size}"})
                code = 206
            self.send_response(code)
            self.send_header("Content-Type", MIME.get(os.path.splitext(path)[1].lower(), "video/mp4"))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if code == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("transferMode.dlna.org", "Streaming")
            self.send_header("contentFeatures.dlna.org", DLNA_FLAGS)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command == "HEAD":
                return
            with open(path, "rb") as fh:
                fh.seek(start)
                left = end - start + 1
                try:
                    while left > 0:
                        chunk = fh.read(min(1 << 20, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
                except (ConnectionError, OSError):
                    pass

        def do_POST(self):
            if not self.guard():
                return
            n = int(self.headers.get("Content-Length") or 0)
            if n < 0 or n > MAX_SOAP:
                self.close_connection = True
                return self.send(413, "too large", "text/plain")
            body = self.rfile.read(n).decode("utf-8", "replace")
            p = urlparse(self.path).path
            action = (self.headers.get("SOAPACTION") or "").strip('"').rpartition("#")[2]
            if p == "/dlna/control/cds":
                if action == "Browse":
                    c = app.db()
                    try:
                        start = int(_arg(body, "StartingIndex") or 0)
                        count = int(_arg(body, "RequestedCount") or 0)
                        res, num, total = browse(c, _arg(body, "ObjectID") or "0", _arg(body, "BrowseFlag") or "BrowseDirectChildren",
                                                 max(0, start), max(0, count), self.base())
                    except KeyError:
                        return self.send(500, soap_fault(701, "No such object"))
                    except ValueError:
                        return self.send(500, soap_fault(402, "Invalid args"))
                    finally:
                        c.close()
                    return self.send(200, soap("Browse", CDS, [("Result", res), ("NumberReturned", num),
                                                                ("TotalMatches", total), ("UpdateID", 1)]))
                if action == "GetSearchCapabilities":
                    return self.send(200, soap(action, CDS, [("SearchCaps", "")]))
                if action == "GetSortCapabilities":
                    return self.send(200, soap(action, CDS, [("SortCaps", "")]))
                if action == "GetSystemUpdateID":
                    return self.send(200, soap(action, CDS, [("Id", 1)]))
            if p == "/dlna/control/cms":
                if action == "GetProtocolInfo":
                    src = ",".join(f"http-get:*:{m}:*" for m in sorted(set(MIME.values())))
                    return self.send(200, soap(action, CMS, [("Source", src), ("Sink", "")]))
                if action == "GetCurrentConnectionIDs":
                    return self.send(200, soap(action, CMS, [("ConnectionIDs", "0")]))
            return self.send(500, soap_fault(401, "Invalid action"))

        def do_SUBSCRIBE(self):
            if not self.guard():
                return
            self.send(200, b"", "text/plain", {"SID": f"uuid:{uuid.uuid4()}", "TIMEOUT": "Second-1800"})

        def do_UNSUBSCRIBE(self):
            self.send(200, b"", "text/plain")

    return H


# ---------- SSDP: being found on the network ----------
def _local_ip_for(remote):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((remote if remote and not remote.startswith("127.") else "192.0.2.1", 9))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def search_targets(uid):
    return ["upnp:rootdevice", f"uuid:{uid}", DEVICE, CDS, CMS]


def usn(uid, st):
    return f"uuid:{uid}" if st == f"uuid:{uid}" else f"uuid:{uid}::{st}"


def answers(datagram, http_port, ip, uid):
    """The replies to one received SSDP packet ([] unless it is an M-SEARCH for something we are)."""
    try:
        text = datagram.decode("utf-8", "replace")
    except AttributeError:
        text = str(datagram)
    lines = text.split("\r\n")
    if not lines or not lines[0].upper().startswith("M-SEARCH"):
        return []
    hdr = {}
    for line in lines[1:]:
        k, _, v = line.partition(":")
        hdr[k.strip().upper()] = v.strip()
    if hdr.get("MAN", "").strip('"') != "ssdp:discover":
        return []
    st = hdr.get("ST", "")
    targets = search_targets(uid)
    wanted = targets if st == "ssdp:all" else [st] if st in targets else []
    date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    return [("HTTP/1.1 200 OK\r\n"
             f"CACHE-CONTROL: max-age={MAX_AGE}\r\nDATE: {date}\r\nEXT:\r\n"
             f"LOCATION: http://{ip}:{http_port}/dlna/description.xml\r\n"
             f"SERVER: Windows/10 UPnP/1.0 HERO-TV/{__version__}\r\n"
             f"ST: {t}\r\nUSN: {usn(uid, t)}\r\n\r\n").encode() for t in wanted]


def notify(kind, http_port, ip, uid):
    out = []
    for t in search_targets(uid):
        msg = (f"NOTIFY * HTTP/1.1\r\nHOST: {SSDP_ADDR}:{SSDP_PORT}\r\nNT: {t}\r\nNTS: ssdp:{kind}\r\nUSN: {usn(uid, t)}\r\n")
        if kind == "alive":
            msg += (f"CACHE-CONTROL: max-age={MAX_AGE}\r\nLOCATION: http://{ip}:{http_port}/dlna/description.xml\r\n"
                    f"SERVER: Windows/10 UPnP/1.0 HERO-TV/{__version__}\r\n")
        out.append((msg + "\r\n").encode())
    return out


class Announcer:
    """Answers 'who is a media server?' questions on the network and says hello / goodbye."""

    def __init__(self, http_port, uid):
        self.http_port, self.uid = http_port, uid
        self.stop_ev = threading.Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        self.sock.bind(("", SSDP_PORT))
        try:
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                 struct.pack("4s4s", socket.inet_aton(SSDP_ADDR), socket.inet_aton("0.0.0.0")))
        except OSError:
            pass                                 # no multicast here: TVs can still be pointed at the address
        self.sock.settimeout(1.0)
        self.out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.out.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    def say(self, kind):
        ip = _local_ip_for(None)
        for pkt in notify(kind, self.http_port, ip, self.uid):
            try:
                self.out.sendto(pkt, (SSDP_ADDR, SSDP_PORT))
            except OSError:
                pass

    def run(self):
        self.say("alive")
        next_hello = time.time() + MAX_AGE / 3
        while not self.stop_ev.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                data = None
            except OSError:
                break
            if data:
                replies = answers(data, self.http_port, _local_ip_for(addr[0]), self.uid)
                if replies:
                    time.sleep(random.uniform(0, 0.5))
                    for r in replies:
                        try:
                            self.out.sendto(r, addr)
                        except OSError:
                            pass
            if time.time() > next_hello:
                self.say("alive")
                next_hello = time.time() + MAX_AGE / 3
        self.say("byebye")
        self.sock.close()
        self.out.close()

    def stop(self):
        self.stop_ev.set()


class Server:
    """The whole thing: HTTP on port 8789 plus the announcer. start()/stop() from Settings."""

    def __init__(self, app):
        self.app = app
        self.http = self.ann = None

    def start(self):
        if self.http:
            return
        p = port(self.app.cfg)
        from .server import _TVServer              # same server class, without the slow network-name lookup
        for attempt in range(8):                   # just switched off? a TV's open connection can hold the port a moment
            try:
                self.http = _TVServer(("0.0.0.0", p), make_handler(self.app))
                break
            except OSError as e:
                if attempt == 7:
                    raise ValueError(f"Port {p} is busy on this PC, so the TV cannot connect ({e}).")
                time.sleep(0.4)
        self.http.daemon_threads = True
        threading.Thread(target=self.http.serve_forever, daemon=True, name="dlna-http").start()
        try:
            self.ann = Announcer(p, device_uuid())
            threading.Thread(target=self.ann.run, daemon=True, name="dlna-ssdp").start()
        except OSError:
            self.ann = None                    # discovery unavailable; the address still works when typed in

    def stop(self):
        if self.ann:
            self.ann.stop()
            self.ann = None
        if self.http:
            self.http.shutdown()
            self.http.server_close()
            self.http = None

    @property
    def running(self):
        return self.http is not None
