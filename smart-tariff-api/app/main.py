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
from datetime import datetime, timedelta
from .mqtt_inbound import PowerMQTTSubscriber, PowerContext as InboundPowerContext  # same fields as core_e7.PowerContext
from .ha_solar import HASolarPoller
from .tariff_engine.core_e7 import TariffEngine as SolarAwareEngine, TariffContext as CoreTariffContext

import time
import json
app = FastAPI(title="Smart Tariff Micro‑API")
import logging
logger = logging.getLogger("smart-tariff")
# Globals
opts = load_options()
store = None
zone = None
zone_name = None
glow = None
power_sub = None  # type: ignore
base_engine = None
intel_engine = None
solar_poller = None  # type: ignore
mqtt = None
solar_engine = SolarAwareEngine()


BROKER_HOST = "core-mosquitto"
BROKER_PORT = 1883
BROKER_USER = "mqtt_user"
BROKER_PASS = "mqtt_password"
GROTT_STATE_TOPIC = "homeassistant/grott/WPDBCH1008/state"

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

def _is_offpeak_configured(now_local: datetime) -> bool:
    """
    Returns True if now_local is inside the configured E7 window,
    where the window is defined in *GMT* in options and we convert
    to local time (Europe/London) with DST handled correctly.
    """
    t = opts["tariff"]
    start_h, start_m = [int(x) for x in t["e7_offpeak_start_gmt"].split(":")]
    end_h, end_m     = [int(x) for x in t["e7_offpeak_end_gmt"].split(":")]

    gmt = tz.gettz("Etc/GMT")  # fixed GMT (no DST)
    # Build window today in GMT
    today_gmt = now_local.astimezone(gmt).replace(hour=0, minute=0, second=0, microsecond=0)
    start_gmt = today_gmt.replace(hour=start_h, minute=start_m)
    end_gmt   = today_gmt.replace(hour=end_h, minute=end_m)

    # Convert window edges to local tz for comparison
    start_local = start_gmt.astimezone(zone)
    end_local   = end_gmt.astimezone(zone)

    # Handle potential wrap
    if start_local <= end_local:
        return start_local <= now_local < end_local
    else:
        return now_local >= start_local or now_local < end_local

def _is_offpeak_simple(dt_local):
    start = dt_local.replace(hour=0, minute=30, second=0, microsecond=0)
    end   = dt_local.replace(hour=7, minute=30, second=0, microsecond=0)
    return start <= dt_local < end

def get_power_snapshot():
    sub = globals().get("power_sub")
    if not sub:
        return None
    try:
        return sub.get_power_context()
    except Exception:
        return None

