from datetime import datetime
from dateutil import tz

def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h)*60 + int(m)

def _is_dst(dt: datetime, zone_name: str) -> bool:
    z = tz.gettz(zone_name)
    return bool((dt.replace(tzinfo=z)).dst())

def _in_window(now: datetime, start_min_gmt: int, end_min_gmt: int, zone_name: str) -> bool:
    shift = 60 if _is_dst(now, zone_name) else 0
    start = (start_min_gmt + shift) % (24*60)
    end   = (end_min_gmt   + shift) % (24*60)
    cur   = now.hour*60 + now.minute
    if start <= end:
        return start <= cur < end
    return cur >= start or cur < end

class WindowedEngine:
    """
    Generic DST-aware engine with 1..N off-peak windows (each in GMT HH:MM).
    """
    def __init__(self, windows_gmt: list[str], zone_name: str):
        """
        windows_gmt: list with pairs of strings ["HH:MM","HH:MM","HH:MM","HH:MM", ...]
        where each (i,i+1) pair is start,end for an off-peak window in GMT.
        """
        assert len(windows_gmt) % 2 == 0, "windows_gmt must have even length"
        self.zone = zone_name
        self.windows = []
        for i in range(0, len(windows_gmt), 2):
            s = _minutes(windows_gmt[i])
            e = _minutes(windows_gmt[i+1])
            self.windows.append((s, e))

    def is_offpeak(self, dt: datetime) -> bool:
        for (s, e) in self.windows:
            if _in_window(dt, s, e, self.zone):
                return True
        return False

    def current_rate(self, ctx, api_rate):
        """
        api_rate kept for symmetry; not used for window classification for now.
        """
        # Prefer api_rate if present
        if api_rate and api_rate > 0:
            return api_rate
        if self.is_offpeak(ctx.now):
            return ctx.last_offpeak_rate or ctx.last_peak_rate
        return ctx.last_peak_rate or ctx.last_offpeak_rate
