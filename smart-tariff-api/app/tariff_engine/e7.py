from datetime import datetime
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
    def __init__(self):
        self.engine = TariffEngine()

    def get_current_rate(self, ctx, power, derived):
        return self.engine.current_rate(ctx, power, derived)
