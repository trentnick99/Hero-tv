"""Edit channels from the Settings screen instead of Notepad: rename, renumber, recolor, change the folder or the
keywords, add a channel, delete one.

config/channels.json and config/auto-sort.json stay the single source of truth (still hand-editable). Every change is
validated, written atomically with a .bak copy of the previous file, and special rules the screen cannot express
(extra groups, time blocks, smart programming, tag/year rules) are left exactly as they were.
"""
import json
import os
import re
from pathlib import Path

HEX = re.compile(r"#[0-9a-fA-F]{6}")
TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
BAD_FOLDER = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MODES = ("sequential", "shuffle", "mixed", "balanced")
SIMPLE_KEYS = {"franchise"}


def _paths(cfg):
    d = Path(cfg.channels_file).parent
    return Path(cfg.channels_file), d / "auto-sort.json", d / "checklist.json"


def _read(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write(p, text):
    p = Path(p)
    if p.is_file():
        try:
            p.with_name(p.name + ".bak").write_bytes(p.read_bytes())
        except OSError:
            pass
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, p)


def _dump_channels(data):
    rest = {k: v for k, v in data.items() if k != "channels"}
    lines = ",\n ".join(json.dumps(c, ensure_ascii=False) for c in data["channels"])
    head = (json.dumps(rest, ensure_ascii=False)[1:-1] + ", ") if rest else ""
    return '{' + head + '"channels": [\n ' + lines + '\n]}\n'


FOR_YOU = {"id": "for-you", "number": 17, "name": "For You", "color": "#ff6ad5", "mode": "sequential", "kind": "foryou",
           "description": "Picked for you: the next episode of what you are watching, films you stopped half-way, and more "
                          "like what you watched lately."}


SHORTS_CHANNEL = {"id": "shorts", "number": 18, "name": "Cartoon Shorts", "color": "#ffa94d", "mode": "shuffle",
                  "match": {"franchise": ["Shorts"]},
                  "also": [{"franchise": ["Free Movies"], "tags": ["cartoon"], "max_minutes": 15}],
                  "description": "Short cartoons around the clock: your Shorts folder and the free classic cartoons."}
BUILTINS = (FOR_YOU, SHORTS_CHANNEL)


def ensure_builtin(cfg):
    """Give an existing channels.json the channels newer versions brought (once - if you delete one, it stays gone)."""
    from . import settings_api
    cf, _af, _ = _paths(cfg)
    data = _read(cf, None)
    if not isinstance(data, dict) or not isinstance(data.get("channels"), list):
        return False
    st = settings_api._load()
    done = st.get("builtins") if isinstance(st.get("builtins"), list) else []
    todo = [b for b in BUILTINS if b["id"] not in done]
    if not todo:
        return False
    chans = data["channels"]
    wrote = False
    for b in todo:
        same = (lambda c: c.get("id") == b["id"] or c.get("kind") == "foryou") if b.get("kind") == "foryou" else \
            (lambda c: c.get("id") == b["id"])
        if not any(same(c) for c in chans):
            c = json.loads(json.dumps(b))
            taken = {x.get("number") for x in chans}
            if c["number"] in taken:
                c["number"] = next(n for n in range(c["number"], 1000) if n not in taken)
            chans.append(c)
            wrote = True
    if wrote:
        _write(cf, _dump_channels(data))
    st["builtins"] = done + [b["id"] for b in todo]
    settings_api._save(st)
    return True


def _summary(c):
    if c.get("kind") == "weather":
        return "Local weather (set the town in Settings > Weather)"
    if c.get("kind") == "foryou":
        return "Picked for you from what you watch"
    m = c.get("match") or {}
    bits = []
    if m.get("franchise"):
        bits.append("Folder: " + ", ".join(m["franchise"]))
    if m.get("tags"):
        bits.append("Tagged: " + ", ".join(m["tags"]))
    if m.get("series"):
        bits.append("Shows: " + ", ".join(m["series"]))
    if m.get("year_min") or m.get("year_max"):
        bits.append(f"Years {m.get('year_min') or ''}-{m.get('year_max') or ''}")
    if m.get("type"):
        bits.append("only " + m["type"] + "s")
    if not bits:
        bits.append("Everything in your library")
    return "; ".join(bits)


