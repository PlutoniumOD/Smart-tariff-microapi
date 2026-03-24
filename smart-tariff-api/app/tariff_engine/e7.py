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
    def __init__(self, offpeak_start_gmt: str, offpeak_end_gmt: str, zone_name: str):
        self.start_gmt = minutes(offpeak_start_gmt)
        self.end_gmt = minutes(offpeak_end_gmt)
        self.zone = zone_name

    def is_offpeak(self, dt: datetime) -> bool:
        return in_window(dt, self.start_gmt, self.end_gmt, self.zone)

    def current_rate(self, ctx, api_rate):
        if api_rate and api_rate > 0:
            return api_rate
        if self.is_offpeak(ctx.now):
            return ctx.last_offpeak_rate or ctx.last_peak_rate
        return ctx.last_peak_rate or ctx.last_offpeak_rate
