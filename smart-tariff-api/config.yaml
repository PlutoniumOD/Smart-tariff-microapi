name: Smart Tariff Micro‑API
version: "0.1.0"
slug: smart_tariff_api
description: "Local micro‑API for Bright/DCC electricity & gas tariffs, consumption, costs. E7 + EV + Intelligent support with DST, MQTT, and REST."
arch:
  - aarch64
  - amd64
startup: services
init: false
boot: auto
ports:
  8787/tcp: 8787
map:
  - data:rw
options:
  glowmarkt:
    email: ""
    password: ""
  tariff:
    mode: "e7"
    e7_offpeak_start_gmt: "00:30"
    e7_offpeak_end_gmt: "07:30"
    timezone: "Europe/London"
  octopus:
    api_key: ""
    account_id: ""
  intelligent:
    allow_post_schedule: true
  mqtt:
    enabled: true
    host: "core-mosquitto"
    port: 1883
    username: ""
    password: ""
    topic_prefix: "smartenergy"
schema:
  glowmarkt:
    email: str
    password: str
  tariff:
    mode: list(e7|go|flex|uw_ev|ovo_powermove|agile|tracker|intelligent)
    e7_offpeak_start_gmt: str
    e7_offpeak_end_gmt: str
    timezone: str
  octopus:
    api_key: str?
    account_id: str?
  intelligent:
    allow_post_schedule: bool
  mqtt:
    enabled: bool
    host: str
    port: int
    username: str?
    password: str?
    topic_prefix: str