def _folder_of(c):
    m = c.get("match") or {}
    if c.get("kind") == "weather" or set(m) != SIMPLE_KEYS or len(m.get("franchise", [])) != 1:
        return None
    return m["franchise"][0]


def _own_keywords(rules, cid):
    """Keywords that belong to this channel alone (rules that name only this channel) and how many words sit in shared rules."""
    mine, shared = [], 0
    for r in rules.get("rules", []):
        chans = r.get("channels", [])
        if chans == [cid]:
            mine += [str(k) for k in r.get("keywords", [])]
        elif cid in chans:
            shared += len(r.get("keywords", []))
    return mine, shared


def _rules(cfg, channels):
    from . import sortrules
    _, af = sortrules.files(cfg)
    rules = _read(af, {"rules": []})
    sortrules.migrate(rules, channels)          # old number-based file: understood (and saved as ids on the next change)
    if isinstance(rules.get("_help"), str):
        rules["_help"] = sortrules.HELP
    return rules


GROUPS = (                       # how the first-start "Your channels" screen groups the starter channels
    ("Superheroes", ("mcu", "marvel-tv", "marvel-animation", "spider-verse", "x-men", "dc", "classics", "action", "comedy", "invincible")),
    ("Cartoons and anime", ("dragon-ball", "south-park")),
    ("Movies", ("horror", "free")),
    ("Extras", ("for-you", "shorts", "weather", "marathon")),
)


def lineup(cfg):
    """The channels as groups of {id, name, on} for the "Your channels" picker; channels you made are listed too."""
    cf, _af, _ = _paths(cfg)
    chans = sorted(_read(cf, {"channels": []}).get("channels", []), key=lambda x: x.get("number", 0))
    by = {c["id"]: c for c in chans}
    out, used = [], set()
    for name, ids in GROUPS:
        items = [by[i] for i in ids if i in by]
        used.update(c["id"] for c in items)
        if items:
            out.append({"name": name, "channels": items})
    rest = [c for c in chans if c["id"] not in used]
    if rest:
        out.append({"name": "Your own channels", "channels": rest})
    return [{"name": g["name"], "channels": [{"id": c["id"], "number": c.get("number"), "name": c.get("name", ""),
                                               "description": c.get("description", ""), "on": not c.get("off")} for c in g["channels"]]}
            for g in out]


def read(cfg):
    cf, af, _ = _paths(cfg)
    data = _read(cf, {"channels": []})
    rules = _rules(cfg, data.get("channels", []))
    from . import sortrules
    smart = sortrules.smart_rules(cfg)
    out = []
    for c in sorted(data.get("channels", []), key=lambda x: x.get("number", 0)):
        kws, shared = _own_keywords(rules, c["id"])
        folder = _folder_of(c)
        out.append({"id": c["id"], "number": c.get("number"), "name": c.get("name", ""), "color": c.get("color", "#ffcf1f"),
                    "mode": c.get("mode", "sequential"), "starts": c.get("starts") or 0, "breaks": bool(c.get("breaks")), "blocks": _block_rows(c), "description": c.get("description", ""), "kind": c.get("kind", "tv"),
                    "folder": folder, "keywords": kws, "shared_keywords": shared, "summary": _summary(c), "off": bool(c.get("off")),
                    "smart": [r.get("label") or "" for r in smart if c["id"] in r["channels"]],
                    "special": bool(c.get("also") or c.get("smart") or (folder is None and c.get("kind") not in ("weather", "foryou")))})
    return {"channels": out, "media_dir": str(cfg.media_dir)}


