' HERO TV for Roku: live channels and the whole library on demand, from HERO TV on the PC.
' Up/Down change channel, OK opens the TV guide, Right the channel list, Left the on-demand library, Replay the last
' channel, Rew starts the show over, Fwd goes back to live, * turns subtitles on/off, Back leaves the guide (or the app).
' On demand: Left/Right skip 10 seconds, Rew/Fwd 30 seconds, Replay starts again, Back returns to the library.

sub init()
    m.cfg = HeroConfig()
    m.tasks = []
    m.channels = []
    m.current = -1
    m.seq = 0
    m.slot = invalid
    m.afterFinish = false
    m.failed = false
    m.subIndex = -1
    m.errors = 0
    m.failedIds = {}

    m.video = m.top.findNode("video")
    m.banner = m.top.findNode("banner")
    m.guide = m.top.findNode("guide")
    m.list = m.top.findNode("list")
    m.msgBox = m.top.findNode("msgBox")
    m.msg = m.top.findNode("msg")
    m.grid = m.top.findNode("grid")
    m.tg = m.top.findNode("tg")
    m.prev = -1
    m.gridCi = -1
    m.gridProg = invalid
    m.selClock = invalid
    m.top.findNode("tgStation").text = m.cfg.station + "  -  TV guide"
    m.bannerTimer = m.top.findNode("bannerTimer")
    m.refreshTimer = m.top.findNode("refreshTimer")
    m.seenTimer = m.top.findNode("seenTimer")

    accent = hexColor(m.cfg.color, "#ffcf1f")
    m.top.findNode("bnBar").color = accent
    m.top.findNode("gStation").text = m.cfg.station

    m.video.observeField("state", "onVideoState")
    m.list.observeField("itemFocused", "onListFocus")
    m.list.observeField("itemSelected", "onListSelect")
    m.tg.observeField("programSelected", "onGridSelect")
    m.tg.observeField("channelSelected", "onGridSelect")
    m.tg.observeField("programFocusedDetails", "onGridFocus")
    m.bannerTimer.observeField("fire", "hideBanner")
    m.refreshTimer.observeField("fire", "refreshChannels")
    m.seenTimer.observeField("fire", "reportSeen")
    m.refreshTimer.control = "start"
    m.seenTimer.control = "start"
    m.skew = 0
    m.live = true
    m.nextSlot = invalid
    m.upShown = ""
    m.remKeys = {}
    m.remShown = {}
    m.remDue = invalid
    m.upNext = m.top.findNode("upNext")
    m.remBox = m.top.findNode("remBox")
    m.top.findNode("unBar").color = accent
    m.top.findNode("rmBar").color = accent
    m.tickTimer = m.top.findNode("tickTimer")
    m.tickTimer.observeField("fire", "onTick")
    m.tickTimer.control = "start"
    m.remTimer = m.top.findNode("remTimer")
    m.remTimer.observeField("fire", "pollReminders")
    m.remTimer.control = "start"
    m.top.findNode("remHide").observeField("fire", "hideReminder")

    ' on demand
    m.mode = "live"                                    ' live, weather or vod
    m.vod = invalid
    m.lib = m.top.findNode("lib")
    m.rows = m.top.findNode("rows")
    m.eps = m.top.findNode("eps")
    m.epList = m.top.findNode("epList")
    m.libRows = []
    m.libResults = invalid
    m.libData = []
    m.epData = []
    m.epShowTile = invalid
    m.searchDlg = invalid
    m.top.findNode("libBar").color = accent
    m.rows.observeField("rowItemFocused", "onLibFocus")
    m.rows.observeField("rowItemSelected", "onLibSelect")
    m.epList.observeField("itemFocused", "onEpFocus")
    m.epList.observeField("itemSelected", "onEpSelect")

    ' the Weather channel
    m.wx = m.top.findNode("wx")
    m.wxTimer = m.top.findNode("wxTimer")
    m.wxTimer.observeField("fire", "loadWeather")
    m.wxHours = []
    m.wxDays = []
    for i = 0 to 9
        l = m.top.findNode("wxHours").createChild("Label")
        l.translation = [i * 168, 0]
        l.width = 160
        l.horizAlign = "center"
        l.wrap = true
        l.font = "font:SmallSystemFont"
        l.color = "0xFFFFFFFF"
        m.wxHours.push(l)
    end for
    for i = 0 to 6
        l = m.top.findNode("wxDays").createChild("Label")
        l.translation = [i * 240, 0]
        l.width = 230
        l.horizAlign = "center"
        l.wrap = true
        l.font = "font:SmallSystemFont"
        l.color = "0xFFFFFFFF"
        m.wxDays.push(l)
    end for

    m.top.setFocus(true)
    loadChannels()
end sub

' ---------- talking to HERO TV ----------
function api(path as string, callback as string, method = "GET" as string, body = "" as string) as object
    t = CreateObject("roSGNode", "ApiTask")
    t.path = path
    t.method = method
    t.body = body
    t.tag = m.seq.ToStr()
    t.observeField("done", callback)
    m.tasks.push(t)
    t.control = "RUN"
    return t
end function

sub dropTask(t as object)
    keep = []
    for each x in m.tasks
        if not x.isSameNode(t) then keep.push(x)
    end for
    m.tasks = keep
end sub

' ---------- the channel list ----------
sub loadChannels()
    showMsg("Connecting to " + m.cfg.station + "...")
    api("/api/channels", "onChannels")
