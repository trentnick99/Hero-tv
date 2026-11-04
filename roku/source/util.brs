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

' the dark background blended with a channel's colour (amt 0..1), so every screen carries the colour of what you are looking at
function tintColor(h as dynamic, amt as float, alpha as string) as string
    if not isStr(h) or Len(h) <> 7 or Left(h, 1) <> "#" then h = "#ffcf1f"
    r = Val(Mid(h, 2, 2), 16)
    g = Val(Mid(h, 4, 2), 16)
    b = Val(Mid(h, 6, 2), 16)
    r2 = Int(11 * (1 - amt) + r * amt)
    g2 = Int(14 * (1 - amt) + g * amt)
    b2 = Int(23 * (1 - amt) + b * amt)
    return "0x" + hex2(r2) + hex2(g2) + hex2(b2) + alpha
end function

function hex2(n as integer) as string
    if n < 0 then n = 0
    if n > 255 then n = 255
    return Right("0" + StrI(n, 16), 2)
end function

function chanColor(h as dynamic) as string
    return hexColor(h, "#ffcf1f")
end function
