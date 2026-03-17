# smart-tariff-api/app/main.py

from fastapi import FastAPI, Body, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
from datetime import datetime, date, time, timedelta
from dateutil import tz

from .settings import load_options
from .storage import load as store_load, save as store_save
from .glow import GlowClient
from .tariff_engine.e7 import E7Engine
from .tariff_engine.windowed import WindowedEngine
from .tariff_engine.flat import FlatEngine
from .tariff_engine.intelligent import IntelligentEngine
from .scheduler import start_scheduler
from .mqtt_pub import MQTTPublisher

app = FastAPI(title="Smart Tariff Micro‑API")

# Globals
opts = None
store = None
zone = None
zone_name = None
glow = None
base_engine = None
intel_engine = None
mqtt = None

# ---------- Models ----------
class Window(BaseModel):
    start_iso: str
    end_iso: str

class Schedule(BaseModel):
    windows: List[Window] = Field(default=[])

# ---------- Auth (optional API key later) ----------
def require_ok():
    # placeholder if you decide to add X-API-Key support
    return True

# ---------- Helpers ----------
def now_local() -> datetime:
    return datetime.now(tz=zone)

def build_ctx(include_intel: bool = True):
    intel_windows: List[Tuple[datetime, datetime]] = []
    if include_intel and store["intelligent"]["windows"]:
        for w in store["intelligent"]["windows"]:
            s = datetime.fromisoformat(w["start_iso"]).astimezone(zone)
            e = datetime.fromisoformat(w["end_iso"]).astimezone(zone)
            intel_windows.append((s, e))
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

# ---------- Engine selector ----------
def make_engine(tariff_mode: str):
    t = opts["tariff"]
    if tariff_mode == "e7":
        return E7Engine(t["e7_offpeak_start_gmt"], t["e7_offpeak_end_gmt"], t["timezone"])
    if tariff_mode == "go":
        windows = t.get("go_windows_gmt", [])
        return WindowedEngine(windows, t["timezone"])
    if tariff_mode == "uw_ev":
        windows = t.get("uw_ev_windows_gmt", [])
        return WindowedEngine(windows, t["timezone"])
    if tariff_mode == "ovo_powermove":
        windows = t.get("ovo_windows_gmt", [])
        return WindowedEngine(windows, t["timezone"])
    if tariff_mode == "flex":
        return FlatEngine()
    if tariff_mode == "intelligent":
        # Base on E7 by default; user can also combine with windows later if desired
        return E7Engine(t["e7_offpeak_start_gmt"], t["e7_offpeak_end_gmt"], t["timezone"])
    # default
    return E7Engine(t["e7_offpeak_start_gmt"], t["e7_offpeak_end_gmt"], t["timezone"])

# ---------- Polling job ----------
def poll_bright():
    global store
    try:
        er = glow.get_electricity_resource()
        if er:
            try:
                t = glow.get_tariff(er)
                rate = float(t.current_rates.rate)
                sc = float(t.current_rates.standing_charge)

                # choose bucket by current engine classification
                in_off = False
                try:
                    in_off = base_engine.is_offpeak(now_local())
                except Exception:
                    in_off = False

                if in_off:
                    store["elec"]["last_offpeak_rate"] = rate
                else:
                    store["elec"]["last_peak_rate"] = rate
                store["elec"]["standing_charge"] = sc
            except Exception:
                pass

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

# ---------- Startup ----------
@app.on_event("startup")
def on_startup():
    global opts, store, zone, zone_name, glow, base_engine, intel_engine, mqtt
    opts = load_options()
    store = store_load()
    zone_name = opts["tariff"]["timezone"]
    zone = tz.gettz(zone_name)

    base_engine = make_engine(opts["tariff"]["mode"])
    intel_engine = IntelligentEngine()

    glow = GlowClient(opts["glowmarkt"]["email"], opts["glowmarkt"]["password"])

    if opts["mqtt"]["enabled"]:
        try:
            _mqtt = MQTTPublisher(
                opts["mqtt"]["host"], int(opts["mqtt"]["port"]),
                opts["mqtt"].get("username",""), opts["mqtt"].get("password",""),
                opts["mqtt"]["topic_prefix"]
            )
        except Exception:
            _mqtt = None
        globals()["mqtt"] = _mqtt

    start_scheduler(poll_bright)