end sub

sub refreshChannels()
    ' not while you scroll the channel list (it would jump back to the top)
    if m.channels.count() > 0 and not m.guide.visible then api("/api/channels", "onChannels")
end sub

sub onChannels(event as object)
    t = event.getRoSGNode()
    dropTask(t)
    if t.error <> ""
        if m.channels.count() = 0
            m.failed = true
            showMsg(t.error + Chr(10) + Chr(10) + "Press OK to try again.")
        end if
        return
    end if
    m.failed = false
    keepId = ""
    if m.current >= 0 and m.current < m.channels.count() then keepId = m.channels[m.current].id
    fresh = []
    all = t.result.channels
    if isArr(all)
        for each c in all
            if isAA(c) and not isTrue(c.empty) then fresh.push(c)       ' the Weather channel too
        end for
    end if
    m.channels = fresh
    if fresh.count() = 0
        showMsg("No channels have anything to show yet." + Chr(10) + "Add videos to HERO TV on the PC.")
        return
    end if
    fillList()
    if keepId <> ""
        m.current = indexOf(keepId)
        if m.current < 0 then m.current = 0
        return                                   ' a refresh: keep watching
    end if
    hideMsg()
    start = indexOf(regRead("lastChannel"))
    if start < 0 then start = 0
    tune(start)
end sub

function indexOf(id as string) as integer
    for i = 0 to m.channels.count() - 1
        if m.channels[i].id = id then return i
    end for
    return -1
end function

sub fillList()
    content = CreateObject("roSGNode", "ContentNode")
    for each c in m.channels
        item = content.createChild("ContentNode")
        line = txt(c.number) + "   " + txt(c.name)
        if isAA(c.now) then line = line + "   -   " + txt(c.now.title)
        if c.kind = "weather" then line = line + "   -   local forecast"
        item.title = line
    end for
    m.list.content = content
end sub

' ---------- tuning ----------
sub tune(idx as integer)
    n = m.channels.count()
    if n = 0 then return
    if idx < 0 then idx = n - 1
    if idx >= n then idx = 0
    if m.current >= 0 and m.current <> idx then m.prev = m.current
    m.current = idx
    m.seq = m.seq + 1
    m.afterFinish = false
    m.errors = 0
    leaveVod()
    m.lib.visible = false
    m.eps.visible = false
    m.top.setFocus(true)
    ch = m.channels[idx]
    regWrite("lastChannel", ch.id)
    if ch.kind = "weather"
        m.mode = "weather"
        m.slot = invalid
        m.nextSlot = invalid
        m.upNext.visible = false
        m.video.control = "stop"
        hideMsg()
        m.wx.visible = true
        showBanner(ch, invalid)
        loadWeather()
        m.wxTimer.control = "start"
        return
    end if
    m.mode = "live"
    m.wx.visible = false
    m.wxTimer.control = "stop"
    showBanner(ch, invalid)
    api("/api/tv/" + ch.id, "onNow")
end sub

sub onNow(event as object)
    t = event.getRoSGNode()
    dropTask(t)
    if t.tag <> m.seq.ToStr() then return             ' you already flipped to another channel
    if t.error <> ""
        showMsg(t.error)
        return
    end if
    r = t.result
    slot = r.slot
    offset = num(r.offset)
    if m.afterFinish and isAA(slot) and isAA(m.slot) and num(slot.start) = num(m.slot.start) and isAA(r.next)
        slot = r.next                                  ' the video ended a little early: go straight on
        offset = 0
    end if
    if isAA(slot) and m.failedIds.DoesExist(txt(slot.media_id)) and isAA(r.next)
        slot = r.next                                  ' this TV could not play it before: on to the next show
        offset = 0
    end if
    m.afterFinish = false
    m.skew = num(r.now) - CreateObject("roDateTime").AsSeconds()
    m.nextSlot = r.next
    m.live = true
    m.upNext.visible = false
    if not isAA(slot)
        showMsg("Nothing is on this channel right now.")
        return
    end if
    hideMsg()
    showBanner(m.channels[m.current], r)
    play(slot, offset)
end sub

sub play(slot as object, offset as integer)
    ext = "mp4"
    if isStr(slot.ext) and slot.ext <> "" then ext = LCase(slot.ext)
    fmt = "mp4"
    if ext = "mkv" or ext = "webm" then fmt = "mkv"
    c = CreateObject("roSGNode", "ContentNode")
    c.url = m.cfg.server + "/media/" + txt(slot.media_id) + "." + ext + "?k=" + m.cfg.mk
    c.streamFormat = fmt
    c.title = txt(slot.title)
    if offset > 5 then c.playStart = offset
    tracks = []
    if isArr(slot.subs)
        for each s in slot.subs
            if isAA(s)
                tracks.push({ Language: txt(s.language), Description: txt(s.label), TrackName: m.cfg.server + txt(s.url) + "?k=" + m.cfg.mk })
            end if
        end for
    end if
    if tracks.count() > 0 then c.subtitleTracks = tracks
    m.slot = slot
    m.subIndex = -1
    m.video.content = c
    m.video.control = "play"
end sub

