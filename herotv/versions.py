"""Several files of the same film (a 1080p and a 4K copy, an unrated cut...) show as ONE tile with a version picker."""
import os

from .insights import _n

MAX_RATIO = 1.5          # copies whose lengths differ more than this are different films / cuts: keep them apart


def _key(d):
    if d.get("show") or d.get("series") or not d.get("year"):
        return None                      # episodes and films with no year are never merged (too easy to mistake two films)
    return (_n(d.get("title")), d["year"])


def _version(d):
    return {"id": d["id"], "height": d.get("height") or 0, "size": d.get("size") or 0, "runtime_s": d.get("runtime_s") or 0,
            "file": os.path.basename(d.get("path") or ""), "position": d.get("position") or 0, "completed": d.get("completed") or 0}


def _clusters(grp):
    """Split copies of one title into sets of similar length (a much longer file is another cut or another film)."""
    out = []
    for g in sorted(grp, key=lambda g: g.get("runtime_s") or 0):
        rt = g.get("runtime_s") or 0
        if out and (not rt or not out[-1][0] or rt <= MAX_RATIO * out[-1][0]):
            out[-1][1].append(g)
        else:
            out.append([rt, [g]])
    return [c[1] for c in out]


def merge(items):
    """items: library rows (dicts with path, size, height, position...). Returns them with duplicates folded into one
    row that gets 'versions' (best picture first). The list keeps its order; 'path' is removed."""
    groups = {}
    for d in items:
        k = _key(d)
        if k is not None:
            groups.setdefault(k, []).append(d)
    stand = {}                           # id of the first copy of a cluster -> the whole cluster
    skip = set()
    for grp in groups.values():
        for cl in _clusters(grp):
            if len(cl) > 1:
                first = min(cl, key=lambda g: items.index(g))
                stand[first["id"]] = cl
                skip.update(g["id"] for g in cl if g is not first)
    out = []
    for d in items:
        if d["id"] in skip:
            continue
        cl = stand.get(d["id"])
        if cl:
            vs = sorted((_version(g) for g in cl), key=lambda v: (-v["height"], -v["size"]))
            started = [v for v in vs if v["position"] > 10 and not v["completed"]]
            main = next(g for g in cl if g["id"] == (started or vs)[0]["id"])
            d = dict(main, versions=vs, favorite=max(int(g.get("favorite") or 0) for g in cl),
                     completed=int(all(g.get("completed") for g in cl)))
        out.append(d)
    for d in out:
        d.pop("path", None)
    return out
