# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for controlling Mitsubishi Electric climate control systems through the Kumo Cloud API. The integration is distributed via HACS and uses the Home Assistant config flow pattern for setup.

**Domain**: `kumo_cloud`
**Integration Name**: Mitsubishi Comfort
**Min Home Assistant Version**: 2023.1.0
**HACS Version**: 1.6.0+

## Architecture

### Component Structure

The integration follows Home Assistant's standard custom component architecture:

- **`__init__.py`**: Entry point, coordinator setup, and base device class
  - `async_setup_entry()`: Authenticates with API, creates coordinator, sets up platforms
  - `KumoCloudDataUpdateCoordinator`: Manages data polling (60s intervals), handles zones/devices/profiles
  - `KumoCloudDevice`: Base class providing zone/device data access and command sending

- **`api.py`**: Kumo Cloud API client
  - `KumoCloudAPI`: Async HTTP client with token management
  - Token refresh logic (20-minute intervals with 5-minute expiry margin)
  - Endpoints: login, refresh, account info, sites, zones, device details, device profiles, send commands

- **`climate.py`**: Climate entity implementation
  - `KumoCloudClimate`: CoordinatorEntity that maps Kumo Cloud state to Home Assistant climate entity
  - Dynamic feature detection from device profiles (fan modes, swing modes, HVAC modes)
  - Immediate refresh after commands via `coordinator.async_refresh_device()`

- **`config_flow.py`**: Configuration flow
  - Two-step flow: credentials → site selection (if multiple sites)
  - Stores access/refresh tokens in config entry
  - Reauth flow support

- **`const.py`**: Constants and enums

### Key Data Flow

1. **Coordinator polls every 60s**: Fetches zones for site, then device details + profiles in parallel
2. **Data structure**: `zones` list, `devices` dict by serial, `device_profiles` dict by serial
3. **State updates**: Entity properties read from coordinator's cached data
4. **Commands**: `device.send_command()` → API call → 1s wait → `coordinator.async_refresh_device()` → update listeners
5. **Zone vs Device data**: Zone data (from `/zones` endpoint) and device data (from `/devices/{serial}`) both contain state; device data is more current when available

### Token Management

- Access tokens expire every 20 minutes
- `_ensure_token_valid()` proactively refreshes 5 minutes before expiry
- Coordinator catches `KumoCloudAuthError` and attempts refresh once before failing
- Tokens stored in config entry data

### Device Capabilities

Device profiles (`get_device_profile()`) determine supported features:
- `numberOfFanSpeeds`: Enables fan mode feature
- `hasVaneSwing`, `hasVaneDir`: Enable swing mode feature
- `hasModeHeat`, `hasModeDry`, `hasModeVent`: Enable corresponding HVAC modes
- `minimumSetPoints`, `maximumSetPoints`: Temperature ranges

## Development

### No Build/Test Commands

This is a Python-based Home Assistant integration with no build system, test suite, or linting configured in the repository. Development is done directly with Python 3.11+ (Home Assistant 2023.1.0+ requirement).

### Testing Approach

Since there are no automated tests:
1. Test in a Home Assistant development environment
2. Enable debug logging: `"kumo_cloud": "debug"` in `configuration.yaml`
3. Monitor logs for issues with authentication, polling, or commands
4. Verify via UI that climate entities respond correctly to commands

### Making Changes

- **API changes**: Modify `api.py` methods, ensure error handling for auth/connection
- **Climate features**: Update `climate.py`, check device profile capabilities
- **New entities**: Add platform to `PLATFORMS` in `__init__.py`, create new platform file
- **Config changes**: Update `config_flow.py` and potentially migration logic in `__init__.py`

### API Information

Unofficial Kumo Cloud API v3:
- Base URL: `https://app-prod.kumocloud.com`
- App Version Header: `x-app-version: 3.0.9`
- Authentication: Bearer token (from login/refresh endpoints)
- All endpoints return JSON except commands (may return empty response)

### Important Implementation Details

- Always use `coordinator.async_refresh_device(device_serial)` after commands for immediate UI updates
- The `operationMode: "off"` is how devices are turned off (not a `power: 0` field alone)
- Auto mode (HEAT_COOL) requires both `spHeat` and `spCool` setpoints
- Temperature step is 0.5°C
- When sending commands, include current setpoints to prevent them from being reset