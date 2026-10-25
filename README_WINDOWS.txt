HERO TV on Windows 10 / 11
==========================

START IT (3 steps)
  1. Right-click the zip file > "Extract All..." and extract it somewhere normal (Desktop or Documents).
     Do NOT run it from inside the zip window - that is the #1 reason it fails.
  2. Double-click  HERO-TV.bat
       - If Windows says "Windows protected your PC": click "More info", then "Run anyway".
         (It shows this for any downloaded script. The file is plain text - you can open it in Notepad and read it.)
       - First run, it checks your PC and offers to install what is missing (Python, ffmpeg). Say Y.
         If it tells you to close the window and start again after an install, that is normal.
  3. The TV opens fullscreen. Leave the black window open while you watch. Close it to turn the TV off.

With no videos yet it runs in DEMO MODE with made-up test clips so you can try the guide and channels.

WHERE THINGS GO  (the short version - there are only two places)
  1. THE PROGRAM FOLDER (where you extracted the zip): the .bat files and settings. Never put videos here.
  2. YOUR MEDIA FOLDER: all your videos. Double-click  Open-Media-Folder.bat  to open it. Inside you will see:
       Inbox          <- NOT SURE where a movie goes? Drop it here, then double-click Sort-Movies.bat
       MCU, DC, X-Men, Dragon Ball, South Park, ...   <- one folder per channel. Know the channel? Put the movie right in it.
       Free Movies    <- filled by Get-Free-Movies.bat. Leave it alone.
       WHERE THINGS GO.txt   <- this same cheat sheet, kept inside the folder
     (The hidden ".originals" folders are safe copies from fixes. Clean-Originals.bat deletes them when you are happy.)
  The folders are created for you, empty ones do no harm, and nothing you already have is moved or changed.
  Everything else (schedule, resume points, settings) HERO TV keeps by itself in a hidden folder. You never touch it.

YOUR CHANNEL LINEUP  (and the folder each one reads)
   1  Marvel Movies      folder MCU                   10  Hero Marathon     everything, shuffled (Movie Night, Saturday cartoons)
   2  Marvel Television  folder Marvel Television     11  Dragon Ball       folder Dragon Ball
   3  Marvel Animation   folder Marvel Animation      12  South Park        folder South Park
   4  Spider-Verse       Spider-Man MOVIES (tag)      13  Weather
   5  X-Men              folder X-Men                 14  Free Movies       Get-Free-Movies.bat
   6  DC Movies          folder DC                    15  Invincible        folder Invincible
   7-9 Classics / Action / Comedy (by tags)            16  Thriller & Horror folder Thriller & Horror (or tag thriller / horror)
  Channels with nothing on them stay hidden, so only the ones you have filled show up. Sort-Movies.bat knows keywords for
  all of these ("invincible" -> 15, Halloween / Hereditary / Psycho... -> 16). Rename or recolour any channel in channels.json.

CHECKLIST - WHAT YOU HAVE AND WHAT IS STILL MISSING
  Press H, then pick "Checklist" (or double-click Checklist.bat). There is a tab for each list - Marvel Movies, Spider-Man,
  X-Men and Deadpool, DC Movies, Invincible (by season, showing the missing episode numbers), South Park, and some Thriller &
  Horror ideas. Press Left / Right to change list. Films not out yet show as "coming soon", not missing.
  Checklist.bat also saves "Shopping list.txt" in your media folder - take it to the store or the library sale.
  - A title counts as "have" when a video's title (and year) matches it. If one is not recognised, press F3 and give it the
    normal name, or put the year in the file name:  Iron Man (2008).mp4 .
  - The lists are in  config\checklist.json  (Notepad). Add a movie like  {"title":"Blade","year":1998}  , or a series with its
    season sizes. "date":"2027-06-18" marks a title as not out yet. Lists were written from public release lists up to 2026;
    add newer titles as they come out.
  - It lists what you could look for; HERO TV does not download copyrighted titles.

