"""Reminders: "tell me when Iron Man starts on Marvel Movies". Set from the guide (R on the PC, OK on a later show
on the Roku); when the show starts, the TV screen and the Roku app offer to switch to it. Kept in the database;
reminders for shows that have finished are cleared by themselves."""
import time

SCHEMA = """CREATE TABLE IF NOT EXISTS reminders(channel_id TEXT NOT NULL, start INTEGER NOT NULL, title TEXT,
            media_id INTEGER, created INTEGER, PRIMARY KEY(channel_id, start))"""
DUE_BEFORE, DUE_AFTER = 60, 300          # a reminder is "due" from 1 minute before a show until 5 minutes into it
MAX = 50


def ensure(conn):
    conn.execute(SCHEMA)


def add(conn, channel_id, start, now=None):
    """Remind me of the show that starts at `start` on that channel. Returns the reminder; ValueError if no such show."""
    now = int(now or time.time())
    ensure(conn)
    try:
        start = int(start)
    except (TypeError, ValueError):
        raise ValueError("choose a show in the guide")
    row = conn.execute("SELECT s.start, s.end, s.media_id, m.title, m.series, m.season, m.episode FROM slots s "
                       "JOIN media m ON m.id=s.media_id WHERE s.channel_id=? AND s.start=?", (str(channel_id), start)).fetchone()
    if row is None:
        raise ValueError("That show is no longer in the guide.")
    if row["end"] <= now:
        raise ValueError("That show has already finished.")
    if conn.execute("SELECT COUNT(*) FROM reminders WHERE start>?", (now,)).fetchone()[0] >= MAX:
        raise ValueError(f"You already have {MAX} reminders - remove some first.")
    title = row["title"]
    if row["series"]:
        title = f"{row['series']} S{row['season'] or 0}E{row['episode'] or 0}" + (f" - {row['title']}" if row["title"] else "")
    conn.execute("INSERT OR REPLACE INTO reminders(channel_id,start,title,media_id,created) VALUES(?,?,?,?,?)",
                 (str(channel_id), start, title, row["media_id"], now))
    conn.commit()
    return {"channel": str(channel_id), "start": start, "title": title, "media_id": row["media_id"]}


def remove(conn, channel_id, start):
    ensure(conn)
    try:
        start = int(start)
    except (TypeError, ValueError):
        raise ValueError("choose a show in the guide")
    n = conn.execute("DELETE FROM reminders WHERE channel_id=? AND start=?", (str(channel_id), start)).rowcount
    conn.commit()
    return n


def listing(conn, now=None):
    """{"reminders": [...upcoming, soonest first], "due": [...starting about now]} - finished ones are cleared."""
    now = int(now or time.time())
    ensure(conn)
    conn.execute("DELETE FROM reminders WHERE start < ?", (now - 6 * 3600,))
    conn.commit()
    out, due = [], []
    for r in conn.execute("SELECT r.channel_id, r.start, r.title, r.media_id, c.number, c.name FROM reminders r "
                          "LEFT JOIN channels c ON c.id=r.channel_id ORDER BY r.start"):
        d = {"channel": r["channel_id"], "start": r["start"], "title": r["title"], "media_id": r["media_id"],
             "number": r["number"], "channel_name": r["name"] or r["channel_id"]}
        if r["start"] - DUE_BEFORE <= now <= r["start"] + DUE_AFTER:
            due.append(d)
        if r["start"] + DUE_AFTER >= now:
            out.append(d)
    return {"now": now, "reminders": out, "due": due}
