
# smart-tariff-api/app/glow.py

import datetime
from glowmarkt import BrightClient

class GlowClient:
    """
    Wrapper around Bright (Glowmarkt) client for DCC-sourced meters.
    Provides discovery for consumption, cost, and (if present) tariff resources.
    """

    def __init__(self, email: str, password: str):
        self.cli = BrightClient(email, password)

    # ---------- Resource discovery ----------

    def _first_resource_matching(self, keyword: str):
        """Return the first resource whose name contains the keyword (case-insensitive)."""
        ents = self.cli.get_virtual_entities()
        for ent in ents:
            for res in ent.get_resources():
                if keyword.lower() in (res.name or "").lower():
                    return res
        return None

    # Electricity resources
    def get_electricity_cost_resource(self):
        return self._first_resource_matching("electricity cost")

    def get_electricity_consumption_resource(self):
        return self._first_resource_matching("electricity consumption")

    # Fallback — some accounts still publish generic "electricity" resource
    def get_electricity_resource(self):
        return self._first_resource_matching("electricity")

    # Gas (not currently derived)
    def get_gas_resource(self):
        return self._first_resource_matching("gas")

    # ---------- Tariff (rare in DCC, mostly for non-DCC imports) ----------

    def get_tariff(self, resource):
        """
        Tariff object: rarely present for DCC meters.
        Provided for gas, or imported agile tariffs.
        """
        return resource.get_tariff()

    # ---------- Readings ----------

    def get_recent_readings(self, resource, minutes=60, period="PT30M"):
        """
        Return (timestamp, value) readings for a given period.
        Value may be a unit object (e.g., Pence) or numeric.
        """
        now = datetime.datetime.now()
        t_from = now - datetime.timedelta(minutes=minutes)
        t_from = resource.round(t_from, period)
        t_to   = resource.round(now, period)
        return resource.get_readings(t_from, t_to, period)

        return resource.get_readings(t_from, t_to, period)
