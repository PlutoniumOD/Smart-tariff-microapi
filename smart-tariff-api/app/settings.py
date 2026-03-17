#!/usr/bin/env bash
import json
import os
from dateutil import tz

# HA Add-on passes options at /data/options.json
OPTIONS_PATH = os.getenv("ADDON_OPTIONS_PATH", "/data/options.json")

def load_options():
    with open(OPTIONS_PATH, "r") as f:
        return json.load(f)

def get_zone(tz_name: str):
    return tz.gettz(tz_name)