def _clean_keywords(v):
    if isinstance(v, str):
        v = re.split(r"[\n,]+", v)
    if not isinstance(v, list):
        raise ValueError("Keywords must be a list of words or titles.")
    seen, out = set(), []
    for k in v:
        k = " ".join(str(k).split())
        if not k:
            continue
        if len(k) > 60:
            raise ValueError("Each keyword must be under 60 characters.")
        if k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    if len(out) > 300:
        raise ValueError("Too many keywords for one channel (300 at most).")
    return out


def _clean_folder(v):
    v = " ".join(str(v).split()).strip(" .")
    if not v:
        raise ValueError("The folder name cannot be empty.")
    if BAD_FOLDER.search(v) or len(v) > 60 or v.lower() in ("inbox", ".originals"):
        raise ValueError("That folder name is not allowed. Use plain letters and numbers (not \\ / : * ? \" < > |), not 'Inbox'.")
    return v


def _slug(name, taken):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "channel"
    s, n = base, 2
    while s in taken:
        s = f"{base}-{n}"
        n += 1
    return s


def _check_number(n, channels, exclude_id=None):
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise ValueError("The channel number must be a whole number.")
    if not 1 <= n <= 999:
        raise ValueError("The channel number must be between 1 and 999.")
    for c in channels:
        if c["number"] == n and c["id"] != exclude_id:
            raise ValueError(f"Channel {n} is already {c['name']}. Pick another number, or change that channel first.")
    return n


def _apply_basic(c, ch, channels):
    if "name" in ch:
        name = " ".join(str(ch["name"]).split())
        if not name or len(name) > 40:
            raise ValueError("The channel name must be 1 to 40 characters.")
        c["name"] = name
    if "color" in ch:
        if not isinstance(ch["color"], str) or not HEX.fullmatch(ch["color"]):
            raise ValueError("The color must look like #ff3b3b.")
        c["color"] = ch["color"]
    if "description" in ch:
        c["description"] = " ".join(str(ch["description"]).split())[:200]
    if "breaks" in ch and c.get("kind") not in ("weather",):
        if ch["breaks"]:
            c["breaks"] = True
        else:
            c.pop("breaks", None)
    if "starts" in ch and c.get("kind") not in ("weather",):
        v = ch["starts"]
        v = int(v) if str(v).isdigit() else 0
        if v not in (0, 15, 30, 60):
            raise ValueError("Start times must be any time, quarter hours, half hours or whole hours.")
        if v:
            c["starts"] = v
        else:
            c.pop("starts", None)
    if "mode" in ch and c.get("kind") != "weather":
        if ch["mode"] not in MODES:
            raise ValueError("Play order must be in order, shuffled, mixed shows or fair share.")
        c["mode"] = ch["mode"]


DAY_LABELS = {"daily": "Every day", "weekdays": "Weekdays", "weekends": "Weekends", "mon": "Mondays", "tue": "Tuesdays",
              "wed": "Wednesdays", "thu": "Thursdays", "fri": "Fridays", "sat": "Saturdays", "sun": "Sundays"}


def _new_block(body, blocks):
    days = str(body.get("days", "daily"))
    if days not in DAY_LABELS:
        raise ValueError("Choose the days from the list.")
    what = body.get("what") if isinstance(body.get("what"), dict) else {}
    if what.get("folder"):
        match, label = {"franchise": [str(what["folder"])]}, str(what["folder"])
    elif what.get("series"):
        match, label = {"series": [str(what["series"])]}, str(what["series"])
    else:
        raise ValueError("Choose what plays in this time slot.")
    mode = body.get("mode", "shuffle")
    if mode not in MODES:
        raise ValueError("Choose the play order from the list.")
    a, z = str(body.get("from", "")), str(body.get("to", ""))
    if not (TIME.fullmatch(a) and TIME.fullmatch(z)):
        raise ValueError('Times must look like 08:00.')
    name = f"{label} - {DAY_LABELS[days]} {a}"
    taken = {str(b.get("name", "")).lower() for b in blocks}
    n, base = 2, name
    while name.lower() in taken:
        name, n = f"{base} ({n})", n + 1
    return {"name": name, "days": days, "from": a, "to": z, "mode": mode, "match": match}


