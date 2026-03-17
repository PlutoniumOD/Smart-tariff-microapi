# smart-tariff-api/app/tariff_engine/intelligent.py

from datetime import datetime
from typing import Iterable, Tuple

def _within_any(now: datetime, windows: Iterable[Tuple[datetime, datetime]]) -> bool:
    for (s, e) in windows:
        if s <= now < e:
            return True
    return False

class IntelligentEngine:
    """
    Overlay engine: if now is inside an intelligent dispatch window,
    treat as off-peak; otherwise defer to the base engine's decision.
    """
    def current_rate(self, ctx, base_rate: float) -> float:
        if _within_any(ctx.now, ctx.intelligent_windows):
            # Prefer the stored off-peak rate if we have it; otherwise fall back to base
            return ctx.last_offpeak_rate or base_rate
        return base_rate
