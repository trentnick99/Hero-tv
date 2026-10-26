"""'What's new' notes, shown once on the TV after an update. Newest first. Keep each line short and plain."""
from . import __version__

NOTES = {
    "1.14.1": [
        "Check the connection now also explains the two-router case: if the phone's address starts differently from the PC's, they are on different routers - and how to fix it.",
    ],
    "1.14.0": [
        "Phone won't connect? Settings > Other devices > Check the connection finds out why (Windows Firewall, a network marked Public, a VPN).",
        "Fix it sorts out the firewall and network type in one press - Windows asks for permission first.",
        "Every address this PC has is listed, in case the first one is not your home network.",
    ],
    "1.13.0": [
        "New channel 17, For You: it learns what you watch - the next episode of your shows, films you stopped half-way, and more like what you enjoyed lately.",
        "Movies play in release order: with your TMDB key, films are sorted by their real release dates, even when the file name has no year.",
        "Hero Marathon follows the clock like real TV: cartoons on weekend mornings, hero films in prime time, scary films late at night (switch it off in Settings > Channels).",
    ],
    "1.12.0": [
        "Pick your channels: a new HERO TV starts by letting you tick the channels you want - handy when you share it with friends.",
        "Switch any channel off or back on in Settings > Channels (Choose your channels..., or inside a channel). Nothing is deleted.",
        "A switched-off channel leaves the guide and gets no new videos until you switch it back on.",
    ],
    "1.11.0": [
        "Updates with one press: when a new HERO TV is out it tells you, and Settings > Backup and about > Install now does the rest.",
        "It closes for a moment, puts the new version in place and starts again by itself - your videos, favorites and settings stay.",
        "It looks every few hours; switch that off in Settings > Backup and about if you like.",
    ],
    "1.10.0": [
        "New channels from the Inbox: a show or pack nobody planned for (say an old PBS Kids show) can get its own channel - pick '+ New channel', name it, done.",
        "A show or a folder of episodes dropped in the Inbox is listed once and moves together.",
        "New episodes of a show you already have go straight to that show's channel.",
        "Missing episodes: a show's Details say which aired episodes you don't have; Tools > Check my shows lists them for every show (needs the TMDB key).",
        "The same video twice: Tools lists duplicates and can set the extra copy aside to free space.",
    ],
    "1.9.0": [
        "Wrong channel? Open a video's Details (D) and press M: tick where it belongs and Save. A show moves with all its episodes.",
        "Details now say which channels a video is on.",
        "Settings > Tools > Inbox lists videos HERO TV could not place - choose a channel and press Put it here.",
        "Tick Remember and HERO TV learns: new episodes or copies of that title go there by themselves from now on.",
    ],
    "1.8.0": [
        "Smart sorting: with your TMDB key, new videos are filed by what they really are - studio, genre and film series.",
        "Marvel channels only get Marvel shows and films, horror gets horror and dark thrillers, DC gets DC - same-name titles stay out.",
        "Spider-Man cartoons go to Marvel Television, X-Men '97 to Marvel Animation, Logan to X-Men (and Logan Lucky nowhere).",
        "Without a key, or for titles TMDB does not know, the keywords are used as before. Switch it off in Settings > Channels.",
    ],
    "1.7.0": [
        "A cleaner look: one matching set of icons on the Home menu, a bigger Live TV tile showing what is on now.",
        "The details screen (D) shows the video's picture full-size with Play and Back buttons.",
        "Tips no longer cover the menus, and on-screen help now points to Settings instead of helper files.",
    ],
    "1.6.0": [
        "Easier phone setup: Settings > Other devices shows a QR code - open the iPhone's Camera, point it at the screen, tap the link.",
    ],
    "1.5.0": [
        "Subtitle size and style: Settings > Appearance (bigger text, outline only, or yellow) - on the TV and on phones.",
        "Roku Media Player and other TV media apps now get the video's subtitles too.",
        "A proper Windows installer for new PCs (HERO-TV-Setup on the Releases page): Start menu, desktop icon, uninstall.",
    ],
    "1.4.0": [
        "Browse your library on the TV itself: Roku Media Player (and VLC or other TV media apps) can now find HERO TV.",
        "Switch it on in Settings > Other devices. It is off until you do - while on, anyone on your WiFi can watch your videos.",
        "On the Roku: open Roku Media Player and pick your station - folders, shows and new arrivals are all there.",
    ],
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
