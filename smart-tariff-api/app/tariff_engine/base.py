from datetime import datetime

def within_any(now: datetime, windows):
    for (s, e) in windows:
        if s <= now < e:
            return True
    return False

class IntelligentEngine:
    def current_rate(self, ctx, base_rate):
        if within_any(ctx.now, ctx.intelligent_windows):
            return ctx.last_offpeak_rate or base_rate
        return base_rate
