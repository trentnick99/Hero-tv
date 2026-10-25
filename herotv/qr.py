"""A small QR code maker (byte mode, error correction level M, versions 1-10), so a phone can open HERO TV by
pointing its camera at the PC screen instead of typing an address. Standard library only."""

# data codewords and block layout per version for level M: (ec codewords per block, [(block count, data codewords)])
_M = {1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
      6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
      10: (26, [(4, 43), (1, 44)])}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
          9: [6, 26, 46], 10: [6, 28, 50]}

_EXP, _LOG = [0] * 512, [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _rs(data, n):
    gen = [1]
    for i in range(n):
        gen = [a ^ b for a, b in zip(gen + [0], [0] + [_mul(g, _EXP[i]) for g in gen])]
    rem = [0] * n
    for d in data:
        f = d ^ rem[0]
        rem = rem[1:] + [0]
        for j in range(n):
            rem[j] ^= _mul(gen[j + 1], f)
    return rem


def _codewords(text):
    data = text.encode("utf-8")
    for v in range(1, 11):
        ec, groups = _M[v]
        cap = sum(c * d for c, d in groups)
        cnt_bits = 8 if v < 10 else 16
        if 4 + cnt_bits + 8 * len(data) <= cap * 8:
            break
    else:
        raise ValueError("text too long for this QR maker")
    bits = "0100" + format(len(data), f"0{cnt_bits}b") + "".join(format(b, "08b") for b in data)
    bits += "0" * min(4, cap * 8 - len(bits))
    bits += "0" * (-len(bits) % 8)
    cw = [int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]
    while len(cw) < cap:
        cw.append(pad[(len(cw) - len(bits) // 8) % 2])
    blocks, pos = [], 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(cw[pos:pos + size])
            pos += size
    eccs = [_rs(b, ec) for b in blocks]
    out = [b[i] for i in range(max(len(b) for b in blocks)) for b in blocks if i < len(b)]
    out += [e[i] for i in range(ec) for e in eccs]
    return v, out


def _format_bits(mask):
    d = (0b00 << 3) | mask                         # level M = 00
    r = d << 10
    for i in range(14, 9, -1):
        if r & (1 << i):
            r ^= 0x537 << (i - 10)
    return ((d << 10) | r) ^ 0x5412


def _version_bits(v):
    r = v << 12
    for i in range(17, 11, -1):
        if r & (1 << i):
            r ^= 0x1F25 << (i - 12)
    return (v << 12) | r


def _base(v):
    n = 17 + 4 * v
    m = [[None] * n for _ in range(n)]

    def finder(r, c):
        for i in range(-1, 8):
            for j in range(-1, 8):
                if 0 <= r + i < n and 0 <= c + j < n:
                    on = 0 <= i <= 6 and 0 <= j <= 6 and (i in (0, 6) or j in (0, 6) or (2 <= i <= 4 and 2 <= j <= 4))
                    m[r + i][c + j] = on
    finder(0, 0), finder(0, n - 7), finder(n - 7, 0)
    for i in range(8, n - 8):
        m[6][i] = m[i][6] = i % 2 == 0
    pos = _ALIGN[v]
    first, last = (pos[0], pos[-1]) if pos else (0, 0)
    for r in pos:
        for c in pos:
            if (r, c) in ((first, first), (first, last), (last, first)):
                continue                           # those three would sit on the finder patterns
            for i in range(-2, 3):
                for j in range(-2, 3):
                    m[r + i][c + j] = max(abs(i), abs(j)) != 1
    m[4 * v + 9][8] = True                         # the dark module
    for i in range(9):                             # reserve format areas
        if m[8][i] is None:
            m[8][i] = False
        if m[i][8] is None:
            m[i][8] = False
    for i in range(8):
        if m[8][n - 1 - i] is None:
            m[8][n - 1 - i] = False
        if m[n - 1 - i][8] is None:
            m[n - 1 - i][8] = False
    if v >= 7:
        vb = _version_bits(v)
        for i in range(18):
            bit = bool((vb >> i) & 1)
            m[n - 11 + i % 3][i // 3] = bit
            m[i // 3][n - 11 + i % 3] = bit
    return m


def _place(m, cw):
    n = len(m)
    bits = [(b >> (7 - i)) & 1 for b in cw for i in range(8)]
    k, data_cells = 0, []
    col, up = n - 1, True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(n - 1, -1, -1) if up else range(n)
        for r in rows:
            for c in (col, col - 1):
                if m[r][c] is None:
                    m[r][c] = bool(bits[k]) if k < len(bits) else False
                    data_cells.append((r, c))
                    k += 1
        up = not up
        col -= 2
    return data_cells


_MASKS = [lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0, lambda r, c: c % 3 == 0,
          lambda r, c: (r + c) % 3 == 0, lambda r, c: (r // 2 + c // 3) % 2 == 0,
          lambda r, c: (r * c) % 2 + (r * c) % 3 == 0, lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
          lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0]


def _apply_format(m, mask):
    n = len(m)
    f = _format_bits(mask)
    bit = lambda i: bool((f >> i) & 1)
    for i in range(6):                     # around the top-left finder
        m[i][8] = bit(i)
    m[7][8], m[8][8], m[8][7] = bit(6), bit(7), bit(8)
    for i in range(9, 15):
        m[8][14 - i] = bit(i)
    for i in range(8):                     # the second copy, split between the other two finders
        m[8][n - 1 - i] = bit(i)
    for i in range(8, 15):
        m[n - 15 + i][8] = bit(i)
    m[n - 8][8] = True                     # the dark module


def _penalty(m):
    n, p = len(m), 0
    for line in m + [list(col) for col in zip(*m)]:
        run, prev = 0, None
        for x in line:
            run = run + 1 if x == prev else 1
            prev = x
            if run == 5:
                p += 3
            elif run > 5:
                p += 1
        s = "".join("1" if x else "0" for x in line)
        p += 40 * (s.count("10111010000") + s.count("00001011101"))
    for r in range(n - 1):
        for c in range(n - 1):
            if m[r][c] == m[r + 1][c] == m[r][c + 1] == m[r + 1][c + 1]:
                p += 3
    dark = sum(sum(row) for row in m)
    p += 10 * (abs(dark * 100 // (n * n) - 50) // 5)
    return p


def matrix(text):
    """The QR code for text as rows of True (dark) / False (light), without the quiet border."""
    v, cw = _codewords(text)
    best = None
    for mask in range(8):
        m = _base(v)
        cells = _place(m, cw)
        for r, c in cells:
            if _MASKS[mask](r, c):
                m[r][c] = not m[r][c]
        _apply_format(m, mask)
        score = _penalty(m)
        if best is None or score < best[0]:
            best = (score, m)
    return best[1]


def svg(text, scale=6, border=4, dark="#000", light="#fff"):
    m = matrix(text)
    n = len(m) + 2 * border
    path = "".join(f"M{c + border},{r + border}h1v1h-1z" for r, row in enumerate(m) for c, x in enumerate(row) if x)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{n * scale}" height="{n * scale}" '
            f'shape-rendering="crispEdges"><rect width="{n}" height="{n}" fill="{light}"/><path d="{path}" fill="{dark}"/></svg>')
