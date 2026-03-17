import datetime
from glowmarkt import BrightClient

class GlowClient:
    def __init__(self, email: str, password: str):
        self.cli = BrightClient(email, password)

    def get_electricity_resource(self):
        ents = self.cli.get_virtual_entities()
        for ent in ents:
            for res in ent.get_resources():
                if "Electricity" in res.name:
                    return res
        return None

    def get_gas_resource(self):
        ents = self.cli.get_virtual_entities()
        for ent in ents:
            for res in ent.get_resources():
                if "Gas" in res.name:
                    return res
        return None

    def get_tariff(self, resource):
        return resource.get_tariff()

    def get_recent_readings(self, resource, minutes=60, period="PT30M"):
        now = datetime.datetime.now()
        t_from = now - datetime.timedelta(minutes=minutes)
        t_from = resource.round(t_from, period)
        t_to = resource.round(now, period)
        return resource.get_readings(t_from, t_to, period)
