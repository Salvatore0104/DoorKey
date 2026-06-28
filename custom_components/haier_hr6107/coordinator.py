from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HR6107Api
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN


class HR6107Coordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, api: HR6107Api) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api

    async def _async_update_data(self) -> dict:
        try:
            return await self.api.state()
        except Exception as exc:
            raise UpdateFailed(f"HR-6107 服务不可用: {exc}") from exc