MAKE IT YOURS
  Double-click  Personalize.bat : give your TV its own name (for example "Nick's Hero TV"), pick its main colour and the
  greeting under the name. It shows on the home menu, the help and checklist screens and the browser tab. Each channel's own
  colour and name are in channels.json. Press F5 in the TV window to see changes.

GETTING YOUR MOVIES AND SHOWS IN  (the easy ways)
  - A USB stick, external drive or folder full of videos?  Drag it onto  Import-Folder.bat  (or double-click it and paste the
    path). It copies every video into your Inbox (your originals are not touched) and files them onto channels by title.
  - A few files?  Drag them onto Add-Movies.bat (you pick the channel) or drop them in Inbox and run Sort-Movies.bat.
  - Free ones?  Get-Free-Movies.bat.
  - Your own DVDs and Blu-rays: copy-protected discs and streaming-service downloads (Netflix, Disney+, iTunes...) cannot be
    copied by HERO TV, and it will not try. Discs without copy protection, home videos and DRM-free purchases work as they are.

PUT YOUR VIDEOS IN
  Double-click  Open-Media-Folder.bat  (it is  C:\Users\<you>\hero-tv-media ). The top folder = which channel:

    hero-tv-media\
      MCU\Some Movie (2008).mp4
      DC\Another Movie (1978).mp4
      Marvel Television\Show Name\Show Name S01E02 Title.mp4

  Folder names for the built-in channels:  MCU, Marvel Television, Marvel Animation, X-Men, DC, Dragon Ball, South Park.
  Channels 4, 7, 8, 9 (Spider-Verse, Classics, Action, Comedy) work from tags - see README.md ("sidecar" files).
  Channel 10 (Hero Marathon) plays everything. Channel 14 (Free Movies) is filled by Get-Free-Movies.bat. Channels can be changed in  config\channels.json .
  Then double-click HERO-TV.bat again - it rescans every time you start it.
  Want a different folder (another drive)?  Set a Windows environment variable HEROTV_MEDIA to that folder.

TWO LANGUAGES / WRONG LANGUAGE  (Fix-Audio.bat)
  Some movies carry several sound tracks (for example Japanese and English). A web browser cannot switch between them
  while playing - it plays one, usually the first. To choose:  drag the video onto  Fix-Audio.bat . It lists the tracks
  ("1. Japanese  <- plays now", "2. English"), you type the number, and it makes a copy that plays that language. The
  picture is not re-encoded, so it takes seconds. Your original is kept in the hidden .originals folder.
  - Why-Isnt-It-Showing.bat now flags every video that has more than one sound track and says which one plays.
  - Subtitles that were inside the video are saved next to the new copy as .srt files (see SUBTITLES below).

SUBTITLES  (press C)
  While watching, press  C : subtitles come on in the first language available, press again for the next language, then off.
  HERO TV remembers your choice (for example English) and turns that language on by itself for the next video.
  Where they come from:
   - A subtitle file next to the video with the same name:  Movie (2008).srt ,  Movie (2008).en.srt ,  Movie (2008).spanish.vtt
   - Text subtitles stored inside the video (.mkv). They are read on the spot.
   - Not possible: picture-style subtitles (many Blu-ray and DVD rips). A browser cannot show those; HERO TV tells you so.
     Download a .srt for the movie and put it beside it, and C will find it.
  Fix-Audio.bat / Convert-Video.bat keep a video's text subtitles by saving them as .srt files beside the new copy.

BACKUP AND RESTORE  (your setup, not your videos)
  Double-click  Backup.bat . It saves one zip in  Documents\HERO TV Backups  with your channels and lists (channels.json,
  checklist, sort keywords), your station name and colours, favorites, resume points, what you have watched, and skip-intro
  settings. Copy it to a USB stick or a cloud folder now and then.
  New PC, or something went wrong?  Install HERO TV, point it at your videos, then double-click  Restore.bat  (it uses the newest
  backup, or drag a backup zip onto it). Your current channel files are kept next to the restored ones as *.before-restore.
  Favorites and resume points are matched by file name inside your media folder, so they come back as long as the videos are there.
  Your videos and their rename/tag files (.hero.json) live in your media folder - back that folder up like any other files.

