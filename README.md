# Smart Tariff Micro‑API (Home Assistant Add‑on)

A local micro‑API that replaces flaky tariff/rate handling by exposing **clean REST (and optional MQTT)** endpoints for:

- **Electricity & Gas**: current rate (GBP/kWh), standing charge (GBP/day), half‑hourly consumption, daily cost
- **Tariffs**: Economy 7 (DST‑aware), EV windowed plans (Go/UW EV/OVO Power Move), future Agile/Tracker & Intelligent overlays
- **Resilience**: bridges DCC/Bright delays using window logic + last‑known rates, then overwrites with live API values as they arrive

> Notes:
> - The Bright/Glowmarkt API returns cost units in **pence**; this service converts to **GBP** for HA sensors and the Energy Dashboard.
> - DCC/Bright data arrives on **half‑hour intervals** and can be delayed; this service aligns polling at `:00/:30` and falls back gracefully.

## Features

- **Home Assistant Add‑on** (Supervisor)
- **FastAPI** on port **8787**
- **pyglowmarkt** client for Bright/Glowmarkt
- **APScheduler** polling at `:00` & `:30`
- **DST-aware** windows for E7 & EV
- **Optional MQTT** publishing

## Install (Custom Add‑on Repository)

1. Add this repository in **Home Assistant → Settings → Add‑ons → Add‑on Store → ⋮ → Repositories**  
   `https://github.com/PlutoniumOD/Smart-tariff-microapi`
2. Install **Smart Tariff Micro‑API**, open **Configuration**, set:
   - `glowmarkt.email`, `glowmarkt.password`
   - `tariff.mode: e7` (default; windows set automatically by DST)
   - `tariff.timezone: "Europe/London"`
   - Enable MQTT if you want topics published
3. Start the add‑on.

## API Endpoints (REST)

- `GET /health` — service status
- `POST /refresh-data` — force a Bright/DCC poll now
- `GET /electricity/current-rate` → `{ rate, standing_charge, updated_utc, intelligent_windows }`
- `GET /gas/current-rate` → `{ rate, standing_charge, updated_utc }`
- `GET /electricity/consumption?hours=48&period=PT30M` → half‑hourly kWh
- **Debug (optional)**  
  - `GET /debug/entities` — show Bright virtual entities/resources  
  - `GET /debug/tariff/electricity` — show current tariff (GBP)

All money values are **GBP**:
- `rate` → **GBP/kWh**  
- `standing_charge` → **GBP/day**

## MQTT Topics (if enabled)

- `smartenergy/electricity/current_rate`
- `smartenergy/electricity/tariff`
- `smartenergy/electricity/consumption`
- `smartenergy/gas/current_rate`
- `smartenergy/gas/tariff`

## Configuration Options

```yaml
glowmarkt:
  email: "name@example.com"
  password: "••••••••"

tariff:
  mode: "e7"                   # e7 | go | uw_ev | ovo_powermove | flex | intelligent
  e7_offpeak_start_gmt: "00:30"  # E7 base (GMT); auto-shifts in BST
  e7_offpeak_end_gmt: "07:30"
  timezone: "Europe/London"
  # Windowed EV modes (fill in when you switch):
  go_windows_gmt: []           # e.g., ["00:30","04:30"]
  uw_ev_windows_gmt: []
  ovo_windows_gmt: []

octopus:
  api_key: ""                  # (Future) Agile/Tracker/Intelligent
  account_id: ""

intelligent:
  allow_post_schedule: true    # POST /tariff/intelligent/schedule

mqtt:
  enabled: true
  host: "core-mosquitto"
  port: 1883
  username: ""
  password: ""
  topic_prefix: "smartenergy"
