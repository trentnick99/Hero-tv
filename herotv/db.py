import os
import sqlite3
import zlib

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
CREATE TABLE IF NOT EXISTS prepared(media_id INTEGER PRIMARY KEY, file TEXT DEFAULT '', src_size INTEGER DEFAULT 0,
 status TEXT DEFAULT 'ready', why TEXT DEFAULT '', made INTEGER DEFAULT 0, bytes INTEGER DEFAULT 0, alang TEXT DEFAULT '', mix INTEGER DEFAULT 0);  -- ready-to-play copies (prepare.py)
"""


def connect(path: str) -> sqlite3.Connection:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # safe with WAL; kind to SD cards
    # Every web request opens its own connection. The tables only need making or changing once per version of this
    # file, so a database that already carries this version's stamp is handed back as it is.
    if conn.execute("PRAGMA application_id").fetchone()[0] == _STAMP:
        return conn
    _setup(conn)
    conn.execute(f"PRAGMA application_id={_STAMP}")
    conn.commit()
    return conn


def _setup(conn):
    """Make the tables and bring an older database up to date. Safe to run again at any time."""
    conn.executescript(SCHEMA)
    if "color" not in [r[1] for r in conn.execute("PRAGMA table_info(channels)")]:
        conn.execute("ALTER TABLE channels ADD COLUMN color TEXT DEFAULT ''")
    if "kind" not in [r[1] for r in conn.execute("PRAGMA table_info(channels)")]:
        conn.execute("ALTER TABLE channels ADD COLUMN kind TEXT DEFAULT 'tv'")
    if "pl" not in [r[1] for r in conn.execute("PRAGMA table_info(slots)")]:
        conn.execute("ALTER TABLE slots ADD COLUMN pl TEXT DEFAULT ''")      # which programming block made the slot
    if "seek" not in [r[1] for r in conn.execute("PRAGMA table_info(slots)")]:
        conn.execute("ALTER TABLE slots ADD COLUMN seek INTEGER DEFAULT 0")  # part of a show after a break: starts this far in
    conn.execute("CREATE TABLE IF NOT EXISTS chapters(media_id INTEGER PRIMARY KEY, marks TEXT DEFAULT '[]')")
    conn.execute("CREATE TABLE IF NOT EXISTS art_ep(key TEXT NOT NULL, season INTEGER NOT NULL, episode INTEGER NOT NULL, name TEXT DEFAULT '', "
                 "overview TEXT DEFAULT '', air TEXT DEFAULT '', PRIMARY KEY(key, season, episode))")      # per-episode descriptions (art.py)
    if "facts" not in [r[1] for r in conn.execute("PRAGMA table_info(art)")]:
        conn.execute("ALTER TABLE art ADD COLUMN facts TEXT DEFAULT '{}'")    # studio, genres, keywords (for sorting)
    if "added" not in [r[1] for r in conn.execute("PRAGMA table_info(media)")]:
        conn.execute("ALTER TABLE media ADD COLUMN added INTEGER DEFAULT 0")   # when HERO TV first found the file (0 = before 1.2)
    if "vfmt" not in [r[1] for r in conn.execute("PRAGMA table_info(media)")]:
        conn.execute("ALTER TABLE media ADD COLUMN vfmt TEXT DEFAULT ''")
    if "atracks" not in [r[1] for r in conn.execute("PRAGMA table_info(media)")]:
        conn.execute("ALTER TABLE media ADD COLUMN atracks TEXT DEFAULT ''")   # sound languages, e.g. 'jpn*,eng' (* = plays by default); '' = not read yet
    if "mix" not in [r[1] for r in conn.execute("PRAGMA table_info(prepared)")]:
        conn.execute("ALTER TABLE prepared ADD COLUMN mix INTEGER DEFAULT 0")   # 1 = surround sound was mixed down to stereo in this copy
    if "alang" not in [r[1] for r in conn.execute("PRAGMA table_info(prepared)")]:
        conn.execute("ALTER TABLE prepared ADD COLUMN alang TEXT DEFAULT ''")  # the preferred language this copy was made for ('' = default track)
    if "height" not in [r[1] for r in conn.execute("PRAGMA table_info(media)")]:
        conn.execute("ALTER TABLE media ADD COLUMN height INTEGER DEFAULT 0")  # picture height in pixels (HD / 4K badges); 0 = not read yet
        conn.execute("UPDATE media SET mtime=0")                                # every file is read once more on the next scan to fill it in
        conn.commit()
    if "roku" not in [r[1] for r in conn.execute("PRAGMA table_info(media)")]:
        conn.execute("ALTER TABLE media ADD COLUMN roku INTEGER DEFAULT 0")    # a Roku TV plays the file as it is (library.roku_ok)
        from . import library
        for r in conn.execute("SELECT id,path,vcodec,acodec,vfmt FROM media WHERE verified=1").fetchall():
            if library.roku_ok(r["vcodec"], r["acodec"], r["vfmt"] or "", os.path.splitext(r["path"])[1]):
                conn.execute("UPDATE media SET roku=1 WHERE id=?", (r["id"],))
        conn.commit()
    if conn.execute("PRAGMA user_version").fetchone()[0] < 4:
        # v2: new episode-number/play-order rules; v3: pixel format is now checked (10-bit / HEVC = black screen); v4: download-style file names are tidied.
        # Either way every file is re-read once on the next scan.
        conn.execute("UPDATE media SET mtime=0")
        conn.execute("PRAGMA user_version=4")
        conn.commit()


def _stamp():
    """A number that changes whenever the tables or the steps in _setup change, so nobody has to remember to raise it."""
    text = SCHEMA + "\x00".join(k for k in _setup.__code__.co_consts if isinstance(k, str))
    return (zlib.crc32(text.encode()) & 0x7FFFFFFF) or 1


_STAMP = _stamp()
