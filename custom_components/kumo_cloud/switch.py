"""Platform for Kumo Cloud switch integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up Kumo Cloud switch devices."""
    coordinator: KumoCloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for zone in coordinator.zones:
        if "adapter" in zone and zone["adapter"]:
            device_serial = zone["adapter"]["deviceSerial"]
            zone_id = zone["id"]

            device = KumoCloudDevice(coordinator, zone_id, device_serial)

            # Get device model info to check for capabilities
            device_data = coordinator.devices.get(device_serial, {})
            model = device_data.get("model", {})

            # Add swing switch if supported
            if model.get("isSwing") is not None:
                entities.append(KumoCloudSwingSwitch(device))

            # Add powerful mode switch if supported
            if model.get("isPowerfulMode") is not None:
                entities.append(KumoCloudPowerfulModeSwitch(device))

    async_add_entities(entities)


class KumoCloudSwingSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Kumo Cloud swing mode switch."""

    _attr_has_entity_name = True

    def __init__(self, device: KumoCloudDevice) -> None:
        """Initialize the swing switch."""
        super().__init__(device.coordinator)
        self.device = device
        self._attr_unique_id = f"{device.unique_id}_swing"
        self._attr_name = "Swing"

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
    def is_on(self) -> bool | None:
        """Return true if swing is enabled."""
        device_data = self.device.device_data
        model = device_data.get("model", {})
        return model.get("isSwing", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on swing mode."""
        # Send command to enable swing (set air direction to swing)
        await self.device.send_command({"airDirection": "swing"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off swing mode."""
        # Send command to disable swing (set air direction to auto or horizontal)
        await self.device.send_command({"airDirection": "auto"})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.available and self.coordinator.last_update_success


class KumoCloudPowerfulModeSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Kumo Cloud powerful mode switch."""

    _attr_has_entity_name = True

    def __init__(self, device: KumoCloudDevice) -> None:
        """Initialize the powerful mode switch."""
        super().__init__(device.coordinator)
        self.device = device
        self._attr_unique_id = f"{device.unique_id}_powerful"
        self._attr_name = "Powerful Mode"

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
    def is_on(self) -> bool | None:
        """Return true if powerful mode is enabled."""
        device_data = self.device.device_data
        model = device_data.get("model", {})
        return model.get("isPowerfulMode", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on powerful mode."""
        # Send command to enable powerful mode (set fan speed to superHigh)
        await self.device.send_command({"fanSpeed": "superHigh"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off powerful mode."""
        # Send command to disable powerful mode (set fan speed to auto or high)
        await self.device.send_command({"fanSpeed": "auto"})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.available and self.coordinator.last_update_success