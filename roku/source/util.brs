' Small helpers shared by the screen and the network task.
function isStr(v as dynamic) as boolean
    return v <> invalid and GetInterface(v, "ifString") <> invalid
end function

function isAA(v as dynamic) as boolean
    return v <> invalid and GetInterface(v, "ifAssociativeArray") <> invalid
end function

function isArr(v as dynamic) as boolean
    return v <> invalid and GetInterface(v, "ifArray") <> invalid
end function

function isTrue(v as dynamic) as boolean
    if v = invalid then return false
    if GetInterface(v, "ifBoolean") <> invalid then return v
    return false
end function

function num(v as dynamic) as integer
    if v = invalid then return 0
    if GetInterface(v, "ifInt") <> invalid then return v
    if GetInterface(v, "ifFloat") <> invalid or GetInterface(v, "ifDouble") <> invalid then return Int(v)
    if GetInterface(v, "ifLongInt") <> invalid then return Val(v.ToStr())
    if isStr(v) then return Val(v)
    return 0
end function

function txt(v as dynamic) as string
    if v = invalid then return ""
    if isStr(v) then return v
    return num(v).ToStr()
end function

' "2026-10-26T19:30:00-05:00" -> "7:30 PM"
function clock(iso as dynamic) as string
    if not isStr(iso) or Len(iso) < 16 then return ""
    h = Val(Mid(iso, 12, 2))
    mins = Mid(iso, 15, 2)
    ampm = "AM"
    if h >= 12 then ampm = "PM"
    h = h mod 12
    if h = 0 then h = 12
    return h.ToStr() + ":" + mins + " " + ampm
end function

function regRead(k as string) as string
    s = CreateObject("roRegistrySection", "herotv")
    if s.Exists(k) then return s.Read(k)
    return ""
end function

sub regWrite(k as string, v as string)
    s = CreateObject("roRegistrySection", "herotv")
    s.Write(k, v)
    s.Flush()
end sub

function hexColor(h as dynamic, fallback as string) as string
    if not isStr(h) or Len(h) <> 7 or Left(h, 1) <> "#" then h = fallback
    return "0x" + Mid(h, 2) + "FF"
end function
