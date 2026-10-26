"""HERO TV on a Roku TV: find the TV on the home network, build the HERO TV app for it (with this PC's address and
its own watch-only key already inside, so nothing has to be typed on the TV) and install it through the Roku's
developer installer. Developer mode has to be switched on once on the TV (remote: Home x3, Up x2, Right, Left,
Right, Left, Right) - it asks for a password, which is then typed here.

The app talks to the paired-devices listener (port 8788) exactly like a phone: watch-only."""
import io
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from . import __version__, config

DEVICE_NAME = "Roku TV (HERO TV app)"
DEV_USER = "rokudev"
APP_DIR = Path(config.ROOT) / "roku"


def _opener(auth=None):
    """LAN only: never through a proxy set in Windows."""
    handlers = [urllib.request.ProxyHandler({})]
    if auth:
        handlers.append(auth)
    return urllib.request.build_opener(*handlers)


def _ip_ok(ip):
    import ipaddress
    try:
        a = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        return False
    return a.version == 4 and a.is_private and not a.is_loopback


# ---------- finding Roku TVs ----------
def discover(timeout=3.0, sock=None):
    """Roku TVs on the home network: [{"ip", "name", "model", "dev"}] (SSDP search for roku:ecp)."""
    msg = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\nST: roku:ecp\r\n\r\n").encode()
    s = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    ips = []
    try:
        s.settimeout(0.5)
        try:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        except OSError:
            pass
        for _ in range(2):
            s.sendto(msg, ("239.255.255.250", 1900))
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                data, addr = s.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            text = data.decode("utf-8", "replace")
            m = re.search(r"(?im)^location:\s*http://([0-9.]+):8060", text)
            ip = m.group(1) if m else addr[0]
            if "roku" in text.lower() and _ip_ok(ip) and ip not in ips:
                ips.append(ip)
    finally:
        if sock is None:
            s.close()
    out = []
    for ip in ips:
        out.append(device_info(ip) or {"ip": ip, "name": "Roku", "model": "", "dev": None})
    return out


def device_info(ip, fetch=None):
    """Name, model and whether developer mode is on, from the TV itself (ECP on port 8060)."""
    if not _ip_ok(ip):
        return None
    try:
        raw = (fetch or (lambda u: _opener().open(u, timeout=4).read()))(f"http://{ip}:8060/query/device-info")
        root = ET.fromstring(raw)
    except (OSError, ET.ParseError, urllib.error.URLError):
        return None
    g = lambda k: (root.findtext(k) or "").strip()
    dev = g("developer-enabled").lower()
    return {"ip": ip, "name": g("user-device-name") or g("friendly-device-name") or g("default-device-name") or "Roku",
            "model": g("friendly-model-name") or g("model-name"), "dev": True if dev == "true" else (False if dev == "false" else None)}


# ---------- building the app ----------
def _bs(s):
    return '"' + str(s).replace('"', '""') + '"'


def config_brs(server, token, mk, station="HERO TV", color="#ffcf1f"):
    return ("' Written by HERO TV on the PC when it installed this app.\n"
            "function HeroConfig() as object\n    return {\n"
            f"        server: {_bs(server)}\n        token: {_bs(token)}\n        mk: {_bs(mk)}\n"
            f"        station: {_bs(station)}\n        color: {_bs(color)}\n        version: {_bs(__version__)}\n"
            "    }\nend function\n")


def build_number(version=__version__):
    p = [int(x) for x in re.findall(r"\d+", version)[:3]] + [0, 0, 0]
    return p[0] * 10000 + p[1] * 100 + p[2]