def mqtt_discovery():
    logger.warning("MQTT DISCOVERY: starting… mqtt object = %s", mqtt)

    if not mqtt:
        logger.error("MQTT DISCOVERY: ABORT — mqtt publisher not initialised")
        return

    # All sensors to publish via MQTT Discovery
    configs = [

        # ---------------- ELECTRICITY ----------------

        {
            "object_id": "smart_tariff_elec_current_rate",
            "name": "Electricity Current Rate",
            "state_topic": "smartenergy/electricity/current_rate",
            "value_template": "{{ value_json.rate | round(2) }}",
            "unit": "GBP/kWh",
            "device_name": "Smart Tariff Micro‑API — Electricity"
        },
        {
            "object_id": "smart_tariff_elec_peak_rate",
            "name": "Electricity Peak Rate",
            "state_topic": "smartenergy/electricity/tariff",
            "value_template": "{{ value_json.rate_peak | round(2) }}",
            "unit": "GBP/kWh",
            "device_name": "Smart Tariff Micro‑API — Electricity"
        },
        {
            "object_id": "smart_tariff_elec_offpeak_rate",
            "name": "Electricity Off‑Peak Rate",
            "state_topic": "smartenergy/electricity/tariff",
            "value_template": "{{ value_json.rate_offpeak | round(2) }}",
            "unit": "GBP/kWh",
            "device_name": "Smart Tariff Micro‑API — Electricity"
        },
        {
            "object_id": "smart_tariff_elec_standing",
            "name": "Electricity Standing Charge",
            "state_topic": "smartenergy/electricity/tariff",
            "value_template": "{{ value_json.standing_charge | round(2) }}",
            "unit": "GBP/day",
            "device_name": "Smart Tariff Micro‑API — Electricity"
        },
        {
            "object_id": "smart_tariff_elec_usage_today",
            "name": "Electricity Usage Today",
            "state_topic": "smartenergy/electricity/cost_today",
            "value_template": "{{ (value_json.kwh_offpeak + value_json.kwh_peak) | round(1) }}",
            "unit": "kWh",
            "device_name": "Smart Tariff Micro‑API — Electricity"
        },
        {
            "object_id": "smart_tariff_elec_cost_today",
            "name": "Electricity Cost Today",
            "state_topic": "smartenergy/electricity/cost_today",
            "value_template": "{{ value_json.cost_total | round(2) }}",
            "unit": "GBP",
            "device_name": "Smart Tariff Micro‑API — Electricity"
        },

        # ---------------- GAS ----------------

        {
            "object_id": "smart_tariff_gas_current_rate",
            "name": "Gas Current Rate",
            "state_topic": "smartenergy/gas/tariff",
            "value_template": "{{ value_json.rate | round(2) }}",
            "unit": "GBP/kWh",
            "device_name": "Smart Tariff Micro‑API — Gas"
        },
        {
            "object_id": "smart_tariff_gas_standing",
            "name": "Gas Standing Charge",
            "state_topic": "smartenergy/gas/tariff",
            "value_template": "{{ value_json.standing_charge | round(2) }}",
            "unit": "GBP/day",
            "device_name": "Smart Tariff Micro‑API — Gas"
        },
        {
            "object_id": "smart_tariff_gas_usage_today",
            "name": "Gas Usage Today",
            "state_topic": "smartenergy/gas/cost_today",
            "value_template": "{{ value_json.kwh | round(1) }}",
            "unit": "kWh",
            "device_name": "Smart Tariff Micro‑API — Gas"
        },
        {
            "object_id": "smart_tariff_gas_cost_today",
            "name": "Gas Cost Today",
            "state_topic": "smartenergy/gas/cost_today",
            "value_template": "{{ value_json.cost_total | round(2) }}",
            "unit": "GBP",
            "device_name": "Smart Tariff Micro‑API — Gas"
        }
    ]

    # ------------------------------------------------
    # PUBLISH DISCOVERY FOR EACH SENSOR
    # ------------------------------------------------
    for cfg in configs:

        device_block = {
            "identifiers": [cfg["device_name"]],
            "name": cfg["device_name"],
            "manufacturer": "PlutoniumOD Industries",
            "model": "DCC‑Bright Engine"
        }

        topic = f"homeassistant/sensor/{cfg['object_id']}/config"

        payload = {
            "name": cfg["name"],
            "state_topic": cfg["state_topic"],
            "value_template": cfg["value_template"],
            "unit_of_measurement": cfg["unit"],
            "unique_id": cfg["object_id"],
            "device": device_block,
            "json_attributes_topic": cfg["state_topic"]
        }

        logger.warning("MQTT DISCOVERY: publishing %s → %s", cfg["object_id"], topic)

        try:
            mqtt.client.publish(topic, json.dumps(payload), qos=1, retain=True)
            logger.warning("MQTT DISCOVERY: OK %s", cfg["object_id"])
        except Exception as e:
            logger.error("MQTT DISCOVERY: FAILED %s — %s", cfg["object_id"], e)

    logger.warning("MQTT DISCOVERY: completed")

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

