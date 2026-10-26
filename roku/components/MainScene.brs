' HERO TV for Roku: live channels from HERO TV on the PC.
' Up/Down change channel, OK opens the channel list, * turns subtitles on/off, Back leaves the list (or the app).

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
    m.bannerTimer = m.top.findNode("bannerTimer")
    m.refreshTimer = m.top.findNode("refreshTimer")
    m.seenTimer = m.top.findNode("seenTimer")

    accent = hexColor(m.cfg.color, "#ffcf1f")
    m.top.findNode("bnBar").color = accent
    m.top.findNode("gStation").text = m.cfg.station

    m.video.observeField("state", "onVideoState")
    m.list.observeField("itemFocused", "onListFocus")
    m.list.observeField("itemSelected", "onListSelect")
    m.bannerTimer.observeField("fire", "hideBanner")
    m.refreshTimer.observeField("fire", "refreshChannels")
    m.seenTimer.observeField("fire", "reportSeen")
    m.refreshTimer.control = "start"
    m.seenTimer.control = "start"

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
        showGuide()
        return true
    else if key = "options"
        cycleSubs()
        return true
    else if key = "info" or key = "left" or key = "right"
        if m.current >= 0 then showBanner(m.channels[m.current], invalid)
        return true
    else if key = "play"
        if m.video.state = "playing" then m.video.control = "pause" else m.video.control = "resume"
        return true
    end if
    return false                                       ' Back leaves the app
end function
