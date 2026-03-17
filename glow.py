import json
from pathlib import Path
from typing import Any, Dict

DATA_FILE = Path("/data/tariff_store.json")

DEFAULT = {
    "last_update": None,
    "elec": {
        "last_offpeak_rate": 0.0,
        "last_peak_rate": 0.0,
        "standing_charge": 0.0
    },
    "gas": {
        "last_rate": 0.0,
        "standing_charge": 0.0
    },
    "intelligent": {
        "windows": []
    }
}

def load() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        save(DEFAULT)
    return json.loads(DATA_FILE.read_text())

def save(data: Dict[str, Any]):
    DATA_FILE.write_text(json.dumps(data, indent=2))
