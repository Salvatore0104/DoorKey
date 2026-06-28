from __future__ import annotations

from homeassistant.components.sensor import SensorEntity

from .entity import HR6107Entity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        [
            HR6107ValueSensor(coordinator, "通话状态", "call_state", "hr6107_501_call_state"),
            HR6107ValueSensor(coordinator, "终端服务", "listener", "hr6107_501_listener"),
        ]
    )


class HR6107ValueSensor(HR6107Entity, SensorEntity):
    def __init__(self, coordinator, name: str, key: str, unique_id: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._key = key

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)

    @property
    def extra_state_attributes(self):
        if self._key != "call_state":
            return None
        data = self.coordinator.data
        return {
            "door_ip": data.get("door_ip"),
            "device_ip": data.get("device_ip"),
            "video_packets": data.get("video_packets", 0),
            "audio_packets": data.get("audio_packets", 0),
            "protocol_verified": data.get("protocol", {}).get("verified", False),
        }

