' HERO TV for Roku: live channels from HERO TV on the PC.
' Up/Down change channel, OK opens the TV guide, Right the channel list, Replay the last channel, Rew starts the show
' over, Fwd goes back to live, * turns subtitles on/off, Back leaves the guide (or the app).

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

    m.video = m.top.findNode("video")
    m.banner = m.top.findNode("banner")
    m.guide = m.top.findNode("guide")
    m.list = m.top.findNode("list")
    m.msgBox = m.top.findNode("msgBox")
    m.msg = m.top.findNode("msg")
    m.grid = m.top.findNode("grid")
    m.tg = m.top.findNode("tg")
    m.prev = -1
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
    if m.channels.count() > 0 then api("/api/channels", "onChannels")
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
            if isAA(c) and c.kind <> "weather" and not isTrue(c.empty) then fresh.push(c)
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
    ch = m.channels[idx]
    regWrite("lastChannel", ch.id)
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
    if s = "finished"
        m.afterFinish = true
        m.seq = m.seq + 1
        if m.current >= 0 then api("/api/tv/" + m.channels[m.current].id, "onNow")
    else if s = "error"
        showMsg("The TV could not play this video (" + m.video.errorMsg + ")." + Chr(10) + "Change channel, or make an iPhone-friendly copy of it on the PC (Settings > Tools).")
    else if s = "playing"
        hideMsg()
    end if
end sub

' tell HERO TV what you watch, so For You and 'continue watching' learn from the TV too
sub reportSeen()
    if m.video.state = "playing" and isAA(m.slot)
        api("/api/seen", "onQuiet", "POST", FormatJson({ media_id: num(m.slot.media_id), secs: 30 }))
    end if
end sub

sub onQuiet(event as object)
    dropTask(event.getRoSGNode())
end sub

' ---------- subtitles (*) ----------
sub cycleSubs()
    c = m.video.content
    if c = invalid then return
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
        if isAA(g) and isArr(g.slots)
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
    if m.current >= 0 then showGridInfo(m.channels[m.current], invalid)
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
    i = m.tg.channelFocused
    prog = m.gridProg
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
            if not m.remShown.DoesExist(k) and not watching and not m.grid.visible
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
        if m.current >= 0 then showBanner(m.channels[m.current], invalid)
        return true
    else if key = "play"
        if m.video.state = "playing" then m.video.control = "pause" else m.video.control = "resume"
        return true
    end if
    return false                                       ' Back leaves the app
end function
