import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS media(
 id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, title TEXT NOT NULL, year INTEGER,
 franchise TEXT DEFAULT '', series TEXT DEFAULT '', season INTEGER DEFAULT 0, episode INTEGER DEFAULT 0,
 tags TEXT DEFAULT '[]', plot TEXT DEFAULT '', runtime_s REAL DEFAULT 0,
 verified INTEGER DEFAULT 0,   -- runtime measured by ffprobe
 playable INTEGER DEFAULT 0,   -- codecs Chromium can decode
 vcodec TEXT DEFAULT '', acodec TEXT DEFAULT '', vfmt TEXT DEFAULT '', available INTEGER DEFAULT 1,
 ord REAL DEFAULT 0, mtime REAL DEFAULT 0, size INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS channels(id TEXT PRIMARY KEY, number INTEGER UNIQUE, name TEXT NOT NULL,
 mode TEXT DEFAULT 'sequential', rules TEXT DEFAULT '{}', description TEXT DEFAULT '', color TEXT DEFAULT '', kind TEXT DEFAULT 'tv');
CREATE TABLE IF NOT EXISTS slots(channel_id TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL,
 media_id INTEGER NOT NULL, cycle INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(channel_id, start));
CREATE INDEX IF NOT EXISTS slots_end ON slots(channel_id, end);
CREATE TABLE IF NOT EXISTS favorites(media_id INTEGER PRIMARY KEY, added INTEGER);
CREATE TABLE IF NOT EXISTS seen(media_id INTEGER PRIMARY KEY, secs REAL DEFAULT 0, last INTEGER);
CREATE TABLE IF NOT EXISTS prefs(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS art(key TEXT PRIMARY KEY, tmdb_id INTEGER, kind TEXT DEFAULT '', title TEXT DEFAULT '', year INTEGER,
 overview TEXT DEFAULT '', tagline TEXT DEFAULT '', genres TEXT DEFAULT '[]', "cast" TEXT DEFAULT '[]', rating REAL DEFAULT 0,
 runtime INTEGER DEFAULT 0, poster TEXT DEFAULT '', fetched INTEGER DEFAULT 0, miss INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS skips(series TEXT PRIMARY KEY, intro REAL DEFAULT 0, outro REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS progress(media_id INTEGER PRIMARY KEY, position REAL DEFAULT 0,
 completed INTEGER DEFAULT 0, updated INTEGER);
"""


def connect(path: str) -> sqlite3.Connection:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # safe with WAL; kind to SD cards
    conn.executescript(SCHEMA)
    if "color" not in [r[1] for r in conn.execute("PRAGMA table_info(channels)")]:
        conn.execute("ALTER TABLE channels ADD COLUMN color TEXT DEFAULT ''")
    if "kind" not in [r[1] for r in conn.execute("PRAGMA table_info(channels)")]:
        conn.execute("ALTER TABLE channels ADD COLUMN kind TEXT DEFAULT 'tv'")
    if "pl" not in [r[1] for r in conn.execute("PRAGMA table_info(slots)")]:
        conn.execute("ALTER TABLE slots ADD COLUMN pl TEXT DEFAULT ''")      # which programming block made the slot
    if "vfmt" not in [r[1] for r in conn.execute("PRAGMA table_info(media)")]:
        conn.execute("ALTER TABLE media ADD COLUMN vfmt TEXT DEFAULT ''")
    if conn.execute("PRAGMA user_version").fetchone()[0] < 4:
        # v2: new episode-number/play-order rules; v3: pixel format is now checked (10-bit / HEVC = black screen); v4: download-style file names are tidied.
        # Either way every file is re-read once on the next scan.
        conn.execute("UPDATE media SET mtime=0")
        conn.execute("PRAGMA user_version=4")
        conn.commit()
    return conn
