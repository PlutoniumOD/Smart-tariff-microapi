class FlatEngine:
    """Single-rate tariff (no off-peak window)."""
    def is_offpeak(self, dt):
        return False
    def current_rate(self, ctx, api_rate):
        # Prefer api_rate if set, else last_peak_rate as the single rate
        return (api_rate if (api_rate and api_rate > 0) else
                (ctx.last_peak_rate or ctx.last_offpeak_rate))
