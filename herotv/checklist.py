"""Checklist: which titles on your wish lists you already have, and which are still missing.

The lists live in config/checklist.json (editable). Matching uses each video's title (and year when it has one)."""
import datetime as dt
import json
import re


def norm(text):
    t = str(text or "").lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    t = re.sub(r"^(the|a|an) ", "", t)
    return re.sub(r"\s+", " ", t)


def load(path):
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    lists = data.get("lists") if isinstance(data, dict) else None
    if not isinstance(lists, list):
        raise ValueError('checklist.json needs a "lists" part')
    return lists


def _has_movie(item, rows):
    names = {norm(item["title"])} | {norm(a) for a in item.get("aka", [])}
    names.discard("")
    year = item.get("year")
    for r in rows:
        t = norm(r["title"])
        if t in names:
            if not r["year"] or not year or abs(r["year"] - year) <= 1:
                return r
            continue
        if year and r["year"] and abs(r["year"] - year) <= 0:
            if any(n and (n in t or t in n) and len(t) > 3 for n in names):
                return r
    return None


def build(rows, lists, today=None):
    """rows: media rows (title, year, franchise, series, season, episode, available, playable). Returns a list per checklist list."""
    today = today or dt.date.today()
    out = []
    for lst in lists:
        res = {"name": lst.get("name", "List"), "channel": lst.get("channel", ""), "kind": lst.get("kind", "movies"),
               "ideas": bool(lst.get("ideas")), "items": [], "have": 0, "missing": 0, "soon": 0}
        if res["kind"] == "series":
            key = norm(lst.get("series", lst.get("name")))
            eps = {}
            for r in rows:
                if norm(r["series"]) == key or (not r["series"] and norm(r["franchise"]) == key):
                    eps.setdefault(r["season"] or 1, set()).add(r["episode"])
            totals = {int(k): int(v) for k, v in (lst.get("seasons") or {}).items()}
            for sn in sorted(set(totals) | set(eps)):
                have = {e for e in eps.get(sn, set()) if e}
                n = totals.get(sn)
                miss = [e for e in range(1, n + 1) if e not in have] if n else []
                res["items"].append({"label": f"Season {sn}", "have": len(have), "total": n, "missing_eps": miss,
                                     "done": bool(n) and not miss, "soon": False})
                res["have"] += len(have)
                res["missing"] += len(miss)
            out.append(res)
            continue
        for it in lst.get("items", []):
            when = None
            if it.get("date"):
                try:
                    when = dt.date.fromisoformat(it["date"])
                except ValueError:
                    when = None
            soon = bool(when and when > today)
            row = None if soon else _has_movie(it, rows)
            label = it["title"] + (f" ({it['year']})" if it.get("year") else "")
            res["items"].append({"label": label, "have": bool(row), "soon": soon, "date": it.get("date") if soon else None,
                                 "playable": bool(row and row["playable"])})
            if soon:
                res["soon"] += 1
            elif row:
                res["have"] += 1
            else:
                res["missing"] += 1
        out.append(res)
    return out


def to_text(result):
    lines = ["YOUR SHOPPING LIST", "=" * 18, ""]
    for r in result:
        if r["kind"] == "series":
            lines.append(f"{r['name'].upper()}  ({r['channel']})  -  {r['have']} episodes in your library")
            for it in r["items"]:
                if it["total"]:
                    tail = "complete" if it["done"] else "missing episode " + ", ".join(map(str, it["missing_eps"]))
                    lines.append(f"   [{'x' if it['done'] else ' '}] {it['label']}: {it['have']} of {it['total']}  ({tail})")
                else:
                    lines.append(f"   [x] {it['label']}: {it['have']} episode(s)")
            if not r["items"]:
                lines.append("   (none yet)")
            lines.append("")
            continue
        total = r["have"] + r["missing"]
        tag = "  (ideas, not a full set)" if r["ideas"] else ""
        lines.append(f"{r['name'].upper()}  ({r['channel']})  -  you have {r['have']} of {total}{tag}")
        for it in r["items"]:
            if it["soon"]:
                lines.append(f"   [-] {it['label']}   coming {it['date']}")
            else:
                lines.append(f"   [{'x' if it['have'] else ' '}] {it['label']}")
        lines.append("")
    lines.append("[x] = you have it    [ ] = still missing    [-] = not out yet")
    return "\n".join(lines)
