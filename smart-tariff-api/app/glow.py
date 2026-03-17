# smart-tariff-api/app/glow.py

import datetime
from glowmarkt import BrightClient

class GlowClient:
    """
    Thin wrapper around the Bright/Glowmarkt client.
    Uses the user's Bright credentials to find electricity/gas resources
    and to fetch tariff and half-hourly readings.
    """

    def __init__(self, email: str, password: str):
        self.cli = BrightClient(email, password)

    # -------- resource discovery --------
    def _first_resource_matching(self, keyword: str):
        """
        Returns the first resource whose name contains the keyword (e.g., "Electricity" or "Gas").
        """
        ents = self.cli.get_virtual_entities()
        for ent in ents:
            for res in ent.get_resources():
                # Name strings vary across accounts, so we use a contains check.
                if keyword.lower() in (res.name or "").lower():
                    return res
        return None

    def get_electricity_resource(self):
        return self._first_resource_matching("Electricity")

    def get_gas_resource(self):
        return self._first_resource_matching("Gas")

    # -------- tariff & readings --------
    def get_tariff(self, resource):
        """
        Returns the tariff object for a resource.
        Tariff exposes: tariff.current_rates.rate and tariff.current_rates.standing_charge
        """
        return resource.get_tariff()

    def get_recent_readings(self, resource, minutes=60, period="PT30M"):
        """
        Returns half-hourly (or chosen period) readings for the last N minutes.
        Each element is [timestamp, value]; value may be a typed object with .value.
        """
        now = datetime.datetime.now()
        t_from = now - datetime.timedelta(minutes=minutes)
        t_from = resource.round(t_from, period)
        t_to = resource.round(now, period)
        return resource.get_readings(t_from, t_to, period)
