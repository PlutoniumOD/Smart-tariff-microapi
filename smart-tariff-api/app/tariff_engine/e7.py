from datetime import datetime
from datetime import time
from dateutil import tz
from .core_e7 import TariffEngine as CoreE7Engine

def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h)*60 + int(m)

def is_dst(dt: datetime, zone_name: str) -> bool:
    z = tz.gettz(zone_name)
    return bool((dt.replace(tzinfo=z)).dst())

def in_window(now: datetime, start_min_gmt: int, end_min_gmt: int, zone_name: str) -> bool:
    shift = 60 if is_dst(now, zone_name) else 0
    start = (start_min_gmt + shift) % (24*60)
    end   = (end_min_gmt   + shift) % (24*60)
    cur   = now.hour*60 + now.minute
    if start <= end:
        return start <= cur < end
    return cur >= start or cur < end

class E7Engine:
    def __init__(self, start_gmt: str = "00:30", end_gmt: str = "07:30", tzname: str = "Europe/London"):
        # Expect "HH:MM" strings; store as hour/min ints (you can add DST handling if needed)
        sh, sm = [int(x) for x in start_gmt.split(":")]
        eh, em = [int(x) for x in end_gmt.split(":")]
        self._start_hm = (sh, sm)
        self._end_hm   = (eh, em)
        self._tzname   = tzname

    def is_offpeak(self, dt_local):
        # dt_local is already timezone-aware in your code (now_local()); if not, localize here
        sh, sm = self._start_hm
        eh, em = self._end_hm
        start = dt_local.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end   = dt_local.replace(hour=eh, minute=em, second=0, microsecond=0)
        return start <= dt_local < end
