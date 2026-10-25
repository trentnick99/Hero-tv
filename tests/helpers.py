import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from herotv import scheduler as S  # noqa: E402
from herotv.db import connect  # noqa: E402

T0 = 1_800_000_000  # fixed "now" for deterministic tests


def make_db(path=":memory:"):
    c = connect(path)
    return c


def add(c, title, runtime, franchise="MCU", tags=(), order=None, verified=1, playable=1, available=1):
    n = c.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    c.execute("INSERT INTO media(path,title,year,franchise,tags,runtime_s,verified,playable,available,ord) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (f"/x/{title}-{n}.mp4", title, 2000, franchise, json.dumps(list(tags)), runtime, verified, playable, available,
               n if order is None else order))
    c.commit()
    return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def channel(c, cid="mcu", mode="sequential", match=None, number=1):
    S.load_channels(c, [{"id": cid, "number": number, "name": cid.upper(), "mode": mode, "match": match or {}}])
    return c.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone()


def slots(c, cid="mcu"):
    return [tuple(r) for r in c.execute("SELECT start,end,media_id,cycle FROM slots WHERE channel_id=? ORDER BY start", (cid,))]


def tmpdb():
    d = tempfile.mkdtemp()
    return os.path.join(d, "t.sqlite3")


def page_source():
    """The TV page as one text: index.html + app.css + app.js (for tests that look at the page's code)."""
    web = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
    return "\n".join(open(os.path.join(web, n), encoding="utf-8").read() for n in ("index.html", "app.css", "app.js"))
