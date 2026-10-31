HERO TV on Windows 10 / 11
==========================

START IT
  New PC (easiest): download  HERO-TV-Setup-v1.x.x.exe  from github.com/trentnick99/Hero-tv > Releases and run it.
    No administrator rights needed. Windows may say "unknown publisher" (the app is not code-signed): More info >
    Run anyway. Tick "Put a HERO TV icon on the desktop". From then on: click the icon - the TV opens fullscreen.
  From the zip instead: right-click the zip > "Extract All...", extract it somewhere normal (Desktop or Documents) -
    never run it from inside the zip window - and double-click  HERO-TV.bat  (Windows may warn: More info > Run anyway).
  The first start checks the PC and offers to install what is missing (the free video tools, ffmpeg).
  HERO TV updates itself: Settings (O) > Backup and about > Install now when a new version is out.

With no videos yet it runs in DEMO MODE with made-up test clips so you can try the guide and channels.

WHERE THINGS GO  (the short version - there are only two places)
  1. THE PROGRAM FOLDER (where HERO TV is installed): the program and its settings. Never put videos here.
  2. YOUR MEDIA FOLDER: all your videos. Settings > Media library > Open media folder. Inside you will see:
       Inbox          <- NOT SURE where a video goes? Drop it here (or drag it onto the TV window): HERO TV files it
                         by itself. Ones it cannot place wait in Settings > Tools > Inbox, where you pick the channel.
       MCU, DC, X-Men, Dragon Ball, South Park, ...   <- one folder per channel. Know the channel? Put the video right in it.
       Free Movies    <- filled by Settings > Tools > Free movies. Leave it alone.
       WHERE THINGS GO.txt   <- this same cheat sheet, kept inside the folder
     (The hidden ".originals" folders are safe copies from fixes. Settings > Tools > Free up space deletes them.)
  The folders are created for you, empty ones do no harm, and nothing you already have is moved or changed.
  Everything else (schedule, resume points, settings) HERO TV keeps by itself in a hidden folder. You never touch it.

YOUR CHANNEL LINEUP  (and the folder each one reads)
   1  Marvel Movies      folder MCU                   10  Hero Marathon     everything, plus time-of-day and seasonal blocks
   2  Marvel Television  folder Marvel Television     11  Dragon Ball       folder Dragon Ball
   3  Marvel Animation   folder Marvel Animation      12  South Park        folder South Park
   4  Spider-Verse       Spider-Man MOVIES (tag)      13  Weather
   5  X-Men              folder X-Men                 14  Free Movies       Settings > Tools > Free movies
   6  DC Movies          folder DC                    15  Invincible        folder Invincible
   7-9 Classics / Action / Comedy (by tags)            16  Thriller & Horror folder Thriller & Horror (or tag thriller / horror)
                                                      17  For You           picked from what you watch
  Channels with nothing on them stay hidden, so only the ones you have filled show up. New videos are filed by smart
  sorting (with the free TMDB key) or by the keywords in Settings > Channels, where you can also rename, recolor,
  reorder, switch off or add channels.

  - Every channel has its own color (the "color" in config\channels.json - use any #rrggbb you like).

START WITHOUT THE BLACK WINDOW
  The Setup puts a HERO TV icon on the Desktop (or: Settings > Tools > Make a desktop shortcut). It opens the TV
  with no console window. Closing the TV window turns HERO TV off - unless Always on is switched on (Settings > Other
  devices), which keeps it running for the Roku app and phones. If something is wrong it shows a message instead of
  failing silently (details are in %LOCALAPPDATA%\HeroTV\herotv.log).

AUTO-SORT BY TITLE
  Drop new movies into the "Inbox" folder inside your media folder (or loose in the media folder), then double-click
  Sort-Movies.bat. It shows where each one will go, asks to confirm, then files them (moves into the channel folder
  and writes the tag file). It also fixes sound/format problems on the way in (AC-3/DTS audio, .avi and similar are
  converted automatically; your original is kept in a hidden ".originals" folder). Movies it doesn't recognize are left alone - use Add-Movies.bat for those.
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
  greeting, color, bigger text), Media library (folder, automatic Inbox, check now), Weather, Cover art (TMDB key) and
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
  Settings (O) > Channels: click a channel to rename it, change its number, color, play order (in order / shuffled),
  folder, description and KEYWORDS (words in a file name that send a new video to that channel). "Add a channel" makes a new
  channel and its folder; Delete removes a channel from the guide (never your videos). Changes show up straight away.
  Channels with special rules (Spider-Verse, tag channels, Hero Marathon...) keep those rules; only their name, number,
  color, order, description and keywords are editable here. If a change cannot be used it is undone automatically, and the
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

