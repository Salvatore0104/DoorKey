from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError

from .entity import HR6107Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HR6107UnlockButton(entry.runtime_data)])


class HR6107UnlockButton(HR6107Entity, ButtonEntity):
    _attr_name = "开门"
    _attr_unique_id = "hr6107_501_unlock"
    _attr_icon = "mdi:door-open"

    @property
    def available(self) -> bool:
        actions = self.coordinator.data.get("actions", {})
        return super().available and bool(actions.get("unlock"))

    async def async_press(self) -> None:
        try:
            await self.coordinator.api.unlock()
        except Exception as exc:
            raise HomeAssistantError(f"HR-6107 开门失败: {exc}") from exc
        await self.coordinator.async_request_refresh()