sub onVideoState()
    s = m.video.state
    if m.mode = "vod"
        onVodState(s)
        return
    end if
    if s = "finished"
        m.afterFinish = true
        m.seq = m.seq + 1
        if m.current >= 0 then api("/api/tv/" + m.channels[m.current].id, "onNow")
    else if s = "error"
        ' like real TV: skip what this TV cannot play and go on with the next show
        m.errors = m.errors + 1
        title = ""
        if isAA(m.slot)
            title = txt(m.slot.title)
            m.failedIds[txt(m.slot.media_id)] = true
        end if
        if m.errors >= 3
            showMsg("Several videos on this channel cannot play on this TV (" + m.video.errorMsg + ")." + Chr(10) + "Change channel. On the PC, Settings > Tools > iPhone-friendly copies makes versions that play here.")
            return
        end if
        showMsg("This TV cannot play " + title + "." + Chr(10) + "Going on with the next show...")
        m.afterFinish = true
        m.seq = m.seq + 1
        if m.current >= 0 then api("/api/tv/" + m.channels[m.current].id, "onNow")
    else if s = "playing"
        m.errors = 0
        hideMsg()
    end if
end sub

' tell HERO TV what you watch, so For You and 'continue watching' learn from the TV too
sub reportSeen()
    if m.video.state = "playing" and isAA(m.slot)
        api("/api/seen", "onQuiet", "POST", FormatJson({ media_id: num(m.slot.media_id), secs: 30 }))
        if m.mode = "vod" then saveVod(false)
    end if
end sub

sub onQuiet(event as object)
    dropTask(event.getRoSGNode())
end sub

' ---------- subtitles (*) ----------
sub cycleSubs()
    c = m.video.content
    if c = invalid or m.mode = "weather" then return
    tr = c.subtitleTracks
    if not isArr(tr) or tr.count() = 0
        flash("No subtitles for this video")
        return
    end if
    m.subIndex = m.subIndex + 1
    if m.subIndex >= tr.count()
        m.subIndex = -1
        m.video.globalCaptionMode = "Off"
        flash("Subtitles off")
        return
    end if
    m.video.subtitleTrack = tr[m.subIndex].TrackName
    m.video.globalCaptionMode = "On"
    flash("Subtitles: " + tr[m.subIndex].Description)
end sub

' ---------- start over / back to live / last channel ----------
sub startOver()
    if not isAA(m.slot) then return
    m.seq = m.seq + 1
    m.live = false
    m.upNext.visible = false
    play(m.slot, 0)
    flash("From the start  -  press Fwd to go back to live")
end sub

sub backToLive()
    if m.current >= 0 then tune(m.current)
end sub

sub lastChannel()
    if m.prev >= 0 and m.prev < m.channels.count()
        tune(m.prev)
    else
        flash("No previous channel yet")
    end if
end sub

' ---------- the TV guide grid (OK) ----------
sub showGrid()
    if m.channels.count() = 0 then return
    m.banner.visible = false
    m.grid.visible = true
    m.top.findNode("tgTitle").text = "Loading the guide..."
    m.top.findNode("tgTime").text = ""
    now = CreateObject("roDateTime").AsSeconds()
    m.gridFrom = now - (now mod 1800)
    api("/api/guide?hours=12&from=" + m.gridFrom.ToStr(), "onGuide")
    pollReminders()
end sub

sub hideGrid()
    m.grid.visible = false
    m.top.setFocus(true)
end sub

sub onGuide(event as object)
    t = event.getRoSGNode()
    dropTask(t)
    if not m.grid.visible then return
    if t.error <> ""
        m.top.findNode("tgTitle").text = t.error
        return
    end if
    byId = {}
    if isArr(t.result.channels)
        for each g in t.result.channels
            if isAA(g) then byId[txt(g.id)] = g
        end for
    end if
    root = CreateObject("roSGNode", "ContentNode")
    for each c in m.channels
        row = root.createChild("ContentNode")
        row.title = txt(c.number) + "  " + txt(c.name)
        g = byId[c.id]
        if c.kind = "weather"
            ' no shows on the Weather channel: one long block instead of "No Data Available"
            p = row.createChild("ContentNode")
            p.title = "Local forecast and weather alerts"
            p.playStart = num(t.result.from)
            p.playDuration = num(t.result["to"]) - num(t.result.from)
            p.description = "All day"
        else if isAA(g) and isArr(g.slots)
            for each sl in g.slots
                if isAA(sl)
                    p = row.createChild("ContentNode")
                    p.title = txt(sl.title)
                    p.playStart = num(sl.start)
                    p.playDuration = num(sl["end"]) - num(sl.start)
                    p.description = clock(sl.start_local) + " - " + clock(sl.end_local)
                end if
            end for
        end if
    end for
    m.tg.contentStartTime = num(t.result.from) - (num(t.result.from) mod 1800)
    m.tg.content = root
    if m.current >= 0 then m.tg.jumpToChannel = m.current
    m.tg.setFocus(true)
    m.top.findNode("tgClock").text = clock(nowIso())
    if m.current >= 0
        ' what is on now on your channel (the grid only reports focus once you move)
        cur = invalid
        rowNode = root.getChild(m.current)
        now = serverNow()
        if rowNode <> invalid
            for k = 0 to rowNode.getChildCount() - 1
                p = rowNode.getChild(k)
                if p.playStart <= now and p.playStart + p.playDuration > now then cur = p
            end for
        end if
        m.gridCi = m.current
        m.gridProg = cur
        showGridInfo(m.channels[m.current], cur)
    end if
end sub