SMART SORTING (needs the free TMDB key from Settings > Cover art)
  New videos (dragged onto the TV, dropped in the Inbox, or Sort-Movies) are looked up on TMDB and filed by what they
  really are: the studio (Marvel Studios, Marvel Television, DC...), the genre (horror, animation, comedy) and the film
  series - not just by words in the file name. So "Iron Man (1931)" or "Logan Lucky" stay out of the Marvel channels,
  Spider-Man cartoons go to Marvel Television, and a thriller like Se7en goes to Thriller & Horror while The Dark
  Knight does not. Titles TMDB does not know (and everything, if you have no key) use the channel keywords as before.
  Settings > Channels shows which smart rules feed each channel and has the on/off switch; the rules themselves are in
  config\smart-sort.json.

FIXING WHERE A VIDEO WENT (and teaching HERO TV)
  On a video that is on the wrong channel: open its Details (D, or right-click > Details) and press M (or "Move to
  another channel"). Tick the channels it belongs on and press Save - the file (for a show: every episode, with its
  season folders, subtitles and poster) is moved into that channel's folder, and resume points and favorites stay.
  Videos HERO TV could not place wait in the Inbox: Settings > Tools > Inbox lists them with a channel picker and a
  "Put it here" button. With "Remember" ticked, HERO TV writes your choice to config\my-sorting.json, and from then on
  new episodes of that show (or other copies of that film) go there by themselves - before keywords and smart sorting.

FOR YOU, RELEASE ORDER AND TIME-OF-DAY TV
  Channel 17 "For You" picks from what you have been watching: the next episode of shows you are in the middle of,
  films you stopped half-way, then unwatched videos most like what you watched lately (genres, studios, film series
  from TMDB, and channel folders). With no history yet it shows what is new in your library. It re-plans itself
  (at most every half hour) after you watch something. Switch it off like any channel.
  Release order: with the TMDB key, films are ordered by their real release dates (Avengers: Age of Ultron before
  Ant-Man, both 2015), also when a file name has no year.
  Time-of-day programming (config\dayparts.json): Hero Marathon plays cartoons on weekend mornings (07:00-11:00),
  hero films in prime time (20:00-23:00) and Thriller & Horror late at night (23:00-02:00) - only from what you have.
  Seasonal specials and blocks you add yourself come first. On/off: Settings > Channels > Time-of-day programming.

REMINDERS
  In the TV guide (G), move to a later show and press R: it is marked "Reminder". When it starts, a card offers to
  switch - Enter to watch, Esc for not now. On the Roku: open the guide (OK), choose a later show and press OK (OK
  again removes it); when it starts the TV shows the reminder - OK to watch, Back for not now. Reminders are shared
  by the PC, phones and the Roku app, and clear themselves after the show.

TIME SLOTS, SEASONAL FOLDERS AND CARTOON SHORTS
  Settings > Channels > a channel > Time slots: during the hours you pick, the channel plays only what you choose -
  a folder or one show - for example "Saturdays 8:00 AM to 11:00 AM: Marvel Animation". Outside them it plays as
  usual. A slot can run past midnight. Remove one with its Remove button.
  Seasonal folders: put videos in a folder named after a month or holiday - for example MCU\December or
  Shorts\Halloween ("Christmas", "Holiday", "Thanksgiving" and "Valentines" work too) - and they only play on the
  channels in that month. They stay in the on-demand library all year.
  Cartoon Shorts (channel 18): your Shorts folder and the free classic cartoons, around the clock. It appears in the
  guide once there is something in it. If a channel ever has nothing it can show (for example only Christmas videos
  in March), it plays shorts instead of going blank.