def _last_valid_slot_pair(cost_res, cons_res, lookback_slots: int = 4):
    """
    Return (cost_gbp, kwh, slot_end_iso) from the latest half-hour slot
    with non-zero consumption. Scans back up to lookback_slots.
    """
    now = datetime.utcnow()
    period = "PT30M"
    for back in range(0, lookback_slots):
        end = now - timedelta(minutes=30*back)
        start = end - timedelta(minutes=30)
        start = cost_res.round(start, period)
        end   = cost_res.round(end, period)

        cost_rdgs = cost_res.get_readings(start, end, period)
        cons_rdgs = cons_res.get_readings(start, end, period)
        if not cost_rdgs or not cons_rdgs:
            continue

        (_, cost_val) = cost_rdgs[-1]
        (_, cons_val) = cons_rdgs[-1]
        cost_p  = getattr(cost_val, "value", cost_val)  # pence
        kwh     = getattr(cons_val, "value", cons_val)  # kWh

        try:
            kwh = float(kwh)
            cost_gbp = float(cost_p) / 100.0
        except Exception:
            continue

        if kwh and kwh > 0:
            # Use 'end' as the slot label for clarity
            return (cost_gbp, kwh, end.isoformat())

    return (None, None, None)


def compute_current_unit_rate():
    """
    Compute implicit unit rate from latest valid cost/consumption slot.

    If no valid slot is available (0 kWh or no data), fallback to tariff schedule:
        - Peak window  -> use last_peak_rate
        - Offpeak window -> use last_offpeak_rate
    """

    try:
        cost_res = glow.get_electricity_cost_resource()
        cons_res = glow.get_electricity_consumption_resource()
        if not cost_res or not cons_res:
            return None, None, None

        cost_gbp, kwh, slot_end = _last_valid_slot_pair(cost_res, cons_res)

        # ---- VALID SLOT FOUND ----
        if cost_gbp is not None and kwh is not None and kwh > 0:
            derived_rate = cost_gbp / kwh
            return derived_rate, cost_gbp, kwh

        # ---- NO VALID SLOT ----
        # Do NOT return a time-based fallback as a "derived" rate.
        # Let the tariff engine decide fallback using Bright rate or stored buckets.
        return None, None, None


    except Exception:
        return None, None, None


def _pence_to_gbp(v) -> float:
    """
    Accepts a pyglowmarkt unit object (e.g. Pence) or a raw float/int.
    Returns GBP as a float (pence/100).
    """
    try:
        raw = getattr(v, "value", v)
        return float(raw) / 100.0
    except Exception:
        return 0.0

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

# ---------- Ensure Store Helper ----------
def ensure_store():
    """Guarantee that `store` is a dict, creating defaults if missing/corrupt."""
    global store
    if store is None:
        try:
            store = store_load()
        except Exception as e:
            # Create a safe default store and persist it
            logger.warning("Store load failed; creating default store: %s", e)
            store = {
                "last_update": None,
                
                "elec": {
                    "last_offpeak_rate": opts["initial_values"]["elec_offpeak_rate"], "last_peak_rate": opts["initial_values"]["elec_peak_rate"], "standing_charge": opts["initial_values"]["elec_standing_charge"]},
                "gas":  {"last_rate": 0.0, "standing_charge": 0.0},
                "intelligent": {"windows": []},
            }
            store_save(store)