def _block_rows(c):
    out = []
    for b in c.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        m = b.get("match") or {}
        what = ", ".join(m.get("franchise") or m.get("series") or m.get("tags") or []) or "the channel's own videos"
        days = b.get("days", "daily")
        days = DAY_LABELS.get(days, days) if isinstance(days, str) else ", ".join(DAY_LABELS.get(d, d) for d in days)
        out.append({"name": b.get("name", ""), "days": days, "from": b.get("from", ""), "to": b.get("to", ""),
                    "what": what, "mode": b.get("mode") or "", "dates": b.get("dates", "")})
    return out


def _set_keywords(rules, cid, words):
    rest = [r for r in rules.get("rules", []) if r.get("channels", []) != [cid]]
    if words:
        rest.append({"keywords": words, "channels": [cid]})
    rules["rules"] = rest


def _relabel(checklist, old_label, new_label):
    """Point the checklist's channel labels ("1 Marvel Movies") at the new number/name. True when it changed.
    (Keyword rules use channel ids, so renumbering never touches them.)"""
    changed = False
    for l in checklist.get("lists", []):
        if l.get("channel") == old_label:
            l["channel"] = new_label
            changed = True
    return changed


def update(cfg, body):
    """Apply one change. Returns {"ok": True, "channels": [...], "note": "..."}; raises ValueError with a plain-English reason."""
    if not isinstance(body, dict):
        raise ValueError("invalid request")
    op = body.get("op")
    cf, af, kf = _paths(cfg)
    data = _read(cf, None)
    if not isinstance(data, dict) or not isinstance(data.get("channels"), list):
        raise ValueError("config\\channels.json cannot be read, so it was not changed. Check it in Notepad first.")
    chans = data["channels"]
    rules = _rules(cfg, chans)
    checklist = _read(kf, None)
    note = ""
    touched_checklist = False
    media = Path(cfg.media_dir)
    if op == "save":
        c = next((x for x in chans if x["id"] == body.get("id")), None)
        if c is None:
            raise ValueError("That channel no longer exists.")
        old_label = f"{c['number']} {c['name']}"
        _apply_basic(c, body, chans)
        if "number" in body:
            c["number"] = _check_number(body["number"], chans, c["id"])
        if "folder" in body and body["folder"] not in (None, ""):
            cur = _folder_of(c)
            if cur is None:
                raise ValueError("This channel has special rules, so its folder is set in config\\channels.json.")
            new = _clean_folder(body["folder"])
            if new != cur:
                c["match"] = {"franchise": [new]}
                (media / new).mkdir(parents=True, exist_ok=True)
                note = f"Videos already in the '{cur}' folder stay there - move them into '{new}' (or rename that folder in Windows)."
        new_label = f"{c['number']} {c['name']}"
        if old_label != new_label:
            touched_checklist = _relabel(checklist or {}, old_label, new_label)
        if "keywords" in body:
            _set_keywords(rules, c["id"], _clean_keywords(body["keywords"]))
    elif op == "add":
        name = " ".join(str(body.get("name", "")).split())
        if not name:
            raise ValueError("Give the new channel a name.")
        number = _check_number(body["number"], chans) if body.get("number") else next(
            n for n in range(1, 1000) if all(c["number"] != n for c in chans))
        folder = _clean_folder(body.get("folder") or name)
        c = {"id": _slug(name, {x["id"] for x in chans}), "number": number, "name": name[:40], "color": "#ffcf1f",
             "mode": "sequential", "match": {"franchise": [folder]}, "description": ""}
        _apply_basic(c, body, chans)
        c["match"] = {"franchise": [folder]}
        chans.append(c)
        (media / folder).mkdir(parents=True, exist_ok=True)
        if body.get("keywords"):
            _set_keywords(rules, c["id"], _clean_keywords(body["keywords"]))
        note = f"Put its videos in the '{folder}' folder inside your media folder - the channel appears in the guide as soon as it has one."
    elif op in ("lineup", "switch"):
        if op == "switch":                                 # one channel on or off (Settings > Channels)
            off = {c["id"] for c in chans if c.get("off")}
            cid = body.get("id")
            if cid not in {c["id"] for c in chans}:
                raise ValueError("That channel no longer exists.")
            (off.add if body.get("off") else off.discard)(cid)
        else:                                              # the whole lineup at once (first start)
            off = body.get("off")
            if not isinstance(off, list):
                raise ValueError("off must be a list of channel ids")
            off = {str(x) for x in off}
        if all(c["id"] in off for c in chans):
            raise ValueError("Keep at least one channel on.")
        for c in chans:
            if c["id"] in off:
                c["off"] = True
            else:
                c.pop("off", None)
        n = sum(1 for c in chans if c.get("off"))
        note = (f"{n} channel(s) switched off - nothing was deleted; switch them back on in Settings > Channels any time." if n
                else "Every channel is on.")
    elif op in ("add_block", "remove_block"):            # time slots: "cartoons on Saturday mornings"
        c = next((x for x in chans if x["id"] == body.get("id")), None)
        if c is None:
            raise ValueError("That channel no longer exists.")
        if c.get("kind") in ("weather", "foryou"):
            raise ValueError("This channel cannot have time slots.")
        blocks = [b for b in (c.get("blocks") or []) if isinstance(b, dict)]
        if op == "remove_block":
            name = str(body.get("name", ""))
            if not any(str(b.get("name")) == name for b in blocks):
                raise ValueError("That time slot is already gone.")
            blocks = [b for b in blocks if str(b.get("name")) != name]
            note = "Time slot removed."
        else:
            b = _new_block(body, blocks)
            blocks.append(b)
            from . import scheduler
            scheduler.parse_blocks(dict(c, blocks=blocks))      # same checks as when HERO TV starts
            note = f"Time slot added: {b['name']}. The guide changes from the next show that has not started yet."
        if blocks:
            c["blocks"] = blocks
        else:
            c.pop("blocks", None)
    elif op == "delete":
        c = next((x for x in chans if x["id"] == body.get("id")), None)
        if c is None:
            raise ValueError("That channel no longer exists.")
        if len(chans) <= 1:
            raise ValueError("You cannot delete your only channel.")
        chans.remove(c)
        for key in ("rules", "year_rules"):
            for r in rules.get(key, []):
                r["channels"] = [x for x in r.get("channels", []) if x != c["id"]]
            rules[key] = [r for r in rules.get(key, []) if r.get("channels")]
        if not rules.get("year_rules"):
            rules.pop("year_rules", None)
        note = "The channel is gone from the guide. Your videos were not touched."
    else:
        raise ValueError("unknown change")
    if len({c["number"] for c in chans}) != len(chans):
        raise ValueError("Every channel needs its own number.")
    _write(cf, _dump_channels(data))
    _write(af, json.dumps(rules, indent=1, ensure_ascii=False) + "\n")
    if checklist is not None and touched_checklist:
        _write(kf, json.dumps(checklist, indent=1, ensure_ascii=False) + "\n")
    return {"ok": True, "note": note, "channels": read(cfg)["channels"]}


def revert(cfg):
    """Put back the previous channels.json / auto-sort.json (used when the new channel list could not be loaded)."""
    cf, af, _ = _paths(cfg)
    for p in (cf, af):
        b = p.with_name(p.name + ".bak")
        if b.is_file():
            os.replace(b, p)