PLAY ORDER AND THE CHANNEL LOGO
  Settings > Channels > a channel > Play order: "In order"; "Mixed shows, each in order" (shows take turns at
  random, but every show's episodes stay in order - good for channels with several shows); "Mixed shows, fair share"
  (the same, and a show with many episodes plays only its next few each round, so small shows get a fair turn);
  "Shuffled" (everything in a random order, episodes too).
  Settings > Appearance > Channel logo: the channel's number and name in the top corner of the picture, like a TV
  network's logo - now and then (when a show starts, after changing channel, and briefly every 5 minutes), always,
  or off. The Roku app follows the same setting.

CLEAN START TIMES AND SHORTS (like real TV)
  Settings > Channels > a channel > Start times: "On the quarter hour", "On the half hour" or "On the hour". Shows
  then start at clean times, and the gap before each one is filled with whole short cartoons - never cut off - from
  a folder called Shorts in your media folder (up to 15 minutes each; subfolders such as Shorts\Superhero are fine).
  Free classic cartoons from Tools > Free movies (for example Superhero-era cartoons) are used as well. Whatever is
  left (usually a minute or two) shows an "Up next" card with a picture and the name of the next show, on the PC,
  phones and the Roku app. With no shorts at all the card fills the whole gap, so quarter hours work best then.
  A channel can keep to some shorts only: add "filler": ["Superhero"] to it in config\channels.json (subfolder
  names or tags).
  "Breaks inside shows" (a tick box under Start times): part of that time becomes a break of shorts in the middle
  of each show - two in shows of 50 minutes or more - placed at a chapter mark of the video when there is one
  nearby, never in the first or last tenth. The guide still lists the show as one. Off unless you tick it.

ALWAYS ON (for the Roku app and phones)
  Settings > Other devices > Always on: "Start HERO TV when I sign in to Windows" puts a HERO TV shortcut in the
  Startup folder; it starts in the background with no window. "Keep HERO TV running when the TV window is closed" is
  on by default once a phone or the Roku TV is set up. If HERO TV stops with an error in the background, it starts
  itself again (up to 3 times in 10 minutes). Turn it off completely: Settings > Backup and about > Quit HERO TV.
  "Keep this PC awake so the TVs always find it" (on by default once a Roku TV is set up) stops Windows from going
  to sleep while HERO TV runs - the screen can still switch off. A TV cannot wake a sleeping PC. Even with it off,
  the PC stays awake while a TV or phone is playing something, and for 15 minutes after.

THE LOOK (Settings > Appearance > Look)
  Classic dark, Pure black (best on OLED TVs) or Retro cable (blue, like a 90s cable box) - on the TV screen, phones
  and the Roku app. The guide shows a still of the show you are on (for other channels and later shows) with a soft
  blurred copy behind it. Text uses Atkinson Hyperlegible (made by the Braille Institute to be easy to read) and
  titles and channel numbers Barlow Condensed; both are free fonts under the SIL Open Font License (web\fonts).

COMFORT: EVEN VOLUME, NIGHT MODE, SCREENSAVER, TV EDGE MARGIN (Settings > Appearance)
  Even volume: each video's loudness is measured once in the background (needs ffmpeg); quiet videos are turned up
  and loud ones down so everything plays at about the same volume, on the TV screen and phones. (The Roku app cannot
  change a video's volume - Roku TVs have their own "Volume leveling" in the TV's sound settings.)
  Night mode: between the times you choose, menus are dimmer and warmer, everything is a little quieter and loud
  bangs are evened out.
  Screensaver: when an on-demand video is paused for 3 minutes or a menu is left open for 5, pictures from your
  library drift across the screen; any key brings you back. Never during live TV.
  TV edge margin: moves menus in from the edges for TVs that cut them off (the picture is not changed).

SKIPPING INTROS AND CREDITS BY ITSELF
  HERO TV listens to the episodes of each show (in the background, a few at a time, at low priority) and finds the
  theme song and the credits they have in common. Watching on demand - on the PC, phones and the Roku app - the intro
  is skipped (Left / the left arrow goes back) and the credits go straight on to the next episode. Live channels are
  never skipped (they keep to the schedule). Points you set yourself with J (intro ends here) and E (credits start
  here) always win. Settings > Tools > Skip intros and credits by themselves shows the progress, has "Check
  everything now", and switches the background checking off. Needs ffmpeg.

LIVE TV IN OTHER APPS (Plex, Jellyfin, Emby, Channels, IPTV apps)
  Settings > Other devices > Live TV in other apps (needs "Let other devices watch" on, and ffmpeg). Off by default:
  when it is on, any app on your home network that knows the address can watch your channels (watch-only, no
  pairing), so it asks twice. It shows three addresses:
  - Channel list (M3U): add it as a playlist URL in IPTV apps such as TiviMate, IPTV Smarters or VLC.
  - TV guide (XMLTV): most IPTV apps find it by themselves; Plex/Jellyfin/Emby ask for it.
  - Tuner address: in Plex (Live TV & DVR > enter the HDHomeRun address manually), Jellyfin or Emby (Live TV >
    add a tuner: HDHomeRun) - your channels then show up as live TV with the guide.
  Each channel is one live stream that follows your schedule. Videos are sent as they are when the format allows
  (H.264/HEVC with AAC/AC-3 sound), otherwise converted on the fly, which uses more of the PC. "New addresses" makes
  a new private key (the old addresses stop working).

HERO TV ON YOUR ROKU TV (a real app on the TV)
  Once, on the TV: press Home 3 times, Up 2 times, then Right, Left, Right, Left, Right on the Roku remote. Choose
  "Enable installer and restart", agree, and pick a password. The TV restarts. (This is Roku's free developer mode.)
  On the PC: Settings > Other devices > HERO TV on your Roku TVs > Find my Roku TVs, choose it, type that password and
  press Install on the TV. The app arrives already linked to this PC (its own watch-only key, listed under Paired
  devices) and starts. On the TV: Up/Down = channel, OK = TV guide grid, Right = quick channel list, Replay (the
  curved arrow) = last channel, Rew = start the show over, Fwd = back to live, * = subtitles on/off, Back = leave.
  Left = ON DEMAND: your whole library in rows (Continue watching, Favorites, New, then one row per folder), a show
  is one tile that opens its episodes at the next one to watch, Search at the top. While watching on demand:
  Left/Right = 10 seconds, Rew/Fwd = 30 seconds, Replay = from the beginning, * = subtitles, Back = the library
  (Back again = live TV). Where you stop is remembered on every screen, the next episode starts by itself, and
  * in the library adds a video to your favorites.
  The Weather channel works on the TV too (the town is chosen in Settings > Weather on the PC).
  The PC must be on with HERO TV open. HERO TV updates the TV app by itself after HERO TV updates, or when this PC
  gets a new network address (the TV must be on). The password is kept in HERO TV's settings on this PC.
  More TVs: do the same on each Roku TV in the house - every TV gets its own key and can watch its own channel.
  A video a TV cannot play is skipped and the channel goes on with the next show.

PHONE WON'T CONNECT (keeps loading)
  Settings > Other devices > "Check the connection". It looks at Windows Firewall (a canceled "Allow access?" question
  leaves a block), whether Windows calls your home network Public, and whether the address belongs to a VPN. "Fix
  it" removes the block, lets HERO TV in on private networks only and marks your home network Private - Windows asks
  for permission first. A PC on a cable and a phone on WiFi is fine as long as both use the same router (not a guest
  WiFi; and the router's "AP/client isolation" must be off). Two routers (one plugged into the other, e.g. your own
  router behind the internet provider's) make two separate networks: the phone's WiFi IP address (iPhone: Settings >
  Wi-Fi > (i)) must start with the same three numbers as the PC's address. If not, plug the PC into the main router,
  put the phone on the second router's WiFi, or set the second router to Access Point / Bridge mode.

REPORT A PROBLEM (for help from Claude)
  Settings > Backup and about > Report a problem: type what happened (e.g. "on Home, Up moves sideways"), press Make a
  report, then Copy and paste it into your Claude chat. It contains the version, Windows version, settings (keys and
  tokens hidden, your user folder shown as <home>), library and channel counts, the network check, script errors on
  the TV screen and the last lines of the log. Nothing is sent anywhere by HERO TV; a copy is kept in the reports
  folder (Open reports folder).

CHOOSING YOUR CHANNELS
  The first time HERO TV starts it shows "Pick your channels": every starter channel (Marvel, Spider-Verse, X-Men, DC,
  South Park, Dragon Ball, Thriller & Horror...) is on - tap the ones you do not want, then Done. Later: Settings >
  Channels > "Choose your channels...", or open one channel and press "Switch this channel off". A channel that is off
  disappears from the guide and gets no new videos, but nothing is deleted - switch it back on any time.

A NEW CHANNEL FOR A NEW KIND OF SHOW
  Drop a show (or a folder of episodes) into the Inbox. If no channel fits, Settings > Tools > Inbox lists it once,
  with how many videos it has. Choose "+ New channel for these..." in its list, check the name, and press "Make the
  channel": the channel is created, every episode moves into its folder, and with Remember ticked new episodes of
  that show go there by themselves. New episodes of a show you already have always follow it to its channel.

MISSING EPISODES AND DUPLICATES (Settings > Tools)
  "Check my shows" compares every show with TMDB's list of aired episodes (needs the TMDB key); a show's Details
  screen says the same for that show. "The same video twice" lists films/episodes you have more than once; "Set
  aside" moves the extra copy into the hidden .originals folder, and "Free up space" deletes those for good.

INSTALLING ON A NEW PC, SUBTITLE STYLE
  New PC: download  HERO-TV-Setup-v1.x.x.exe  from github.com/trentnick99/Hero-tv > Releases and run it. No administrator
  rights needed; it installs into your user folder, adds HERO TV to the Start menu (and the desktop if you tick it),
  and appears in Windows' "Installed apps" so it can be uninstalled normally. Uninstalling keeps your channel files,
  videos, favorites and settings. Windows may warn "unknown publisher" (not code-signed): More info > Run anyway.
  Updates: HERO TV offers them by itself (see UPDATING HERO TV), or download the release zip and run Update-HERO-TV.bat from the Start menu's
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
    2. On the iPhone (same WiFi): open the Camera and point it at the QR code shown on the PC, then tap the link
       (or type the address shown into Safari, e.g.  http://192.168.1.20:8788 )
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
  From 1.11 on, HERO TV looks for a new version every few hours and tells you when one is ready. Open Settings (O) >
  Backup and about and press "Install now": it downloads the update from github.com/trentnick99/Hero-tv > Releases,
  closes for a moment, puts the new version in place and starts again by itself. Your videos, favorites, resume
  points and any settings file you edited are kept (a changed settings file gets the new standard version beside it
  as  name.new ). Replaced files are copied to  .update-backup  first. If an update ever fails, the version you had
  starts again and says so. After an update, the TV shows a short "What's new" once.
  The automatic look can be switched off in Settings > Backup and about.
  By hand (older versions, or no Internet on the PC): download  HERO-TV-v1.x.x-windows.zip  (leave it in Downloads),
  then double-click Update-HERO-TV.bat . Version shown in: Settings > Backup and about.

EPISODE NAMES (anime too)
  "Show - 012 - Title.mp4", "Show Episode 12.mp4", "Show E012.mp4" and "Show S01E12.mp4" all work. Put a show's
  episodes in one folder inside its channel folder (Dragon Ball\Dragon Ball Z\...) and they play in order.

ONE CARD PER SHOW IN THE LIBRARY (1.36)
  The Library's All list shows each TV show as one stacked card with an episode count. Enter opens it to show its episodes in order;
    Esc or Backspace goes back to where you were. Shows with the same name in different folders stay separate. Movies are unchanged.

  1.36.1: 'Invincible' and 'Invincible season 1' count as one show. A folder of episodes without numbers (Dragon Ball) is one card; folders of dated movies stay a plain list.

ENGLISH BY ITSELF FOR VIDEOS WITH SEVERAL LANGUAGES (1.35)
  Settings > Tools > 'Preferred sound language' (English to start with). A video that has an English sound track but plays
  another language first gets a hidden ready-to-play copy that plays English; the PC, phones and Roku use it. Your own files
  are never changed and nothing is deleted. The copies count toward the space limit. Choose Off to switch this off.

FINISH SETTING UP, AND SMOOTHER SCREENS (1.34)
  While something is still missing (videos added, video tools installed, videos playable), the Home screen has a 'Finish setting up'
  tile that takes you to the right place; it disappears when everything is done. Screens fade in, the info bar slides up
  (both off if your system asks for less motion), and the Library remembers its last tab.

WHEN A TOOL HAS PROBLEMS, IT SAYS WHY (1.33)
  After a tool in Settings > Tools finishes with problems, each video that did not work is listed with a plain-words reason,
  and Try again runs the same tool once more. 'Show the full log' has the technical details.

SETTINGS IS EASIER TO FIND YOUR WAY AROUND (1.32)
  A 'Needs a look' box at the top of Settings lists what wants your attention (an update, videos that cannot play,
  videos waiting in the Inbox) with an Open button for each. Settings > Tools is folded into four sections - press
  Enter on a section name to open or close it. Nothing is deleted by any of this.

SEE HOW FAR NEW VIDEOS ARE (1.31)
  Settings > Tools > 'New videos: how far along' shows every movie that arrives in the Inbox while HERO TV checks it,
  fixes its picture or sound, and sorts it onto its channel - with a progress bar, how many are still waiting, and how
  many ready-to-play copies are done. It updates by itself. It only shows progress; it never deletes anything.

VIDEOS IN OTHER FORMATS PREPARE THEMSELVES (1.30)
  Movies with Dolby (AC-3) or DTS sound, and H.265 inside an .mkv file, no longer need fixing by hand. HERO TV makes a
  hidden ready-to-play copy of each one in the hidden .prepared folder inside your media folder, one at a time in the
  background (the picture is copied, so it is quick; only the sound is converted). A video joins the channels when its
  copy is ready. Your own files are never changed or moved. Settings > Tools > Videos in other formats shows the
  progress and the space used. It can switch copying off, delete the copies (they are simply made again if needed) or set
  a space limit: when the copies reach it, HERO TV only stops making NEW ones - it never deletes anything by itself.
  A Roku TV plays the originals directly, so those movies show up in On Demand on the Roku at once; if a Roku ever
  refuses one, it tries the ready copy by itself. Only pictures that really cannot be shown (10-bit H.264, avi) still
  need Fix, below.

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
  Press ? on the TV: the help screen says what is wrong and how to fix it. Settings > Tools > Check setup lists what is
  OK and what is missing. Still stuck? Settings > Backup and about > Report a problem: type what happened, press Make a
  report, then Copy and paste it into your Claude chat.
  - "ffprobe not found"          : Settings > Tools > Install video tools.
  - "No programming" on a channel: no playable video matches that channel's folder/tags. Check folder names above.
  - "Port 8787 is being used"    : another copy of HERO TV is running - Settings > Backup and about > Quit HERO TV,
                                   then start it again.
  - Black screen / no sound       : click the picture once; Settings > Tools lists skipped videos with a Fix button.
  - Phone or Roku cannot connect : Settings > Other devices > Check the connection.

GOOD TO KNOW
  - Everything stays on your PC. HERO TV only listens on this computer (127.0.0.1) - unless you switch on Other devices
    (phones, laptops and the Roku app: paired once, watch-only) or the TV media server (no pairing, off by default).
  - The schedule and your resume points are stored in  %LOCALAPPDATA%\HeroTV  (not in the program folder, so
    OneDrive cannot lock the database). Delete that folder to reset the guide.
  - Showtimes are generated for your own virtual channels - they are not real TV listings.
  - Times follow your Windows clock/timezone automatically.
  - Very long file paths (over ~250 characters) can fail on Windows; keep names reasonably short.
  - HERO TV plays videos you own and never unlocks or copies protected content. It only goes online for: weather
    (channel 13), cover art and smart sorting (TMDB, with your key), public-domain free movies when YOU ask, and
    checking GitHub for HERO TV updates (can be switched off).
  - Uses Microsoft Edge (already on Windows) or Chrome, in its own separate profile - your normal browser is untouched.
  - The Raspberry Pi files (scripts\*.sh) are for the Pi and are not needed on Windows.
