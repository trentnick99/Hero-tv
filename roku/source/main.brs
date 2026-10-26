' HERO TV for Roku - plays your HERO TV channels from the PC, like real TV.
' Installed by HERO TV on the PC (Settings > Other devices > Install on my Roku TV), which also writes config.brs.
sub Main(args as dynamic)
    screen = CreateObject("roSGScreen")
    port = CreateObject("roMessagePort")
    screen.setMessagePort(port)
    scene = screen.CreateScene("MainScene")
    screen.show()
    scene.observeField("exitApp", port)
    while true
        msg = wait(0, port)
        t = type(msg)
        if t = "roSGScreenEvent"
            if msg.isScreenClosed() then return
        else if t = "roSGNodeEvent"
            if msg.getField() = "exitApp" then return
        end if
    end while
end sub
