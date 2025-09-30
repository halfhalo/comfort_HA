"""Platform for Kumo Cloud binary sensor integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
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
    """Set up Kumo Cloud binary sensor devices."""
    coordinator: KumoCloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for zone in coordinator.zones:
        if "adapter" in zone and zone["adapter"]:
            device_serial = zone["adapter"]["deviceSerial"]
            zone_id = zone["id"]

            device = KumoCloudDevice(coordinator, zone_id, device_serial)

            # Get device details to check display config
            device_data = coordinator.devices.get(device_serial, {})
            display_config = device_data.get("displayConfig", {})

            # Add defrost sensor if supported
            if display_config.get("defrost") is not None:
                entities.append(KumoCloudDefrostSensor(device))

            # Add standby sensor if supported
            if display_config.get("standby") is not None:
                entities.append(KumoCloudStandbySensor(device))

    async_add_entities(entities)


class KumoCloudDefrostSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Kumo Cloud defrost status sensor."""

    _attr_has_entity_name = True

    def __init__(self, device: KumoCloudDevice) -> None:
        """Initialize the defrost sensor."""
        super().__init__(device.coordinator)
        self.device = device
        self._attr_unique_id = f"{device.unique_id}_defrost"
        self._attr_name = "Defrost"

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
        """Return true if defrost is active."""
        device_data = self.device.device_data
        display_config = device_data.get("displayConfig", {})
        return display_config.get("defrost", False)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.available and self.coordinator.last_update_success


class KumoCloudStandbySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Kumo Cloud standby status sensor."""

    _attr_has_entity_name = True

    def __init__(self, device: KumoCloudDevice) -> None:
        """Initialize the standby sensor."""
        super().__init__(device.coordinator)
        self.device = device
        self._attr_unique_id = f"{device.unique_id}_standby"
        self._attr_name = "Standby"

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
        """Return true if standby is active."""
        device_data = self.device.device_data
        display_config = device_data.get("displayConfig", {})
        return display_config.get("standby", False)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.available and self.coordinator.last_update_success