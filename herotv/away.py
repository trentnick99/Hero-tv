"""Watching away from home, through Tailscale.

Tailscale is a free app that puts your PC and your phone on one private, encrypted network wherever they are (home
WiFi, mobile data, a hotel). Nothing on your router changes and nothing is opened to the internet: only devices signed
in to your own Tailscale account can reach the PC, and HERO TV still asks each of them to pair first.

This module only looks: is Tailscale on this PC, is it signed in, what is the PC's private address, and which of your
other devices (your iPhone...) are on the same private network. It never changes Tailscale's settings.
"""
import ipaddress
import json
import os
import shutil
import subprocess
import threading
import time

# Tailscale gives every device an address in 100.64.0.0/10 (and fd7a:115c:a1e0::/48 for IPv6). Nothing else on a home
# network uses these, so a request from one of them came through Tailscale.
TAILNET_V4 = ipaddress.ip_network("100.64.0.0/10")
TAILNET_V6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
WIN_PATHS = (r"C:\Program Files\Tailscale\tailscale.exe", r"C:\Program Files (x86)\Tailscale\tailscale.exe")
DOWNLOAD = "https://tailscale.com/download/windows"
PHONE_APP = {"ios": "https://apps.apple.com/app/tailscale/id1470499037",
             "android": "https://play.google.com/store/apps/details?id=com.tailscale.ipn"}
CACHE_S = 15

_cache = {"at": 0.0, "val": None}
_lock = threading.Lock()


def is_tailnet(addr):
    """True for an address Tailscale hands out (a phone reaching the PC through Tailscale)."""
    try:
        ip = ipaddress.ip_address(str(addr or "").strip().strip("[]").split("%")[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip in (TAILNET_V4 if ip.version == 4 else TAILNET_V6)


def exe():
    """tailscale.exe (or the tailscale command), or '' when Tailscale is not installed."""
    found = shutil.which("tailscale")
    if found:
        return found
    for p in WIN_PATHS:
        if os.path.isfile(p):
            return p
    return ""


def _run_status(path):
    from . import tools
    r = tools.run([path, "status", "--json"], timeout=8)
    return r.stdout or ""


def parse(raw):
    """What `tailscale status --json` says, in the few words HERO TV needs."""
    try:
        d = json.loads(raw or "{}")
    except ValueError:
        d = {}
    if not isinstance(d, dict):
        d = {}
    me = d.get("Self") if isinstance(d.get("Self"), dict) else {}
    ips = [a for a in me.get("TailscaleIPs") or [] if isinstance(a, str)]
    v4 = next((a for a in ips if ":" not in a), "")
    dns = str(me.get("DNSName") or "").rstrip(".").lower()
    peers = []
    for p in (d.get("Peer") or {}).values() if isinstance(d.get("Peer"), dict) else []:
        if not isinstance(p, dict):
            continue
        pips = [a for a in p.get("TailscaleIPs") or [] if isinstance(a, str)]
        os_ = str(p.get("OS") or "").lower()
        peers.append({"name": str(p.get("HostName") or p.get("DNSName") or "device")[:60], "os": os_,
                      "phone": os_ in ("ios", "android"), "online": bool(p.get("Online")),
                      "ip": next((a for a in pips if ":" not in a), ""), "last_seen": str(p.get("LastSeen") or "")})
    peers.sort(key=lambda p: (not p["phone"], not p["online"], p["name"].casefold()))
    state = str(d.get("BackendState") or "")
    return {"state": state, "running": state == "Running" and bool(v4), "ip": v4, "dns": dns,
            "name": str(me.get("HostName") or "")[:60], "peers": peers,
            "tailnet": str((d.get("CurrentTailnet") or {}).get("Name") or "") if isinstance(d.get("CurrentTailnet"), dict) else "",
            "magic_dns": bool((d.get("CurrentTailnet") or {}).get("MagicDNSEnabled")) if isinstance(d.get("CurrentTailnet"), dict) else False}


def _from_cards():
    """No Tailscale command to ask (an unusual install): the PC's own Tailscale address, if it has one."""
    from . import remote
    for a in remote._by_name():
        if is_tailnet(a):
            return a
    return ""


def status(fresh=False, run=None, find=None):
    """{"installed", "running", "state", "ip", "dns", "name", "peers", "words"}: is this PC on a Tailscale network.
    Asked at most every 15 seconds (the command takes a moment)."""
    now = time.monotonic()
    with _lock:
        if not fresh and _cache["val"] is not None and now - _cache["at"] < CACHE_S:
            return dict(_cache["val"])
    path = (find or exe)()
    out = {"installed": bool(path), "running": False, "state": "", "ip": "", "dns": "", "name": "", "peers": [],
           "tailnet": "", "magic_dns": False}
    if path:
        try:
            out.update(parse((run or _run_status)(path)))
        except (OSError, subprocess.SubprocessError):
            pass
    if not out["ip"]:
        ip = _from_cards()
        if ip:                                   # a Tailscale address without the command: say it is on
            out.update(ip=ip, running=True, installed=True)
    out["words"] = words(out)
    with _lock:
        _cache.update(at=now, val=dict(out))
    return out


def words(s):
    """One line saying where things stand, for Settings."""
    if not s["installed"]:
        return "Tailscale is not on this PC yet."
    if s["state"] == "NeedsLogin":
        return "Tailscale is installed but not signed in. Click its icon by the clock and sign in."
    if s["state"] in ("Stopped", "NoState") or not s["running"]:
        return "Tailscale is installed but switched off. Click its icon by the clock and choose Connect."
    phones = [p for p in s["peers"] if p["phone"]]
    if not phones:
        return "This PC is on your Tailscale network. Now install Tailscale on your phone and sign in with the same account."
    on = [p for p in phones if p["online"]]
    if on:
        return f"Ready. {on[0]['name']} is on your Tailscale network and can reach this PC from anywhere."
    return f"Ready. {phones[0]['name']} is on your Tailscale network (Tailscale is off on it right now)."


def own_names(s=None):
    """The names this PC answers to on the Tailscale network ('desktop.tail1234.ts.net', 'desktop')."""
    s = s if s is not None else status()
    out = set()
    if s.get("dns"):
        out.add(s["dns"])
        out.add(s["dns"].split(".", 1)[0])
    return out


def clear_cache():
    with _lock:
        _cache.update(at=0.0, val=None)
