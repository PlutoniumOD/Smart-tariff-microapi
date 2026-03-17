from datetime import datetime

def within_any(now: datetime, windows):
    for (s, e) in windows:
        if s <= now < e:
            return True
    return False

class IntelligentEngine:
    def current_rate(self, ctx, api_rate):
        # If an intelligent dispatch window is active, treat as offpeak
        if within_any(ctx.now, ctx.intelligent_windows):
            return api_rate or ctx.last_offpeak_rate or ctx.last_peak_rate
        # Otherwise fall back to peak/offpeak model if provided by outer profile
        # This engine is meant to be composed with a base profile (E7/EV/etc.)
        return api_rate or ctx.last_peak_rate or ctx.last_offpeak_rate