HOME MENU AND EASIER CONTROLS
  Press  H  (or Esc while watching live TV) for the HOME MENU - big tiles you pick with the arrow keys and Enter:
    Live TV | Continue watching (one press resumes exactly where you stopped) | tonight's special programming
    (Movie Night, Saturday cartoons - it shows when it starts) | TV guide | Library and search | Favorites |
    Free movies | Weather | Sleep timer | Bigger text | Help.
  - SLEEP TIMER (S): press S to step through 30, 60, 90, 120 minutes, "end of this show", and off. When time is up the
    picture pauses with "Sleep timer finished"; press any key to carry on. A note appears one minute before.
  - UP NEXT: about a minute before a show ends, a small card shows what is coming next on that channel.
  - BIGGER TEXT (T): makes all the writing larger for reading from the couch. It is remembered.
  - HELP (?): a screen with the keys, and a plain-English check - how many videos can play, whether ffmpeg is found,
    and for any video being skipped, WHY and what to do (usually: drag it onto Convert-Video.bat).
  - SKIP INTRO / CREDITS (for shows, when you watch on demand - from the Library, or press R on live TV):
    when the intro ends, press J. Every episode of that show then jumps past the intro when you start it
    (it says "Skipped the intro" - press Left to go back). Press E where the credits begin, and from then on
    that show jumps out when its credits start. Shift+J / Shift+E turn them off. N skips the intro if you started
    partway in. Live channels keep their schedule, so they cannot skip.

