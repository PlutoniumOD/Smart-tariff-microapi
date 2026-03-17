import json
from pathlib import Path
from typing import Any, Dict

DATA_FILE = Path("/data/tariff_store.json")

DEFAULT: Dict[str, Any] = {
    "last_update": None,
    "elec": {
        "last_offpeak_rate": 0.0,
        "last_peak_rate": 0.0,
        "standing_charge": 0.0,
    },
    "gas": {
        "last_rate": 0.0,
        "standing_charge": 0.0,
    },
    "intelligent": {
        "windows": []  # list of {"start_iso": "...", "end_iso": "..."}
    },
}

def load() -> Dict[str, Any]:
    """Load persisted store from /data; create with defaults if missing."""
    if not DATA_FILE.exists():
        save(DEFAULT)
    try:
        return json.loads(DATA_FILE.read_text())
    except Exception:
        # If the file is unreadable/corrupt, recreate it
        save(DEFAULT)
        return json.loads(DATA_FILE.read_text())

def save(data: Dict[str, Any]) -> None:
    """Persist store back to /data."""
    DATA_FILE.write_text(json.dumps(data, indent=2))
