"""Platform for Kumo Cloud sensor integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KumoCloudDataUpdateCoordinator, KumoCloudDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kumo Cloud sensor devices."""
    coordinator: KumoCloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for zone in coordinator.zones:
        if "adapter" in zone and zone["adapter"]:
            device_serial = zone["adapter"]["deviceSerial"]
            zone_id = zone["id"]

            device = KumoCloudDevice(coordinator, zone_id, device_serial)

            # Add humidity sensor if device reports humidity
            adapter = zone.get("adapter", {})
            if adapter.get("humidity") is not None:
                entities.append(KumoCloudHumiditySensor(device))

            # Add temperature setpoint range sensors
            profile = coordinator.device_profiles.get(device_serial, [])
            if profile:
                profile_data = profile[0] if isinstance(profile, list) else profile
                if profile_data.get("minimumSetPoints"):
                    entities.append(KumoCloudMinSetpointSensor(device, "cool"))
                    entities.append(KumoCloudMinSetpointSensor(device, "heat"))
                    entities.append(KumoCloudMaxSetpointSensor(device, "cool"))
                    entities.append(KumoCloudMaxSetpointSensor(device, "heat"))

    async_add_entities(entities)


class KumoCloudHumiditySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Kumo Cloud humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_has_entity_name = True

    def __init__(self, device: KumoCloudDevice) -> None:
        """Initialize the humidity sensor."""
        super().__init__(device.coordinator)
        self.device = device
        self._attr_unique_id = f"{device.unique_id}_humidity"
        self._attr_name = "Humidity"

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
    def native_value(self) -> int | None:
        """Return the humidity value."""
        adapter = self.device.zone_data.get("adapter", {})
        device_data = self.device.device_data
        return device_data.get("humidity", adapter.get("humidity"))

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.available and self.coordinator.last_update_success


class KumoCloudMinSetpointSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Kumo Cloud minimum setpoint sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: KumoCloudDevice, mode: str) -> None:
        """Initialize the minimum setpoint sensor."""
        super().__init__(device.coordinator)
        self.device = device
        self.mode = mode
        self._attr_unique_id = f"{device.unique_id}_min_setpoint_{mode}"
        self._attr_name = f"Minimum {mode.capitalize()} Setpoint"

        # Cache the value on init since it won't change
        self._cached_value = self._get_setpoint_value()

    def _get_setpoint_value(self) -> float | None:
        """Get the setpoint value from profile."""
        profile = self.device.profile_data
        if profile:
            profile_data = profile[0] if isinstance(profile, list) else profile
            min_setpoints = profile_data.get("minimumSetPoints", {})
            return min_setpoints.get(self.mode)
        return None

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
    def native_value(self) -> float | None:
        """Return the cached minimum setpoint value."""
        return self._cached_value

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.available and self.coordinator.last_update_success


class KumoCloudMaxSetpointSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Kumo Cloud maximum setpoint sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: KumoCloudDevice, mode: str) -> None:
        """Initialize the maximum setpoint sensor."""
        super().__init__(device.coordinator)
        self.device = device
        self.mode = mode
        self._attr_unique_id = f"{device.unique_id}_max_setpoint_{mode}"
        self._attr_name = f"Maximum {mode.capitalize()} Setpoint"

        # Cache the value on init since it won't change
        self._cached_value = self._get_setpoint_value()

    def _get_setpoint_value(self) -> float | None:
        """Get the setpoint value from profile."""
        profile = self.device.profile_data
        if profile:
            profile_data = profile[0] if isinstance(profile, list) else profile
            max_setpoints = profile_data.get("maximumSetPoints", {})
            return max_setpoints.get(self.mode)
        return None

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
    def native_value(self) -> float | None:
        """Return the cached maximum setpoint value."""
        return self._cached_value

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.available and self.coordinator.last_update_success