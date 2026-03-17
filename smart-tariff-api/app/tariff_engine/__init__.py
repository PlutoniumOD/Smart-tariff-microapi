from fastapi import FastAPI
from pydantic import BaseModel, Field
from datetime import datetime
from dateutil import tz
from typing import List

from .settings import load_options
from .storage import load, save
from .glow import GlowClient
from .tariff_engine.e7 import E7Engine
from .tariff_engine.intelligent import IntelligentEngine
from .scheduler import start_scheduler
from .mqtt_pub import MQTTPublisher

app = FastAPI(title="Smart Tariff Micro‑API")
opts = load_options()
store = load()

zone_name = opts["tariff"]["timezone"]
zone = tz.gettz(zone_name)

glow = GlowClient(opts["glowmarkt"]["email"], opts["glowmarkt"]["password"])

# Engines (extend with provider engines later)
base_engine = E7Engine(
    opts["tariff"]["e7_offpeak_start_gmt"],
    opts["tariff"]["e7_offpeak_end_gmt"],
    zone_name
)
intel_engine = IntelligentEngine()

mqtt = None
if opts["mqtt"]["enabled"]:
    mqtt = MQTTPublisher(
        opts["mqtt"]["host"], opts["mqtt"]["port"],
        opts["mqtt"].get("username",""), opts["mqtt"].get("password",""),
        opts["mqtt"]["topic_prefix"]
    )

def now_local():
    return datetime.now(tz=zone)

# ---------------- Polling job -----------------

def poll_bright():
    global store
    # Electricity tariff
    er = glow.get_electricity_resource()
    if er:
        try:
            t = glow.get_tariff(er)
            rate = float(t.current_rates.rate)
            sc = float(t.current_rates.standing_charge)
            # Decide bucket using window
            in_off = base_engine.current_rate(
                type("ctx", (), {
                    "now": now_local(),
                    "zone_name": zone_name,
                    "last_offpeak_rate": store["elec"]["last_offpeak_rate"],
                    "last_peak_rate": store["elec"]["last_peak_rate"],
                    "standing_charge": store["elec"]["standing_charge"],
                    "intelligent_windows": []
                }),
                None
            ) == store["elec"]["last_offpeak_rate"]
            if in_off:
                store["elec"]["last_offpeak_rate"] = rate
            else:
                store["elec"]["last_peak_rate"] = rate
            store["elec"]["standing_charge"] = sc
        except Exception:
            pass

    # Gas tariff
    gr = glow.get_gas_resource()
    if gr:
        try:
            tg = glow.get_tariff(gr)
            store["gas"]["last_rate"] = float(tg.current_rates.rate)
            store["gas"]["standing_charge"] = float(tg.current_rates.standing_charge)
        except Exception:
            pass

    store["last_update"] = datetime.utcnow().isoformat()
    save(store)

    if mqtt:
        mqtt.pub("electricity/tariff",
                 {"rate_offpeak": store["elec"]["last_offpeak_rate"],
                  "rate_peak": store["elec"]["last_peak_rate"],
                  "standing_charge": store["elec"]["standing_charge"],
                  "updated_utc": store["last_update"]})
        mqtt.pub("gas/tariff",
                 {"rate": store["gas"]["last_rate"],
                  "standing_charge": store["gas"]["standing_charge"],
                  "updated_utc": store["last_update"]})

scheduler = start_scheduler(poll_bright)

# ---------------- Models -----------------

class Window(BaseModel):
    start_iso: str
    end_iso: str

class Schedule(BaseModel):
    windows: List[Window] = Field(default=[])

# ---------------- Endpoints -----------------

@app.get("/electricity/current-rate")
def get_electricity_current_rate():
    ctx = type("ctx", (), {
        "now": now_local(),
        "zone_name": zone_name,
        "last_offpeak_rate": store["elec"]["last_offpeak_rate"],
        "last_peak_rate": store["elec"]["last_peak_rate"],
        "standing_charge": store["elec"]["standing_charge"],
        "intelligent_windows": [
            (datetime.fromisoformat(w["start_iso"]).astimezone(zone),
             datetime.fromisoformat(w["end_iso"]).astimezone(zone))
            for w in store["intelligent"]["windows"]
        ]
    })
    # Compose base + intelligent overlay
    base_rate = base_engine.current_rate(ctx, None)
    rate = intel_engine.current_rate(ctx, base_rate) if ctx.intelligent_windows else base_rate

    payload = {
        "rate": rate,
        "standing_charge": store["elec"]["standing_charge"],
        "updated_utc": store["last_update"],
        "intelligent_windows": store["intelligent"]["windows"]
    }
    if mqtt:
        mqtt.pub("electricity/current_rate", payload)
    return payload

@app.get("/gas/current-rate")
def get_gas_current_rate():
    payload = {
        "rate": store["gas"]["last_rate"],
        "standing_charge": store["gas"]["standing_charge"],
        "updated_utc": store["last_update"]
    }
    if mqtt:
        mqtt.pub("gas/current_rate", payload)
    return payload

@app.post("/tariff/intelligent/schedule")
def post_intelligent_schedule(body: Schedule):
    store["intelligent"]["windows"] = [w.dict() for w in body.windows]
    save(store)
    return {"status": "ok", "count": len(body.windows)}

@app.post("/refresh-data")
def manual_refresh():
    poll_bright()
    return {"status": "refreshed", "updated_utc": store["last_update"]}

@app.get("/electricity/consumption")
def electricity_consumption(hours: int = 48, period: str = "PT30M"):
    er = glow.get_electricity_resource()
    if not er:
        return {"readings": []}
    minutes = hours * 60
    try:
        rdgs = glow.get_recent_readings(er, minutes=minutes, period=period)
    except Exception:
        rdgs = []
    # rdgs is list of [timestamp, value]
    payload = {"period": period, "readings": [[str(ts), float(val.value) if hasattr(val, 'value') else float(val)] for ts, val in rdgs]}
    if mqtt:
        mqtt.pub("electricity/consumption", payload)
    return payload