# ---------- Polling job ----------
def poll_bright():
    global store
    ensure_store()
    try:
        # ELECTRICITY: derive the current unit rate from cost/consumption
        er = glow.get_electricity_resource()
        if er:
            try:
                rate_now, _, _ = compute_current_unit_rate()
        
                # Bright tariff (authoritative, if available)
                bright_rate = None
                try:
                    t = er.get_tariff()
                    bright_rate = _pence_to_gbp(t.current_rates.rate)
                except Exception:
                    bright_rate = None

                now = now_local()
                is_offpeak = _is_offpeak_configured(now)

                # ---- Seed active bucket from Bright when present ----
                if bright_rate is not None and 0.001 <= bright_rate <= 1.0:
                    if is_offpeak:
                        store["elec"]["last_offpeak_rate"] = bright_rate
                    else:
                        store["elec"]["last_peak_rate"] = bright_rate

                # ---- Update from derived slot rate (only if present and sane) ----
                if rate_now is not None and 0.001 <= rate_now <= 1.0:
                    off = store["elec"]["last_offpeak_rate"] or 0.0
                    peak = store["elec"]["last_peak_rate"] or off
                    # Anti‑swap: refuse to overwrite the active bucket with a value
                    # that is "too close" to the opposite bucket in the wrong window.
                    EPS = 0.003
                    if is_offpeak:
                        if abs(rate_now - peak) <= EPS and peak > off:
                            # looks like a peak value during off‑peak -> ignore
                            pass
                        else:
                            store["elec"]["last_offpeak_rate"] = rate_now
                    else:
                        if abs(rate_now - off) <= EPS and off < peak:
                            # looks like an off‑peak value during peak -> ignore
                            pass
                        else:
                            store["elec"]["last_peak_rate"] = rate_now



        
            except Exception:
                # swallow transient API hiccups
                pass
    
        # GAS: leave as-is for now (you can convert pence->GBP when HAN is back)
        gr = glow.get_gas_resource()
        if gr:
            try:
                tg = glow.get_tariff(gr)
                store["gas"]["last_rate"] = float(getattr(tg.current_rates.rate, "value",
                                                          tg.current_rates.rate)) / 100.0
                store["gas"]["standing_charge"] = float(getattr(tg.current_rates.standing_charge, "value",
                                                                tg.current_rates.standing_charge)) / 100.0
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

        # Push electricity cost_today
        try:
            electricity_cost_today()
        except Exception as e:
            logger.error("Error computing elec cost_today during poll: %s", e)
        
        # Push gas cost_today
        try:
            gas_cost_today()
        except Exception as e:
            logger.error("Error computing gas cost_today during poll: %s", e)

# ---------- Startup ----------
@app.on_event("startup")
def on_startup():
    global opts, store, zone, zone_name, glow, base_engine, intel_engine, mqtt, solar_poller
    # 1) Options & store first
    opts = load_options()
    ensure_store()
    # 2) Timezone, engines, clients
    zone_name = opts["tariff"]["timezone"]
    zone = tz.gettz(zone_name)

    base_engine = make_engine(opts["tariff"]["mode"])
    intel_engine = IntelligentEngine()

    glow = GlowClient(opts["glowmarkt"]["email"], opts["glowmarkt"]["password"])
    # 3) MQTT (optional)
    
    if opts["mqtt"]["enabled"]:
        try:
            _mqtt = MQTTPublisher(
                opts["mqtt"]["host"],
                int(opts["mqtt"]["port"]),
                opts["mqtt"].get("username", ""),
                opts["mqtt"].get("password", ""),
                opts["mqtt"]["topic_prefix"]
            )
            logger.warning("MQTT INIT: publisher created successfully → %s", _mqtt)
        except Exception as e:
            logger.error("MQTT INIT: FAILED to create publisher — %s", e)
            _mqtt = None
    
        globals()["mqtt"] = _mqtt
    else:
        logger.warning("MQTT INIT: disabled in configuration")
    # 3b) MQTT inbound subscriber + HA Solar poller (Supervisor by default)
    if opts["mqtt"].get("enabled", False):
        try:
            # Optional: start HA Solar poller (Supervisor by default)
            ha_cfg = opts.get("homeassistant", {})
            solar_enabled = ha_cfg.get("solar_enabled", True)
            if solar_enabled:
                sp = HASolarPoller(
                    entity_id=ha_cfg.get("solar_entity_id", "sensor.solaredge_ac_power"),
                    use_supervisor=ha_cfg.get("use_supervisor", True),
                    base_url=ha_cfg.get("base_url"),
                    token=ha_cfg.get("token"),
                    interval_secs=int(ha_cfg.get("solar_poll_secs", 15)),
                    stale_after_secs=int(ha_cfg.get("solar_stale_secs", 60)),
                    on_log=lambda s: logger.info(s),
                    
                )
                sp.start()
                # Store in module global (so /debug/solar sees THIS instance)
                globals()["solar_poller"] = sp
                logger.warning("HA SOLAR: poller started")


                # Optional: log initial status right away
                try:
                    logger.warning("HA SOLAR status (boot): %s", sp.get_status())
                except Exception:
                    pass
            else:
                logger.warning("HA SOLAR: disabled via options")
    
        except Exception as e:
            logger.error("HA SOLAR: FAILED to start poller — %s", e)
            globals()["solar_poller"] = None

        # ---- start MQTT inbound subscriber (own try) ----
        try:
            sp = globals().get("solar_poller")
            globals()["power_sub"] = PowerMQTTSubscriber(
                host=opts["mqtt"]["host"],
                port=int(opts["mqtt"]["port"]),
                username=opts["mqtt"].get("username"),
                password=opts["mqtt"].get("password"),
                grott_state_topic="homeassistant/grott/WPDBCH1008/state",
                on_log=lambda s: logger.info(s),
                solar_supplier=(sp.get_solar_w if sp else None),
            )
            power_sub.start()
            logger.warning("MQTT INBOUND: subscriber started")
        except Exception as e:
            logger.error("MQTT INBOUND: FAILED to start subscriber — %s", e)
    
    
        # Publish MQTT Entites
        logger.warning("MQTT INIT: running mqtt_discovery()…")
        mqtt_discovery()
    
        # 4) Start the scheduler, then do a safe first poll
        start_scheduler(poll_bright)
        
        try:
            poll_bright()
        except Exception as e:
            logger.warning("Initial poll failed (will retry on schedule): %s", e)

