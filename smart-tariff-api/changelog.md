# Changelog

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
- 
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
