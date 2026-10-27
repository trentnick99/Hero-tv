"""The keyword rules in config/auto-sort.json that file new videos onto channels.

Rules name channels by their id ("mcu", "south-park"), not their number, so renumbering a channel never breaks them.
Older files that used channel numbers are converted automatically the first time they are read (the previous file is
kept as auto-sort.json.bak). Numbers typed by hand are still understood.
"""
import json
import re
from pathlib import Path

from . import config


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


def smart_rules(cfg):
    """config/smart-sort.json (ships with HERO TV and is updated with it), or [] when switched off / missing."""
    try:
        if json.loads(config.settings_file().read_text(encoding="utf-8-sig")).get("smart_sort", True) is False:
            return []
    except (OSError, ValueError, AttributeError):
        pass
    try:
        with open(Path(cfg.channels_file).parent / "smart-sort.json", encoding="utf-8-sig") as f:
            return [r for r in json.load(f).get("rules", []) if isinstance(r, dict) and r.get("channels")]
    except (OSError, ValueError):
        return []


def _words(patterns, values):
    vals = [str(v).lower() for v in values if v]
    return any(re.search(r"(?<![a-z0-9])" + re.escape(str(p).lower()) + r"(?![a-z0-9])", v) for p in patterns for v in vals)


def fits(rule, facts):
    """Does a smart rule describe this title? Every condition the rule names must hold."""
    if rule.get("type") and facts.get("type") != rule["type"]:
        return False
    genres = {str(g).lower() for g in facts.get("genres") or []}
    if rule.get("genres") and not genres & {g.lower() for g in rule["genres"]}:
        return False
    if rule.get("not_genres") and genres & {g.lower() for g in rule["not_genres"]}:
        return False
    if rule.get("companies") and not _words(rule["companies"], facts.get("companies") or []):
        return False
    if rule.get("keywords") and not _words(rule["keywords"], (facts.get("keywords") or []) + [facts.get("collection") or ""]):
        return False
    if rule.get("year_max") and not (facts.get("year") and facts["year"] <= rule["year_max"]):
        return False
    return True


def smart_channels(facts, smart):
    out = []
    for r in smart:
        if fits(r, facts):
            out += [c for c in r["channels"] if c not in out]
            if r.get("stop"):
                break
    return out


def targets(stem, rules, channels, facts=None, smart=None, fixes=None):
    """Channels (with their own match rules) that a file name belongs on, lowest number first. Your own corrections
    (fixes.py) win outright. When TMDB facts are known, channels that have smart rules are decided by those facts
    only; the rest still use file-name keywords."""
    from .launcher import plan_sort
    from . import fixes as F
    mine = F.lookup(fixes, stem)
    keys = set(mine) if mine else plan_sort(stem, rules)
    if not mine and facts and smart:
        governed = {c for r in smart for c in r["channels"]}
        keys = {k for k in keys if k not in governed} | set(smart_channels(facts, smart))
    by_id = {c["id"]: c for c in channels if c.get("match") and not c.get("off")}       # nothing is filed onto a switched-off channel
    by_num = {c.get("number"): c for c in channels if c.get("match") and not c.get("off")}
    out = []
    for k in keys:
        c = by_id.get(k) if isinstance(k, str) and not k.isdigit() else by_num.get(int(k))
        if c and c not in out:
            out.append(c)
    return sorted(out, key=lambda c: c.get("number", 0))
