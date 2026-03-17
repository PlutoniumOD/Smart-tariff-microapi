# smart-tariff-api/app/main.py

from fastapi import FastAPI, Body
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
from datetime import datetime
from dateutil import tz

# ---- local modules (same folder structure you have) ----
from .settings import load_options
from .storage import load as store_load, save as store_save
from .glow import GlowClient
from .tariff_engine.e7 import E7Engine
from .tariff_engine.intelligent import IntelligentEngine
from .scheduler import start_scheduler
from .mqtt_pub import MQTTPublisher

# ------------- FastAPI app (must be named `app`) -------------
app = FastAPI(title="Smart Tariff Micro‑API")

# ------------- Globals initialised on startup -------------
opts = None          # add-on options (/data/options.json)
store = None         # persisted JSON (rates, standing, windows)
zone = None          # tzinfo
zone_name = None
glow = None          # Glowmarkt client
base_engine = None   # E7 (default) – we’ll extend with provider engines later
intel_engine = None  # Intelligent overlay
mqtt = None          # MQTT publisher (optional)

# --------------------- Models ---------------------
class Window(BaseModel):
    start_iso: str  # ISO8601 with timezone e.g. "2026-03-17T00:30:00+00:00"
    end_iso: str

class Schedule(BaseModel):
    windows: List[Window] = Field(default=[])

# --------------------- Helpers ---------------------
def now_local() -> datetime:
    return datetime.now(tz=zone)

def build_ctx(include_intel: bool = True):
    """Ad-hoc context object the engines expect."""
    intel_windows: List[Tuple[datetime, datetime]] = []
    if include_intel and store["intelligent"]["windows"]:
        for w in store["intelligent"]["windows"]:
            s = datetime.fromisoformat(w["start_iso"]).astimezone(zone)
            e = datetime.fromisoformat(w["end_iso"]).astimezone(zone)
            intel_windows.append((s, e))

    # simple object with attributes
    return type(
        "Ctx", (), {
            "now": now_local(),
            "zone_name": zone_name,
            "last_offpeak_rate": store["elec"]["last_offpeak_rate"],
            "last_peak_rate": store["elec"]["last_peak_rate"],
            "standing_charge": store["elec"]["standing_charge"],
            "intelligent_windows": intel_windows
        }
    )

def mqtt_pub(topic: str, payload: dict):
    if mqtt:
        mqtt.pub(topic, payload)

# ------------------ Polling Job -------------------
def poll_bright():
    """Called on schedule (:00/:30) and on /refresh-data"""
    global store

    try:
        # Electricity tariff
        er = glow.get_electricity_resource()
        if er:
            try:
                t = glow.get_tariff(er)
                rate = float(t.current_rates.rate)
                sc = float(t.current_rates.standing_charge)

                # classify current window (off-peak vs peak) using E7 engine
                ctx = build_ctx(include_intel=False)
                # we don't pass api_rate to base_engine classification; we use the window
                in_off = False
                try:
                    # we want to know if *now* is off-peak per schedule (E7)
                    # E7Engine.current_rate returns a numeric rate; we compare windows instead:
                    # quick re-use: compute desired window outcome by comparing times
                    from .tariff_engine.e7 import in_window, minutes, is_dst
                    shift = 60 if is_dst(ctx.now, zone_name) else 0
                    start_min_gmt = minutes(opts["tariff"]["e7_offpeak_start_gmt"])
                    end_min_gmt = minutes(opts["tariff"]["e7_offpeak_end_gmt"])
                    in_off = in_window(ctx.now, start_min_gmt, end_min_gmt, zone_name)
                except Exception:
                    # if anything odd, default to "peak bucket" storage
                    in_off = False

                if in_off:
                    store["elec"]["last_offpeak_rate"] = rate
                else:
                    store["elec"]["last_peak_rate"] = rate
                store["elec"]["standing_charge"] = sc
            except Exception as e:
                # swallow transient API hiccups
                pass

        # Gas tariff (optional – may be unavailable if HAN is down)
        gr = glow.get_gas_resource()
        if gr:
            try:
                tg = glow.get_tariff(gr)
                store["gas"]["last_rate"] = float(tg.current_rates.rate)
                store["gas"]["standing_charge"] = float(tg.current_rates.standing_charge)
            except Exception:
                pass

    finally:
        store["last_update"] = datetime.utcnow().isoformat()
        store_save(store)

        mqtt_pub("electricity/tariff", {
            "rate_offpeak": store["elec"]["last_offpeak_rate"],
            "rate_peak": store["elec"]["last_peak_rate"],
            "standing_charge": store["elec"]["standing_charge"],
            "updated_utc": store["last_update"]
        })
        mqtt_pub("gas/tariff", {
            "rate": store["gas"]["last_rate"],
            "standing_charge": store["gas"]["standing_charge"],
            "updated_utc": store["last_update"]
        })