def build_zip(server, token, mk, station="HERO TV", color="#ffcf1f", app_dir=None):
    """The app as the zip the Roku installer wants (manifest at the top)."""
    app_dir = Path(app_dir or APP_DIR)
    if not (app_dir / "manifest").is_file():
        raise ValueError("The Roku app files are missing from this HERO TV folder - reinstall HERO TV.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(app_dir.rglob("*")):
            if not f.is_file() or f.name.startswith("."):
                continue
            rel = f.relative_to(app_dir).as_posix()
            if rel == "source/config.brs":
                z.writestr(rel, config_brs(server, token, mk, station, color))
            elif rel == "manifest":
                text = f.read_text(encoding="utf-8")
                text = re.sub(r"(?m)^build_version=.*$", f"build_version={build_number()}", text)
                z.writestr(rel, text)
            else:
                z.write(f, rel)
    return buf.getvalue()


# ---------- installing ----------
def _multipart(fields, files):
    boundary = "----herotv" + os.urandom(8).hex()
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, (name, data, ctype) in files.items():
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{name}\"\r\n"
                  f"Content-Type: {ctype}\r\n\r\n".encode())
        out.write(data)
        out.write(b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


def install(ip, password, zip_bytes, opener=None):
    """Send the app to the TV's developer installer. Returns a short plain-English result; raises ValueError."""
    if not _ip_ok(ip):
        raise ValueError("That is not a home-network address (it should look like 192.168.1.23).")
    if not password:
        raise ValueError("Type the developer password you chose on the TV.")
    url = f"http://{ip}/plugin_install"
    if opener is None:
        pm = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        pm.add_password(None, f"http://{ip}/", DEV_USER, password)
        opener = _opener(urllib.request.HTTPDigestAuthHandler(pm))
    body, ctype = _multipart({"mysubmit": "Install"}, {"archive": ("herotv.zip", zip_bytes, "application/zip")})
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype}, method="POST")
    try:
        with opener.open(req, timeout=90) as r:
            page = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ValueError("The TV did not accept the password. Use the developer password you set on the TV.")
        raise ValueError(f"The TV refused the app (error {e.code}).")
    except (urllib.error.URLError, OSError):
        raise ValueError("Could not reach the TV's installer. Is developer mode switched on (see the steps above), "
                         "and is the TV on?")
    low = page.lower()
    if "install success" in low or "application received" in low:
        return "installed"
    if "identical to previous version" in low:
        return "already up to date"
    m = re.search(r"(?i)install failure:?\s*([^<\n]{0,160})", page)
    raise ValueError("The TV could not install the app" + (f": {m.group(1).strip()}" if m else "."))


def launch(ip, opener=None):
    try:
        (opener or _opener()).open(urllib.request.Request(f"http://{ip}:8060/launch/dev", data=b"", method="POST"), timeout=5).read()
        return True
    except (OSError, urllib.error.URLError):
        return False


# ---------- remembered TV (settings.json "roku") ----------
def saved():
    from . import settings_api
    r = settings_api._load().get("roku")
    return r if isinstance(r, dict) else {}


def remember(**kw):
    from . import settings_api
    d = settings_api._load()
    r = d.get("roku") if isinstance(d.get("roku"), dict) else {}
    r.update({k: v for k, v in kw.items() if v is not None})
    d["roku"] = r
    settings_api._save(d)
    return r


def forget():
    from . import settings_api
    d = settings_api._load()
    d.pop("roku", None)
    settings_api._save(d)


def server_url(cfg):
    from . import remote as R
    addrs = R.lan_addresses()
    if not addrs:
        raise ValueError("This PC has no home-network address right now - check its cable or WiFi.")
    return f"http://{addrs[0]}:{R.lan_port(cfg)}"


def install_on_tv(conn, cfg, ip, password, name="", opener=None, launcher=None):
    """Everything in one go: a fresh watch-only key for the TV, the app built with it and this PC's address,
    installed and started. The previous key of this TV (if any) is removed. Returns a summary dict."""
    from . import remote as R
    server = server_url(cfg)
    st = config.station()
    old = saved()
    token, mk = R.add_device(conn, DEVICE_NAME + (f" - {name}" if name else ""), ip)
    try:
        result = install(ip, password, build_zip(server, token, mk, st.get("name", "HERO TV"), st.get("color", "#ffcf1f")), opener)
    except Exception:
        R.remove_token(conn, token)                       # nothing installed: do not leave a key behind
        raise
    if old.get("key_id"):
        R.remove(conn, old["key_id"])
    remember(ip=ip, name=name or old.get("name") or "Roku TV", password=password, server=server,
             installed=__version__, key_id=R.id_for(token), when=int(time.time()))
    started = (launcher or launch)(ip)
    return {"result": result, "server": server, "started": started}


def needs_update(cfg):
    """Why the TV app should be reinstalled now (newer HERO TV, or this PC got a new address), or ""."""
    r = saved()
    if not r.get("ip") or not r.get("password"):
        return ""
    if r.get("installed") != __version__:
        return "HERO TV was updated"
    try:
        if r.get("server") != server_url(cfg):
            return "this PC's network address changed"
    except ValueError:
        return ""
    return ""
