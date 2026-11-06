"""'What's new' notes, shown once on the TV after an update. Newest first. Keep each line short and plain."""
from . import __version__

NOTES = {
    "1.38.74": [
        "Library: searching on the New, Continue watching or Favorites tab now tells you when the title is under All instead (\"1 found in All\"); press Enter or the button to see it.",
        "Details: after Move to another channel, the \"On:\" line shows the new channels straight away.",
        "Settings > Tools: a film that is still being prepared in the Inbox is no longer listed as one HERO TV could not place (it shows under New videos: how far along).",
    ],
    "1.38.73": [
        "Sorting: newer MCU films (Spider-Man: Brand New Day, Thunderbolts, The Fantastic Four: First Steps, Deadpool & Wolverine, Captain America: Brave New World, Avengers: Doomsday and Secret Wars) now go on Marvel Movies as well as their other channels, even if you changed your keyword list.",
    ],
    "1.38.72": [
        "Fix (finishes 1.38.71): videos sorted automatically out of the Inbox now keep playing straight away; the automatic sorter had not been updating the library entry at all. Subtitle files and posters now move along with the film.",
    ],
    "1.38.71": [
        "Fix: a film sorted out of the Inbox could refuse to play (\"format error\") until the next library scan, when the library already knew its new folder from an earlier copy. HERO TV now switches that entry back on and reads newly filed videos straight away.",
    ],
    "1.38.71": [
        "Fix: a new film dropped in the Inbox could fail to play (\"format error\") right after it was sorted onto its channel, because the library still pointed at its old place in the Inbox. The library entry now follows the film at once (and keeps its progress).",
        "Fix: subtitle files (.srt) and the film's own poster now move with the film when it is sorted onto a channel, instead of staying behind in the Inbox.",
    ],
    "1.38.70": [
        "Guide: the picture box at the top is always there (the channel you are watching shows its still too, weather shows the channel number), so the text no longer jumps sideways between channels.",
        "Library: search puts the best match first (typing invincible shows Invincible before a Dragon Ball episode that mentions the word). Length badges read \"127 min HD\" instead of the HD tag covering the minutes, and the key hints no longer break across lines.",
        "Episodes without a proper name (Invincible S1E1, or SHOUTING file names) get their real name from TMDB in the library and the P episode list.",
        "Videos with no episode number inside a show's folder (for example Dragon Ball episodes named only by title) now get that show's description, rating and genres, and Pick for me says which show each episode is from.",
        "Check everything only counts program errors since HERO TV last started, and Report a problem now includes the error itself.",
    ],
    "1.38.69": [
        "Player info bar: long titles no longer run into the VOD/channel badge (they stop at 2 lines), and the key hints fit on one line (J and E for marking intros and credits are now listed in Help).",
        "Intros: the title card uses smaller letters for long names, is not shown before short clips (under 10 minutes), and the info bar stays hidden while it plays.",
    ],
    "1.38.68": [
        "Home: when you come back to Home it returns to the tile you opened, already in view. Before, the highlight jumped back to the top while the screen stayed where you were.",
    ],
    "1.38.67": [
        "Your watching: hours this week are now counted day by day from today (they wrongly added up everything ever watched on anything you touched this week), and live TV is no longer counted twice in hours watched.",
    ],
    "1.38.66": [
        "Home > More > Your watching: hours watched (all time and this week), what you watch most, your favourite genres and what was added this week.",
        "Home > More > Pick for me: swipe through films and shows you have not seen, one at a time with the poster and story. Right = maybe, Left = skip, Enter = play now. Press Esc to choose from your maybes.",
        "New Home row: New this week (Settings > Appearance > Home rows), with how many films and episodes were added.",
    ],
    "1.38.65": [
        "Subtitles: C now simply turns them on or off (your last language, else English). Shift+C opens a list of every language to pick from. Before, C stepped through every language one by one, so a film with many took many presses to turn them off.",
        "Sound tracks: press A while watching a film with several languages (for example Hindi and English) to switch straight away, no copy needed. HERO TV remembers your pick for the next film. Close and start HERO TV once after this update for A to work. The Roku app and phones still use the ready-to-play copy.",
    ],
    "1.38.64": [
        "Fix: videos with an emoji in the file name (many download sites add one) no longer break the background volume check, intro finder and start-up checks. Videos that could not be measured before are measured again.",
    ],
    "1.38.63": [
        "Intros: the channel tag now stands in for the bottom info bar when you change channel (press I to see the bar).",
    ],
    "1.38.62": [
        "New, off by default: Intros (Settings > Appearance > Intros). A short branded moment drawn by HERO TV: a start-up ident with your station name when it opens, a channel tag in the channel's colour when you change channel, and a title card before a film or episode you start from the beginning. Any key skips it.",
    ],
    "1.38.61": [
        "Even volume is better: quiet films can now be turned up by as much as 15 dB (was 9) with a limiter so they do not crackle, the volume is measured after surround sound is mixed down to stereo (what you actually hear), and a quiet film no longer stays quiet if the sound system had not started yet. Every video is measured once more in the background, so levels settle over the next while.",
    ],
    "1.38.60": [
        "Home: rest on a film or episode for a moment and a short muted clip plays inside its tile. It stops when you move on. The big description panel at the bottom of Home now fades away after 3 seconds too (any key brings it back), so it stops covering the rows. The clips follow Settings > Appearance > Live picture on Home (turn that off to stop the clips too).",
    ],
    "1.38.59": [
        "The key-hint bar now fades after 3 seconds instead of 6.",
    ],
    "1.38.58": [
        "The key-hint bar at the bottom of Home, the Guide and the Library now fades away after 3 seconds and comes back when you press a key or move the mouse.",
    ],
    "1.38.57": [
        "While an episode plays, press P to see every episode of the show: pick one to jump straight to it (the one playing is marked). The player's key hints are shorter so they fit on one line.",
    ],
    "1.38.56": [
        "Library: copies of the same film (a 1080p and a 4K file, an unrated cut) now show as one tile marked \"2 versions\". Press Enter and pick which one to play. Films with different lengths, episodes and files with no year are never merged.",
    ],
    "1.38.55": [
        "Fix for the 1.38.54 release build: the Watched tick no longer breaks the Windows build tests. (1.38.54 itself was not published; its changes are in this version.)",
    ],
    "1.38.54": [
        "Home: a rotating Featured banner (turn it on in Settings > Appearance > Home rows), HD and 4K badges and green Watched ticks on picture tiles and in the library, and a Surprise me tile under More that plays something you have not watched. HERO TV reads each video once more after this update to learn its picture size.",
    ],
    "1.38.53": [
        "New smart rows for Home: Not watched yet, Quick watches (under 30 minutes), Movies, Top rated, and one row per genre (Comedy, Animation and so on, from the TMDB information). Turn them on in Settings > Appearance > Home rows. Each show appears once, as its first unwatched episode.",
    ],
    "1.38.52": [
        "Shuffled channels no longer play the same video twice in a row when a new round of the shuffle begins.",
        "Folders linked into your media folder (symbolic links) are now scanned too, so their videos show up on your channels.",
    ],
    "1.38.51": [
        "Roku: the TV guide and the channel list now carry each channel's colour (a coloured stripe and a softly tinted background) instead of being all black and grey. Update the Roku app from Settings > Other devices to get it.",
    ],
    "1.38.50": [
        "Guide: the L key now really opens the Library (the hint at the bottom promised it), and H opens Home.",
    ],
    "1.38.49": [
        "Roku: Back on the live picture no longer drops you straight out to the Roku home screen. It asks you to press Back a second time within 3 seconds. Update the Roku app from Settings > Other devices to get it.",
    ],
    "1.38.48": [
        "Fixed a small video box that stayed at the top right of Home, Library or Help after you came from the Guide.",
    ],
    "1.38.47": [
        "Guide: the top part now keeps exactly the same layout for every program - channel name always at the same spot, long titles and descriptions are cut short instead of pushing things around, and the small live picture is lined up again each time you move.",
    ],
    "1.38.46": [
        "Home: the Live TV tile keeps its name and the red LIVE badge in front of the live picture.",
    ],
    "1.38.45": [
        "Guide: a very long title (some episode names run to three lines) can no longer push the channel name off the top or crowd the time ruler.",
    ],
    "1.38.44": [
        "Many more descriptions: episodes that sit in a folder named for their show (South Park, Dragon Ball) now get the show's description, and each episode gets its own plot when TMDB lists it. Dragon Ball is looked up as Dragon Ball Super - your folder and channel are not changed.",
        "Names with leftovers like \"[60FPS]\" or \"Hindi English\", and \"Invincible season 1\", are cleaned before the lookup. The Spider-Man 1994 series is matched to the right show. The new lookups run by themselves in the background after the update.",
        "Check everything now also tells you how many titles have a description.",
    ],
    "1.38.43": [
        "The information panel on Home now grows to fit its text, so the title is never cut off at the top.",
    ],
    "1.38.42": [
        "On Home, the picture you have selected now shows an information panel at the bottom: the title, channel, year, length, rating and a short description (when your library has them), and whether it is on now, starts later, or where you left off.",
    ],
    "1.38.41": [
        "On Home, the Live TV tile is now bigger and plays the channel that is on - without sound - with the time it ends and a progress bar. Turn it off under Settings > Appearance > Live picture on Home if you prefer a still picture.",
    ],
    "1.38.40": [
        "New: Settings > Backup and about > Check everything. It looks at the library, video tools, media folder, free space, channels, the TV guide and the recent log and says in plain words what is fine and what is not. It only looks; nothing is changed.",
        "After an update, HERO TV now checks itself once on the first start and tells you if something looks wrong (also listed under Needs a look). The folder with the earlier version can be opened from Check everything.",
        "Screen errors are now also written to the log, so they are still there after a restart and Report a problem can include them.",
    ],
    "1.38.39": [
        "The TV Guide and Library tiles on Home now have a picture too, so the Start here row no longer has two blank tiles in the middle.",
    ],
    "1.38.38": [
        "HERO TV now opens on Home, with a row of big 'Start here' tiles: Live TV (with a live picture), TV Guide, Library and Continue watching. Prefer the old way? Settings > Appearance > Open HERO TV on > Live TV.",
        "The Start here row can be hidden or moved with the Home rows setting.",
    ],
    "1.38.37": [
        "Fixed the TV guide: a long description no longer spills over the time ruler or cuts off the channel name at the top.",
    ],
    "1.38.36": [
        "New setting: Home rows (Settings > Appearance). Choose which rows show on Home (On now, Continue watching, New in your library, Favorites) and put them in the order you like.",
    ],
    "1.38.35": [
        "New setting: Text colour (Settings > Appearance). Soft grey is a little dimmer than white and easier on the eyes; Warm and Cool are also there.",
    ],
    "1.38.34": [
        "The outline around the picture you have selected can now be gold, cyan, red, green, purple or orange (Settings > Appearance > Highlight), and has a soft glow you can turn up or off (Highlight glow).",
        "The title on the Details screen now follows your Font and Lettering settings.",
    ],
    "1.38.33": [
        "The left-side menu now starts as Light glass (see-through). You can still pick Smoked glass or Solid in Settings > Appearance > Menu style.",
    ],
    "1.38.32": [
        "The left-side menu is a little wider so 'Continue watching' stays on one line.",
    ],
    "1.38.31": [
        "The left-side menu is now a floating glass panel. Settings > Appearance > Menu style lets you choose Smoked glass, Light glass (more see-through) or Solid (easiest to read). The menu text is brighter and bolder too.",
    ],
    "1.38.30": [
        "New left-side menu: on Home press Left from the first picture (or move the mouse to the left edge of the screen, or use the Menu button over the picture) to open Home, Guide, Library, Continue watching, Details, Settings and Back to TV. It replaces the buttons across the top. Phones keep their button bar.",
        "The picture you have selected now stands out more: a bold white outline, slightly larger, with the others dimmed. Settings > Appearance > Highlight lets you use your main colour instead.",
    ],
    "1.38.29": [
        "Lettering: a long title that wraps onto two lines now shines evenly on both lines, and the Glossy reflection is shorter so it stays clear of the text under it.",
    ],
    "1.38.28": [
        "New in Settings > Appearance: Lettering. Choose Flat, Soft shadow, Satin or Glossy for the big titles (the station name and the featured title on Home). Smaller text stays flat so it is easy to read.",
    ],
    "1.38.27": [
        "New in Settings > Appearance: a Font choice (Broadcast, Cinema, Classic guide, Modern streaming) and four new looks (Cool, Warm, HDR, Cinematic). The main colour picker is still there and works with every look. Fonts and looks also apply on paired phones.",
    ],
    "1.38.26": [
        "Cleaned up: the 'Up next' card no longer sits under the menu bar that appears when you move the mouse, and on a phone it is wider so the show name is not squeezed. The arrow next to the groups in Settings > Tools now lines up with the text.",
    ],
    "1.38.25": [
        "Continue watching no longer lists videos you got most of the way through (90% or more). To take any other video off it yourself, select it and press X on Home, or F6 in the Library's Continue watching list.",
    ],
    "1.38.24": [
        "Fixed: on Home, the greeting under the station name no longer runs into the label above the big title (the title is a little smaller).",
    ],
    "1.38.23": [
        "Fixed: two settings changed in quick succession could save out of order and undo each other. They now save one at a time.",
        "Fixed: 'Keep both' choices on the duplicates screen are now part of a backup and come back after a restore.",
    ],
    "1.38.22": [
        "Fixed: after an update from inside HERO TV, HERO TV's own window did not come back by itself. It now opens again automatically. A program file that Windows will not let the update overwrite is now renamed aside instead of failing the update.",
    ],
    "1.38.21": [
        "The guide shows showtimes in a shorter form (5:00\u20135:24 PM) so they fit in a narrow box instead of being cut off. The first-run tip about the H key now only appears while you are watching TV, never on top of a menu.",
    ],
    "1.38.20": [
        "A quieter log: a video that is already being converted is no longer tried again every few seconds (no more repeated \"already being fixed\" lines), and a Roku TV that cannot be reached is mentioned once instead of on every retry. Nothing changes in how things work.",
    ],
    "1.38.19": [
        "When a video you added cannot be placed on any channel, a quiet \"needs a channel\" shortcut now shows in the More row on Home. Nothing pops up and nothing is interrupted; it takes you to the Inbox, where you pick a channel for it.",
    ],
    "1.38.18": [
        "Dropping a big video on HERO TV's window no longer dims the picture so much, and the copy into your Inbox is a little gentler on the disk, so the movie you are watching is less likely to freeze while it is added.",
    ],
    "1.38.17": [
        "Dropping a video on HERO TV's own window now adds it: the window copies it into your Inbox itself, and the \"drop videos here\" sign can no longer get stuck over the picture (it goes away by itself, or on any key or click). Your original file stays where it was.",
    ],
    "1.38.16": [
        "Fixed: after an in-app update, clicking your HERO TV shortcut could start an old copy from the update's backup folder and say it cannot start. Windows had re-pointed the shortcut when the old program was moved away. Updates now copy the old program instead of moving it, and HERO TV points any shortcut (Desktop, Start menu, Startup, taskbar) that went to the backup folder back at itself every time it starts.",
        "HERO TV's own window now closes by itself when HERO TV is shut down, and an update closes it first so it cannot hold the program files.",
    ],
    "1.38.15": [
        "In HERO TV's own window, dropping a video on it could turn the whole window black (the window opened the file itself). The window now puts HERO TV straight back and keeps the drop for HERO TV. If a drop still does not add the video, switch off Settings > Appearance > Open in HERO TV's own window, or copy the video into your Inbox folder.",
    ],
    "1.38.14": [
        "New: under \"The same video twice\" each group has a Keep both button. Press it when the files are really different (like episodes filed under the wrong season) and the group disappears from the list. If another copy of the same thing turns up later, it is listed again.",
    ],
    "1.38.13": [
        "Fixed: \"The same video twice\" no longer lists episodes that only share a number. Two files with different episode names (or in different Season folders) are different episodes that were filed wrongly, not copies - so you will not be asked to set one aside.",
        "Fixed: after an update, an old HERO TV window that was still open could fail to start from the update's backup folder. It now closes itself, and starting the old program from there starts the new one instead.",
    ],
    "1.38.12": [
        "New: Settings > Tools > Tidy HERO TV's own files. It shows what can go - old schedule rows from days that are over, the subtitle cache, update files already installed, the old log - and tidies it with one button. Your videos, favorites, resume points and settings are never touched.",
    ],
    "1.38.11": [
        "A video you downloaded again after it was marked as a damaged download is checked afresh instead of staying on the damaged list. Starting HERO TV again no longer opens a second own window.",
    ],
    "1.38.10": [
        "Fixed the Home screen bouncing up and down for a moment when you open it (it was sliding back to where you were after it filled in).",
    ],
    "1.38.9": [
        "New: HERO TV can open in its own window with no Edge around it. Turn it on in Settings > Appearance > Open in HERO TV's own window, then start HERO TV again. If it cannot open, Edge is used like before.",
    ],
    "1.38.8": [
        "The HERO TV window now has its own icon in the taskbar and a dark title bar that matches the picture, instead of looking like a plain Edge page.",
    ],
    "1.38.7": [
        "For a homelab: http://your-pc:8788/health says HERO TV is up (for Uptime Kuma and similar), and /metrics gives counts for Grafana or Prometheus (videos, problems, copies, free space). On the home network /metrics needs the live-TV key (Settings > Other apps); /health shows nothing private.",
    ],
    "1.38.6": [
        "When a repair fails because the picture inside the file is broken (not the sound), Help now lists the video as a damaged download and tells you to get it again, instead of trying to repair it over and over. The Amazing Spider-Man 2 file is one of these.",
    ],
    "1.38.5": [
        "A video that stops on its very first sound packet (The Amazing Spider-Man 2 does) now gets a new repair try: HERO TV skips that one bad packet and keeps the rest of the sound, in the right language. If the repair failed on an earlier version, play the video again and it is tried again with the new method.",
        "Settings > Report a problem now also runs the repair on the first 30 seconds of such a video and says what happened, and a failed repair keeps ffmpeg's exit code and last lines - so a repair that still fails can be understood.",
    ],
    "1.38.4": [
        "When a video stops on a damaged sound packet, Settings > Report a problem now also describes that sound track and what ffmpeg says about its first seconds, and it keeps more of the reason a repair failed. This is to find out why The Amazing Spider-Man 2 cannot be repaired yet.",
        "Fixed a rare error when switching to Weather or to an on-demand video at the same moment the previous channel finished loading.",
    ],
    "1.38.3": [
        "Settings > Report a problem now says what became of the repair of a video that would not play: waiting in line, failed (and why), or ready - plus how much room is left on the drive for ready copies. HERO TV also writes a line in its log when a repair or copy fails or has to wait for room.",
    ],
    "1.38.2": [
        "The big picture at the top of Home is sharper and brighter: HERO TV now makes a larger still of the video for it (the first time you open Home with a new video there, it takes a moment).",
        "An episode whose file name had only download tags after the episode number (like 'S03E08 1080p AMZN') is now called 'Episode 8' instead of showing the tags.",
    ],
    "1.38.1": [
        "The Home screen no longer keeps asking for pictures that do not exist yet, so it draws a little faster and the PC does less work.",
        "The log file (Settings > Report a problem uses it) now starts over by itself when it gets big, even if you leave HERO TV running for weeks. The previous part is kept as herotv.old.log.",
    ],
    "1.38.0": [
        "The Home screen has a new look, like Netflix or YouTube TV: a big banner for what to watch next (Resume if you are partway through something, otherwise what is on now), then rows of pictures - On now, Continue watching, New in your library and Favorites - and a row of shortcuts (TV guide, Library, Settings, Help and the rest).",
        "Use the arrow keys to move: Left and Right along a row, Up and Down between rows. Enter plays or opens the picture you are on, and 'See all' at the end of a row opens the full list in the Library.",
    ],
    "1.37.8": [
        "A video whose picture is damaged as well as its sound is now repaired too: if copying the picture fails, HERO TV makes the picture again in the background (slower, but it plays).",
        "HERO TV now prefers your real home network address over a VPN card (like Mozilla VPN) when it tells phones and Roku TVs where to connect. A Roku app that was set up with the VPN address is reinstalled with the right one automatically.",
    ],
    "1.37.7": [
        "A video with a damaged piece of sound (the player stops with a decode error and the TV jumps back to live TV) is now repaired automatically: HERO TV says so on screen and makes a ready-to-play copy with the sound made again and the damaged bits skipped. Try the video again after a few minutes. Your own file is not touched.",
    ],
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