# ---------- Endpoints ----------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "last_update": store["last_update"] if store else None,
        "mode": opts["tariff"]["mode"] if opts else None
    }

@app.get("/debug/power-snapshot")
def debug_power_snapshot():
    sub = globals().get("power_sub")
    if not sub:
        return {"error": "power_sub not started"}
    snap = sub.get_debug_snapshot()
    if not snap:
        return {"error": "no recent GROTT payload"}
    return snap



@app.get("/electricity/current-rate")
def electricity_current_rate():

    ctx = build_ctx(include_intel=True)

    # Latest derived unit rate from Bright (may be None)
    rate_now, _, _ = compute_current_unit_rate()

    # Use Bright's current rate if available (authoritative).
    bright_rate = None
    try:
        er = glow.get_electricity_resource()
        if er:
            t = er.get_tariff()
            bright_rate = _pence_to_gbp(t.current_rates.rate)
    except Exception:
        bright_rate = None

    # Build solar-aware context
    core_ctx = CoreTariffContext(
        now=now_local(),
        last_offpeak_rate=store["elec"]["last_offpeak_rate"],
        last_peak_rate=store["elec"]["last_peak_rate"],
        standing_charge=store["elec"]["standing_charge"],
        bright_rate=bright_rate
    )

    # Live power snapshot (or zeros if stale)
    power = get_power_snapshot() or InboundPowerContext(0.0, 0.0, 0.0, 0.0)

    base_rate = solar_engine.current_rate(
        ctx=core_ctx,
        power=power,
        derived_rate=rate_now
    )

    # Preserve intelligent windows overlay if configured
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
        return _is_offpeak_configured(dt_local)
    except Exception:
        return False

