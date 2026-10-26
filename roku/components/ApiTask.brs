sub init()
    m.top.functionName = "go"
end sub

sub go()
    cfg = HeroConfig()
    xfer = CreateObject("roUrlTransfer")
    port = CreateObject("roMessagePort")
    xfer.SetMessagePort(port)
    xfer.SetUrl(cfg.server + m.top.path)
    xfer.AddHeader("Cookie", "herotv_dev=" + cfg.token)
    xfer.AddHeader("Accept", "application/json")
    xfer.AddHeader("User-Agent", "HERO TV for Roku")
    started = false
    if m.top.method = "POST"
        xfer.AddHeader("Content-Type", "application/json")
        started = xfer.AsyncPostFromString(m.top.body)
    else
        started = xfer.AsyncGetToString()
    end if
    result = invalid
    err = ""
    if started
        msg = wait(10000, port)
        if type(msg) = "roUrlEvent"
            code = msg.GetResponseCode()
            if code = 200
                result = ParseJson(msg.GetString())
                if not isAA(result) then err = "HERO TV sent an answer this app does not understand."
            else if code = 401
                err = "This TV is not paired any more. On the PC: Settings > Other devices > Install on my Roku TV."
            else if code = 403
                err = "On the PC, 'Let other devices watch' is switched off (Settings > Other devices)."
            else
                err = "Can't reach HERO TV at " + cfg.server + ". Is the PC on and HERO TV open?"
            end if
        else
            xfer.AsyncCancel()
            err = "HERO TV did not answer. Is the PC on and HERO TV open?"
        end if
    else
        err = "This TV could not start a request to HERO TV."
    end if
    if not isAA(result) then result = {}
    m.top.error = err
    m.top.result = result
    m.top.done = true
end sub
