from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HR6107Api
from .const import CONF_BASE_URL, CONF_TOKEN, DOMAIN, PLATFORMS
from .coordinator import HR6107Coordinator
from .views import register_views


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = HR6107Api(
        async_get_clientsession(hass),
        entry.data[CONF_BASE_URL],
        entry.data.get(CONF_TOKEN, ""),
    )
    coordinator = HR6107Coordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {}).setdefault("coordinators", {})[entry.entry_id] = coordinator
    entry.runtime_data = coordinator

    register_views(hass)
    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = entry.runtime_data
    await coordinator.async_stop()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.get(DOMAIN, {}).get("coordinators", {}).pop(entry.entry_id, None)
    return unloaded