# -------------- FastAPI Lifecycle ----------------
@app.on_event("startup")
def on_startup():
    global opts, store, zone, zone_name, glow, base_engine, intel_engine, mqtt

    # 1) Load options & storage
    opts = load_options()
    store = store_load()

    # 2) Timezone
    zone_name = opts["tariff"]["timezone"]
    zone = tz.gettz(zone_name)

    # 3) Engines (E7 default; provider engines will be swapped later by opts["tariff"]["mode"])
    base_engine = E7Engine(
        opts["tariff"]["e7_offpeak_start_gmt"],
        opts["tariff"]["e7_offpeak_end_gmt"],
        zone_name
    )
    intel_engine = IntelligentEngine()

    # 4) Glow client
    glow = GlowClient(opts["glowmarkt"]["email"], opts["glowmarkt"]["password"])

    # 5) MQTT (optional)
    if opts["mqtt"]["enabled"]:
        mqtt_host = opts["mqtt"]["host"]
        mqtt_port = int(opts["mqtt"]["port"])
        mqtt_user = opts["mqtt"].get("username", "")
        mqtt_pass = opts["mqtt"].get("password", "")
        mqtt_prefix = opts["mqtt"]["topic_prefix"]
        try:
            _mqtt = MQTTPublisher(mqtt_host, mqtt_port, mqtt_user, mqtt_pass, mqtt_prefix)
        except Exception:
            _mqtt = None
        # keep even if connect fails (we won't pub)
        globals()["mqtt"] = _mqtt

    # 6) Start scheduler
    start_scheduler(poll_bright)

# --------------------- Endpoints ---------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "last_update": store["last_update"] if store else None,
        "mode": opts["tariff"]["mode"] if opts else None
    }

@app.get("/electricity/current-rate")
def electricity_current_rate():
    """Return the best-known current electricity rate & standing charge."""
    # Build context with intelligent windows (if any were posted)
    ctx = build_ctx(include_intel=True)

    # For now we rely on schedule + last-known buckets; api_rate can be used later for provider engines
    # Compose base + intelligent overlay:
    base_rate = base_engine.current_rate(ctx, None)
    rate = intel_engine.current_rate(ctx, base_rate) if ctx.intelligent_windows else base_rate

    payload = {
        "rate": rate,
        "standing_charge": store["elec"]["standing_charge"],
        "updated_utc": store["last_update"],
        "intelligent_windows": store["intelligent"]["windows"],
    }
    mqtt_pub("electricity/current_rate", payload)
    return payload

@app.get("/gas/current-rate")
def gas_current_rate():
    payload = {
        "rate": store["gas"]["last_rate"],
        "standing_charge": store["gas"]["standing_charge"],
        "updated_utc": store["last_update"]
    }
    mqtt_pub("gas/current_rate", payload)
    return payload

@app.post("/tariff/intelligent/schedule")
def post_intelligent_schedule(body: Schedule):
    store["intelligent"]["windows"] = [w.dict() for w in body.windows]
    store_save(store)
    return {"status": "ok", "count": len(body.windows)}

@app.post("/refresh-data")
def manual_refresh():
    poll_bright()
    return {"status": "refreshed", "updated_utc": store["last_update"]}

@app.get("/electricity/consumption")
def electricity_consumption(hours: int = 48, period: str = "PT30M"):
    """Read recent electricity consumption from Bright."""
    try:
        er = glow.get_electricity_resource()
        if not er:
            return {"period": period, "readings": []}
        minutes = max(1, hours) * 60
        rdgs = glow.get_recent_readings(er, minutes=minutes, period=period)
        readings = [[str(ts), float(getattr(val, "value", val))] for ts, val in rdgs]
    except Exception:
        readings = []
    payload = {"period": period, "readings": readings}
    mqtt_pub("electricity/consumption", payload)
    return payload