function nowIso() as string
    d = CreateObject("roDateTime")
    d.ToLocalTime()
    return d.ToISOString()
end function

sub onGridFocus()
    d = m.tg.programFocusedDetails
    if not isAA(d) then return
    ci = num(d.focusChannelIndex)
    if ci < 0 or ci >= m.channels.count() then return
    m.gridCi = ci
    m.gridProg = d.content
    showGridInfo(m.channels[ci], d.content)
end sub

function serverNow() as integer
    return CreateObject("roDateTime").AsSeconds() + m.skew
end function

sub showGridInfo(ch as object, prog as dynamic)
    title = txt(ch.name)
    times = "Channel " + txt(ch.number)
    if prog <> invalid
        title = prog.title
        times = prog.description + "   on " + txt(ch.number) + " " + txt(ch.name)
        if m.remKeys.DoesExist(ch.id + ":" + num(prog.playStart).ToStr()) then times = times + "   -   REMINDER SET (OK removes it)"
    end if
    m.top.findNode("tgTitle").text = title
    m.top.findNode("tgTime").text = times
end sub

sub onGridSelect()
    ' one OK can arrive twice (program and channel): act once
    if m.selClock = invalid
        m.selClock = CreateObject("roTimespan")
    else if m.selClock.TotalMilliseconds() < 500
        return
    end if
    m.selClock.Mark()
    i = m.tg.channelFocused
    prog = m.gridProg
    if m.gridCi <> i then prog = invalid                ' focus details from another row
    if prog <> invalid and i >= 0 and i < m.channels.count() and num(prog.playStart) > serverNow() + 60
        ' a later show: set (or clear) a reminder instead of switching
        ch = m.channels[i]
        k = ch.id + ":" + num(prog.playStart).ToStr()
        op = "add"
        if m.remKeys.DoesExist(k) then op = "remove"
        api("/api/reminders", "onReminders", "POST", FormatJson({ op: op, channel: ch.id, start: num(prog.playStart) }))
        if op = "add"
            m.remKeys[k] = true
            m.top.findNode("tgTime").text = "Reminder set: " + prog.title + "  -  " + prog.description
        else
            m.remKeys.Delete(k)
            m.top.findNode("tgTime").text = "Reminder removed"
        end if
        return
    end if
    hideGrid()
    if i >= 0 and i < m.channels.count()
        if i <> m.current then tune(i) else showBanner(m.channels[m.current], invalid)
    end if
end sub

' ---------- reminders and "up next" ----------
sub pollReminders()
    api("/api/reminders", "onReminders")
end sub

sub onReminders(event as object)
    t = event.getRoSGNode()
    dropTask(t)
    if t.error <> "" then return
    r = t.result
    keys = {}
    if isArr(r.reminders)
        for each x in r.reminders
            if isAA(x) then keys[txt(x.channel) + ":" + num(x.start).ToStr()] = true
        end for
    end if
    m.remKeys = keys
    if not isArr(r.due) then return
    for each d in r.due
        if isAA(d)
            k = txt(d.channel) + ":" + num(d.start).ToStr()
            watching = false
            if m.live and m.current >= 0 and m.current < m.channels.count()
                if m.channels[m.current].id = txt(d.channel) then watching = true
            end if
            if not m.remShown.DoesExist(k) and not watching and not m.grid.visible and not m.lib.visible and not m.eps.visible
                m.remShown[k] = true
                m.remDue = d
                m.top.findNode("rmTitle").text = txt(d.title)
                m.top.findNode("rmWhere").text = txt(d.number) + " " + txt(d.channel_name)
                m.remBox.visible = true
                hideTimer = m.top.findNode("remHide")
                hideTimer.control = "stop"
                hideTimer.control = "start"
                return
            end if
        end if
    end for
end sub

sub hideReminder()
    m.remBox.visible = false
    m.remDue = invalid
end sub

sub watchReminder()
    d = m.remDue
    hideReminder()
    if not isAA(d) then return
    i = indexOf(txt(d.channel))
    if i < 0
        flash("That channel is not on the TV right now")
        return
    end if
    tune(i)
end sub

' every few seconds: the "up next" card in the last minute of a show
sub onTick()
    if not m.live or not isAA(m.slot) or not isAA(m.nextSlot) or m.grid.visible or m.guide.visible
        m.upNext.visible = false
        return
    end if
    left = num(m.slot["end"]) - serverNow()
    if left > 0 and left <= 60
        k = txt(m.nextSlot.media_id) + ":" + txt(m.nextSlot.start)
        if m.upShown <> k
            m.upShown = k
            ch = m.channels[m.current]
            m.top.findNode("unHead").text = "UP NEXT ON " + UCase(txt(ch.name))
            m.top.findNode("unTitle").text = txt(m.nextSlot.title)
            m.top.findNode("unTime").text = "at " + clock(m.nextSlot.start_local)
        end if
        m.upNext.visible = true
    else
        m.upNext.visible = false
    end if
end sub

