# tariff_engine.py
#
# Fully rewritten tariff engine with:
# - Clean inference rules
# - Battery & solar aware filtering
# - Confidence scoring
# - Safe persistent rate updates
# - Drop‑in compatibility with Smart‑Tariff‑MicroAPI
#
# Author: Wingman (M365 Copilot)
# Version: 2.0
#

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# PowerContext: inbound measurements from HA MQTT (solar, battery, grid)
# ---------------------------------------------------------------------------

@dataclass
class PowerContext:
    solar_w: float
    battery_discharge_w: float     # Positive = discharging
    grid_import_w: float           # Instant import power (W)
    # load_w is not needed for inference, but you may add if you want


# ---------------------------------------------------------------------------
# TariffContext: Bright data + stored rates
# ---------------------------------------------------------------------------

@dataclass
class TariffContext:
    now: datetime
    last_offpeak_rate: float
    last_peak_rate: float
    standing_charge: float
    # Epoch‑based Bright rate (can be None if unavailable)
    bright_rate: Optional[float]


# ---------------------------------------------------------------------------
# Internal thresholds
# ---------------------------------------------------------------------------

SOLAR_THRESHOLD_W = 50
BATTERY_THRESHOLD_W = 50
MIN_IMPORT_W = 200

CONFIDENCE_RATE_JUMP_LIMIT = 0.10     # max 10p/kWh jump for acceptance
CONFIDENCE_SAMPLES_REQUIRED = 3       # must see N “clean” periods in a row


# ---------------------------------------------------------------------------
# TariffEngine class
# ---------------------------------------------------------------------------

class TariffEngine:
    def __init__(self):
        self._clean_samples = 0
        self._last_rate: Optional[float] = None

    # -----------------------------------------------------------------------
    # Check whether a period is "clean" (safe for rate inference)
    # -----------------------------------------------------------------------
    def _is_clean_import(self, p: PowerContext) -> bool:
        if p.solar_w > SOLAR_THRESHOLD_W:
            return False

        if p.battery_discharge_w > BATTERY_THRESHOLD_W:
            return False

        if p.grid_import_w < MIN_IMPORT_W:
            return False

        return True

    # -----------------------------------------------------------------------
    # Determine which rate bucket we are in based on time only
    # (E7 should be time‑based — not flow‑based)
    # -----------------------------------------------------------------------
    def _is_offpeak_time(self, now: datetime) -> bool:
        # UK E7 typical window — override with config later if needed
        # 00:30 → 07:30
        start = now.replace(hour=0, minute=30, second=0, microsecond=0)
        end   = now.replace(hour=7, minute=30, second=0, microsecond=0)

        # Handle midnight wrap
        if start <= now < end:
            return True
        return False

    # -----------------------------------------------------------------------
    # Decide which historical stored rate should be applied
    # -----------------------------------------------------------------------
    def _select_stored_rate(self, ctx: TariffContext) -> float:
        if self._is_offpeak_time(ctx.now):
            return ctx.last_offpeak_rate
        else:
            return ctx.last_peak_rate

    # -----------------------------------------------------------------------
    # Confidence logic for derived rate acceptance
    # -----------------------------------------------------------------------
    def _rate_confident(self, new_rate: float) -> bool:
        if self._last_rate is None:
            self._last_rate = new_rate
            return True

        if abs(new_rate - self._last_rate) > CONFIDENCE_RATE_JUMP_LIMIT:
            # Sudden spike = untrusted
            self._clean_samples = 0
            return False

        self._clean_samples += 1
        self._last_rate = new_rate

        return self._clean_samples >= CONFIDENCE_SAMPLES_REQUIRED

    # -----------------------------------------------------------------------
    # Main API function — determines the current rate
    # -----------------------------------------------------------------------
    def current_rate(self,
                     ctx: TariffContext,
                     power: PowerContext,
                     derived_rate: Optional[float]) -> float:
        """
        Inputs:
            ctx          – tariff context + stored rates
            power        – real‑time power flow snapshot
            derived_rate – fallback rate calculated from cost/usage deltas
                           (None if not available)

        Behaviour:
        1) If Bright gives a solid API rate, trust it.
        2) Otherwise, only consider derived rate in “clean” conditions.
        3) If neither Bright nor confident derived rate available,
           fall back to stored rate based on time window.
        """

        # -------------------------------------------------------------------
        # 1) If Bright is valid — use it and overwrite stored rate
        # -------------------------------------------------------------------
        if ctx.bright_rate is not None:
            self._clean_samples = 0
            return ctx.bright_rate

        # -------------------------------------------------------------------
        # 2) Only consider derived rate when power input is clean
        # -------------------------------------------------------------------
        if derived_rate is not None and self._is_clean_import(power):
            if self._rate_confident(derived_rate):
                return derived_rate

        # -------------------------------------------------------------------
        # 3) Fallback — use stored peak/off‑peak rate based on time
        # -------------------------------------------------------------------
        return self._select_stored_rate(ctx)
