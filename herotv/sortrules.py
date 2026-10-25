"""The keyword rules in config/auto-sort.json that file new videos onto channels.

Rules name channels by their id ("mcu", "south-park"), not their number, so renumbering a channel never breaks them.
Older files that used channel numbers are converted automatically the first time they are read (the previous file is
kept as auto-sort.json.bak). Numbers typed by hand are still understood.
"""
import json
import os
from pathlib import Path


def files(cfg):
    d = Path(cfg.channels_file).parent
    return Path(cfg.channels_file), d / "auto-sort.json"


def _groups(rules):
    return [r for key in ("rules", "year_rules") for r in rules.get(key, []) if isinstance(r, dict)]


def migrate(rules, channels):
    """Turn channel numbers into ids. Returns True when anything changed. Numbers of channels that no longer exist are dropped."""
    by_num = {c.get("number"): c["id"] for c in channels if "id" in c}
    changed = False
    for r in _groups(rules):
        new = []
        for x in r.get("channels", []):
            if isinstance(x, bool):
                changed = True
                continue
            if isinstance(x, int) or (isinstance(x, str) and x.isdigit()):
                cid = by_num.get(int(x))
                changed = True
                if cid and cid not in new:
                    new.append(cid)
            elif x not in new:
                new.append(x)
        r["channels"] = new
    return changed


def load(cfg, write=True):
    """(rules, channels) from the config folder, converting an old number-based rules file on the way."""
    from . import channels_api
    cf, af = files(cfg)
    with open(cf, encoding="utf-8-sig") as f:
        channels = json.load(f)["channels"]
    with open(af, encoding="utf-8-sig") as f:
        rules = json.load(f)
    if migrate(rules, channels):
        if isinstance(rules.get("_help"), str):
            rules["_help"] = HELP
        if write:
            channels_api._write(af, json.dumps(rules, indent=1, ensure_ascii=False) + "\n")
    return rules, channels


HELP = ("Keywords are matched against the file name as whole words/phrases, ignoring capitals and - . _ : ' . 'channels' "
        "are channel ids from channels.json (\"mcu\", \"south-park\"...; Settings > Channels edits keywords for you). A movie "
        "matching several rules goes on all of them. Edit freely.")


def targets(stem, rules, channels):
    """Channels (with their own match rules) that a file name belongs on, lowest number first."""
    from .launcher import plan_sort
    keys = plan_sort(stem, rules)
    by_id = {c["id"]: c for c in channels if c.get("match")}
    by_num = {c.get("number"): c for c in channels if c.get("match")}
    out = []
    for k in keys:
        c = by_id.get(k) if isinstance(k, str) and not k.isdigit() else by_num.get(int(k))
        if c and c not in out:
            out.append(c)
    return sorted(out, key=lambda c: c.get("number", 0))