' ---------- banner, list and messages ----------
sub showBanner(ch as object, r as dynamic)
    m.top.findNode("bnNum").text = txt(ch.number)
    m.top.findNode("bnChan").text = txt(ch.name)
    title = ""
    times = ""
    nxt = ""
    if isAA(r) and isAA(r.slot)
        title = txt(r.slot.title)
        times = clock(r.slot.start_local) + " - " + clock(r.slot.end_local)
        if isAA(r.next) then nxt = "Next: " + txt(r.next.title) + "  at " + clock(r.next.start_local)
    else if isAA(ch.now)
        title = txt(ch.now.title)
    end if
    m.top.findNode("bnTitle").text = title
    m.top.findNode("bnTime").text = times
    m.top.findNode("bnNext").text = nxt
    m.top.findNode("bnHelp").text = "OK guide    Left: on demand    Replay: last channel    Rew: start over    *: subtitles"
    m.banner.visible = true
    m.bannerTimer.control = "stop"
    m.bannerTimer.control = "start"
end sub

sub flash(text as string)
    m.top.findNode("bnTime").text = text
    m.banner.visible = true
    m.bannerTimer.control = "stop"
    m.bannerTimer.control = "start"
end sub

sub hideBanner()
    m.banner.visible = false
end sub

sub showGuide()
    if m.channels.count() = 0 then return
    m.banner.visible = false
    m.guide.visible = true
    if m.current >= 0 then m.list.jumpToItem = m.current
    m.list.setFocus(true)
    onListFocus()
end sub

sub hideGuide()
    m.guide.visible = false
    m.top.setFocus(true)
end sub

sub onListFocus()
    i = m.list.itemFocused
    if i < 0 or i >= m.channels.count() then return
    c = m.channels[i]
    title = "Nothing on right now"
    times = ""
    nxt = ""
    pic = ""
    if isAA(c.now)
        title = txt(c.now.title)
        times = clock(c.now.start_local) + " - " + clock(c.now.end_local)
        pic = m.cfg.server + "/thumb/" + txt(c.now.media_id) + "?k=" + m.cfg.mk
    end if
    if isAA(c.next) then nxt = "Next: " + txt(c.next.title) + "  at " + clock(c.next.start_local)
    m.top.findNode("gTitle").text = title
    m.top.findNode("gTime").text = times
    m.top.findNode("gNext").text = nxt
    m.top.findNode("gDesc").text = txt(c.description)
    m.top.findNode("gPic").uri = pic
end sub

sub onListSelect()
    i = m.list.itemSelected
    hideGuide()
    if i >= 0 and i <> m.current then tune(i) else showBanner(m.channels[m.current], invalid)
end sub

sub showMsg(text as string)
    m.msg.text = text
    m.msgBox.visible = true
end sub

sub hideMsg()
    m.msgBox.visible = false
end sub

' ---------- the remote ----------
function onKeyEvent(key as string, press as boolean) as boolean
    if not press then return false
    if m.remBox.visible and (key = "OK" or key = "back")
        if key = "OK" then watchReminder() else hideReminder()
        return true
    end if
    if m.grid.visible
        if key = "back"
            hideGrid()
            return true
        end if
        return false                                   ' the grid moves itself and selects with OK
    end if
    if m.guide.visible
        if key = "back" or key = "left"
            hideGuide()
            return true
        end if
        return false                                   ' the list moves itself and selects with OK
    end if
    if m.eps.visible
        if key = "back"
            m.eps.visible = false
            m.rows.setFocus(true)
            return true
        else if key = "options"
            i = m.epList.itemFocused
            if i >= 0 and i < m.epData.count() then toggleFavorite(m.epData[i], m.top.findNode("epLine"))
            return true
        end if
        return false
    end if
    if m.lib.visible
        if key = "back"
            closeLib()
            return true
        else if key = "options"
            t = focusedTile()
            if t <> invalid then toggleFavorite(t, m.top.findNode("libLine"))
            return true
        end if
        return false                                   ' the rows move themselves and select with OK
    end if
    if m.mode = "vod" then return vodKey(key)
    if m.failed and key = "OK"
        loadChannels()
        return true
    end if
    if key = "up" or key = "channelup"
        tune(m.current + 1)
        return true
    else if key = "down" or key = "channeldown"
        tune(m.current - 1)
        return true
    else if key = "OK"
        showGrid()
        return true
    else if key = "right"
        showGuide()
        return true
    else if key = "replay"
        lastChannel()
        return true
    else if key = "rev"
        startOver()
        return true
    else if key = "fwd"
        backToLive()
        return true
    else if key = "options"
        cycleSubs()
        return true
    else if key = "left"
        openLib()
        return true
    else if key = "play"
        if m.mode = "weather" then return true
        if m.video.state = "playing" then m.video.control = "pause" else m.video.control = "resume"
        return true
    end if
    return false                                       ' Back leaves the app
end function

' ---------- on demand: the library (Left) ----------
sub openLib()
    m.banner.visible = false
    m.upNext.visible = false
    m.lib.visible = true
    if m.libData.count() = 0 then m.top.findNode("libTitle").text = "Loading your library..."
    m.rows.setFocus(true)
    api("/api/ondemand", "onLib")
end sub

sub closeLib()
    m.lib.visible = false
    m.eps.visible = false
    m.top.setFocus(true)
    if m.mode = "vod"
        backToLive()                                   ' the video was stopped: back to the channel you were on
    end if
end sub

sub onLib(event as object)
    t = event.getRoSGNode()
    dropTask(t)
    if not m.lib.visible then return
    if t.error <> ""
        m.top.findNode("libTitle").text = t.error
        return
    end if
    if isArr(t.result.rows) then m.libRows = t.result.rows
    buildLib(1)
end sub

