"""Draws the HERO TV icon (a TV with a play arrow) as a Windows .ico, using only the standard library."""
import struct
import zlib


def _png(w, h, px):
    raw = b"".join(b"\x00" + bytes(px[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def _inside_round(x, y, x0, y0, x1, y1, r):
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def render(size=256):
    s = size / 256.0
    px = bytearray(size * size * 4)
    body, rim, screen, red = (18, 22, 42), (255, 207, 31), (9, 11, 19), (255, 59, 59)
    for y in range(size):
        for x in range(size):
            X, Y = x / s, y / s
            c = None
            if _inside_round(X, Y, 8, 8, 248, 248, 44):
                c = body
                if _inside_round(X, Y, 30, 52, 226, 206, 22):
                    c = rim
                    if _inside_round(X, Y, 42, 64, 214, 194, 14):
                        c = screen
                        # play triangle (left edge x=98, tip x=170)
                        if 98 <= X <= 170 and abs(Y - 129) <= (170 - X) * (46 / 72.0) * 1.0 + 0 and abs(Y - 129) <= 46 * (170 - X) / 72.0 + 0:
                            c = red
                # antenna
                if abs((X - 128) * 1.0) <= 5 and 22 <= Y <= 52:
                    c = rim
            if c:
                i = (y * size + x) * 4
                px[i:i + 4] = bytes((*c, 255))
    return bytes(px)


def make_ico(path):
    sizes = []
    for n in (256, 64, 32):
        sizes.append((n, _png(n, n, render(n))))
    head = struct.pack("<HHH", 0, 1, len(sizes))
    off = 6 + 16 * len(sizes)
    entries, data = b"", b""
    for n, png in sizes:
        entries += struct.pack("<BBBBHHII", 0 if n == 256 else n, 0 if n == 256 else n, 0, 0, 1, 32, len(png), off + len(data))
        data += png
    with open(path, "wb") as f:
        f.write(head + entries + data)
    return path
