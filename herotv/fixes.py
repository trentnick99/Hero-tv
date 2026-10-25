"""Your own sorting corrections: "this title (or show) goes on that channel". Saved in config/my-sorting.json when you
use "Put it here" in the Inbox helper or "Move to another channel" on a Details screen, with "remember" ticked.
Checked before keywords and smart sorting, so a correction always wins. Updates and backups keep the file."""
import json
import os

FILE = "my-sorting.json"
HELP = ("Titles and shows you placed yourself. The key is the title (or show name) in lower case; the value is the "
        "channel ids it goes on. HERO TV adds to this when you tick 'remember'. Delete a line to forget it.")


def path(cfg):
    return os.path.join(os.path.dirname(str(cfg.channels_file)), FILE)


def key(stem):
    """'Daredevil S01E02 Cut Man' -> 'daredevil';  'Iron.Man.(2008).1080p' -> 'iron man 2008'."""
    from . import library
    from .launcher import _norm
    g = library._guess([stem], stem)
    if g["series"]:
        return _norm(g["series"])
    return _norm(g["title"] + (f" {g['year']}" if g["year"] else ""))


def load(cfg):
    try:
        with open(path(cfg), encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    titles = data.get("titles") if isinstance(data, dict) else None
    if not isinstance(titles, dict):
        return {}
    return {str(k): [str(c) for c in v if isinstance(c, str)] for k, v in titles.items() if isinstance(v, list)}


def remember(cfg, stem, channel_ids):
    titles = load(cfg)
    k = key(stem)
    if not k:
        return None
    titles[k] = list(dict.fromkeys(channel_ids))
    p = path(cfg)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"_help": HELP, "titles": dict(sorted(titles.items()))}, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, p)
    return k


def lookup(fixes, stem):
    """Channel ids you chose for this title, or None."""
    if not fixes:
        return None
    return fixes.get(key(stem))
