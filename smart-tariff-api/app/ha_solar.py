
#app/ha_solar.py
#
# Polls Home Assistant for real-time SolarEdge AC power (W).
# Supports:
#   - Supervisor proxy:  http://supervisor/core/api/states/<entity_id>
#       Header: Authorization: Bearer $SUPERVISOR_TOKEN
#   - Core HTTP API:     <base_url>/api/states/<entity_id>
#       Header: Authorization: Bearer <long-lived-token>
#
# Returns latest solar W (float) or None if stale/unavailable.

import os
import time
import threading
from typing import Optional, Callable
import requests  # Ensure available in Dockerfile/requirements

class HASolarPoller:
    def __init__(
        self,
        entity_id: str = "sensor.solaredge_ac_power",
        use_supervisor: bool = True,
        base_url: Optional[str] = None,     # e.g. http://homeassistant.local:8123
        token: Optional[str] = None,        # long-lived token if not using supervisor
        interval_secs: int = 15,
        stale_after_secs: int = 60,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        self._entity_id = entity_id
        self._use_supervisor = use_supervisor
        self._base_url = base_url
        self._token = token
        self._interval = interval_secs
        self._stale_after = stale_after_secs
        self._log = on_log or (lambda s: None)

        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._last_val: Optional[float] = None
        self._last_ts: float = 0.0

        # Supervisor token (if running as HA add-on)
        self._sup_token = os.environ.get("SUPERVISOR_TOKEN")

    def start(self):
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._loop, name="ha-solar", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop_evt.is_set():
            try:
                val = self._fetch_once()
                if val is not None and val >= 0:
                    self._last_val = float(val)
                    self._last_ts = time.time()
            except Exception as e:
                self._log(f"[ha_solar] fetch error: {e}")
            # sleep small intervals so we’re responsive on stop
            for _ in range(self._interval):
                if self._stop_evt.is_set():
                    break
                time.sleep(1)

    def _fetch_once(self) -> Optional[float]:
        if self._use_supervisor:
            if not self._sup_token:
                self._log("[ha_solar] SUPERVISOR_TOKEN missing; cannot use supervisor proxy")
                return None
            url = f"http://supervisor/core/api/states/{self._entity_id}"
            headers = {"Authorization": f"Bearer {self._sup_token}"}
        else:
            if not (self._base_url and self._token):
                self._log("[ha_solar] base_url or token missing for core API mode")
                return None
            url = f"{self._base_url.rstrip('/')}/api/states/{self._entity_id}"
            headers = {"Authorization": f"Bearer {self._token}"}

        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code != 200:
            self._log(f"[ha_solar] HTTP {r.status_code} {r.text[:120]}")
            return None

        js = r.json()
        # HA state is a string; try float
        state = js.get("state")
        try:
            val = float(state)
            return max(val, 0.0)
        except Exception:
            return None

    def get_solar_w(self) -> Optional[float]:
        if self._last_ts <= 0:
            return None
        age = time.time() - self._last_ts
        if age > self._stale_after:
            return None
        return self._last_val
