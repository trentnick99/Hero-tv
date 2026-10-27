sub showItem()
    c = m.top.itemContent
    if c = invalid then return
    m.top.findNode("pic").uri = c.HDPosterUrl
    m.top.findNode("big").text = c.title
    m.top.findNode("title").text = c.title
    m.top.findNode("tag").text = c.ShortDescriptionLine1
end sub
