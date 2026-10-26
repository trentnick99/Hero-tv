"""Other devices on your home WiFi (phones, laptops): OFF until you switch it on in Settings > Other devices.

When on, a second listener answers on port 8788 of this PC's home-network address. Nothing there works until a device
is PAIRED: the PC shows a 6-digit code for 10 minutes, the device types it in once and gets a long random key (kept as
a cookie). A wrong code 5 times cancels it. Paired devices can watch, browse and keep their place - they cannot open
Settings, Tools, the channel editor, uploads or anything that changes files. Remove a device in Settings at any time.
The PC itself (127.0.0.1:8787) is unchanged and never needs pairing.
"""
import hashlib
import ipaddress
import json
import secrets
import socket
import threading
import time

from . import config

PAIR_SECONDS = 600
MAX_TRIES = 5
COOKIE = "herotv_dev"

# What a paired device may use. Everything else on the network port answers 403.
REMOTE_GET_API = {"channels", "guide", "library", "info", "now", "prefs", "skip", "theme", "weather", "weather/alerts",
                  "health", "hb", "checklist", "help", "device"}
REMOTE_GET_API_PREFIX = ("info/", "subs/", "skip/", "channel/", "progress/", "next/", "missing/")
REMOTE_POST_API = {"progress", "favorite", "seen", "prefs"}    # prefs from a phone are answered but never saved
OPEN_PATHS = {"/pair", "/pair.html", "/api/pair"}            # usable before pairing

SCHEMA = """CREATE TABLE IF NOT EXISTS devices(token_hash TEXT PRIMARY KEY, media_key TEXT UNIQUE, name TEXT,
            created INTEGER, last_seen INTEGER, ip TEXT)"""

_lock = threading.Lock()
_pairing = {"code": None, "expires": 0, "tries": 0}


def _h(token):
    return hashlib.sha256(token.encode()).hexdigest()


def ensure(conn):
    conn.execute(SCHEMA)


# ---------- the on/off switch (settings.json "lan_share") ----------
def enabled():
    try:
        return bool(json.loads(config.settings_file().read_text(encoding="utf-8-sig")).get("lan_share", False))
    except (OSError, ValueError, AttributeError):
        return False


def set_enabled(on):
    from . import settings_api
    d = settings_api._load()
    d["lan_share"] = bool(on)
    settings_api._save(d)


def lan_port(cfg):
    return cfg.port + 1


def lan_addresses():
    """This PC's addresses on the home network (private IPv4 only), best guess first."""
    found = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))          # no packet is sent; this just asks which network card would be used
        found.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    found += _other_addresses(wait=2 if not found else 0)   # also every other address this PC has (best guess stays first)
    out = []
    for a in found:
        try:
            ip = ipaddress.ip_address(a)
        except ValueError:
            continue
        if ip.version == 4 and ip.is_private and not ip.is_loopback and not ip.is_link_local and a not in out:
            out.append(a)
    return out


_names = {"at": 0.0, "addrs": [], "busy": False}


def _other_addresses(wait=0.0):
    """This PC's other addresses, looked up in the background and remembered for a minute (the lookup can be slow)."""
    import time as _t
    if _t.monotonic() - _names["at"] > 60 and not _names["busy"]:
        _names["busy"] = True

        def look():
            try:
                _names["addrs"] = _by_name()
            finally:
                _names["at"], _names["busy"] = _t.monotonic(), False
        t = threading.Thread(target=look, daemon=True)
        t.start()
        if wait:
            t.join(wait)
    return list(_names["addrs"])


def _by_name():
    try:
        return socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        return []


def host_ok(host_header):
    """The network port only answers to a plain IP address (blocks DNS-rebinding tricks from web pages)."""
    h = (host_header or "").strip().lower()
    if h.startswith("["):
        h = h[1:h.find("]")] if "]" in h else h
    else:
        h = h.rsplit(":", 1)[0]
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


# ---------- pairing ----------
def start_pairing(now=None):
    with _lock:
        _pairing.update(code=f"{secrets.randbelow(10 ** 6):06d}", expires=(now or time.time()) + PAIR_SECONDS, tries=0)
        return pairing_state(now)


def cancel_pairing():
    with _lock:
        _pairing.update(code=None, expires=0, tries=0)


def pairing_state(now=None):
    now = now or time.time()
    if not _pairing["code"] or now >= _pairing["expires"]:
        return None
    return {"code": _pairing["code"], "seconds_left": int(_pairing["expires"] - now)}


def pair(conn, code, name="", ip="", now=None):
    """Swap a correct code for a device key. Returns (token, media_key). Raises ValueError with a plain reason."""
    now = now or time.time()
    with _lock:
        if not _pairing["code"] or now >= _pairing["expires"]:
            raise ValueError("No pairing is open. On the PC: Settings > Other devices > Pair a device.")
        if not secrets.compare_digest(str(code or "").strip(), _pairing["code"]):
            _pairing["tries"] += 1
            if _pairing["tries"] >= MAX_TRIES:
                _pairing.update(code=None, expires=0, tries=0)
                raise ValueError("Too many wrong codes, so pairing was cancelled. Start it again on the PC.")
            raise ValueError("That code is not right. Check the number on the PC screen.")
        _pairing.update(code=None, expires=0, tries=0)            # one code = one device
    token, mkey = secrets.token_urlsafe(32), secrets.token_urlsafe(18)
    ensure(conn)
    conn.execute("INSERT INTO devices(token_hash,media_key,name,created,last_seen,ip) VALUES(?,?,?,?,?,?)",
                 (_h(token), mkey, (str(name or "").strip() or "Device")[:60], int(now), int(now), ip))
    conn.commit()
    return token, mkey


def device_for(conn, token):
    if not token:
        return None
    ensure(conn)
    return conn.execute("SELECT * FROM devices WHERE token_hash=?", (_h(token),)).fetchone()


def device_for_media_key(conn, key):
    if not key:
        return None
    ensure(conn)
    return conn.execute("SELECT * FROM devices WHERE media_key=?", (key,)).fetchone()


def touch(conn, row, ip, now=None):
    if row and int(now or time.time()) - (row["last_seen"] or 0) > 60:
        conn.execute("UPDATE devices SET last_seen=?, ip=? WHERE token_hash=?", (int(now or time.time()), ip, row["token_hash"]))
        conn.commit()


def devices(conn):
    ensure(conn)
    return [{"id": r["token_hash"][:12], "name": r["name"], "created": r["created"], "last_seen": r["last_seen"], "ip": r["ip"]}
            for r in conn.execute("SELECT * FROM devices ORDER BY created")]


def remove(conn, device_id=None):
    """Forget one device (id from devices()), or every device when device_id is None."""
    ensure(conn)
    if device_id is None:
        n = conn.execute("DELETE FROM devices").rowcount
    else:
        if not device_id or len(device_id) < 8:
            raise ValueError("unknown device")
        n = conn.execute("DELETE FROM devices WHERE substr(token_hash,1,12)=?", (device_id,)).rowcount
    conn.commit()
    return n


def cookie_token(cookie_header):
    for part in (cookie_header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return v
    return None


def device_name(user_agent):
    ua = user_agent or ""
    for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android device"), ("Macintosh", "Mac"),
                      ("Windows", "Windows PC"), ("CrOS", "Chromebook"), ("Linux", "Linux computer")):
        if key in ua:
            return name
    return "Device"
