"""'What's new' notes, shown once on the TV after an update. Newest first. Keep each line short and plain."""
from . import __version__

NOTES = {
    "1.37.6": [
        "When a video fails to start and the TV jumps back to live TV, the problem report (Settings > Report a problem) now names that video, says what the player complained about, and lists its sound tracks - so the reason can be found.",
    ],
    "1.37.5": [
        "Some downloads state a length in their header that is much longer than the video inside (an Invincible episode said 90 minutes). Fixing those used to fail with 'came out shorter'. HERO TV now checks where the picture really ends and makes the copy.",
        "Copies that still have surround sound (made before 1.37.2) are now remade first, ahead of other background work, so a movie with no voices is fixed sooner.",
    ],
    "1.37.4": [
        "The problem report (Settings > Report a problem) now lists the sound tracks of the last videos you played - language, type, channels - and whether a ready-to-play copy exists, so a sound problem can be found quickly.",
    ],
    "1.37.3": [
        "When fixing a video fails because the file itself is cut off (a download that stopped early, so the picture ends long before the length it claims), HERO TV now says so in plain words and skips the slow second try. Download that file again.",
    ],
    "1.37.2": [
        "Surround sound (5.1) is now mixed down to stereo in the ready-to-play copies and when HERO TV fixes a video. Some players lose the voices from a 5.1 track on two speakers and play only music and effects. Copies made before this that still have surround sound are made again in the background; the old copy keeps working until the new one is ready. Your own files are not touched.",
    ],
    "1.37.1": [
        "Fixed videos that played Hindi (or another language) with no way to get English: when HERO TV fixed a video with several sound tracks it kept only the first one. Now it keeps every language and puts English first.",
        "Videos already fixed that way get a hidden English copy made from the original HERO TV saved in its .originals folder. Nothing is moved or deleted. It happens in the background, so give it some time; progress shows in Settings > Tools.",
    ],
    "1.37.0": [
        "Video names are cleaned up more: edition and streaming labels after the year (IMAX, Remastered, Directors Cut, NF, German DL...), a download site in front of the name, leftover release-group tags, and 'Season 2 Episode 4' wording are dropped so only the title, year, season and episode remain. Videos already in your library are renamed the same way the next time the library is checked. Names you set yourself are never changed, and your files are never renamed.",
    ],
    "1.36.1": [
        "Library shows are grouped better: 'Invincible' and 'Invincible season 1' are now one show, and a folder of episodes with no season/episode numbers (like Dragon Ball) shows as one card instead of one row per episode. Folders of dated movies stay a plain list.",
    ],
    "1.36.0": [
        "The Library now groups episodes by show. Each show is one card (with a stacked look and an episode count) that opens into its episodes in order; press Esc or Backspace to go back to where you were. Shows with the same name in different folders stay separate. Movies and other videos look the same as before.",
    ],
    "1.35.0": [
        "Videos with more than one language now play English by themselves. Settings > Tools > Videos in other formats has a new 'Preferred sound language' choice (English to start with; other languages or Off if you like).",
        "When a video has an English sound track but plays another language first, HERO TV makes a hidden ready-to-play copy that plays the English one - for the PC, phones and the Roku. Your own files are never changed, and videos that already play English are left alone.",
        "The copies count toward the space limit in the same card, and nothing is deleted. It takes a while at first: HERO TV reads each video's sound tracks in the background, then makes the copies one at a time.",
    ],
    "1.34.1": [
        "Settings > Tools > 'New videos: how far along' now also shows when HERO TV is checking your library for new or removed videos, and which new video it is reading.",
    ],
    "1.34.0": [
        "New 'Finish setting up' tile on the Home screen while something is still missing (videos added, video tools installed, videos playable). It takes you straight to the right place and goes away by itself when everything is done.",
        "Screens now fade in instead of snapping open, and the info bar slides up gently when you press I or change channel. (Turned off if your system asks for less motion.)",
        "The Library remembers which tab you used last (All, New, Continue watching, Favorites).",
    ],
    "1.33.0": [
        "When a tool in Settings > Tools finishes with problems (Fix all, Free movies, bringing in a folder...), it now says in plain words what went wrong with each video, and offers 'Try again'. The full technical log is one button away ('Show the full log').",
    ],
    "1.32.0": [
        "Settings has a 'Needs a look' box at the top. It lists anything that wants your attention - an update, videos that cannot play, videos waiting in the Inbox, missing video tools, ready-to-play copies that failed - and an Open button takes you straight to it. It stays hidden when everything is fine.",
        "Settings > Tools is shorter: its cards are folded into four sections (Right now, Add videos, Formats and copies, Tidy and check). Press Enter on a section name to open or close it; HERO TV remembers which ones you left open.",
    ],
    "1.31.0": [
        "Settings > Tools has a new card, 'New videos: how far along'. It shows each movie from the Inbox as it is checked, fixed (picture, then sound) and sorted onto its channel, with a progress bar, how many more are waiting, and the ready-to-play copy progress.",
        "It updates by itself while the card is open. Nothing is deleted - it only shows what HERO TV is doing.",
    ],
    "1.30.1": [
        "Settings > Tools > Videos in other formats has a space limit: choose how many GB the ready-to-play copies may use. When it is reached HERO TV just stops making new copies - nothing is ever deleted, copies and videos alike.",
        "Updates are now checked against the checksum GitHub publishes for the file, so a damaged or swapped download is refused instead of installed.",
        "If the Checklist file is missing or broken, the Checklist screen now says so instead of showing an empty page.",
    ],
    "1.30.0": [
        "Far fewer videos need fixing: movies with Dolby (AC-3) or DTS sound, or H.265 inside an .mkv, now get a hidden ready-to-play copy that HERO TV makes by itself in the background (the picture is copied, only the sound is converted). They join the channels when the copy is ready. Your own files are never changed. Settings > Tools > Videos in other formats shows the progress.",
        "Roku: plays your original files directly when it can (Dolby sound, H.265 in .mkv), so those movies are in On Demand at once. If a Roku ever refuses one, it tries the ready copy by itself.",
    ],
    "1.29.4": [
        "Videos with a damaged sound track (ffmpeg: 'Decode error rate exceeds maximum') can be fixed now: HERO TV uses the file's other sound track if it has one, or keeps the sound and skips the damaged bits (those moments are silent).",
        "A failed fix no longer blames the graphics card when the problem was the sound.",
    ],
    "1.29.3": [
        "Fixing a video is safer: a file is never converted twice at the same time (the Inbox and Fix all could both pick it up and leave a damaged copy), and a new copy must be as long as the original before it replaces it.",
        "When copying the picture fails, HERO TV tries again by re-encoding it, and the log now says what ffmpeg reported.",
        "Long fixes show how far along they are (10%, 20% ...).",
    ],
    "1.29.2": [
        "DVD rips that were already turned into .mp4 files with raw (PCM) sound are now listed under Settings > Tools > Videos that are skipped too, so Fix all repairs their sound.",
    ],
    "1.29.1": [
        "Bad sound (static, noise) fixed: Dolby (AC-3) sound is always converted to AAC again, and so is the raw sound of DVD rips (MakeMKV). Videos this affected now show under Settings > Tools > Videos that are skipped - press Fix all.",
        "When the graphics card converts a video, HERO TV now checks the picture came out right, and if it did not, does it again on the processor.",
    ],
    "1.29.0": [
        "H.265 (HEVC) videos: HERO TV now tests once whether this PC can show them, and plays them when it can instead of skipping them. If it cannot, Settings > Tools > H.265 says what to install (Microsoft's HEVC Video Extensions). Dolby (AC-3) sound is tested the same way.",
        "Fix is much faster when your PC has an NVIDIA, Intel or AMD graphics chip: it converts with the graphics card (minutes, not 15-40 minutes for a movie).",
        "Sorting: videos loose in your media folder are now filed automatically, like the Inbox. Settings > Tools has a new 'Videos not on any channel' card with a Sort them button.",
        "Names like 'Avengers Endgame 2019 Hindi-English' or '... [Hindi + English] Dual Audio' are cleaned up to the title and year.",
    ],
    "1.28.2": [
        "Cover art: titles that differ a little from TMDB's (Spiderman 3 / Spider-Man 3, X Men / X-Men) now find their poster and details. Titles that found nothing before are looked up again once.",
        "'Phone can't connect?' no longer says the firewall has no rule for HERO TV when Windows saved the rule with a differently written path.",
        "Help (?): a new 'Where to find things' list, and the keys list fits on the screen again.",
    ],
    "1.28.1": [
        "Update checks that fail with 'a security certificate was refused' try again the safe way: Windows is asked to check GitHub once (it then fetches a root certificate it was missing), then HERO TV's own up-to-date list of trusted certificates. Nothing is ever left unchecked.",
        "Roku TVs: the HERO TV app on them is brought up to date every half hour until it is done (no longer only every 6 hours), and never while you are watching HERO TV on that TV.",
        "Quieter log: a TV or phone stopping a video no longer writes error lines.",
    ],
    "1.28.0": [
        "A new look: easy-to-read text and TV-style condensed titles and channel numbers (free fonts, built in).",
        "Pictures in the guide: a still of the show you are on, with a soft blurred copy behind the guide - on the PC, phones and the Roku app.",
        "Three looks to choose from (Settings > Appearance > Look): Classic dark, Pure black for OLED TVs, and Retro cable blue.",
    ],
    "1.27.0": [
        "Even volume: quiet videos are turned up and loud ones down, so everything plays at about the same volume (Settings > Appearance).",
        "Night mode: dimmer, warmer menus and gentler sound between the times you choose.",
        "Screensaver: pictures from your library drift across the screen when a video is paused or a menu is left open (never during live TV).",
        "TV edge margin for TVs that cut off the edges of the menus.",
    ],
    "1.26.0": [
        "Intros and credits are found by themselves: HERO TV listens to the episodes of each show and finds the theme song and the credits. On demand (PC, phones, Roku) the intro is skipped and the credits go straight on to the next episode.",
        "Progress and a 'Check everything now' button: Settings > Tools. Points you set with J and E still win.",
    ],
    "1.25.1": [
        "Live TV in other apps: streams stop cleanly when HERO TV quits or other devices are switched off.",
    ],
    "1.25.0": [
        "Live TV in other apps (Settings > Other devices): your channels and the guide in Plex, Jellyfin, Emby, Channels and IPTV apps like TiviMate on Fire TV, Apple TV and Android TV. Off until you switch it on.",
    ],
    "1.24.0": [
        "Breaks inside shows, like real TV: tick 'Breaks inside shows' under Start times on a channel. Shorts play in the middle of each show (two breaks in longer ones), at a chapter mark when the video has one.",
        "A show cut short by a time slot now switches over on time on every screen.",
    ],
    "1.23.0": [
        "Time slots (Settings > Channels > a channel > Time slots): pick days and hours and what plays then - like cartoons on Saturday mornings.",
        "Seasonal folders: videos in a folder named December, Halloween, Christmas (or any month) only play on the channels in that month.",
        "New channel 18, Cartoon Shorts: your Shorts folder and the free classic cartoons, all day. A channel with nothing to show plays shorts instead of going blank.",
    ],
    "1.22.0": [
        "New play orders (Settings > Channels > a channel > Play order): 'Mixed shows, each in order' - shows take turns but episodes never jump around - and 'Mixed shows, fair share', so a big show no longer crowds out the small ones.",
        "Channel logo in the corner of the picture, like a TV network's (Settings > Appearance > Channel logo): now and then, always, or off. On the Roku too.",
    ],
    "1.21.0": [
        "Clean start times, like real TV: Settings > Channels > a channel > Start times - on the quarter hour, half hour or hour.",
        "The gap before each show is filled with whole short cartoons from a Shorts folder in your media folder (free classic cartoons from Tools > Free movies count too) - never cut off.",
        "The last minute or two shows an 'Up next' card with a picture of the next show, on the PC, phones and the Roku app.",
    ],
    "1.20.2": [
        "Updates: when GitHub limits update checks from your Internet address (common with T-Mobile and other shared home internet), HERO TV asks GitHub's releases page instead.",
        "If checking still fails, the message now says why (no connection, a refused certificate, or GitHub's limit).",
    ],
    "1.20.1": [
        "Roku guide: the key help no longer hides behind the time bar, the top shows what is on now, and the Weather channel shows a forecast block instead of 'No Data Available'.",
        "Roku on demand: shows without season numbers no longer say 'S0 E0', and folder names typed in lower case look tidy ('South Park').",
        "Videos whose built-in title was a download site's label (like 'PSArips.com | ...') are named from the file again.",
        "Get Free Movies skips uploads that are too new to be public domain (from 1978 on), whatever the upload claims.",
    ],
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
