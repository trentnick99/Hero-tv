"""'What's new' notes, shown once on the TV after an update. Newest first. Keep each line short and plain."""
from . import __version__

NOTES = {
    "1.20.0": [
        "Roku app: ON DEMAND - press Left for your whole library: Continue watching, Favorites, New, every folder, and Search. Pick any movie or episode and watch it.",
        "On demand on the Roku goes on where you left off (on any screen), plays the next episode by itself, and Left/Right skip 10 seconds.",
        "Roku app: the Weather channel now works on the TV too.",
        "The PC no longer falls asleep while a TV is watching. 'Keep this PC awake' (Settings > Other devices > Always on) keeps the TVs able to find it.",
    ],
    "1.19.2": [
        "Every Roku TV in the house: set up as many as you like (Settings > Other devices > HERO TV on your Roku TVs) - each keeps its own access and is updated by itself.",
        "Roku app: a video the TV cannot play is skipped and the channel goes on with the next show, like real TV.",
    ],
    "1.19.1": [
        "Tidy-up: the help screen (?) and messages point to the right places in Settings, and list the newer keys.",
        "Roku app fixes: the next show always plays in the right format, OK in the guide no longer counts twice, and the channel list no longer jumps while you scroll.",
        "The README guides were brought up to date.",
    ],
    "1.19.0": [
        "Reminders: in the guide press R on a later show (on the Roku: OK on it). When it starts, HERO TV offers to switch - Enter (OK on the Roku) to watch.",
        "Roku app: an 'Up next' card in the last minute of every show, like the one on the PC.",
    ],
    "1.18.0": [
        "Always on (Settings > Other devices): HERO TV can start by itself when you sign in to Windows, quietly in the background, so the Roku app and phones always find it.",
        "It keeps running when the TV window is closed (on by default once a phone or the Roku TV is set up), and starts itself again if it ever stops with an error.",
        "To turn it off completely: Settings > Backup and about > Quit HERO TV.",
    ],
    "1.17.0": [
        "Roku app: OK now opens a real TV guide grid - move through channels and times, OK to watch.",
        "Roku app: Replay jumps back to the last channel, Rew starts the show over, Fwd goes back to live, Right shows the quick channel list.",
    ],
    "1.16.0": [
        "HERO TV on your Roku TV: a real app on the TV - Up/Down changes channel, OK shows the channel list, * turns subtitles on.",
        "Installed from this PC (Settings > Other devices > HERO TV on your Roku TV) - nothing to type on the TV, no pairing code.",
        "HERO TV keeps the TV app up to date by itself, and what you watch on the TV counts for For You too.",
    ],
    "1.15.0": [
        "Report a problem (Settings > Backup and about): type what happened, press Make a report, then Copy and paste it into your Claude chat.",
        "The report holds what is needed to find the cause - version, settings (keys hidden), library, channels, the network check, errors on the screen and the last log lines. Nothing is sent anywhere.",
    ],
    "1.14.3": [
        "Home menu: Down and Up now move between rows properly (the wide Live TV tile confused them before).",
    ],
    "1.14.2": [
        "Arrow keys work properly in Settings: up/down to pick a section, right to go in, then the arrows move to the button or box in that direction (left from the edge goes back).",
        "Changing a setting no longer throws you back to the top - you stay where you were.",
        "The same arrow movement in Pick your channels and on the Details screen.",
    ],
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
        "Settings > Channels: rename, renumber, recolor, change folders and keywords, add or delete channels.",
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
