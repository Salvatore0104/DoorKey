from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .entity import HR6107Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HR6107RingingSensor(entry.runtime_data)])


class HR6107RingingSensor(HR6107Entity, BinarySensorEntity):
    _attr_name = "来电"
    _attr_unique_id = "hr6107_501_ringing"
    _attr_device_class = BinarySensorDeviceClass.SOUND

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("call_state") == "RINGING"
