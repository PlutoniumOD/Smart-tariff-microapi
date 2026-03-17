from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime

@dataclass
class TariffContext:
    now: datetime
    zone_name: str
    last_offpeak_rate: float
    last_peak_rate: float
    standing_charge: float
    intelligent_windows: List[Tuple[datetime, datetime]]

class TariffEngine:
    def current_rate(self, ctx: TariffContext, api_rate: Optional[float]) -> float:
        raise NotImplementedError