sub buildLib(focusRow as integer)
    data = []
    data.push({ title: "Search", items: [{ type: "search", title: "Search", line: "Find any movie or show by name", plot: "", thumb: "" }] })
    if isAA(m.libResults) then data.push(m.libResults)
    for each r in m.libRows
        if isAA(r) and isArr(r.items) and r.items.count() > 0 then data.push(r)
    end for
    root = CreateObject("roSGNode", "ContentNode")
    m.libData = []
    for each r in data
        row = root.createChild("ContentNode")
        row.title = txt(r.title)
        tiles = []
        for each it in r.items
            if isAA(it)
                n = row.createChild("ContentNode")
                n.title = txt(it.title)
                n.ShortDescriptionLine1 = tileTag(it)
                if isStr(it.thumb) and it.thumb <> "" then n.HDPosterUrl = m.cfg.server + it.thumb + "?k=" + m.cfg.mk
                tiles.push(it)
            end if
        end for
        m.libData.push(tiles)
    end for
    m.rows.content = root
    if focusRow >= data.count() then focusRow = 0
    m.rows.jumpToRowItem = [focusRow, 0]
    m.rows.setFocus(true)
    if data.count() = 1 then m.top.findNode("libTitle").text = "Nothing in your library yet - add videos to HERO TV on the PC."
end sub

function tileTag(it as object) as string
    tag = txt(it.line)
    if isTrue(it.favorite) then tag = "* " + tag
    return tag
end function

function focusedTile() as dynamic
    f = m.rows.rowItemFocused
    if not isArr(f) or f.count() < 2 then return invalid
    r = num(f[0])
    c = num(f[1])
    if r < 0 or r >= m.libData.count() then return invalid
    if c < 0 or c >= m.libData[r].count() then return invalid
    return m.libData[r][c]
end function

sub onLibFocus()
    t = focusedTile()
    if t = invalid then return
    m.top.findNode("libTitle").text = txt(t.title)
    m.top.findNode("libLine").text = tileTag(t)
    m.top.findNode("libPlot").text = txt(t.plot)
end sub

sub onLibSelect()
    t = focusedTile()
    if t = invalid then return
    kind = txt(t["type"])
    if kind = "search"
        openSearch()
    else if kind = "series"
        m.epShowTile = t
        m.top.findNode("libLine").text = "Opening " + txt(t.title) + "..."
        api("/api/ondemand?series=" + esc(txt(t.series)) + "&franchise=" + esc(txt(t.franchise)), "onEps")
    else
        startVod(num(t.id))
    end if
end sub

function esc(s as string) as string
    return CreateObject("roUrlTransfer").Escape(s)
end function

sub toggleFavorite(t as object, where as object)
    if txt(t["type"]) = "search" then return
    if txt(t["type"]) = "series"
        where.text = "Open the show and press * on an episode to add it to your favorites."
        return
    end if
    wantOn = not isTrue(t.favorite)
    t.favorite = wantOn
    api("/api/favorite", "onQuiet", "POST", FormatJson({ media_id: num(t.id), on: wantOn }))
    if wantOn then where.text = "Added to your favorites" else where.text = "Removed from your favorites"
end sub

' ---------- search ----------
sub openSearch()
    d = CreateObject("roSGNode", "StandardKeyboardDialog")
    if d = invalid then d = CreateObject("roSGNode", "KeyboardDialog")
    if d = invalid then return
    d.title = "Search your library"
    d.buttons = ["Search", "Cancel"]
    d.observeField("buttonSelected", "onSearchButton")
    m.searchDlg = d
    m.top.dialog = d
end sub

sub onSearchButton()
    d = m.searchDlg
    if d = invalid then return
    words = ""
    if d.buttonSelected = 0 then words = d.text
    d.close = true
    m.searchDlg = invalid
    m.rows.setFocus(true)
    if words = "" then return
    m.top.findNode("libTitle").text = "Searching for " + words + "..."
    api("/api/ondemand?q=" + esc(words), "onSearch")
end sub

sub onSearch(event as object)
    t = event.getRoSGNode()
    dropTask(t)
    if not m.lib.visible then return
    if t.error <> ""
        m.top.findNode("libTitle").text = t.error
        return
    end if
    m.libResults = invalid
    if isArr(t.result.rows) and t.result.rows.count() > 0
        r = t.result.rows[0]
        if isAA(r)
            if isArr(r.items) and r.items.count() > 0
                m.libResults = r
            else
                m.top.findNode("libTitle").text = txt(r.title)
                m.top.findNode("libLine").text = "Try fewer letters, or another name."
                return
            end if
        end if
    end if
    buildLib(1)
end sub

' ---------- the episodes of a show ----------
sub onEps(event as object)
    t = event.getRoSGNode()
    dropTask(t)
    if not m.lib.visible then return
    if t.error <> "" or not isArr(t.result.items) or t.result.items.count() = 0
        m.top.findNode("libLine").text = "Could not open that show right now."
        return
    end if
    m.epData = t.result.items
    content = CreateObject("roSGNode", "ContentNode")
    at = 0
    for i = 0 to m.epData.count() - 1
        e = m.epData[i]
        n = content.createChild("ContentNode")
        n.title = txt(e.title)
        if num(e.id) = num(t.result["next"]) then at = i
    end for
    m.top.findNode("epShow").text = txt(t.result.series)
    m.epList.content = content
    m.epList.jumpToItem = at
    m.eps.visible = true
    m.epList.setFocus(true)
    onEpFocus()
