"""Timezone helper.

Windows has no IANA timezone database and no /etc/timezone, so ``zoneinfo`` cannot work out the
local zone there. The special name ``"local"`` therefore means "whatever this computer's clock is
set to" and is implemented on top of the C runtime (which knows Windows' own DST rules).
Any real IANA name (``America/Chicago``) still works through ``zoneinfo`` (on Windows that needs
the ``tzdata`` pip package, which the launcher installs when it can).
"""
import datetime as dt
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOCAL = "local"
_EPOCH = dt.datetime(1970, 1, 1)


class LocalTZ(dt.tzinfo):
    """The computer's own timezone, DST included, using only the standard library."""

    def utcoffset(self, d):
        if d is None:
            return None
        naive = d.replace(tzinfo=None)
        base = naive.timetuple()[:6]
        found = []
        for isdst in (1, 0):          # 1 = summer time first, so fold=0 is the earlier of two repeated hours
            try:
                ts = time.mktime(base + (0, 0, isdst))
                lt = time.localtime(ts)
            except (OverflowError, OSError, ValueError):
                continue
            if lt[:6] == base and lt.tm_isdst == isdst:
                found.append(ts)
        if not found:                 # wall time that does not exist (spring-forward gap): let the C runtime decide
            try:
                found = [time.mktime(base + (0, 0, -1))]
            except (OverflowError, OSError, ValueError):
                return dt.timedelta(0)
        ts = found[min(d.fold, len(found) - 1)]
        return naive - (_EPOCH + dt.timedelta(seconds=ts))

    def dst(self, d):
        return None

    def tzname(self, d):
        return "local"

    def fromutc(self, d):
        ts = (d.replace(tzinfo=None) - _EPOCH).total_seconds()
        lt = time.localtime(ts)
        res = dt.datetime(*lt[:6], tzinfo=self)
        want = res.replace(tzinfo=None) - d.replace(tzinfo=None)
        if self.utcoffset(res) != want:   # second pass through a repeated hour
            res = res.replace(fold=1)
        return res


_LOCAL = LocalTZ()


def get_tz(name):
    """tzinfo for an IANA name or ``"local"``; raises ValueError with a readable message otherwise."""
    if not name or str(name).lower() == LOCAL:
        return _LOCAL
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise ValueError(
            f"Timezone '{name}' is not available. On Windows run:  python -m pip install tzdata   "
            f"(or remove HEROTV_TZ to use this computer's own timezone)."
        ) from exc


def js_zone(name):
    """Value the browser UI should pass to Intl.DateTimeFormat (None = the browser's own zone)."""
    return None if not name or str(name).lower() == LOCAL else name
