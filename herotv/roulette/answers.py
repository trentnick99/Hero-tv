"""Is a typed guess the film?

A guess counts when, with capitals, punctuation, accents, a leading "the" and number spelling (2 / two / II) set
aside, it is the film's title, the title without its subtitle (when no other film in the library shares that short
name), its initials (for titles of three words or more), or - when spelling help is on - a near miss of one of those.
Sharing a word is never enough: "Spider-Man" is "close" for Spider-Man: Homecoming while other Spider-Man films
are in the library, not correct."""
import difflib
import re
import unicodedata

_WORDNUM = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
            "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13"}
_ROMAN = {"ii": "2", "iii": "3", "iv": "4", "vi": "6", "vii": "7", "viii": "8", "ix": "9", "xi": "11", "xii": "12", "xiii": "13"}
_ARTICLES = ("the ", "a ", "an ")
_SPLIT = re.compile(r"\s*(?::|\s-\s|\s–\s|\s—\s)\s*")


def norm(text):
    t = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().casefold()
    t = t.replace("&", " and ").replace("'", "").replace("’", "")
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    words = [_WORDNUM.get(w, _ROMAN.get(w, w)) for w in t.split()]
    t = " ".join(words)
    for a in _ARTICLES:
        if t.startswith(a) and len(t) > len(a):
            t = t[len(a):]
            break
    return t


def _parts(title):
    """(whole title, part before the subtitle or '') normalised."""
    whole = norm(title)
    bits = _SPLIT.split(str(title or ""), maxsplit=1)
    head = norm(bits[0]) if len(bits) > 1 else ""
    return whole, (head if head and head != whole else "")


def forms(title, others=()):
    """Every spelling that counts as this film: the title, and its short name when that is this film's alone."""
    whole, head = _parts(title)
    out = {whole} if whole else set()
    if head and len(head) >= 3:
        clash = False
        for o in others:
            ow, oh = _parts(o)
            if ow != whole and (ow == head or oh == head or ow.startswith(head + " ")):
                clash = True
                break
        if not clash:
            out.add(head)
    bits = _SPLIT.split(str(title or ""), maxsplit=1)
    tail = norm(bits[1]) if len(bits) > 1 else ""
    if len(tail) >= 5 and not any(ow == tail or ow.endswith(" " + tail) for ow in (_parts(o)[0] for o in others) if ow != whole):
        out.add(tail)                    # "Ragnarok" for Thor: Ragnarok, when no other film ends that way
    for name in (whole, head):
        words = name.split()
        if len(words) >= 3:
            out.add("".join(w[0] for w in words))
    return out


def _near(a, b):
    if min(len(a), len(b)) < 5:
        return False
    if abs(len(a) - len(b)) > 3:
        return False
    if re.findall(r"\d+", a) != re.findall(r"\d+", b):
        return False                     # the numbers differ: Toy Story 2 is not Toy Story 3, and Spider-Man is not Spider-Man 2
    return difflib.SequenceMatcher(None, a, b).ratio() >= (0.84 if len(b) >= 8 else 0.88)


def check(guess, title, others=(), spelling=True, alts=()):
    """'correct', 'close' (right film family, be more exact) or 'wrong'. alts = other names of the same film
    (the name on the file, say)."""
    g = norm(guess)
    if not g:
        return "wrong"
    ok = forms(title, others)
    for a in alts:
        if norm(a) and norm(a) != norm(title):
            ok |= forms(a, list(others) + [title])
    if g in ok:
        return "correct"
    if spelling and any(_near(g, f) for f in ok if len(f) > 4):
        return "correct"
    whole, head = _parts(title)
    if head and (g == head or (spelling and _near(g, head))):
        return "close"                   # the short name, but other films share it
    for name in [whole] + [norm(a) for a in alts]:
        if len(g) >= 4 and name.startswith(g + " ") and (len(g.split()) >= 2 or len(g) >= 6):
            return "close"
    return "wrong"