end sub

sub onEpFocus()
    i = m.epList.itemFocused
    if i < 0 or i >= m.epData.count() then return
    e = m.epData[i]
    m.top.findNode("epTitle").text = txt(e.title)
    m.top.findNode("epLine").text = tileTag(e)
    m.top.findNode("epPlot").text = txt(e.plot)
    m.top.findNode("epPic").uri = m.cfg.server + txt(e.thumb) + "?k=" + m.cfg.mk
end sub

sub onEpSelect()
    i = m.epList.itemSelected
    if i >= 0 and i < m.epData.count() then startVod(num(m.epData[i].id))
end sub

' ---------- watching on demand ----------
sub startVod(id as integer)
    m.seq = m.seq + 1
    api("/api/play/" + id.ToStr(), "onPlay")
end sub

sub onPlay(event as object)
    t = event.getRoSGNode()
    dropTask(t)
    if t.tag <> m.seq.ToStr() then return
    r = t.result
    if t.error <> "" or not isAA(r) or r.id = invalid
        where = m.top.findNode("libLine")
        if m.eps.visible then where = m.top.findNode("epLine")
        if t.error <> "" then where.text = t.error else where.text = "That video is not available any more."
        if not m.lib.visible then showMsg("That video is not available any more. Press Back.")
        return
    end if
    if m.mode = "vod" then saveVod(false)
    m.mode = "vod"
    m.vod = r
    m.live = false
    m.slot = invalid
    m.nextSlot = invalid
    m.wx.visible = false
    m.wxTimer.control = "stop"
    m.upNext.visible = false
    m.lib.visible = false
    m.eps.visible = false
    m.top.setFocus(true)
    hideMsg()
    play({ media_id: r.id, ext: r.ext, subs: r.subs, title: r.title }, num(r.resume))
    m.top.findNode("bnNum").text = ""
    m.top.findNode("bnChan").text = "ON DEMAND"
    m.top.findNode("bnTitle").text = txt(r.title)
    m.top.findNode("bnNext").text = ""
    m.top.findNode("bnHelp").text = "Left/Right: 10 s    Rew/Fwd: 30 s    Replay: from the start    Back: library"
    if num(r.resume) > 0
        flash("Going on where you left off  -  press Replay to start from the beginning")
    else
        flash(txt(r.line))
    end if
end sub

sub onVodState(s as string)
    if s = "finished"
        saveVod(true)
        nx = invalid
        if isAA(m.vod) then nx = m.vod["next"]
        if isAA(nx)
            showMsg("Up next: " + txt(nx.title))
            startVod(num(nx.id))
        else
            stopVod()
        end if
    else if s = "error"
        title = ""
        if isAA(m.vod) then title = txt(m.vod.title)
        showMsg("This TV cannot play " + title + " (" + m.video.errorMsg + ")." + Chr(10) + "On the PC, Settings > Tools makes copies that play here." + Chr(10) + Chr(10) + "Press Back for the library.")
    else if s = "playing"
        hideMsg()
    end if
end sub

' remember where you are, so Continue watching (on every screen) picks up from here
sub saveVod(finished as boolean)
    if m.mode <> "vod" or not isAA(m.vod) then return
    at = Int(m.video.position)
    length = Int(m.video.duration)
    if length <= 0 then length = num(m.vod.runtime)
    done = finished or (length > 0 and at > length * 0.93)
    if at < 5 and not done then return
    api("/api/progress", "onQuiet", "POST", FormatJson({ media_id: num(m.vod.id), position: at, completed: done }))
end sub

sub leaveVod()
    if m.mode <> "vod" then return
    saveVod(false)
    m.vod = invalid
    m.mode = "live"
end sub

' Back while watching on demand: stop and return to the library (Back there returns to live TV)
sub stopVod()
    saveVod(false)
    m.seq = m.seq + 1
    m.video.control = "stop"
    hideMsg()
    m.banner.visible = false
    openLib()
end sub

sub seekBy(secs as integer)
    at = m.video.position + secs
    if at < 0 then at = 0
    if m.video.duration > 0 and at > m.video.duration - 3 then at = m.video.duration - 3
    m.video.seek = at
    flash(clockLen(Int(at)) + " of " + clockLen(Int(m.video.duration)))
end sub

function clockLen(s as integer) as string
    if s < 0 then s = 0
    h = s \ 3600
    mm = (s mod 3600) \ 60
    ss = s mod 60
    out = ""
    if h > 0 then out = h.ToStr() + ":"
    if h > 0 and mm < 10 then out = out + "0"
    out = out + mm.ToStr() + ":"
    if ss < 10 then out = out + "0"
    return out + ss.ToStr()
end function

function vodKey(key as string) as boolean
    if key = "back"
        stopVod()
    else if key = "left"
        seekBy(-10)
    else if key = "right"
        seekBy(10)
    else if key = "rev"
        seekBy(-30)
    else if key = "fwd"
        seekBy(30)
    else if key = "replay"
        m.video.seek = 0
        flash("From the beginning")
    else if key = "play"
        if m.video.state = "playing" then m.video.control = "pause" else m.video.control = "resume"
    else if key = "options"
        cycleSubs()
    else if key = "OK" or key = "up" or key = "down"
        flash(clockLen(Int(m.video.position)) + " of " + clockLen(Int(m.video.duration)) + "    Back: library")
    else
        return false
    end if
    return true
