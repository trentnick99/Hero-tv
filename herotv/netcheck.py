"""Why can't my phone reach HERO TV? Checks the things that usually stop it on Windows, in plain words, and fixes the
firewall / network-type ones with one press (Windows asks for permission first).

Checked: is the listener on; which address the phone is told; whether Windows treats this network as Public
(which blocks phones and TVs); whether Windows Firewall blocks HERO TV, or has no rule letting it in."""
import json
import os
import subprocess
import sys
import tempfile

RULE = "HERO TV (home network)"


def program():
    """The program Windows Firewall sees: HERO-TV.exe, or python.exe when run from source."""
    return os.path.abspath(sys.executable)


def _ps_quote(s):
    return "'" + str(s).replace("'", "''") + "'"


def _powershell(script, timeout=45):
    from . import tools
    r = tools.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout=timeout)
    return r.stdout or ""


SNAPSHOT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$exe = %s
$prof = @(Get-NetConnectionProfile | ForEach-Object { [pscustomobject]@{ alias = "$($_.InterfaceAlias)"; category = "$($_.NetworkCategory)"; name = "$($_.Name)" } })
$ips = @(Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { [pscustomobject]@{ alias = "$($_.InterfaceAlias)"; ip = "$($_.IPAddress)" } })
$want = [Environment]::ExpandEnvironmentVariables($exe).ToLower()
# every rule for this program - also ones Windows saved with %%USERPROFILE%% or different capital letters in the path
$filters = @(Get-NetFirewallApplicationFilter -All | Where-Object { [Environment]::ExpandEnvironmentVariables("$($_.Program)").ToLower() -eq $want })
$rules = @($filters | Get-NetFirewallRule | Where-Object { "$($_.Direction)" -eq 'Inbound' -and "$($_.Enabled)" -eq 'True' } |
  ForEach-Object { [pscustomobject]@{ name = "$($_.DisplayName)"; action = "$($_.Action)"; profile = "$($_.Profile)" } })
[pscustomobject]@{ profiles = $prof; ips = $ips; rules = $rules } | ConvertTo-Json -Depth 4 -Compress
"""


def snapshot(run=None):
    """{"profiles": [...], "ips": [...], "rules": [...]} from Windows, or None elsewhere / when PowerShell fails."""
    if os.name != "nt" and run is None:
        return None
    try:
        out = (run or _powershell)(SNAPSHOT % _ps_quote(program()))
        d = json.loads(out.strip() or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    norm = lambda v: v if isinstance(v, list) else ([v] if isinstance(v, dict) else [])
    return {k: norm(d.get(k)) for k in ("profiles", "ips", "rules")}


def _covers(profile, category):
    p = profile.replace(" ", "").lower()
    return p in ("any", "0", "") or category.lower() in p.split(",")


VIRTUAL = ("vethernet", "virtualbox", "vmware", "hyper-v", "wsl", "tap", "tun", "vpn", "nordlynx", "wireguard", "zerotier",
           "tailscale", "hamachi", "loopback", "bluetooth")


def diagnose(listening, addresses, snap):
    """Problems (most likely first) as [{"id", "title", "text", "fixable"}] plus what was seen."""
    problems = []
    if not listening:
        problems.append({"id": "off", "title": "Other devices are switched off",
                         "text": "Turn on 'Let other devices watch' above first.", "fixable": False})
    if not addresses:
        problems.append({"id": "noaddr", "title": "This PC has no home-network address",
                         "text": "Check that the PC is connected to your router (cable or WiFi).", "fixable": False})
    alias, category = "", ""
    if snap is not None and addresses:
        alias = next((i["alias"] for i in snap["ips"] if i.get("ip") == addresses[0]), "")
        category = next((p["category"] for p in snap["profiles"] if p.get("alias") == alias), "")
        if alias and any(v in alias.lower() for v in VIRTUAL):
            problems.append({"id": "virtual", "title": f"The address shown belongs to '{alias}'",
                             "text": "That looks like a VPN or virtual network, not your home network. Switch the VPN off "
                                     "(or try the other addresses listed) and check again.", "fixable": False})
        cat = {"domainauthenticated": "Domain", "public": "Public"}.get(category.lower(), "Private")
        rules = snap["rules"]
        blocked = [r for r in rules if r.get("action", "").lower() == "block" and _covers(r.get("profile", ""), cat)]
        allowed = [r for r in rules if r.get("action", "").lower() == "allow" and _covers(r.get("profile", ""), cat)]
        if cat == "Public" and (blocked or not allowed):
            problems.append({"id": "public", "title": "Windows treats your home network as Public",
                             "text": "On a Public network Windows blocks phones and TVs from reaching this PC. "
                                     "Fixing it marks this one network as Private (your home network).", "fixable": True})
        if blocked:
            problems.append({"id": "blocked", "title": "Windows Firewall is blocking HERO TV",
                             "text": "This usually happens when the 'Allow access?' question was closed or answered "
                                     "Cancel. Fixing it removes the block and lets HERO TV in on your home network only.",
                             "fixable": True})
        elif not allowed:
            problems.append({"id": "noallow", "title": "Windows Firewall has no rule letting HERO TV in",
                             "text": "Fixing it lets HERO TV in on your home network only (not on Public networks).",
                             "fixable": True})
    return {"problems": problems, "alias": alias, "category": category, "windows": snap is not None,
            "addresses": addresses, "program": program()}


FIX = r"""
$ErrorActionPreference = 'SilentlyContinue'
$exe = %s
Get-NetFirewallApplicationFilter -Program $exe | Get-NetFirewallRule | Where-Object { "$($_.Direction)" -eq 'Inbound' -and "$($_.Action)" -eq 'Block' } | Remove-NetFirewallRule
Get-NetFirewallRule -DisplayName %s | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName %s -Direction Inbound -Program $exe -Action Allow -Profile Private,Domain | Out-Null
%s
"""


def fix_script(alias=""):
    extra = f"Set-NetConnectionProfile -InterfaceAlias {_ps_quote(alias)} -NetworkCategory Private" if alias else ""
    return FIX % (_ps_quote(program()), _ps_quote(RULE), _ps_quote(RULE), extra)


def fix(alias="", shell=None):
    """Run the fix as administrator (Windows shows its permission question). Returns True when it was started."""
    if os.name != "nt" and shell is None:
        raise ValueError("This fix is for Windows.")
    fd, path = tempfile.mkstemp(prefix="herotv-net-", suffix=".ps1")
    with os.fdopen(fd, "w", encoding="utf-8-sig") as fh:
        fh.write(fix_script(alias))
    args = f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{path}"'
    if shell is not None:
        return shell(path, args)
    import ctypes
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", args, None, 0)
    if rc <= 32:
        raise ValueError("Windows did not allow the change (the permission question was answered No).")
    return True