# ---------- Endpoints ----------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "last_update": store["last_update"] if store else None,
        "mode": opts["tariff"]["mode"] if opts else None
    }

@app.get("/electricity/current-rate")
def electricity_current_rate():
    ctx = build_ctx(include_intel=True)
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

# ----- Daily cost helpers -----
def _local_midnight(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

def _is_offpeak_at(dt_local: datetime) -> bool:
    try:
        return base_engine.is_offpeak(dt_local)
    except Exception:
        return False

@app.get("/electricity/cost/today")
def electricity_cost_today():
    """Compute today's electricity cost using last-known peak/off-peak & windows (+ standing)."""
    try:
        er = glow.get_electricity_resource()
        if not er:
            raise HTTPException(503, "Electricity resource not available")

        # Pull last 24h; we'll filter to local 'today'
        rdgs = glow.get_recent_readings(er, minutes=24*60, period="PT30M")
        today0 = _local_midnight(now_local())
        tomorrow0 = today0 + timedelta(days=1)

        kwh_off = 0.0
        kwh_peak = 0.0
        for ts, val in rdgs:
            kwh = float(getattr(val, "value", val))
            ts_local = ts.astimezone(zone)
            if not (today0 <= ts_local < tomorrow0):
                continue
            if _is_offpeak_at(ts_local):
                kwh_off += kwh
            else:
                kwh_peak += kwh

        off_rate = store["elec"]["last_offpeak_rate"] or 0.0
        peak_rate = store["elec"]["last_peak_rate"] or off_rate
        sc = store["elec"]["standing_charge"] or 0.0

        cost = (kwh_off * off_rate) + (kwh_peak * peak_rate) + sc
        return {
            "kwh_offpeak": round(kwh_off, 6),
            "kwh_peak": round(kwh_peak, 6),
            "rate_offpeak": off_rate,
            "rate_peak": peak_rate,
            "standing_charge": sc,
            "cost_total": round(cost, 6),
            "updated_utc": store["last_update"]
        }
    except HTTPException:
        raise
    except Exception:
        # non-fatal
        return {
            "kwh_offpeak": 0.0, "kwh_peak": 0.0,
            "rate_offpeak": store["elec"]["last_offpeak_rate"],
            "rate_peak": store["elec"]["last_peak_rate"],
            "standing_charge": store["elec"]["standing_charge"],
            "cost_total": None, "updated_utc": store["last_update"]
        }

@app.get("/gas/cost/today")
def gas_cost_today():
    """Compute today's gas cost with single rate + standing charge."""
    try:
        gr = glow.get_gas_resource()
        if not gr:
            raise HTTPException(503, "Gas resource not available")
        rdgs = glow.get_recent_readings(gr, minutes=24*60, period="PT30M")
        today0 = _local_midnight(now_local())
        tomorrow0 = today0 + timedelta(days=1)

        kwh = 0.0
        for ts, val in rdgs:
            ts_local = ts.astimezone(zone)
            if today0 <= ts_local < tomorrow0:
                kwh += float(getattr(val, "value", val))

        rate = store["gas"]["last_rate"] or 0.0
        sc = store["gas"]["standing_charge"] or 0.0
        cost = (kwh * rate) + sc
        return {
            "kwh": round(kwh, 6),
            "rate": rate,
            "standing_charge": sc,
            "cost_total": round(cost, 6),
            "updated_utc": store["last_update"]
        }
    except HTTPException:
        raise
    except Exception:
        return {
            "kwh": 0.0,
            "rate": store["gas"]["last_rate"],
            "standing_charge": store["gas"]["standing_charge"],
            "cost_total": None,
            "updated_utc": store["last_update"]
        }