end function

' ---------- the Weather channel ----------
sub loadWeather()
    if m.mode = "weather" then api("/api/weather", "onWeather")
end sub

sub onWeather(event as object)
    t = event.getRoSGNode()
    dropTask(t)
    if m.mode <> "weather" then return
    w = t.result
    for each l in m.wxHours
        l.text = ""
    end for
    for each l in m.wxDays
        l.text = ""
    end for
    m.top.findNode("wxAlert").text = ""
    if t.error <> ""
        m.top.findNode("wxPlace").text = ""
        m.top.findNode("wxTemp").text = ""
        m.top.findNode("wxCond").text = "Weather is not available right now"
        m.top.findNode("wxDetail").text = t.error
        return
    end if
    if not isTrue(w.configured)
        m.top.findNode("wxPlace").text = ""
        m.top.findNode("wxTemp").text = ""
        m.top.findNode("wxCond").text = "No town chosen yet"
        m.top.findNode("wxDetail").text = "On the PC: Settings > Weather, type your town and press Save."
        return
    end if
    unitT = "°"
    unitW = ""
    if isAA(w.units)
        unitT = txt(w.units.temp)
        unitW = txt(w.units.wind)
    end if
    off = num(w.utc_offset)
    m.top.findNode("wxPlace").text = txt(w.location)
    c = w.current
    if isAA(c)
        m.top.findNode("wxTemp").text = deg(c.temp) + unitT
        m.top.findNode("wxCond").text = wmoText(c.code)
        d = ""
        if c.feels <> invalid then d = "Feels like " + deg(c.feels) + "°"
        if c.humidity <> invalid then d = d + "    Humidity " + deg(c.humidity) + "%"
        if c.wind <> invalid then d = d + Chr(10) + "Wind " + compass(c.wind_dir) + " " + deg(c.wind) + " " + unitW
        if isArr(w.daily) and w.daily.count() > 0 and isAA(w.daily[0])
            d = d + Chr(10) + "Today: high " + deg(w.daily[0].hi) + "°, low " + deg(w.daily[0].lo) + "°"
        end if
        m.top.findNode("wxDetail").text = d
    else
        m.top.findNode("wxTemp").text = ""
        m.top.findNode("wxCond").text = "No forecast right now"
        m.top.findNode("wxDetail").text = txt(w.error)
    end if
    if isArr(w.alerts) and w.alerts.count() > 0
        a = ""
        n = 0
        for each x in w.alerts
            if isAA(x) and n < 2
                if a <> "" then a = a + Chr(10)
                a = a + "ALERT: " + txt(x.headline)
                n = n + 1
            end if
        end for
        m.top.findNode("wxAlert").text = a
    end if
    if isArr(w.hourly)
        i = 0
        for each h in w.hourly
            if isAA(h) and i < m.wxHours.count()
                hr = ((num(h.t) + off) mod 86400) \ 3600
                rain = ""
                if num(h.pop) > 0 then rain = num(h.pop).ToStr() + "%"
                m.wxHours[i].text = hour12(hr) + Chr(10) + deg(h.temp) + "°" + Chr(10) + rain
                i = i + 1
            end if
        end for
    end if
    if isArr(w.daily)
        names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        i = 0
        for each dy in w.daily
            if isAA(dy) and i < m.wxDays.count()
                day = "Today"
                if i > 0 then day = names[(((num(dy.t) + off) \ 86400) + 4) mod 7]
                m.wxDays[i].text = day + Chr(10) + deg(dy.hi) + "° / " + deg(dy.lo) + "°" + Chr(10) + wmoShort(dy.code)
                i = i + 1
            end if
        end for
    end if
end sub

function deg(v as dynamic) as string
    if v = invalid then return "-"
    if GetInterface(v, "ifFloat") <> invalid or GetInterface(v, "ifDouble") <> invalid then return Int(v + 0.5).ToStr()
    return num(v).ToStr()
end function

function hour12(h as integer) as string
    ampm = "AM"
    if h >= 12 then ampm = "PM"
    h = h mod 12
    if h = 0 then h = 12
    return h.ToStr() + " " + ampm
end function

function compass(d as dynamic) as string
    if d = invalid then return ""
    names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return names[((num(d) + 22) mod 360) \ 45]
end function

function wmoText(code as dynamic) as string
    if code = invalid then return ""
    c = num(code)
    if c = 0 then return "Clear"
    if c = 1 then return "Mostly clear"
    if c = 2 then return "Partly cloudy"
    if c = 3 then return "Cloudy"
    if c = 45 or c = 48 then return "Fog"
    if c >= 51 and c <= 55 then return "Drizzle"
    if c = 56 or c = 57 or c = 66 or c = 67 then return "Freezing rain"
    if c >= 61 and c <= 65 then return "Rain"
    if c >= 71 and c <= 77 then return "Snow"
    if c >= 80 and c <= 82 then return "Rain showers"
    if c = 85 or c = 86 then return "Snow showers"
    if c = 95 then return "Thunderstorms"
    if c = 96 or c = 99 then return "Thunderstorms with hail"
    return ""
end function

function wmoShort(code as dynamic) as string
    t = wmoText(code)
    if t = "Thunderstorms with hail" then return "Storms, hail"
    if t = "Thunderstorms" then return "Storms"
    return t
end function
