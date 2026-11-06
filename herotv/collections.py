"""On-demand collections: films in a set order you can watch through (Home > More > MCU in story order).

The lists live in config/collections.json (editable, kept on update like your other settings). Titles you do not have are
left out; matching works like the Checklist (title, plus year within one)."""
import json
import os

from . import checklist


def path(cfg):
    return os.path.join(os.path.dirname(str(cfg.channels_file)), "collections.json")


def load(cfg):
    try:
        with open(path(cfg), encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    return [c for c in (data.get("collections") or []) if isinstance(c, dict) and c.get("id") and isinstance(c.get("items"), list)]


def _rows(conn):
    return [dict(r) for r in conn.execute(
        "SELECT m.id,m.title,m.year,m.franchise,m.series,m.season,m.episode,m.plot,m.runtime_s,m.tags,m.added,m.height,"
        "COALESCE(p.position,0) AS position,COALESCE(p.completed,0) AS completed,(f.media_id IS NOT NULL) AS favorite "
        "FROM media m LEFT JOIN progress p ON p.media_id=m.id LEFT JOIN favorites f ON f.media_id=m.id "
        "WHERE m.available=1 AND m.verified=1 AND m.playable=1 AND COALESCE(m.series,'')='' ORDER BY m.height DESC, m.id")]


def build(conn, col, rows=None):
    """The collection with the films you have, in order: each item is a library row plus 'n' (its place in the story).
    'missing' names what you do not have; 'next' is the id of the first one not finished."""
    rows = rows if rows is not None else _rows(conn)
    items, missing, used = [], [], set()
    for n, it in enumerate(col["items"], 1):
        r = checklist._has_movie(it, [x for x in rows if x["id"] not in used])
        if r:
            used.add(r["id"])
            items.append(dict(r, n=n, story_title=it["title"]))
        else:
            missing.append(it["title"])
    nxt = next((d["id"] for d in items if not d["completed"]), None)
    return {"id": col["id"], "name": col.get("name") or col["id"], "sub": col.get("sub", ""), "items": items,
            "missing": missing, "total": len(col["items"]), "next": nxt}


def summary(conn, cfg):
    rows = _rows(conn)
    out = []
    for col in load(cfg):
        b = build(conn, col, rows)
        if b["items"]:
            nx = next((d for d in b["items"] if d["id"] == b["next"]), None)
            out.append({"id": b["id"], "name": b["name"], "have": len(b["items"]), "total": b["total"],
                        "next_title": nx["story_title"] if nx else "", "next_n": nx["n"] if nx else 0})
    return out
