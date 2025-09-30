"""Platform for Kumo Cloud climate integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KumoCloudDataUpdateCoordinator, KumoCloudDevice
from .const import (
    DOMAIN,
    OPERATION_MODE_OFF,
    OPERATION_MODE_COOL,
    OPERATION_MODE_HEAT,
    OPERATION_MODE_DRY,
    OPERATION_MODE_VENT,
    OPERATION_MODE_AUTO,
    OPERATION_MODE_AUTO_COOL,
    OPERATION_MODE_AUTO_HEAT,
    FAN_SPEED_AUTO,
    FAN_SPEED_LOW,
    FAN_SPEED_MEDIUM,
    FAN_SPEED_HIGH,
    FAN_SPEED_POWERFUL,
    AIR_DIRECTION_AUTO,
    AIR_DIRECTION_HORIZONTAL,
    AIR_DIRECTION_MIDHORIZONTAL,
    AIR_DIRECTION_MIDPOINT,
    AIR_DIRECTION_MIDVERTICAL,
    AIR_DIRECTION_VERTICAL,
    AIR_DIRECTION_SWING,
)

_LOGGER = logging.getLogger(__name__)

# Mapping from Kumo Cloud operation modes to Home Assistant HVAC modes
KUMO_TO_HVAC_MODE = {
    OPERATION_MODE_OFF: HVACMode.OFF,
    OPERATION_MODE_COOL: HVACMode.COOL,
    OPERATION_MODE_HEAT: HVACMode.HEAT,
    OPERATION_MODE_DRY: HVACMode.DRY,
    OPERATION_MODE_VENT: HVACMode.FAN_ONLY,
    OPERATION_MODE_AUTO: HVACMode.HEAT_COOL,
    OPERATION_MODE_AUTO_COOL: HVACMode.HEAT_COOL,
    OPERATION_MODE_AUTO_HEAT: HVACMode.HEAT_COOL,
}

# Reverse mapping
HVAC_TO_KUMO_MODE = {v: k for k, v in KUMO_TO_HVAC_MODE.items()}

# Air direction mappings - basic units
KUMO_AIR_DIRECTIONS_BASIC = [
    AIR_DIRECTION_AUTO,
    AIR_DIRECTION_HORIZONTAL,
    AIR_DIRECTION_VERTICAL,
    AIR_DIRECTION_SWING,
]

# Air direction mappings - MLZ units (1-way ceiling cassette)
KUMO_AIR_DIRECTIONS_MLZ = [
    AIR_DIRECTION_AUTO,
    AIR_DIRECTION_HORIZONTAL,
    AIR_DIRECTION_MIDHORIZONTAL,
    AIR_DIRECTION_MIDPOINT,
    AIR_DIRECTION_MIDVERTICAL,
    AIR_DIRECTION_VERTICAL,
    AIR_DIRECTION_SWING,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kumo Cloud climate devices."""
    coordinator: KumoCloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for zone in coordinator.zones:
        if "adapter" in zone and zone["adapter"]:
            device_serial = zone["adapter"]["deviceSerial"]
            zone_id = zone["id"]

            device = KumoCloudDevice(coordinator, zone_id, device_serial)
            entities.append(KumoCloudClimate(device))

    async_add_entities(entities)


class KumoCloudClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Kumo Cloud climate device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: KumoCloudDevice) -> None:
        """Initialize the climate device."""
        super().__init__(device.coordinator)
        self.device = device
        self._attr_unique_id = device.unique_id

        # Set up supported features based on device profile
        self._setup_supported_features()

    def _setup_supported_features(self) -> None:
        """Set up supported features based on device capabilities."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

        profile = self.device.profile_data
        if profile:
            profile_data = profile[0] if isinstance(profile, list) else profile

            # Check for fan speed support
            if profile_data.get("numberOfFanSpeeds", 0) > 0:
                features |= ClimateEntityFeature.FAN_MODE

            # Check for vane/swing support
            if profile_data.get("hasVaneSwing", False):
                features |= ClimateEntityFeature.SWING_MODE

            if profile_data.get("hasVaneDir", False):
                features |= ClimateEntityFeature.SWING_MODE

            # Add target temperature range support for auto mode
            if profile_data.get("hasModeHeat", False):
                features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

        self._attr_supported_features = features

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return self.hass.config.units.temperature_unit

    def _celsius_to_user_unit(self, celsius_temp: float | None) -> float | None:
        """Convert Celsius temperature to user's configured unit, rounding to nearest whole degree."""
        if celsius_temp is None:
            return None

        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            fahrenheit = (celsius_temp * 9 / 5) + 32
            return round(fahrenheit)

        return celsius_temp

    def _user_unit_to_celsius(self, temp: float | None) -> float | None:
        """Convert user's temperature unit to Celsius."""
        if temp is None:
            return None

        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return (temp - 32) * 5 / 9

        return temp

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        zone_data = self.device.zone_data
        device_data = self.device.device_data

        model = device_data.get("model", {}).get("materialDescription", "Unknown Model")

        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_serial)},
            name=zone_data.get("name", "Kumo Cloud Device"),
            manufacturer="Mitsubishi Electric",
            model=model,
            sw_version=device_data.get("model", {}).get("serialProfile"),
            serial_number=device_data.get("serialNumber"),
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        adapter = self.device.zone_data.get("adapter", {})
        celsius_temp = adapter.get("roomTemp")
        return self._celsius_to_user_unit(celsius_temp)

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        adapter = self.device.zone_data.get("adapter", {})
        device_data = self.device.device_data
        hvac_mode = self.hvac_mode

        celsius_temp = None
        if hvac_mode == HVACMode.COOL:
            celsius_temp = device_data.get("spCool", adapter.get("spCool"))
        elif hvac_mode == HVACMode.HEAT:
            celsius_temp = device_data.get("spHeat", adapter.get("spHeat"))
        elif hvac_mode == HVACMode.HEAT_COOL:
            # For auto mode, return None since we use target_temperature_low/high
            return None

        return self._celsius_to_user_unit(celsius_temp)

    @property
    def target_temperature_low(self) -> float | None:
        """Return the low target temperature for auto mode."""
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None

        adapter = self.device.zone_data.get("adapter", {})
        device_data = self.device.device_data
        celsius_temp = device_data.get("spHeat", adapter.get("spHeat"))
        return self._celsius_to_user_unit(celsius_temp)

    @property
    def target_temperature_high(self) -> float | None:
        """Return the high target temperature for auto mode."""
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None

        adapter = self.device.zone_data.get("adapter", {})
        device_data = self.device.device_data
        celsius_temp = device_data.get("spCool", adapter.get("spCool"))
        return self._celsius_to_user_unit(celsius_temp)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        # Check both adapter (zone) and device data for most current status
        adapter = self.device.zone_data.get("adapter", {})
        device_data = self.device.device_data

        # Use device data if available (more current), otherwise use adapter data
        operation_mode = device_data.get(
            "operationMode", adapter.get("operationMode", OPERATION_MODE_OFF)
        )
        power = device_data.get("power", adapter.get("power", 0))

        # If power is 0, device is off regardless of operation mode
        if power == 0:
            return HVACMode.OFF

        return KUMO_TO_HVAC_MODE.get(operation_mode, HVACMode.OFF)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        modes = [HVACMode.OFF]

        profile = self.device.profile_data
        if profile:
            profile_data = profile[0] if isinstance(profile, list) else profile

            # Add modes based on device capabilities
            if profile_data.get("hasModeHeat", False):
                modes.append(HVACMode.HEAT)

            modes.append(HVACMode.COOL)  # All units should support cool

            if profile_data.get("hasModeDry", False):
                modes.append(HVACMode.DRY)

            if profile_data.get("hasModeVent", False):
                modes.append(HVACMode.FAN_ONLY)

            # Auto mode if device supports both heat and cool
            if profile_data.get("hasModeHeat", False):
                modes.append(HVACMode.HEAT_COOL)

        return modes

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action based on actual device status."""
        hvac_mode = self.hvac_mode
        if hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        # Check both adapter (zone) and device data for most current status
        adapter = self.device.zone_data.get("adapter", {})
        device_data = self.device.device_data

        # Use device data if available (more current), otherwise use adapter data
        power = device_data.get("power", adapter.get("power", 0))
        operation_mode = device_data.get(
            "operationMode", adapter.get("operationMode", OPERATION_MODE_OFF)
        )

        if power == 0:
            return HVACAction.OFF

        # If device is on and has a valid operation mode, show it as active
        if operation_mode in (OPERATION_MODE_HEAT, OPERATION_MODE_AUTO_HEAT):
            # For heating mode, show as heating if power is on
            return HVACAction.HEATING
        elif operation_mode in (OPERATION_MODE_COOL, OPERATION_MODE_AUTO_COOL):
            # For cooling mode, show as cooling if power is on
            return HVACAction.COOLING
        elif operation_mode == OPERATION_MODE_DRY:
            return HVACAction.DRYING
        elif operation_mode == OPERATION_MODE_VENT:
            return HVACAction.FAN
        elif operation_mode in (OPERATION_MODE_AUTO, OPERATION_MODE_AUTO_COOL, OPERATION_MODE_AUTO_HEAT):
            # For auto mode, determine action based on current temperature vs setpoint range
            current_temp = self.current_temperature
            sp_heat = adapter.get("spHeat", device_data.get("spHeat"))
            sp_cool = adapter.get("spCool", device_data.get("spCool"))

            if current_temp is not None and sp_heat is not None and sp_cool is not None:
                if current_temp >= sp_cool:
                    return HVACAction.COOLING
                elif current_temp <= sp_heat:
                    return HVACAction.HEATING

            # Default to idle for auto mode if we can't determine
            return HVACAction.IDLE

        # If power is on but we can't determine the action, show as idle
        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str | None:
        """Return current fan mode."""
        # Check device data first, then adapter data
        device_data = self.device.device_data
        adapter = self.device.zone_data.get("adapter", {})
        return device_data.get("fanSpeed", adapter.get("fanSpeed"))

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        profile = self.device.profile_data
        if not profile:
            return None

        profile_data = profile[0] if isinstance(profile, list) else profile
        num_fan_speeds = profile_data.get("numberOfFanSpeeds", 0)

        if num_fan_speeds == 0:
            return None

        # Return fan modes based on number of speeds supported
        modes = []

        # Add auto mode if supported
        if profile_data.get("hasFanSpeedAuto", False):
            modes.append(FAN_SPEED_AUTO)

        if num_fan_speeds >= 1:
            modes.append(FAN_SPEED_LOW)
        if num_fan_speeds >= 2:
            modes.append(FAN_SPEED_MEDIUM)
        if num_fan_speeds >= 3:
            modes.append(FAN_SPEED_HIGH)

        # Add powerful mode (4th speed level)
        if num_fan_speeds >= 4:
            modes.append(FAN_SPEED_POWERFUL)

        return modes

    @property
    def swing_mode(self) -> str | None:
        """Return current swing mode."""
        # Check device data first, then adapter data
        device_data = self.device.device_data
        adapter = self.device.zone_data.get("adapter", {})
        return device_data.get("airDirection", adapter.get("airDirection"))

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes."""
        profile = self.device.profile_data
        if not profile:
            return None

        profile_data = profile[0] if isinstance(profile, list) else profile

        modes = []
        if profile_data.get("hasVaneDir", False) or profile_data.get(
            "hasVaneSwing", False
        ):
            # Check if this is an MLZ unit (1-way ceiling cassette)
            device_data = self.device.device_data
            model_number = device_data.get("modelNumber", "")

            if model_number.startswith("MLZ"):
                # MLZ units support more granular vane positions
                modes.extend(KUMO_AIR_DIRECTIONS_MLZ)
            else:
                # Other units use basic air directions
                modes.extend(KUMO_AIR_DIRECTIONS_BASIC)

        return modes if modes else None

    @property
    def min_temp(self) -> float:
        """Return minimum temperature."""
        profile = self.device.profile_data
        celsius_min = 16.0
        if profile:
            profile_data = profile[0] if isinstance(profile, list) else profile
            min_setpoints = profile_data.get("minimumSetPoints", {})
            # Return the minimum of heat and cool setpoints
            celsius_min = min(min_setpoints.get("heat", 16), min_setpoints.get("cool", 16))
        return self._celsius_to_user_unit(celsius_min) or 16.0

    @property
    def max_temp(self) -> float:
        """Return maximum temperature."""
        profile = self.device.profile_data
        celsius_max = 30.0
        if profile:
            profile_data = profile[0] if isinstance(profile, list) else profile
            max_setpoints = profile_data.get("maximumSetPoints", {})
            # Return the maximum of heat and cool setpoints
            celsius_max = max(max_setpoints.get("heat", 30), max_setpoints.get("cool", 30))
        return self._celsius_to_user_unit(celsius_max) or 30.0

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        # For Fahrenheit, use 1 degree steps (rounded)
        # For Celsius, keep 0.5 degree steps
        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return 1.0
        return 0.5  # Kumo Cloud typically supports 0.5 degree steps

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.available and self.coordinator.last_update_success

    async def _send_command_and_refresh(self, commands: dict[str, Any]) -> None:
        """Send command and ensure fresh status update."""
        await self.device.send_command(commands)
        # The device.send_command method now handles refreshing the device status
        # Also trigger a state update for this entity to reflect changes immediately
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._send_command_and_refresh({"operationMode": OPERATION_MODE_OFF})
        else:
            kumo_mode = HVAC_TO_KUMO_MODE.get(hvac_mode)
            if kumo_mode:
                commands = {"operationMode": kumo_mode}

                # Include current setpoints to maintain them
                adapter = self.device.zone_data.get("adapter", {})
                device_data = self.device.device_data

                # Use device data if available, otherwise adapter data
                sp_cool = device_data.get("spCool", adapter.get("spCool"))
                sp_heat = device_data.get("spHeat", adapter.get("spHeat"))

                if sp_cool is not None:
                    commands["spCool"] = sp_cool
                if sp_heat is not None:
                    commands["spHeat"] = sp_heat

                await self._send_command_and_refresh(commands)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get("target_temp_low")
        target_temp_high = kwargs.get("target_temp_high")

        # Convert temperatures from user unit to Celsius
        target_temp_celsius = self._user_unit_to_celsius(target_temp)
        target_temp_low_celsius = self._user_unit_to_celsius(target_temp_low)
        target_temp_high_celsius = self._user_unit_to_celsius(target_temp_high)

        hvac_mode = self.hvac_mode
        commands = {}

        adapter = self.device.zone_data.get("adapter", {})
        device_data = self.device.device_data

        if hvac_mode == HVACMode.COOL and target_temp_celsius is not None:
            commands["spCool"] = target_temp_celsius
            # Maintain heat setpoint
            sp_heat = device_data.get("spHeat", adapter.get("spHeat"))
            if sp_heat is not None:
                commands["spHeat"] = sp_heat
        elif hvac_mode == HVACMode.HEAT and target_temp_celsius is not None:
            commands["spHeat"] = target_temp_celsius
            # Maintain cool setpoint
            sp_cool = device_data.get("spCool", adapter.get("spCool"))
            if sp_cool is not None:
                commands["spCool"] = sp_cool
        elif hvac_mode == HVACMode.HEAT_COOL:
            # For auto mode, use target_temp_low and target_temp_high if provided
            if target_temp_low_celsius is not None:
                commands["spHeat"] = target_temp_low_celsius
            if target_temp_high_celsius is not None:
                commands["spCool"] = target_temp_high_celsius

        if commands:
            await self._send_command_and_refresh(commands)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._send_command_and_refresh({"fanSpeed": fan_mode})

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        await self._send_command_and_refresh({"airDirection": swing_mode})

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        # Turn on with the last used mode, or cool mode if no previous mode
        adapter = self.device.zone_data.get("adapter", {})
        device_data = self.device.device_data

        # Use device data if available, otherwise adapter data
        operation_mode = device_data.get(
            "operationMode", adapter.get("operationMode", OPERATION_MODE_COOL)
        )

        # If the operation mode is "off", default to cool
        if operation_mode == OPERATION_MODE_OFF:
            operation_mode = OPERATION_MODE_COOL

        commands = {"operationMode": operation_mode}

        # Include setpoints
        sp_cool = device_data.get("spCool", adapter.get("spCool"))
        sp_heat = device_data.get("spHeat", adapter.get("spHeat"))

        if sp_cool is not None:
            commands["spCool"] = sp_cool
        if sp_heat is not None:
            commands["spHeat"] = sp_heat

        await self._send_command_and_refresh(commands)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self._send_command_and_refresh({"operationMode": OPERATION_MODE_OFF})
