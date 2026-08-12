# Changelog

> Note: Earlier development builds used inconsistent version numbers.
> Version history has been normalised to the 0.1.x development series.

## [0.1.3] - 2026-08-12

### Added
- Added Home Assistant Energy Dashboard-compatible MQTT metadata.
- Added `device_class`, `state_class`, and display precision to usage and cost sensors.
- Added MQTT connection status and manual rediscovery debug endpoints.
- Added delayed MQTT Discovery publishing after broker connection.
- Added broker acknowledgement checks for MQTT Discovery messages.
- Added stable MQTT device identifiers for electricity and gas devices.
- Added Docker build-time Python syntax validation.

### Changed
- Increased electricity and gas usage precision to three decimal places.
- Improved MQTT connection diagnostics without exposing credentials.
- Updated the Dockerfile for the current Home Assistant app build process.
- Replaced the deprecated `BUILD_FROM` dependency with an explicit Home Assistant base image.

### Fixed
- Fixed MQTT devices not returning after deletion from Home Assistant.
- Fixed MQTT Discovery publishing before the broker connection was ready.
- Fixed missing MQTT credentials after updating the app.
- Fixed discovery metadata required for Energy Dashboard statistics.
- Fixed several Python dictionary and indentation errors identified during build validation.

## [0.1.2] - 2026-08-11

### Added
- Added retained MQTT Discovery republishing.
- Added MQTT publisher connection checks before discovery publication.
- Added source build markers and copied-file verification.
- Added Docker build diagnostics for confirming the correct `main.py` is packaged.
- Added Python compilation checks to prevent broken images from being created.

### Changed
- Updated MQTT Discovery payload generation to support optional device and state classes.
- Improved MQTT publishing logs and error reporting.
- Updated application packaging for Home Assistant Supervisor changes.
- Updated application versioning to force repository updates to be downloaded correctly.

### Fixed
- Fixed stale source files being rebuilt under an unchanged application version.
- Fixed the app starting with invalid Python syntax.
- Fixed the Docker build failure caused by an empty `BUILD_FROM` argument.
- Fixed MQTT Discovery configuration publication reporting success without confirming delivery.

## [0.1.1] - 2026-03-27

### Added
- Added inbound MQTT monitoring of GROTT Growatt power data.
- Added battery discharge, grid import, export, and local-load monitoring.
- Added SolarEdge AC power retrieval through the Home Assistant Supervisor API.
- Added estimated solar power fallback when the SolarEdge entity is unavailable.
- Added debug endpoints for tariff windows, power flow, solar data, MQTT state, and persistent storage.
- Added a current-rate heartbeat publisher for prompt tariff changes at configured boundaries.
- Added persistent store inspection, reset, and configuration synchronisation tools.
- Added configurable tariff bucket locking.

### Changed
- Made Economy 7 current-rate selection time-based and DST-aware.
- Changed Bright/DCC tariff data to diagnostic input rather than the sole source of truth.
- Separated peak and off-peak stored tariff buckets.
- Improved handling of missing, zero, stale, and delayed Bright consumption data.
- Prevented derived rates from being used when solar generation or battery discharge obscures grid consumption.

### Fixed
- Fixed peak and off-peak rate flip-flopping.
- Fixed incorrect tariff inference during solar generation and battery discharge.
- Fixed Bright fallback values being mistaken for genuinely derived tariff rates.
- Fixed peak and off-peak bucket contamination.
- Fixed delayed MQTT current-rate changes at tariff transition times.
- Fixed SolarEdge Supervisor token discovery in s6 container environments.
- Fixed tariff values remaining at zero after persistent-store recreation.
  
## 0.0.2 (2026‑03‑19)
- Added MQTT Discovery for Electricity & Gas
- Added Electricity Usage Today / Cost Today sensors
- Added Gas Usage Today / Cost Today sensors
- Fixed timezone handling
- Fixed MQTT prefix consistency
- Added two‑device layout for HA
- Improved logging
- Patched cost_today publishing

## 0.0.1
- Added E7 DST‑aware switching
- Added rate derivation via cost/consumption pairing
- Added debug endpoints

## 0.0.0
- Initial add-on release
- Basic tariff engine
- Glowmarkt integration
- REST endpoints