FREE MOVIES AND SHOWS  (channel 14)
  Double-click  Get-Free-Movies.bat  and pick a list: classic cartoons (Superman, Popeye and friends), old sci-fi and
  horror, silent films, classic feature films, classic TV. It downloads a few titles from each (you choose how many) into
  a folder called "Free Movies" in your media folder. They are ordinary video files, so they play on channel 14 and in the
  Library like anything else, and you can delete any of them. Run it again any time for more - it skips what you have.
  - Only items the Internet Archive itself marks as PUBLIC DOMAIN are downloaded (it checks the item's own licence mark).
    It does not download anything else. A few lists may find little: many old films carry no licence mark and are skipped.
  - Each file is roughly 100-700 MB; it keeps 2 GB of your drive free, and stops if space runs low. If a download is cut
    off, run it again and it carries on.
  - The lists are in  config\free-sources.json  (open in Notepad): add your own Internet Archive search words.
    The public-domain check always applies.
  - Free ad-supported services (Pluto, Tubi, Roku Channel, YouTube...) cannot be added: they only play inside their own
    apps and websites, and HERO TV does not work around that.

WEATHER CHANNEL (13) AND LIVE ALERTS
  Double-click  Set-Weather-Location.bat  once, type your town, pick it from the list. Then restart HERO TV.
  Channel 13 shows current conditions, the next hours, 7 days, and active alerts. It needs an internet connection.
  Live alerts (US only, from the National Weather Service): when a WARNING or WATCH (tornado, severe thunderstorm,
  flood...) is issued for your location, a red crawl runs across the top of EVERY channel until it expires. Advisories
  are listed on channel 13 only. Checked every 2 minutes. Forecast data: Open-Meteo (free, no account needed).
  HERO TV is not an emergency alert system - keep your phone's emergency alerts on.

NEW LOOK, THUMBNAILS, FAVORITES
  - Every video gets a picture: HERO TV grabs a real frame from the video itself (about 18% in, past the studio logos).
    It happens in the background the first time - a big library can take a while, and the TV keeps working meanwhile.
    Until a picture exists you see a colored tile. Pictures are stored in %LOCALAPPDATA%\HeroTV (delete that folder's
    "-thumbs" folder to redo them).
  - Press L for the library: a grid of pictures. Press Tab to switch All / Continue watching / Favorites.
    Press F2 on a video to add or remove it from Favorites (a star shows on it).
  - Every channel has its own color (the "color" in config\channels.json - use any #rrggbb you like).

START WITHOUT THE BLACK WINDOW
  Double-click  Create-Desktop-Shortcut.bat  once. A "HERO TV" icon appears on your Desktop. Double-click it and the TV opens
  with no console window; closing the TV window turns HERO TV off by itself. If something is wrong it shows a message
  instead of failing silently (details are in %LOCALAPPDATA%\HeroTV\herotv.log). Do the first start with HERO-TV.bat so it
  can install what is missing.

AUTO-SORT BY TITLE
  Drop new movies into the "Inbox" folder inside your media folder (or loose in the media folder), then double-click
  Sort-Movies.bat. It shows where each one will go, asks to confirm, then files them (moves into the channel folder
  and writes the tag file). It also fixes sound/format problems on the way in (AC-3/DTS audio, .avi and similar are
  converted automatically; your original is kept in a hidden ".originals" folder). Movies it doesn't recognise are left alone - use Add-Movies.bat for those.
  The keyword list is  config\auto-sort.json  (open in Notepad): "spider man" -> channel 4, "batman" -> channel 6, etc.
  Movies dated (1979) or earlier also go to Superhero Classics. Add your own keywords any time.

SMART PROGRAMMING  (it learns what you have watched)
  - HERO TV remembers what you really watch: at least half of a show on a live channel, or playing it to the end from the library.
  - Channels then pass over what you have already seen while there is still something new. Shuffle channels stop repeating
    things you just watched, and in-order channels (Dragon Ball, South Park, MCU...) carry on with the next episode you have not seen.
  - Every time HERO TV starts, in-order channels pick up at the first episode you have not watched (what is on right now keeps playing).
  - Once everything on a channel has been seen it simply plays through again in the usual order.
  - Want a channel to ignore all this and play strictly in order every time?  Add  "smart":false  to its line in channels.json.
  - Movie Night: Hero Marathon (channel 10) plays only full-length movies on Friday and Saturday 7 to 11 pm.
    Build your own with these extra match rules (they work in a channel's "match" and in any block's "match"):
       "min_minutes":75        only videos at least 75 minutes long        "max_minutes":30     only short ones (episodes)
       "type":"movie"          only movies  (or "episode" for series episodes)
  - New videos: HERO TV checks your media folder about once a minute. Drop a movie in and, a minute or two after the copy
    finishes, it appears in the Library and on its channel with a small "Library updated" note. No restart or F5 needed.
    (Add-Movies.bat / Sort-Movies.bat still work the same.)
  - HERO TV remembers your last channel, volume and mute, and opens on them next time.

SHORT, CLEAN NAMES  (rename any video or show without touching its file)
  - HERO TV already tidies download-style file names: "Spider.Man.No.Way.Home.2021.1080p.BluRay.x264-GRP.mkv"
    shows as "Spider Man No Way Home" (2021). It tidies existing videos once, the first time you start this version.
  - To type your own name: press  F3  on a video  (in the Library, in the Guide on the highlighted show, or while watching).
    A box opens with the current name - type the new one, Enter saves, Esc cancels. Empty = back to the automatic name.
  - F4 renames the WHOLE SHOW (every episode of "Season 1" or "Dragon.Ball.Z.1080p" at once). Only for videos in a series.
  - The name is saved in a small file next to the video (same name, ending .hero.json), so it survives rescans and moving the
    folder. Your video file is never renamed or touched. If a channel's "match" uses "series", keep it in step with the new show name.

EDIT / ADD CHANNELS  (double-click Edit-Channels.bat, save with Ctrl+S, restart HERO TV)
  Each channel is one line in  config\channels.json , for example:
    {"id":"dragon-ball","number":11,"name":"Dragon Ball","mode":"sequential","match":{"franchise":["Dragon Ball"]},"description":"..."},
  - name : what the TV shows. Change it freely.
  - number : the channel number (must be unique).    id : internal name - keep it the same once created.
  - mode : "sequential" (in order) or "shuffle".
  - match : which videos belong. {"franchise":["Dragon Ball"]} = videos in a folder called "Dragon Ball".
            {"tags":["spider-verse"]} = videos tagged that way (Add-Movies.bat / Sort-Movies.bat do this for you).
  - also : extra videos that belong too. A video is on the channel if it fits "match" OR any "also" group. Example: Marvel
            Television is its folder PLUS Spider-Man shows:  "also":[{"tags":["spider-verse"],"type":"episode"}] .
            (Spider-Verse itself is only the movies:  "type":"movie","min_minutes":50 . Shows and anything under 50 minutes
            with the spider-verse tag go to Marvel Television.)
  To ADD a channel: copy a line, change id/number/name/match, and make sure every line except the last ends with a comma.
  To REMOVE one: delete its line. Then put matching keywords in  config\auto-sort.json  so Sort-Movies.bat can file into it.
  If you make a typo, HERO-TV.bat (or Check-Setup.bat) tells you which file and roughly where - nothing breaks.

SCHEDULED PROGRAMMING  (e.g. Saturday Morning Cartoons)
  A channel can switch to different shows at set times. Add a "blocks" part to its line in channels.json:
    "blocks":[{"name":"Saturday Morning Cartoons","days":["sat"],"from":"07:00","to":"12:00","mode":"shuffle",
               "match":{"franchise":["Marvel Animation","Dragon Ball","South Park"]}}]
  - days : mon tue wed thu fri sat sun   (or "weekdays", "weekends", "daily").      from / to : 24-hour clock, "07:00".
  - match : which videos play during the block (same style as a channel's match). Leave it out to use the channel's own.
  - The block starts on the dot: whatever was on at 7:00 is cut off, and the channel goes back to normal at 12:00
    (a show that is already running at 12:00 finishes first). Each block remembers where it stopped, so next Saturday
    carries on with the next episodes. If a block has no videos yet, the channel just plays normally.
  - The guide and the info banner show the block's name. Several blocks per channel are fine - separate them with commas.
  - Hero Marathon (channel 10) already has a Saturday Morning Cartoons block as an example.

SAVE DISK SPACE
  - Shrink-Library.bat : re-encodes your whole library to efficient standard H.264. It first shows how much it will save
    and asks. Each new file is checked (same length, really smaller, plays in a browser) before it replaces anything.
    Movies are kept at up to 1080p, episodes at up to 720p; cartoons/anime (Dragon Ball, South Park...) get extra savings.
    It is slow (roughly 15-40 min per movie, a few min per episode) - run it overnight. Running it again skips finished files.
  - Shrink-Video.bat : the same for just the files or folders you drag onto it.
  - Clean-Originals.bat : Convert, Sort and Shrink keep each original in a hidden ".originals" folder, so at first you use
    MORE space. Once you have checked the new versions, this deletes those originals (it shows the size and asks first;
    deleting is permanent). Shrink can also delete each original right away - it asks.
  - Why-Isnt-It-Showing.bat now ends with a storage line: library size and how much the originals take.
  - Bigger library than your drive? Put it on an external drive and double-click Choose-Media-Folder.bat to point
    HERO TV there (inside it: one folder per channel, as before). Keep the drive plugged in while watching.

KEYS
  Watching TV:   Up / Down = change channel     0-9 = type a channel number     Backspace = previous channel
                 G or Enter = guide     L or / = library and search     R = start the current show over (then you can skip)
                 F3 = rename this video     F4 = rename the whole show (also works in the Library and Guide)
                 I = what's on     M = mute     F = fullscreen     Left / Right = volume
                 H or Esc = home menu     S = sleep timer     T = bigger text     C = subtitles     D = details     O = settings     ? = help
  Guide:         arrows move, Enter tunes, G/Esc closes. The channel you are watching keeps playing in the top-right corner.
  On demand (anything played from the library, or after R):
                 Left / Right = back 10 s / forward 30 s     PgUp / PgDn = forward / back 5 min     0-9 = jump to 0%..90%
                 Space = pause     Up / Down = volume     Esc or Backspace = back to live TV
                 J = intro ends here     E = credits start here     N = skip intro (shows only)
                 With a mouse: move it to show the bar, then click or drag anywhere on the bar (it shows the time under the pointer).

SETTINGS AND MOUSE CONTROLS
  Settings: press O, choose Settings on the Home menu, or move the mouse and click Settings. Sections: Appearance (name,
  greeting, colour, bigger text), Media library (folder, automatic Inbox, check now), Weather, Cover art (TMDB key) and
  Backup and about (backup, log folder, versions). Nothing changes until you press Save; Esc warns about unsaved changes;
  anything that resets something asks you to press twice. A copy of the previous settings is kept as settings.json.bak.
  Mouse: move it over the picture and a row of buttons (Home, Guide, Library, Details, Settings, Full screen) appears at
  the bottom. Right-click a video in the Library or Guide for Play / Details / Favorite / Rename; right-click the TV
  picture for the main menu. Everything still works with the keyboard alone.

TOOLS (Settings > Tools) - instead of the .bat files
  Everything the helper .bat files do can now be done from Settings > Tools, and it runs in the background while you
  keep watching: download free movies, bring in a folder or USB drive, sort the Inbox, fix videos that are skipped,
  choose a video's sound language, delete saved originals to free space, install the video tools, check setup and
  make a desktop shortcut. Its messages show on the screen. The .bat files still work if you prefer them.

CHANGING CHANNELS WITHOUT NOTEPAD
  Settings (O) > Channels: click a channel to rename it, change its number, colour, play order (in order / shuffled),
  folder, description and KEYWORDS (words in a file name that send a new video to that channel). "Add a channel" makes a new
  channel and its folder; Delete removes a channel from the guide (never your videos). Changes show up straight away.
  Channels with special rules (Spider-Verse, tag channels, Hero Marathon...) keep those rules; only their name, number,
  colour, order, description and keywords are editable here. If a change cannot be used it is undone automatically, and the
  previous files are kept as channels.json.bak / auto-sort.json.bak. Editing config\channels.json by hand still works.

POSTERS, PLOTS, CAST AND RATINGS (optional, free)
  Press D on anything (F8 inside the Library) to see its poster, story, cast, rating and runtime. The pictures on the
  guide and library stay as screengrabs from the video itself. To fill in the details:
    1. Make a free account at  https://www.themoviedb.org/signup
    2. Open  https://www.themoviedb.org/settings/api  and ask for a personal (non-commercial) API key.
    3. Double-click  Set-Poster-Key.bat  and paste the key. Restart HERO TV.
  It then looks everything up quietly in the background (a big library takes a few minutes, and keeps working if the
  Internet drops). Only a video's TITLE and YEAR are sent to TMDB - never file names, folders or anything else.
  Your own picture always wins: put  Movie Name.jpg  next to a video (or  poster.jpg  in a show's folder).
  This product uses the TMDB API but is not endorsed or certified by TMDB.

MAKE IT A REAL APPLICATION (optional)
  Double-click  Build-App.bat  once. It needs Python and the Internet one time, and a few minutes. It makes
  HERO-TV.exe in this folder. After that HERO-TV.bat, the desktop shortcut (run Create-Desktop-Shortcut.bat again) and
  HERO-TV.exe itself start the TV without needing Python. Keep the whole folder together - the program, the "_internal"
  folder, "web", "config" and your data live side by side, so channels and settings stay easy to edit and back up.
  Windows may say "unknown publisher" the first time (the program is not code-signed): More info > Run anyway.
  ffmpeg is still needed for converting videos. Run Build-App.bat again after updating HERO TV's files.
  To undo: delete HERO-TV.exe and the "_internal" folder.

ADDING MOVIES HANDS-FREE (Inbox)
  While HERO TV is running, drop new videos into the  Inbox  folder (Open-Media-Folder.bat shows it). A minute after a file
  has finished copying, HERO TV files it onto the right channel by its title (the same keywords as Sort-Movies.bat),
  fixes its sound or format if needed, and it appears on its own - no restart. Videos whose title matches no keyword
  stay in the Inbox (Help shows how many): use Add-Movies.bat to choose their channel, or add a keyword in
  config\auto-sort.json. Only the Inbox is watched, never your channel folders. You can also just DRAG
  videos (or whole folders) from Explorer onto the TV window: they are copied into the Inbox for you. To switch this off, add
  "auto_inbox": false to settings.json in %LOCALAPPDATA%\HeroTV.

INSTALLING ON A NEW PC, SUBTITLE STYLE
  New PC: download  HERO-TV-Setup-v1.x.x.exe  from github.com/trentnick99/Hero-tv > Releases and run it. No administrator
  rights needed; it installs into your user folder, adds HERO TV to the Start menu (and the desktop if you tick it),
  and appears in Windows' "Installed apps" so it can be uninstalled normally. Uninstalling keeps your channel files,
  videos, favorites and settings. Windows may warn "unknown publisher" (not code-signed): More info > Run anyway.
  Updates still work the same way: download the release zip and run Update-HERO-TV.bat from the Start menu's
  "HERO TV tools folder".
  Subtitles: Settings > Appearance > Subtitles - size (normal / large / extra large), dark box or outline only, white
  or yellow. Applies on the TV and on paired phones. TV media players (Roku Media Player) also get the subtitles.

SEASONAL SPECIALS AND WEEKLY BACKUPS
  Hero Marathon runs "Halloween Horror Nights" every evening Oct 24-31 (your Thriller & Horror videos) and
  "Holiday Hero Specials" Dec 18-26 (videos tagged christmas or holiday). If you have nothing that fits, the
  channel plays as usual. Switch them off in Settings > Channels; the list lives in config\seasonal.json.
  A backup is made automatically once a week (the last 8 are kept in Documents\HERO TV Backups). Turn it off in
  Settings > Backup and about.

NEW IN YOUR LIBRARY, NEXT EPISODE, WINDOW MODE
  Home > "New in your library" and the library's New tab list what arrived in the last 30 days, newest first.
  Playing a show from the library? When an episode ends, the next one starts by itself after 10 seconds
  (Enter = start now, Esc = back to live TV). Settings > Appearance > "Open in a window instead of full screen".
  Moving or renaming videos in Windows, or converting them with HERO TV, keeps their favorite, resume point and
  watch history (as long as it is clearly the same video).

WATCHING ON YOUR PHONE OR TV (Settings > Other devices)
  Off until you switch it on. Then:
    1. On the PC: Settings (O) > Other devices > tick "Let other devices on my home WiFi watch". If Windows asks
       whether HERO TV may use the network, choose Allow for PRIVATE networks only.
    2. On the iPhone (same WiFi): open Safari and type the address shown, e.g.  http://192.168.1.20:8788
    3. On the PC press "Pair a device" and type the 6-digit code on the phone. Done - only once per device.
  The phone shows the same live channels as the PC, plus the guide and library. Tap the picture for buttons
  (channel up/down, guide, library). Turn the phone sideways for the full view. Phones can only WATCH: they cannot
  open Settings, Tools, the channel editor, rename or add files. Remove a device in Settings at any time.
  To the Roku TV: start a video on the iPhone, tap the AirPlay icon and pick the TV (on the TV first turn on
  Settings > Apple AirPlay and HomeKit). Or mirror the whole PC: Windows key + K, pick the TV.
  iPhones cannot play .mkv files: Settings > Tools > "Make iPhone-friendly copies" makes .mp4 copies (quick).
  Browse on the TV itself (Roku Media Player, VLC, a smart TV's "Media" app): Settings > Other devices >
  "Turn on TV media player browsing" (press twice to confirm). On the Roku open the free Roku Media Player
  channel and choose your station. Your folders, shows (in episode order) and new arrivals appear and play on the TV.
  IMPORTANT: this standard has no pairing - while it is on, ANY device on your WiFi can see and play your videos
  (nothing can be changed or deleted through it). Untick it when you are done if you share your WiFi.
  Note: on your WiFi the video is not encrypted - fine at home, do not switch this on on a public network.
  Something wrong? Untick the switch (everything stops at once), or go back to the previous version: download the
  older release from GitHub and run Update-HERO-TV.bat with it (it asks before installing an older version).

UPDATING HERO TV
  New versions are published on your GitHub page: github.com/trentnick99/Hero-tv > Releases. Each one is built and
  tested on a Windows PC first. Download  HERO-TV-v1.x.x-windows.zip  (leave it in Downloads), then double-click
  Update-HERO-TV.bat . It shows your version and the new one and asks first. HERO TV closes, the new HERO-TV.exe swaps
  itself in and starts again - no Python and no Build-App.bat needed. Your videos, favorites, resume points and any
  settings file you edited are kept (a changed settings file gets the new standard version beside it as  name.new ).
  Replaced files are copied to  .update-backup  first. After an update, the TV shows a short "What's new" once.
  Version shown in: Settings > Backup and about.
  New PC: unzip the release anywhere and double-click HERO-TV.exe.

EPISODE NAMES (anime too)
  "Show - 012 - Title.mp4", "Show Episode 12.mp4", "Show E012.mp4" and "Show S01E12.mp4" all work. Put a show's
  episodes in one folder inside its channel folder (Dragon Ball\Dragon Ball Z\...) and they play in order.

IF A VIDEO IS SKIPPED, HAS NO SOUND, OR HAS SOUND BUT NO PICTURE
  Browsers cannot play: AC-3 / DTS sound (very common in movie rips), .avi / old Xvid video, 10-bit H.264 (very common
  in anime rips - this is the classic "sound but black screen"), and HEVC / H.265 on many Windows PCs.
  HERO TV now spots these when it scans and skips them. Drag the file(s) onto  Convert-Video.bat  : sound-only problems
  take a minute; picture problems (10-bit, HEVC, avi) re-encode the video, which can take 15-40 minutes for a movie
  (leave the window open). You get a normal .mp4 and your original is kept in a hidden ".originals" folder.
  Sort-Movies.bat and Add-Movies.bat do the same thing automatically for new files.
  Not sure which file is the problem?  Double-click  Why-Isnt-It-Showing.bat : it lists every video with its exact format
  and says which ones are skipped and why. If a bad file slips through, the TV notices "sound but no picture", shows a
  message and skips it.
  Works as is: .mp4 .m4v .mkv .webm .mov with normal 8-bit H.264 (or VP9 / AV1) video and AAC / MP3 / Opus / FLAC sound.
  (If your PC does show HEVC fine, set the Windows environment variable HEROTV_ALLOW_HEVC=1 to stop converting it.)

IF SOMETHING GOES WRONG
  Double-click  Check-Setup.bat  - it lists what is OK, what is missing and how to fix it.
  - "ffprobe not found"          : let HERO-TV.bat install ffmpeg (winget), or see the manual steps it prints.
  - "No programming" on a channel: no playable video matches that channel's folder/tags. Check folder names above.
  - "Port 8787 is being used"    : close the other copy of HERO TV, or set HEROTV_PORT=8788.
  - Black screen / no sound       : click the picture once; run Why-Isnt-It-Showing.bat and convert any skipped file.

GOOD TO KNOW
  - Everything stays on your PC. The server only listens on this computer (127.0.0.1), nobody else on your network can reach it.
  - The schedule and your resume points are stored in  %LOCALAPPDATA%\HeroTV  (not in the program folder, so
    OneDrive cannot lock the database). Delete that folder to reset the guide.
  - Showtimes are generated for your own virtual channels - they are not real TV listings.
  - Times follow your Windows clock/timezone automatically.
  - Very long file paths (over ~250 characters) can fail on Windows; keep names reasonably short.
  - HERO TV plays videos you own and never unlocks or copies protected content. The only thing it ever downloads is the
    public-domain list when YOU run Get-Free-Movies.bat (plus weather data for channel 13).
  - Uses Microsoft Edge (already on Windows) or Chrome, in its own separate profile - your normal browser is untouched.
  - The Raspberry Pi files (scripts\*.sh) are for the Pi and are not needed on Windows.
