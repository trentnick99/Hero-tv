"""MCU in story order: the films you have, in the collection's order, with the next one to watch."""
import json
import os
import tempfile
from pathlib import Path

from herotv import collections as COL, config
from herotv.config import Config
from herotv.db import connect


def _db(films):
    c = connect(os.path.join(tempfile.mkdtemp(), "t.sqlite3"))
    for i, (t, y) in enumerate(films, 1):
        c.execute("INSERT INTO media(id,path,title,year,franchise,verified,playable,available,runtime_s) VALUES(?,?,?,?,'MCU',1,1,1,7000)",
                  (i, f"/m/{i}.mkv", t, y))
    c.commit()
    return c


def test_story_order_from_the_shipped_list():
    cfg = Config(media_dir=Path("."), db_path="x", channels_file=str(Path(config.ROOT) / "config" / "channels.json"))
    col = next(x for x in COL.load(cfg) if x["id"] == "mcu-story")
    c = _db([("Iron Man", 2008), ("Captain America- The First Avenger", 2011), ("Spider-Man Brand New Day", 2026),
             ("Captain Marvel", 2019), ("Spider-Man- Far from Home", 2019), ("Heat", 1995)])
    c.execute("INSERT INTO progress(media_id,position,completed,updated) VALUES(2,0,1,1)")     # First Avenger watched
    b = COL.build(c, col)
    assert [d["story_title"] for d in b["items"]] == ["Captain America: The First Avenger", "Captain Marvel", "Iron Man",
                                                       "Spider-Man: Far From Home", "Spider-Man: Brand New Day"]
    assert b["items"][0]["n"] == 1 and b["items"][2]["n"] == 3
    assert b["next"] == 4                                                  # Captain Marvel: the first one not finished
    assert "Thor" in b["missing"] and b["total"] == len(col["items"])
    s = COL.summary(c, cfg)
    assert s[0]["next_title"] == "Captain Marvel" and s[0]["have"] == 5
