
# Smart Tariff Micro‑API (Home Assistant Add‑on)

<p align="center">
  <img src="https://img.shields.io/badge/Home%20Assistant-Addon-blue" height="28" />
  <img src="https://img.shields.io/badge/MQTT-Discovery-green" height="28" />
  <img src="https://img.shields.io/badge/Python-3.12-blue" height="28" />
  <img src="https://img.shields.io/badge/Glowmarkt-DCC-orange" height="28" />
  <img src="https://img.shields.io/badge/License-MIT-green" height="28" />
</p>

A lightweight tariff and energy‑cost engine for Home Assistant.  
Designed to be resilient against Bright/DCC delays, provide accurate E7/EV rate switching, and publish clean MQTT sensors for the Energy Dashboard.

This add‑on polls Glowmarkt (Bright App) DCC virtual meter data every 30 minutes, derives the **current unit rate**, splits usage into peak/off‑peak blocks, computes **daily usage & cost**, and publishes everything via **MQTT Discovery**.

---

# 🔌 Features

- ⚡ **Electricity & Gas tariff engine**
- 🕑 **E7, Go, UW EV, OVO**, windowed tariffs  
- 🕧 **DST‑aware off‑peak switching**
- 🧮 **Live tariff derivation** from cost/consumption  
- 💬 **MQTT Discovery** (no YAML needed)
- 📊 **Energy Dashboard compatible**
- 🔍 Debug endpoints for investigation
- 💾 Persistent store of last-known rates

---

# 🗺️ Architecture Overview


All computations occur locally, HA simply consumes the MQTT sensors.

---

# 📦 MQTT Sensors Created

### **Electricity (Device: Smart Tariff Micro‑API — Electricity)**  
- `electricity_current_rate`  
- `electricity_peak_rate`  
- `electricity_offpeak_rate`  
- `electricity_standing_charge`  
- `electricity_usage_today`  
- `electricity_cost_today`  

### **Gas (Device: Smart Tariff Micro‑API — Gas)**  
- `gas_current_rate`  
- `gas_standing_charge`  
- `gas_usage_today`  
- `gas_cost_today`  

All sensors include:

- Correct units (GBP, kWh)  
- Proper rounding (GBP: 2dp, kWh: 1dp)  
- Auto attributes  
- Retained state  

---

# ⚙️ Installation

1. Go to **Settings → Add‑ons → Add‑on Store**
2. Click **⋮ → Repositories**
3. Add: https://github.com/PlutoniumOD/Smart-tariff-microapi
4. Install the **Smart Tariff Micro‑API** add-on  
5. Open the add‑on → **Configuration**  
6. Enter Bright/Glowmarkt credentials  
7. Enable MQTT  
8. Start the add‑on  
9. Sensors will appear automatically in HA

---
## API Endpoints (REST provided as legacy)

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


<img width="555" height="779" alt="image" src="https://github.com/user-attachments/assets/7a0554a0-c11d-4208-89e8-85f1fa4d9ce1" />
<img width="553" height="682" alt="image" src="https://github.com/user-attachments/assets/fd093705-b293-4294-912a-c4caf9783112" />


# 🧰 Configuration Options

Inside the add-on config panel:

```yaml
glowmarkt:
  email: "name@example.com"
  password: "..."

mqtt:
  enabled: true
  host: "core-mosquitto"
  port: 1883
  username: "mqtt_user"
  password: "mqtt_password"
  topic_prefix: "smartenergy"

tariff:
  mode: "e7"               # e7 | go | uw_ev | ovo_powermove | flex | intelligent
  e7_offpeak_start_gmt: "00:30"
  e7_offpeak_end_gmt: "07:30"
  timezone: "Europe/London"
  go_windows_gmt: []
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
```
## Credits

Inspiration: HandyHat, Jonandel

DCC data via Glowmarkt (Bright app)
