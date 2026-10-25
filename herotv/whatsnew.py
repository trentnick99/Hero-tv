"""'What's new' notes, shown once on the TV after an update. Newest first. Keep each line short and plain."""
from . import __version__

NOTES = {
    "1.3.0": [
        "Seasonal specials: Halloween Horror Nights on Hero Marathon (Oct 24-31, evenings), holiday specials in December.",
        "Weekly automatic backups (the last 8 are kept) - Settings > Backup and about.",
        "Open-Media-Folder now opens the folder you chose in Settings.",
        "Behind the scenes: the TV page is split into smaller files, and is never shown out of date after an update.",
    ],
    "1.2.0": [
        "Moved, renamed or converted a video? It now keeps its favorite, resume point and history.",
        "New in your library: a Home tile and a New tab in the library show what arrived in the last 30 days.",
        "Watching a show on demand? The next episode starts by itself (Enter = now, Esc = back to live TV).",
        "Settings > Appearance: open HERO TV in a window instead of full screen.",
        "A short welcome on a brand-new install.",
    ],
    "1.1.0": [
        "Watch on your iPhone (or another computer) over your home WiFi: Settings > Other devices. Off until you switch it on.",
        "Each device is paired once with a 6-digit code, and can only watch - never change settings, channels or files.",
        "From the iPhone, AirPlay a video to your Roku TV (turn on AirPlay in the TV's settings first).",
        "Settings > Tools > Make iPhone-friendly copies: .mkv files become .mp4 so phones can play them.",
        "Fixed: 'What's new' did not appear after an update.",
    ],
    "1.0.0": [
        "Settings > Tools does what the helper .bat files did, in the background while you watch.",
        "Settings > Channels: rename, renumber, recolour, change folders and keywords, add or delete channels.",
        "Keyword rules now follow the channel itself, so renumbering a channel never breaks them.",
        "Tested and built automatically on a real Windows PC for every change.",
        "Updates can install the ready-made HERO-TV.exe - no more Build-App.bat after each update.",
        "Fixed: the built application now includes the time-zone database.",
    ],
}


def _vt(v):
    from .updater import version_tuple
    return version_tuple(v)


def since(seen):
    """[(version, [lines])] newer than `seen` (everything when seen is None), newest first."""
    out = [(v, NOTES[v]) for v in NOTES if seen is None or _vt(v) > _vt(seen)]
    return sorted(out, key=lambda x: _vt(x[0]), reverse=True)


def current():
    return __version__
