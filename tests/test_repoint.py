"""A video moved out of the Inbox must stay playable even when the library already knew its new path from an earlier copy."""
import os
import tempfile

from herotv import launcher
from herotv.db import connect


def test_known_new_path_is_switched_back_on():
    d = tempfile.mkdtemp()
    db = os.path.join(d, "t.sqlite3")
    new = os.path.join(d, "MCU", "Film.mkv")
    old = os.path.join(d, "Inbox", "Film.mkv")
    os.makedirs(os.path.dirname(new))
    open(new, "wb").close()
    c = connect(db)
    c.execute("INSERT INTO media(path,title,available,verified,playable) VALUES(?,?,1,1,1)", (old, "Film"))
    c.execute("INSERT INTO media(path,title,available,verified,playable) VALUES(?,?,0,1,1)", (new, "Film"))   # an earlier copy, gone then
    c.commit()
    c.close()
    launcher._repoint(db, {old}, new)
    c = connect(db)
    got = {r["path"]: r["available"] for r in c.execute("SELECT path,available FROM media")}
    assert got == {old: 0, new: 1}