@app.get("/electricity/cost/today")
def electricity_cost_today():
    """Compute today's electricity cost using last-known peak/off-peak & windows (+ standing)."""
    try:
        er = glow.get_electricity_resource()
        if not er:
            raise HTTPException(503, "Electricity resource not available")

        # Pull last 24h
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


        payload = {
            "kwh_offpeak": round(kwh_off, 6),
            "kwh_peak": round(kwh_peak, 6),
            "rate_offpeak": off_rate,
            "rate_peak": peak_rate,
            "standing_charge": sc,
            "cost_total": round(cost, 6),
            "updated_utc": store["last_update"]
        }

        # Publish to MQTT
        mqtt_pub("electricity/cost_today", {
            "kwh_offpeak": round(kwh_off, 1),
            "kwh_peak": round(kwh_peak, 1),
            "cost_total": round(cost, 2),
            "updated_utc": store["last_update"]
        })

        return payload

    except Exception:
        fallback = {
            "kwh_offpeak": 0.0,
            "kwh_peak": 0.0,
            "rate_offpeak": store["elec"]["last_offpeak_rate"],
            "rate_peak": store["elec"]["last_peak_rate"],
            "standing_charge": store["elec"]["standing_charge"],
            "cost_total": None,
            "updated_utc": store["last_update"]
        }

        # Publish fallback too
        mqtt_pub("electricity/cost_today", fallback)
        return fallback


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


        payload = {
            "kwh": round(kwh, 6),
            "rate": rate,
            "standing_charge": sc,
            "cost_total": round(cost, 6),
            "updated_utc": store["last_update"]
        }

        mqtt_pub("gas/cost_today", {
            "kwh": round(kwh, 1),
            "cost_total": round(cost, 2),
            "updated_utc": store["last_update"]
        })

        return payload

    except Exception:
        fallback = {
            "kwh": 0.0,
            "rate": store["gas"]["last_rate"],
            "standing_charge": store["gas"]["standing_charge"],
            "cost_total": None,
            "updated_utc": store["last_update"]
        }

        mqtt_pub("gas/cost_today", fallback)
        return fallback

@app.get("/debug/entities")
def debug_entities():
    """List virtual entities/resources and any names we see (helps discovery)."""
    try:
        ents = glow.cli.get_virtual_entities()
        out = []
        for ent in ents:
            res_list = []
            for res in ent.get_resources():
                res_list.append({"name": res.name, "id": getattr(res, "resource_id", None)})
            out.append({"entity": getattr(ent, "name", None), "resources": res_list})
        return {"entities": out}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

@app.get("/debug/tariff/electricity")
def debug_tariff_electricity():
    try:
        er = glow.get_electricity_resource()
        if not er:
            return {"error": "No electricity resource found"}
        t = er.get_tariff()
        return {
            "rate_gbp_per_kwh": _pence_to_gbp(t.current_rates.rate),
            "standing_charge_gbp_per_day": _pence_to_gbp(t.current_rates.standing_charge),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

@app.get("/debug/derived-unit-rate")
def debug_derived_unit_rate():
    rate_now, cost_gbp, kwh = compute_current_unit_rate()
    return {"rate_gbp_per_kwh": rate_now, "slot_cost_gbp": cost_gbp, "slot_kwh": kwh}

@app.get("/debug/slot-pairs")
def debug_slot_pairs():
    try:
        cost_res = glow.get_electricity_cost_resource()
        cons_res = glow.get_electricity_consumption_resource()
        if not cost_res or not cons_res:
            return {"error": "Missing cost or consumption resource"}

        out = []
        now = datetime.utcnow()
        period = "PT30M"
        for back in range(0, 6):
            end = now - timedelta(minutes=30*back)
            start = end - timedelta(minutes=30)
            start = cost_res.round(start, period)
            end   = cost_res.round(end, period)

            try:
                cost_rdgs = cost_res.get_readings(start, end, period)
                cons_rdgs = cons_res.get_readings(start, end, period)
            except Exception as e:
                out.append({"slot": back, "error": str(e)})
                continue

            out.append({
                "slot": back,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "cost_rdgs": [str(x[1]) for x in cost_rdgs],
                "cons_rdgs": [str(x[1]) for x in cons_rdgs],
            })

        return out
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/e7-window")
def debug_e7_window():
    now = now_local()
    return {
        "now_local": now.isoformat(),
        "is_offpeak_simple": _is_offpeak_simple(now),
        "store_rates": {
            "offpeak": store["elec"]["last_offpeak_rate"],
            "peak": store["elec"]["last_peak_rate"],
            "standing": store["elec"]["standing_charge"],
        }
    }

@app.get("/debug/solar")
def debug_solar():
    sp = globals().get("solar_poller")
    if not sp:
        return {"error": "solar_poller not started"}
    status = sp.get_status()
    return status
    
