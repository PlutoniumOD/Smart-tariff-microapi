# smart-tariff-api/io/mqtt_inbound.py
#
# MQTT inbound subscriber for GROTT/ Growatt state -> PowerContext.
# Consumes a single JSON state topic:
#   homeassistant/grott/WPDBCH1008/state
#
# Exposes get_power_context() returning a fresh snapshot for the engine.
#
# No external deps beyond paho-mqtt (already used by publishers in many HA add-ons).
# If your add-on doesn't include paho-mqtt yet, add it to requirements.txt or vendor it.

import json
import threading
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable

import paho.mqtt.client as mqtt  # type: ignore


# ---- Shared model (kept here to avoid circular imports) --------------------

@dataclass
class PowerContext:
    solar_w: float
    battery_discharge_w: float  # +ve W when discharging
    grid_import_w: float        # +ve W when importing
    load_w: float               # house load W


# ---- Subscriber ------------------------------------------------------------

class PowerMQTTSubscriber:
    """
    Subscribes to GROTT's aggregated state JSON and extracts:
      - pdischarge1 -> battery discharge W  (/10)
      - plocaloadr  -> load W               (/10)
      - pactouserr  -> grid import W        (/10)
      - pactogridr  -> grid export W        (/10)

    Builds a PowerContext with an estimated PV value:
        solar_est = max(0, export + load - import - batt_discharge)
    """

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: str = "smart_tariff_microapi_in",
        grott_state_topic: str = "homeassistant/grott/WPDBCH1008/state",
        keepalive: int = 30,
        stale_after_secs: int = 180,
        on_log: Optional[Callable[[str], None]] = None,
        solar_supplier: Optional[Callable[[], Optional[float]]] = None,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._client_id = client_id
        self._topic = grott_state_topic
        self._keepalive = keepalive
        self._stale_after = stale_after_secs
        self._log = on_log or (lambda s: None)
        self._solar_supplier = solar_supplier

        self._client = mqtt.Client(client_id=self._client_id, clean_session=True)
        if self._username:
            self._client.username_pw_set(self._username, self._password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # Internal store (protected by a lock)
        self._lock = threading.RLock()
        self._last_seen_ts: float = 0.0
        self._last_payload: Dict[str, Any] = {}

        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

    # ---- Lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Start the background MQTT loop."""
        self._stop_evt.clear()
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._thread = threading.Thread(target=self._loop, name="mqtt-inbound", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background MQTT loop."""
        self._stop_evt.set()
        try:
            self._client.disconnect()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    # ---- Internals ---------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                self._client.connect(self._host, self._port, self._keepalive)
                self._client.loop_start()
                # Stay connected until stop requested
                while not self._stop_evt.is_set():
                    time.sleep(0.5)
                break
            except Exception as e:
                self._log(f"[mqtt_inbound] connect failed: {e}; retrying in 5s")
                time.sleep(5)

        try:
            self._client.loop_stop()
        except Exception:
            pass

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._log(f"[mqtt_inbound] connected; subscribing to {self._topic}")
            try:
                client.subscribe(self._topic, qos=0)
            except Exception as e:
                self._log(f"[mqtt_inbound] subscribe error: {e}")
        else:
            self._log(f"[mqtt_inbound] connect rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._log(f"[mqtt_inbound] disconnected rc={rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            self._log("[mqtt_inbound] JSON decode error")
            return

        with self._lock:
            self._last_payload = payload
            self._last_seen_ts = time.time()

    # ---- Public API --------------------------------------------------------

    def get_power_context(self) -> Optional[PowerContext]:
        """
        Returns a PowerContext if we have fresh data; None if stale/not yet received.
        """
        with self._lock:
            age = time.time() - self._last_seen_ts
            if self._last_seen_ts == 0 or age > self._stale_after:
                return None

            # Extract, divide by 10 as per your value_templates
            get = self._last_payload.get
            def f(key: str) -> float:
                try:
                    return float(get(key, 0)) / 10.0
                except Exception:
                    return 0.0

            batt_discharge_w = max(0.0, f("pdischarge1"))
            load_w           = max(0.0, f("plocaloadr"))
            import_w         = max(0.0, f("pactouserr"))
            export_w         = max(0.0, f("pactogridr"))

            # Prefer real solar from HA (if supplied & fresh), otherwise estimate
            solar_from_ha = None
            if self._solar_supplier:
               try:
                   solar_from_ha = self._solar_supplier()
               except Exception:
                   solar_from_ha = None
            if solar_from_ha is not None:
                 solar_w = max(0.0, float(solar_from_ha))
            else:
                 solar_w = export_w + load_w - import_w - batt_discharge_w
                 if solar_w < 0:
                     solar_w = 0.0
    
            return PowerContext(
                solar_w=solar_w,
                battery_discharge_w=batt_discharge_w,
                grid_import_w=import_w,
                load_w=load_w,
            )

    def get_debug_snapshot(self) -> Optional[dict]:
        """Return a debug dict with raw GROTT fields and solar source."""
        with self._lock:
            if self._last_seen_ts == 0 or (time.time() - self._last_seen_ts) > self._stale_after:
                return None
            get = self._last_payload.get
            def f(key: str) -> float:
                try:
                    return float(get(key, 0)) / 10.0
                except Exception:
                    return 0.0
            batt_discharge_w = max(0.0, f("pdischarge1"))
            load_w           = max(0.0, f("plocaloadr"))
            import_w         = max(0.0, f("pactouserr"))
            export_w         = max(0.0, f("pactogridr"))

            # compute both, and show which is used
            est = export_w + load_w - import_w - batt_discharge_w
            if est < 0:
                est = 0.0
            src = "estimate"
            solar = est
            if self._solar_supplier:
                try:
                    ha_val = self._solar_supplier()
                except Exception:
                    ha_val = None
                if ha_val is not None:
                    solar = max(0.0, float(ha_val))
                    src = "ha"
            return {
                "battery_discharge_w": batt_discharge_w,
                "load_w": load_w,
                "grid_import_w": import_w,
                "grid_export_w": export_w,
                "solar_w": solar,
                "solar_source": src
            }
